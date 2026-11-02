"""Hodisa payload'i (m3b-contract.md §2) — SOF funksiyalar: AMI `DialBegin`/`DialEnd` dan
`call.ringing`/`call.answered`, `cdr` qatorlaridan `call.ended`.

Kanal nomlari: ichki raqam `PJSIP/<code>-<raqam>-<hex>`, trunk `PJSIP/<code>-trunk-<uuid>-<hex>`.
Yo'nalish qoidasi `call_direction.classify_direction` bilan BIR XIL (tarix va jonli panel kabi).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections.abc import Mapping
from typing import Any

from app.services.call_direction import classify_direction
from app.services.integrations.outbox import iso_z
from app.services.number_normalize import normalize_number

DIRECTION = {"in": "inbound", "out": "outbound", "internal": "internal"}
_EXT_CHANNEL = re.compile(r"^PJSIP/([a-z][a-z0-9]{1,15})-([0-9*#]{2,10})-[0-9a-f]+$")
_PJSIP_CODE = re.compile(r"^PJSIP/([a-z][a-z0-9]{1,15})-")
_QUEUE_ID = re.compile(r"-q-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})")


# ------------------------------------------------------------ kanal nomlari
def channel_extension(channel: str | None) -> str | None:
    match = _EXT_CHANNEL.match(channel or "")
    return match.group(2) if match else None


def channel_code(channel: str | None) -> str | None:
    match = _PJSIP_CODE.match(channel or "")
    return match.group(1) if match else None


def is_trunk(channel: str | None) -> bool:
    return bool(channel) and "-trunk-" in channel


def queue_id_of(lastdata: str | None) -> str | None:
    match = _QUEUE_ID.search(lastdata or "")
    return match.group(1) if match else None


# `manager.conf channelvars` ISHLATILMAYDI: u yoqilsa Asterisk har `Set()` da kanal snapshot'ini e'lon qiladi va CDR
# `dst`/`dcontext` Gosub ichidagi `s` ga o'zgaradi (m2a qora ro'yxat CDR'i buzilgan edi). O'rniga AMI `VarSet`.
TRACKED_VARS = frozenset({"INNOVA_DID", "INNOVA_QUEUE"})


def var_update(evt: dict[str, str]) -> tuple[str, str, str] | None:
    """`VarSet` (`Set(__INNOVA_DID=...)`) → (linkedid, nom, qiymat); kuzatilmaydigan o'zgaruvchi → `None`."""
    name = (evt.get("Variable") or "").lstrip("_")
    linkedid = evt.get("Linkedid") or ""
    if evt.get("Event") != "VarSet" or name not in TRACKED_VARS or not linkedid:
        return None
    return linkedid, name, evt.get("Value") or ""


def _digits(raw: str | None) -> str | None:
    value = normalize_number(raw or "")
    return value or None


# ------------------------------------------------------------ jonli hodisalar (AMI)
@dataclass(frozen=True)
class LiveEvent:
    type: str
    code: str
    linkedid: str
    dedupe_key: str
    direction: str
    from_: str | None
    to: str | None
    extension: str | None
    did: str | None = None
    queue_id: str | None = None

    @property
    def internal(self) -> bool:
        return self.direction == "internal"


def _dial_party(evt: dict[str, str]) -> tuple[str, str, str | None, str | None] | None:
    """(code, direction, ichki raqam, tashqi raqam) — ichki raqam ishtirok etmasa `None`."""
    src, dst = evt.get("Channel", ""), evt.get("DestChannel", "")
    src_ext, dst_ext = channel_extension(src), channel_extension(dst)
    code = channel_code(dst) or channel_code(src)
    if code is None:
        return None
    if dst_ext and is_trunk(src):
        return code, "inbound", dst_ext, _digits(evt.get("CallerIDNum"))
    if dst_ext and src_ext:
        return code, "internal", dst_ext, src_ext
    if src_ext and is_trunk(dst):
        return code, "outbound", src_ext, _digits(evt.get("DialString", "").split("@", 1)[0])
    return None


def _var_fields(direction: str, variables: Mapping[str, str] | None) -> tuple[str | None, str | None]:
    """(did — faqat kiruvchida, queue_id) `VarSet` qiymatlaridan."""
    variables = variables or {}
    did = _digits(variables.get("INNOVA_DID")) if direction == "inbound" else None
    return did, variables.get("INNOVA_QUEUE") or None


_LIVE_TYPES = {"DialBegin": "call.ringing", "DialEnd": "call.answered"}


def _live_type(evt: dict[str, str]) -> str | None:
    name = evt.get("Event") or ""
    if name == "DialEnd" and evt.get("DialStatus") != "ANSWER":
        return None
    return _LIVE_TYPES.get(name)


def live_event(evt: dict[str, str], variables: Mapping[str, str] | None = None) -> LiveEvent | None:
    """`DialBegin` → `call.ringing` (har jiringlagan raqam uchun), `DialEnd ANSWER` → `call.answered`.
    `variables` — shu qo'ng'iroqning `VarSet` orqali yig'ilgan `INNOVA_DID`/`INNOVA_QUEUE` qiymatlari."""
    event_type = _live_type(evt)
    party = _dial_party(evt) if event_type else None
    linkedid = evt.get("Linkedid") or evt.get("DestLinkedid")
    if party is None or not linkedid:
        return None
    code, direction, ext, other = party
    did, queue_id = _var_fields(direction, variables)
    from_, to = (other, ext) if direction != "outbound" else (ext, other)
    suffix = f":{ext}" if event_type == "call.ringing" else ""
    kind = event_type.split(".", 1)[1]
    return LiveEvent(type=event_type, code=code, linkedid=linkedid, dedupe_key=f"{kind}:{linkedid}{suffix}",
                     direction=direction, from_=from_, to=to, extension=ext, did=did,
                     queue_id=queue_id)


