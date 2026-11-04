"""`GET/POST /system/update*` — m11-update-contract.md bo'lim 1/4. Hostdagi
`innova-update --agent` yozadigan `status`/`changelog.md`/`update.log`/
`request` fayllarini o'qish/yozish — BARCHA tahlil/validatsiya mantig'i
sof funksiyalarda (router faqat chaqiradi, fayl tizimiga tegadi)."""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

from app.schemas_update import ChangelogEntryOut, SystemUpdateOut

REQUEST_FILENAME = "request"
STATUS_FILENAME = "status"
CHANGELOG_FILENAME = "changelog.md"
LOG_FILENAME = "update.log"
MAX_LOG_CHUNK = 64 * 1024

_STATES = {"idle", "checking", "updating", "done", "failed"}
_PHASES = {"backup", "code", "install"}
_PENDING_WORDS = {"check", "update"}
_ERRORS = {
    "no_source", "fetch_failed", "git_dirty", "backup_failed",
    "install_failed", "interrupted", "bad_request",
}

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_HEADING_RE = re.compile(r"^##\s+(\d[\w.]*)(?:\s*[—-]\s*(\S.*))?\s*$")


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def agent_available(update_dir: Path) -> bool:
    """Shell agentining `upd_usable()` bilan BIR XIL qoida: papka bor va
    yozish mumkin (M0: agentsiz muhitda — dev docker-compose — papka yo'q)."""
    return update_dir.is_dir() and os.access(update_dir, os.W_OK)


def parse_status(text: str) -> dict[str, str]:
    """`key=value` qatorlarni lug'atga o'giradi — noma'lum kalitlar/qatorlar
    e'tiborsiz (shell tomoni ham faqat `STATUS_KEYS`ni yozadi)."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            out[key] = value
    return out


def _parsed_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def pending_word(request_text: str | None) -> str | None:
    """`request` fayli mazmunini `check`/`update`ga tekshiradi — boshqa
    hamma narsa (bo'sh, buzuq) `None` (agent ham xuddi shunday — e'tiborsiz)."""
    word = (request_text or "").strip()
    return word if word in _PENDING_WORDS else None


def build_update_out(
    *, agent: bool, raw_status: dict[str, str], request_text: str | None,
    configured_version: str | None, changelog: list[ChangelogEntryOut],
) -> SystemUpdateOut:
    """Xom status lug'atini javob modeliga o'giradi — noma'lum/buzuq qiymat
    HECH QACHON xato chiqarmaydi (bo'lmasa=null yoki xavfsiz sukut)."""
    state = raw_status.get("state", "")
    phase = raw_status.get("phase", "")
    error = raw_status.get("error", "")
    return SystemUpdateOut(
        agent=agent,
        current=raw_status.get("current") or configured_version or None,
        latest=raw_status.get("latest") or None,
        available=raw_status.get("available") == "1",
        state=state if state in _STATES else "idle",
        phase=phase if phase in _PHASES else None,
        pending=pending_word(request_text),
        checked_at=_parsed_datetime(raw_status.get("checked_at", "")),
        started_at=_parsed_datetime(raw_status.get("started_at", "")),
        finished_at=_parsed_datetime(raw_status.get("finished_at", "")),
        error=error if error in _ERRORS else None,
        backup=raw_status.get("backup") or None,
        changelog=changelog,
    )


def version_tuple(version: str) -> tuple[int, ...]:
    """`"1.0.13"` → `(1, 0, 13)` — taqqoslash uchun; raqam bo'lmagan qism 0
    (buzuq versiya yorlig'i bo'lsa ham qulamasin)."""
    parts = []
    for chunk in version.split("."):
        digits = re.match(r"\d+", chunk)
        parts.append(int(digits.group()) if digits else 0)
    return tuple(parts)


def parse_changelog(markdown: str, current_version: str | None) -> list[ChangelogEntryOut]:
    """`## X.Y.Z — sana` bo'limlarini ajratadi, `current_version`dan KATTA
    bo'lganlarini yangisi birinchi tartibda qaytaradi (m11-update-contract.md
    bo'lim 4). `current_version=None` — baseline noma'lum, HAMMASI yangi
    hisoblanadi."""
    lines = markdown.splitlines()
    sections: list[tuple[str, str | None, list[str]]] = []
    for line in lines:
        match = _HEADING_RE.match(line)
        if match:
            sections.append((match.group(1), match.group(2), []))
        elif sections:
            sections[-1][2].append(line)

    baseline = version_tuple(current_version) if current_version else (0,)
    entries: list[ChangelogEntryOut] = []
    for version, date, body in sections:
        if version_tuple(version) <= baseline:
            continue
        entries.append(ChangelogEntryOut(version=version, date=date, body="\n".join(body).strip()))
    entries.sort(key=lambda e: version_tuple(e.version), reverse=True)
    return entries


def write_request(update_dir: Path, word: str) -> None:
    """`O_CREAT|O_EXCL` — ikki so'rov bir vaqtda yozilmasligi (agent
    o'qib-o'chirgunча bittadan): fayl bor bo'lsa `FileExistsError`."""
    path = update_dir / REQUEST_FILENAME
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(fd, f"{word}\n".encode())
    finally:
        os.close(fd)


def read_log_chunk(path: Path, offset: int, max_bytes: int = MAX_LOG_CHUNK) -> tuple[int, int, str]:
    """Fayl yo'q → `(0, 0, "")`. `offset > size` → log qayta yaratilgan,
    boshidan o'qiladi. Natija ANSI'siz, ≤ `max_bytes`."""
    if not path.is_file():
        return 0, 0, ""
    size = path.stat().st_size
    start = offset if 0 <= offset <= size else 0
    with path.open("rb") as handle:
        handle.seek(start)
        raw = handle.read(max_bytes)
    text = strip_ansi(raw.decode("utf-8", errors="replace"))
    return start + len(raw), size, text
