"""AMI orqali jonli holat — m0-contract.md: `status` — AMI/`ps_contacts`dan jonli.
Asterisk sorcery.conf'da `contact` obyekti realtime EMAS (M0 qarori), shuning
uchun kontakt holatini bazadan emas, `pjsip show endpoints`/`pjsip show aor`
buyruqlaridan (AMI `Command` action, bitta sinxron javob) o'qiymiz. AMI
mavjud bo'lmasa — xato ko'tarilmaydi, hammasi "unknown" bilan qaytadi
(jonli holat ixtiyoriy ma'lumot, ro'yxatni to'xtatmasligi kerak)."""
from __future__ import annotations

import re

from app.services.ami import AmiError
from app.services.call_direction import classify_direction

_CONTACT_RE = re.compile(
    # Asterisk 22: "Contact:  t1-103/sip:x@172.21.0.5:59158;trans 0fb0660acf NonQual  -nan" — URI bilan
    # holat orasida <Hash> ustuni bor (jonli tasdiqlangan 2026-10-29). NonQual = ro'yxatdan o'tgan, hali
    # qualify qilinmagan (yoki qualify o'chiq) — onlayn.
    r"Contact:\s+(?P<endpoint>[\w.-]+)/(?P<uri>\S+)\s+(?:[0-9a-f]{6,}\s+)?(?P<state>Avail|Unavail|NonQual|Unknown)\b",
    re.IGNORECASE,
)
_ONLINE_STATES = {"avail", "nonqual"}
_QUALIFY_RE = re.compile(r"\b(Avail|Unavail)\b.*?(?P<rtt>[\d.]+)\s*m?s?\b", re.IGNORECASE)

UNKNOWN_STATE = {"status": "unknown", "contact": None, "user_agent": None}


async def endpoint_states(ami, endpoint_ids: list[str]) -> dict[str, dict]:
    """endpoint_id -> {"status","contact","user_agent"}."""
    result = {eid: dict(UNKNOWN_STATE) for eid in endpoint_ids}
    if not endpoint_ids:
        return result
    output = await run_command(ami, "pjsip show endpoints")
    if output is None:
        return result
    for match in _CONTACT_RE.finditer(output):
        eid = match.group("endpoint")
        if eid not in result:
            continue
        online = match.group("state").lower() in _ONLINE_STATES
        result[eid] = {
            "status": "online" if online else "offline",
            "contact": match.group("uri"),
            "user_agent": None,
        }
    return result


_URI_HOST_RE = re.compile(r"@(?P<host>\[[0-9a-fA-F:.]+\]|[^:;>@\s]+)")


def contact_hosts(output: str, endpoint_ids: set[str]) -> dict[str, set[str]]:
    """`pjsip show endpoints` matnidan endpoint → ONLAYN contact'lar hostlari (M4a: apparat `registered` —
    contact shu apparat IP'sidan; `rewrite_contact=yes` tufayli URI hosti = paket manbasi)."""
    hosts: dict[str, set[str]] = {eid: set() for eid in endpoint_ids}
    for match in _CONTACT_RE.finditer(output):
        eid = match.group("endpoint")
        host = _URI_HOST_RE.search(match.group("uri"))
        if eid in hosts and host and match.group("state").lower() in _ONLINE_STATES:
            hosts[eid].add(host.group("host").strip("[]"))
    return hosts


async def endpoint_contact_hosts(ami, endpoint_ids: list[str]) -> dict[str, set[str]] | None:
    """AMI ishlamasa `None` (chaqiruvchi «noma'lum» deb ko'rsatadi, xato ko'tarmaydi)."""
    if not endpoint_ids:
        return {}
    output = await run_command(ami, "pjsip show endpoints")
    return None if output is None else contact_hosts(output, set(endpoint_ids))


async def run_command(ami, command: str) -> str | None:
    try:
        await ami.ensure_connected()
        resp = await ami.action("Command", Command=command)
    except (AmiError, OSError, ConnectionError):
        return None
    return resp.get("Output", "") or ""


_QUEUE_HEADER_RE = re.compile(r"has\s+(\d+)\s+calls?", re.IGNORECASE)
# `queue show` "Callers:" qatori — jonli tasdiqlangan (`innova-m0-asterisk-1`,
# 2026-10-28): "      1. Local/700@parkedcalls-00000004;1 (wait: 0:11, prio: 0)".
_QUEUE_WAIT_RE = re.compile(r"\(wait:\s*(\d+):(\d+)", re.IGNORECASE)


def _longest_wait_s(output: str) -> int:
    waits = [int(m.group(1)) * 60 + int(m.group(2)) for m in _QUEUE_WAIT_RE.finditer(output)]
    return max(waits, default=0)