# ------------------------------------------------------------ call.ended (CDR)
@dataclass(frozen=True)
class EndedFacts:
    direction: str
    status: str
    from_: str | None
    to: str | None
    did: str | None
    extension: str | None
    answered_by: str | None
    queue_id: str | None
    started_at: datetime
    answered_at: datetime | None
    ended_at: datetime
    duration_s: int
    billsec: int
    extras: dict[str, Any] = field(default_factory=dict)


def _seq(row: Any) -> int:
    return row.sequence if row.sequence is not None else 0


def _winner(rows: list[Any]) -> Any | None:
    """Haqiqiy suhbat: `ANSWERED` VA manzil kanali bor (IVR/ovozli pochta `Answer()`i emas)."""
    return next((r for r in rows if (r.disposition or "").upper() == "ANSWERED" and r.dstchannel), None)


def _status(rows: list[Any], winner: Any | None) -> str:
    if winner is not None:
        return "answered"
    dispositions = {(r.disposition or "").upper() for r in rows}
    if "BUSY" in dispositions:
        return "busy"
    if dispositions & {"NO ANSWER", "ANSWERED"}:
        return "missed"
    return "failed"


def _last_rung_ext(rows: list[Any]) -> str | None:
    exts = [e for e in (channel_extension(r.dstchannel) for r in rows) if e]
    return exts[-1] if exts else None


def _end_time(row: Any) -> datetime:
    return row.calldate + timedelta(seconds=row.duration or 0)


def _outbound_parties(primary: Any, rows: list[Any], winner: Any | None) -> tuple:
    ext = channel_extension(primary.channel) or _digits(primary.src)
    dialed = winner if winner is not None else next((r for r in rows if is_trunk(r.dstchannel)), primary)
    return ext, _digits(dialed.dst), ext, ext if winner is not None else None


def _parties(direction: str, primary: Any, rows: list[Any], winner: Any | None) -> tuple:
    """(from, to, extension, answered_by)."""
    if direction == "outbound":
        return _outbound_parties(primary, rows, winner)
    callee = channel_extension(winner.dstchannel) if winner is not None else None
    target = callee or _last_rung_ext(rows)
    if direction == "inbound":
        return _digits(primary.src), target or _digits(primary.userfield), target, callee
    caller = channel_extension(primary.channel) or _digits(primary.src)
    return caller, target or _digits(primary.dst), target, callee


def ended_facts(rows: list[Any]) -> EndedFacts:
    ordered = sorted(rows, key=_seq)
    primary = ordered[0]
    winner = _winner(ordered)
    trunk_dst = next((r.dstchannel for r in ordered if is_trunk(r.dstchannel)), None)
    direction = DIRECTION[classify_direction(primary.channel, (winner.dstchannel if winner else None) or trunk_dst)]
    from_, to, extension, answered_by = _parties(direction, primary, ordered, winner)
    started_at = primary.calldate
    ended_at = max(_end_time(r) for r in ordered)
    answered_at = (winner.calldate + timedelta(seconds=winner.duration - winner.billsec)) if winner else None
    return EndedFacts(
        direction=direction, status=_status(ordered, winner), from_=from_, to=to,
        did=_digits(primary.userfield) if direction == "inbound" else None,
        extension=extension, answered_by=answered_by,
        queue_id=next((q for q in (queue_id_of(r.lastdata) for r in ordered if r.lastapp == "Queue") if q), None),
        started_at=started_at, answered_at=answered_at, ended_at=ended_at,
        duration_s=max(0, int((ended_at - started_at).total_seconds())), billsec=winner.billsec if winner else 0,
    )


# ------------------------------------------------------------ payload
def _iso(value: datetime | None) -> str | None:
    return iso_z(value) if value is not None else None


def base_call(*, linkedid: str, direction: str, from_: str | None, to: str | None, did: str | None,
              extension: str | None, queue: dict | None, origin: dict | None) -> dict[str, Any]:
    call: dict[str, Any] = {"id": linkedid, "direction": direction, "from": from_, "to": to, "did": did,
                            "extension": extension, "queue": queue}
    if origin is not None:
        call["origin"] = origin
    return call


def ended_call(linkedid: str, facts: EndedFacts, *, queue: dict | None, origin: dict | None,
               recordings: list[dict], did_hint: str | None = None) -> dict[str, Any]:
    call = base_call(linkedid=linkedid, direction=facts.direction, from_=facts.from_, to=facts.to,
                     did=facts.did or (did_hint if facts.direction == "inbound" else None),
                     extension=facts.extension, queue=queue, origin=origin)
    call.update({
        "status": facts.status, "started_at": _iso(facts.started_at), "answered_at": _iso(facts.answered_at),
        "ended_at": _iso(facts.ended_at), "duration_s": facts.duration_s, "billsec": facts.billsec,
        "answered_by": facts.answered_by, "recordings": recordings,
    })
    return call
