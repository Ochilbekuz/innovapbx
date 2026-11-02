"""M6 kampaniyalar — sof qoidalar (bazasiz): CSV tahlili, ish oynasi, terish natijasi, AMI maydonlari.
m6-contract.md §2–§3. Bazaga tegadigan qism — `campaigns.py`, fon dialer — `campaign_dialer.py`."""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from app.services.number_normalize import normalize_number

MAX_CSV_BYTES = 1_000_000
MAX_CONTACTS = 50_000
MAX_INVALID_REPORTED = 50
LOST_AFTER = timedelta(hours=3)

_NUMBER_RE = re.compile(r"[0-9]{3,15}")
_NUMBER_CHARS = re.compile(r"[+0-9 ()\-.]+")
# AMI `Variable:` qiymatlari — faqat shu belgilar (CR/LF, `,`, `;`, `@` — in'ektsiya; originate.py saboqi).
_AMI_SAFE = re.compile(r"[A-Za-z0-9/_.\-]*")

FINAL_STATUSES = ("done", "failed", "skipped")
OPEN_STATUSES = ("pending", "retry", "dialing")
STOPPED_RESULT = "STOPPED"  # to'xtatish paytida terilmay qolgan kontakt
_DIAL_RESULTS = {"ANSWER", "BUSY", "NOANSWER", "CHANUNAVAIL", "CONGESTION"}


@dataclass
class ParsedCsv:
    rows: list[tuple[str, str | None]] = field(default_factory=list)
    invalid: list[dict] = field(default_factory=list)
    invalid_count: int = 0
    duplicates: int = 0


def _split_row(line: str) -> list[str]:
    delimiter = ";" if line.count(";") > line.count(",") else ","
    return next(csv.reader([line], delimiter=delimiter), [])


def _is_header(cells: list[str]) -> bool:
    first = cells[0].strip() if cells else ""
    return bool(first) and not _NUMBER_CHARS.fullmatch(first)


def parse_number(raw: str) -> str | None:
    """`+998 (90) 111-22-33` → `998901112233`; raqam bo'lmagan matn yoki 3..15 dan tashqari → None."""
    value = raw.strip()
    if not _NUMBER_CHARS.fullmatch(value):
        return None
    digits = normalize_number(value)
    return digits if _NUMBER_RE.fullmatch(digits) else None


def _clean_name(raw: str | None) -> str | None:
    name = (raw or "").strip()[:80]
    return name or None


def parse_contacts_csv(text: str, existing: set[str] | None = None) -> ParsedCsv:
    """1-ustun raqam, 2-ustun ism. Birinchi qator raqam bo'lmasa — sarlavha (tashlanadi).
    `existing` — kampaniyada allaqachon bor raqamlar (takror hisoblanadi)."""
    seen = set(existing or ())
    out = ParsedCsv()
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        cells = _split_row(line) or [line]
        if line_no == 1 and _is_header(cells):
            continue
        _take_row(out, seen, line_no, cells)
    return out


def _take_row(out: ParsedCsv, seen: set[str], line_no: int, cells: list[str]) -> None:
    number = parse_number(cells[0])
    if number is None:
        _add_invalid(out, line_no, cells[0])
    elif number in seen:
        out.duplicates += 1
    else:
        seen.add(number)
        out.rows.append((number, _clean_name(cells[1] if len(cells) > 1 else None)))


def _add_invalid(out: ParsedCsv, line_no: int, value: str) -> None:
    out.invalid_count += 1
    if len(out.invalid) < MAX_INVALID_REPORTED:
        out.invalid.append({"line": line_no, "value": value.strip()[:40]})


def in_window(local_now: datetime, start: time, end: time, days: list[int]) -> bool:
    """Tenant mahalliy vaqtida. `start > end` — tun oshib o'tadigan oyna (22:00–02:00);
    kun — oyna BOSHLANGAN kun (02:00 dagi qo'ng'iroq kechagi kunniki)."""
    now_t = local_now.time()
    if start < end:
        return local_now.isoweekday() in days and start <= now_t < end
    if now_t >= start:
        return local_now.isoweekday() in days
    return now_t < end and (local_now - timedelta(days=1)).isoweekday() in days