def _member_lines(output: str) -> list[str]:
    """`Members:` sarlavhasi bilan `Callers:`/`No Callers` orasidagi, bo'sh
    bo'lmagan, chekinilgan qatorlar — har biri BITTA a'zo (jonli chiqishda
    a'zo nomi `PJSIP/...` oldidan ism bilan ham kelishi mumkin — "Agent101
    (PJSIP/t1-101) ... (Unavailable) ..." — shu sabab oddiy regex emas,
    bo'lim chegarasiga qarab ajratamiz)."""
    lines = output.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip().startswith("Members"))
    except StopIteration:
        return []
    members: list[str] = []
    for line in lines[start + 1:]:
        stripped = line.strip()
        if not line.startswith(" ") or not stripped:
            break
        if stripped.startswith("Callers") or stripped.startswith("No Callers"):
            break
        members.append(line)
    return members


async def queue_live_status(ami, queue_name: str) -> dict | None:
    """`queue show <name>` — m1a-contract.md: `live: {"waiting","members_online"}|null`;
    m1b-contract.md bo'lim 5 (`/dashboard`) — qo'shimcha `longest_wait_s`
    (AMI xatosi/ulanmasa — `None`, ro'yxatni to'xtatmaydi)."""
    output = await run_command(ami, f"queue show {queue_name}")
    if output is None or not output.strip():
        return None
    header_match = _QUEUE_HEADER_RE.search(output)
    waiting = int(header_match.group(1)) if header_match else 0
    members_online = sum(1 for line in _member_lines(output) if "unavailable" not in line.lower())
    return {"waiting": waiting, "members_online": members_online, "longest_wait_s": _longest_wait_s(output)}


# `pjsip show registration <id>` chiqishi (jonli tasdiqlangan,
# `innova-m0-asterisk-1` konteyneridan, 2026-10-27): endpoint/URI, auth,
# so'ngra holat so'zi — `res_pjsip_outbound_registration.so` ichidagi
# aniq literal satrlar (`strings` bilan tasdiqlangan): Registered/Rejected/Unregistered.
def _registration_regex(endpoint_id: str) -> re.Pattern[str]:
    return re.compile(
        rf"{re.escape(endpoint_id)}/\S+\s+\S+\s+(Registered|Unregistered|Rejected)",
        re.IGNORECASE,
    )


async def trunk_registration_state(ami, endpoint_id: str) -> dict:
    """`health.registration`/`reason` — register-rejim trunk uchun JONLI
    (bazadagi eski holat EMAS — `trunk_health` jadvalini hech kim yozmaydi,
    m1b-contract.md bo'lim 1). AMI yo'q/xato — `None` (noma'lum, 404 emas)."""
    output = await run_command(ami, f"pjsip show registration {endpoint_id}")
    if output is None or not output.strip() or "Unable to find object" in output:
        return {"registration": None, "reason": "Registratsiya holati noma'lum"}
    match = _registration_regex(endpoint_id).search(output)
    if match is None:
        return {"registration": None, "reason": "Registratsiya holati o'qilmadi"}
    state = match.group(1).lower()
    reason = None if state == "registered" else f"PJSIP holati: {match.group(1)}"
    return {"registration": state, "reason": reason}


async def reload_pjsip(ami) -> bool:
    """Register-rejim trunk yaratildi/o'zgardi — `ps_registrations`/`ps_auths`
    realtime qatorlari YANGI obyekt sifatida faqat `pjsip reload`dan keyin
    ko'rinadi (sorcery obyekt keshi) — m1b-contract.md bo'lim 1."""
    output = await run_command(ami, "pjsip reload")
    return output is not None


_ACTIVE_CHANNELS_RE = re.compile(r"(\d+)\s+active channels?", re.IGNORECASE)


async def active_channels_count(ami) -> int | None:
    """`core show channels count` — Asterisk'ning O'ZI aytgan "N active
    channels" qatoridan sonni oladi (m1b-contract.md bo'lim 4: `POST
    /settings/sip/restart` 409 `active_calls` + `details.count` uchun).
    AMI mavjud bo'lmasa `None` (chaqiruvchi buni "noma'lum" deb talqin qilishi
    kerak — xavfsiz tomonga: 0 DEB FARZ QILMAYDI, balki restart'ni rad etadi)."""
    output = await run_command(ami, "core show channels count")
    if output is None:
        return None
    match = _ACTIVE_CHANNELS_RE.search(output)
    return int(match.group(1)) if match else None


_CHANNEL_TABLE_COLUMNS = (
    "Channel", "Context", "Extension", "Prio", "State", "Application", "Data",
    "CallerID", "Duration", "Accountcode", "PeerAccount", "BridgeID",
)
_CHANNEL_SEQ_RE = re.compile(r"-(\d+)$")


_CHANNEL_TABLE_TRAILER_RE = re.compile(
    r"^\d+\s+(active channels?|active calls?|calls? processed)$", re.IGNORECASE,
)