def classify_dial_status(raw: str) -> str:
    """Dialplan `DIALSTATUS` → saqlanadigan natija. CANCEL — Originate Timeout (ring_seconds) tugadi;
    bo'sh — Dial bo'lmagan (marshrut yo'q / toll-limit)."""
    status = raw.strip().upper()
    if status in _DIAL_RESULTS:
        return status
    if status == "CANCEL":
        return "NOANSWER"
    return "NOROUTE" if status == "" else "CONGESTION"


def parse_billsec(raw: str) -> int:
    try:
        return max(0, int(float(raw)))
    except ValueError:
        return 0


def contact_outcome(result: str, attempts: int, max_attempts: int, now: datetime,
                    retry_delay_s: int, *, stopped: bool = False) -> tuple[str, datetime | None]:
    """Urinishdan keyingi kontakt holati: (status, next_attempt_at). To'xtatilgan kampaniyada qayta urinish yo'q."""
    if result == "ANSWER":
        return "done", None
    if attempts >= max_attempts:
        return "failed", None
    if stopped:
        return "skipped", None
    return "retry", now + timedelta(seconds=retry_delay_s)


def key_action(key: str, *, mode: str, dtmf_connect: bool, dtmf_optout: bool, target_number: str | None) -> str:
    """Mijoz bosgan tugma → dialplan harakati: `connect` | `optout` | `none`."""
    if mode != "message":
        return "none"
    if key == "1" and dtmf_connect and target_number:
        return "connect"
    if key == "9" and dtmf_optout:
        return "optout"
    return "none"


def audio_playback_path(storage_path: str) -> str:
    """`snapshot.py` IVR audio yo'li bilan BIR XIL (`/var/lib/innova/<storage_path>`)."""
    return f"/var/lib/innova/{storage_path}"


@dataclass(frozen=True)
class DialRequest:
    code: str
    number: str
    attempt_id: int
    campaign_id: str
    mode: str
    ring_seconds: int
    callerid: str | None = None
    audio_path: str = ""
    dtmf: bool = False
    target_number: str | None = None


def _safe(value: str) -> str:
    if not _AMI_SAFE.fullmatch(value):
        raise ValueError(f"AMI uchun xavfli qiymat: {value!r}")
    return value


def originate_fields(req: DialRequest) -> dict[str, str]:
    """Local kanal `<code>-campaign-dial` (chiquvchi marshrut + hangup handler natija) — javob bersa
    `<code>-campaign-answer` (audio / DTMF / ulash). Har qiymat oq ro'yxatdan o'tadi."""
    variables = {
        "INNOVA_CAMP_ATTEMPT": str(req.attempt_id),
        "INNOVA_CAMP_ID": req.campaign_id,
        "INNOVA_CAMP_NUM": req.number,
        "INNOVA_CAMP_MODE": req.mode,
        "INNOVA_CAMP_AUDIO": req.audio_path,
        "INNOVA_CAMP_DTMF": "1" if req.dtmf else "0",
        "INNOVA_CAMP_TO": req.target_number or "",
        "INNOVA_CAMP_CID": req.callerid or "",
    }
    fields = {
        "Channel": f"Local/{_safe(req.number)}@{_safe(req.code)}-campaign-dial/n",
        "Context": f"{req.code}-campaign-answer",
        "Exten": "s",
        "Priority": "1",
        "Timeout": str(req.ring_seconds * 1000),
        "Async": "true",
        "Variable": ",".join(f"{k}={_safe(v)}" for k, v in variables.items()),
    }
    if req.callerid:
        fields["CallerID"] = f"<{_safe(req.callerid)}>"
    return fields