def _parse_channel_table(output: str) -> list[dict[str, str]]:
    """`core show channels verbose` — SUTUNLAR BIR XIL JOYDA (fixed-width),
    lekin ba'zi ustunlar orasida FAQAT BITTA probel bo'lishi mumkin (masalan
    bir xonali `Prio`+`State`), shu sabab oddiy `split()` ISHONCHSIZ —
    sarlavha qatoridagi har ustun nomining BOSHLANISH INDEKSIGA qarab
    har qatorni KESAMIZ (jonli `innova-m0-asterisk-1`da tasdiqlangan usul).

    Diqqat (jonli tasdiqlangan, 2026-10-28): quyi qator KO'PLIK ham bo'lishi
    mumkin ("3 calls processed", bitta emas "1 call processed") — oldingi
    variant FAQAT birlik shaklini ("call processed") qidirgani sabab bu
    qatorni soxta kanal qatori deb noto'g'ri qo'shib qo'ygan edi."""
    lines = output.splitlines()
    if not lines:
        return []
    header = lines[0]
    try:
        starts = [(name, header.index(name)) for name in _CHANNEL_TABLE_COLUMNS]
    except ValueError:
        return []
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        if not line.strip() or _CHANNEL_TABLE_TRAILER_RE.match(line.strip()):
            continue
        row = {
            name: line[start:starts[i + 1][1] if i + 1 < len(starts) else len(line)].strip()
            for i, (name, start) in enumerate(starts) if start < len(line)
        }
        if row.get("Channel"):
            rows.append(row)
    return rows


def duration_seconds(hms: str) -> int:
    parts = hms.split(":")
    if len(parts) != 3:
        return 0
    try:
        hours, minutes, seconds = (int(p) for p in parts)
    except ValueError:
        return 0
    return hours * 3600 + minutes * 60 + seconds


def channel_creation_seq(channel: str) -> int:
    """Asterisk kanal nomi `...-NNNNNNNN[;N]` bilan tugaydi — oxirgi raqam
    monoton o'suvchi hisoblagich, shu sabab bitta ko'prikdagi ikki oyoqdan
    QAYSI BIRI OLDIN yaratilganini (ya'ni "manba") shundan bilib olamiz."""
    match = _CHANNEL_SEQ_RE.search(channel.split(";")[0])
    return int(match.group(1)) if match else 0


def _group_rows_by_bridge(rows: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = {}
    order: list[str] = []
    singles: list[list[dict[str, str]]] = []
    for row in rows:
        bridge = row.get("BridgeID") or ""
        if not bridge:
            singles.append([row])
            continue
        if bridge not in groups:
            groups[bridge] = []
            order.append(bridge)
        groups[bridge].append(row)
    return [groups[b] for b in order] + singles


def _live_call_from_bridge_group(group: list[dict[str, str]]) -> dict:
    """Ikki oyoqli ko'prikda ERTA yaratilgan oyoq — manba (`channel`), KEYINGI
    — manzil (`dstchannel`); bitta oyoqli guruhda (hali ko'priklanmagan) ikkisi
    ham o'sha BITTA kanal — `calls.py`dagi CDR direction qoidasi bilan BIR XIL
    (`classify_direction`, m1b-contract.md bo'lim 5: "live.calls")."""
    ordered = sorted(group, key=lambda r: channel_creation_seq(r["Channel"]))
    source, dest = ordered[0], ordered[-1]
    direction = classify_direction(source["Channel"], dest["Channel"])
    return {
        "channel": source["Channel"], "from": source.get("CallerID") or "",
        "to": dest.get("Extension") or source.get("Extension") or "",
        "state": source.get("State") or "", "duration_s": duration_seconds(source.get("Duration", "")),
        "direction": direction,
    }


async def active_calls_live(ami) -> list[dict] | None:
    """`GET /dashboard` `live.calls` — m1b-contract.md bo'lim 5. AMI
    mavjud bo'lmasa `None` (dashboard buni "jonli ma'lumot yo'q" deb
    talqin qiladi — 500 EMAS)."""
    output = await run_command(ami, "core show channels verbose")
    if output is None:
        return None
    rows = _parse_channel_table(output)
    return [_live_call_from_bridge_group(g) for g in _group_rows_by_bridge(rows)]


async def test_trunk_endpoint(ami, endpoint_id: str) -> dict:
    """`POST /trunks/{id}/test` — PJSIP qualify (OPTIONS) natijasi."""
    try:
        await ami.ensure_connected()
        await ami.action("PJSIPQualify", Endpoint=endpoint_id)
    except (AmiError, OSError, ConnectionError) as exc:
        return {"ok": False, "rtt_ms": None, "detail": f"AMI xatosi: {exc}"}

    output = await run_command(ami, f"pjsip show aor {endpoint_id}")
    if output is None:
        return {"ok": False, "rtt_ms": None, "detail": "AMI javob bermadi"}
    match = _QUALIFY_RE.search(output)
    if match and match.group(1).lower() == "avail":
        return {"ok": True, "rtt_ms": round(float(match.group("rtt"))), "detail": "OPTIONS javob berdi"}
    return {"ok": False, "rtt_ms": None, "detail": "Trunk OPTIONS'ga javob bermadi"}
