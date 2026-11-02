"""`GET /live` (S29, m2b-contract.md §2) — admin jonli monitoring.

Manba: AMI `CoreShowChannels` (faol kanallar) + `QueueStatus` (navbatda
kutayotganlar, `QueueEntry` hodisasi) — PARALLEL (`asyncio.gather`, m1b-contract.md
bo'lim 5dagi `_trunk_dashboard_items` BILAN BIR XIL naqsh) + PG (agent holati —
`queue_members`, yagona haqiqat manbai). Asterisk/AMI mavjud bo'lmasa — xato
KO'TARILMAYDI, `asterisk="down"`, kanal-bog'liq ro'yxatlar bo'sh qaytadi
(`live_status.py`dagi "jonli ma'lumot ixtiyoriy" naqshi BILAN BIR XIL).

Sof funksiyalar (DB/AMI'siz sinaladi) — pastda, boshida; orkestratsiya oxirida."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Extension, Queue, QueueMember
from app.services.call_direction import classify_direction
from app.services.dashboard import today_bounds_utc
from app.services.live_status import channel_creation_seq, duration_seconds, endpoint_states
from app.services.numbers import dial_number_for_target
from app.services.queue_agents import queue_asterisk_name, queue_interface
from app.services.sip_identity import extension_from_channel

_DIRECTION_WORDS = {"in": "inbound", "out": "outbound", "internal": "internal"}


# ------------------------------------------------------------- sof: kanallar
def channel_extension_number(channel: str) -> str | None:
    """Trunk kanal (`-trunk-` ichida) — `None`; aks holda ichki raqam. Yangi
    (`PJSIP/103-...`) VA eski (`PJSIP/t1-103-...`) shakllarning ikkisi ham
    tushuniladi (`sip_identity.extension_from_channel`, dryer)."""
    return extension_from_channel(channel)


def group_channels_by_linkedid(channels: list[dict]) -> list[list[dict]]:
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for ch in channels:
        key = ch.get("Linkedid") or ch.get("Uniqueid") or ch.get("Channel", "")
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(ch)
    return [groups[k] for k in order]


def _call_state(app: str, state_desc: str, bridged: bool) -> str:
    if app == "ParkedCall":
        return "parked"
    if app == "Queue" and not bridged:
        return "queued"
    if "ring" in (state_desc or "").lower():
        return "ringing"
    return "up" if bridged else "ringing"


def _first_nonempty(*values: str | None) -> str:
    return next((v for v in values if v), "")


def _call_app_and_data(first: dict, last: dict) -> tuple[str, str]:
    """`last` oyog'i (odatda agent/so'nggi sakrash) ustunlik qiladi — bo'sh
    bo'lsa `first`ga qaytiladi (masalan hali ulanmagan navbat qo'ng'irog'i)."""
    return (_first_nonempty(last.get("Application"), first.get("Application")),
            _first_nonempty(last.get("ApplicationData"), first.get("ApplicationData")))


def _call_queue_id(app: str, app_data: str, queue_ids_by_name: dict[str, str]) -> str | None:
    if app != "Queue" or not app_data:
        return None
    return queue_ids_by_name.get(app_data.split(",", 1)[0])


def _call_extension(first: dict, last: dict) -> str | None:
    return channel_extension_number(last.get("Channel", "")) or channel_extension_number(first.get("Channel", ""))


def _call_timestamps(ordered: list[dict], last: dict, *, state: str, now: datetime) -> tuple[datetime, datetime | None]:
    started_at = now - timedelta(seconds=max((duration_seconds(c.get("Duration", "")) for c in ordered), default=0))
    answered_at = now - timedelta(seconds=duration_seconds(last.get("Duration", ""))) if state == "up" else None
    return started_at, answered_at


def build_call_item(group: list[dict], *, now: datetime, queue_ids_by_name: dict[str, str]) -> dict:
    """Bitta `Linkedid` guruhi -> `LiveCallItem` shakli (sof — AMI/DB'siz)."""
    ordered = sorted(group, key=lambda c: channel_creation_seq(c.get("Channel", "")))
    first, last = ordered[0], ordered[-1]
    bridged = len(ordered) > 1 or bool(first.get("BridgeId"))
    app, app_data = _call_app_and_data(first, last)
    state = _call_state(app, last.get("ChannelStateDesc", ""), bridged)
    started_at, answered_at = _call_timestamps(ordered, last, state=state, now=now)
    return {
        "id": _first_nonempty(first.get("Linkedid"), first.get("Uniqueid")),
        "direction": _DIRECTION_WORDS[classify_direction(first.get("Channel"), last.get("Channel"))],
        "from": first.get("CallerIDNum") or "",
        "to": _first_nonempty(last.get("Exten"), first.get("Exten")),
        "state": state,
        "started_at": started_at,
        "answered_at": answered_at,
        "queue_id": _call_queue_id(app, app_data, queue_ids_by_name),
        "extension": _call_extension(first, last),
        "channels": [c.get("Channel", "") for c in ordered],
    }


# -------------------------------------------------------- sof: navbat kutish
def build_waiting_items(entries: list[dict], queue_name: str, now: datetime) -> list[dict]:
    items = []
    for e in entries:
        if e.get("Event") != "QueueEntry" or e.get("Queue") != queue_name:
            continue
        items.append({
            "from": e.get("CallerIDNum") or "",
            "since": now - timedelta(seconds=int(e.get("Wait") or 0)),
            "position": int(e.get("Position") or 0),
        })
    items.sort(key=lambda w: w["position"])
    return items


# --------------------------------------------------------------- sof: holat
def extension_live_state(*, dnd: bool, online: bool, busy: bool, ringing: bool) -> str:
    if dnd:
        return "dnd"
    if not online:
        return "unavailable"
    if ringing:
        return "ringing"
    if busy:
        return "busy"
    return "idle"


def agent_live_state(*, dynamic: bool, logged_in: bool, paused: bool, online: bool, busy: bool,
                      ringing: bool) -> str:
    if dynamic and not logged_in:
        return "offline"
    if not online:
        return "unavailable"
    if paused:
        return "paused"
    if ringing:
        return "ringing"
    if busy:
        return "busy"
    return "idle"


# ---------------------------------------------------------------- orkestr
async def _safe_action_list(ami, action: str, **fields: object) -> list[dict] | None:
    try:
        await ami.ensure_connected()
        return await ami.action_list(action, **fields)
    except Exception:  # noqa: BLE001 — AMI/Asterisk yo'q -> "down", xato EMAS
        return None


async def active_channels(ami) -> list[dict] | None:
    """`POST /live/spy` ham shu funksiyadan foydalanadi (dryer) — `GET /live`
    bilan BIR XIL `CoreShowChannels` chaqiruvi."""
    return await _safe_action_list(ami, "CoreShowChannels")


def pick_agent_channel(channels: list[dict], *, call_id: str | None, channel: str | None) -> str | None:
    """`POST /live/spy` (m2b-contract.md §2): aniq `channel` berilsa — faqat
    mavjudligi tasdiqlanadi; `call_id` (linkedid) berilsa — shu guruhdagi
    EXT TOMONI (`channel_extension_number` mos keladigan, oxiri yaratilgan —
    odatda agent oyog'i) tanlanadi."""
    if channel:
        return channel if any(c.get("Channel") == channel for c in channels) else None
    group = [c for c in channels if (c.get("Linkedid") or c.get("Uniqueid")) == call_id]
    pool = [c for c in group if channel_extension_number(c.get("Channel", "")) is not None] or group
    if not pool:
        return None
    return sorted(pool, key=lambda c: channel_creation_seq(c.get("Channel", "")))[-1].get("Channel")


async def _answered_today_counts(
    session: AsyncSession, *, tenant_code: str, tz_name: str, now: datetime,
) -> dict[tuple[str, str], int]:
    """`queue_log` CONNECT hodisalari (bugun, tenant TZ) — navbat/agent bo'yicha
    guruhlangan (bitta so'rov, N emas). Best-effort: to'liq analitika §5 (keyingi agent)."""
    start, end = today_bounds_utc(tz_name, now)
    rows = (await session.execute(text(
        "select queuename, agent, count(*) from queue_log "
        "where event = 'CONNECT' and time >= :start and time < :end and queuename like :prefix "
        "group by queuename, agent"
    ), {"start": start, "end": end, "prefix": f"{tenant_code}-q-%"})).all()
    return {(row[0], row[1]): row[2] for row in rows}


@dataclass(frozen=True)
class _LiveCtx:
    """Barcha navbat/ichki-raqam elementlari uchun UMUMIY, oldindan hisoblangan
    holat (`build_live_status`dagi bitta `gather`+guruhlashdan) — har bir
    kichik qurish funksiyasiga uzun parametr ro'yxati o'rniga shu uzatiladi."""
    tenant_code: str
    busy_exts: set[str]
    ringing_exts: set[str]
    online_endpoints: set[str]
    answered_today: dict[tuple[str, str], int]

    def online(self, number: str) -> bool:
        return number in self.online_endpoints


def _agent_item(member: QueueMember, *, ctx: _LiveCtx, queue_name: str) -> dict | None:
    if member.extension is None:
        return None
    number = member.extension.number
    return {
        "extension": number, "name": member.extension.name, "dynamic": member.dynamic,
        "logged_in": member.logged_in, "paused": member.paused, "pause_reason": member.pause_reason,
        "state": agent_live_state(
            dynamic=member.dynamic, logged_in=member.logged_in, paused=member.paused, online=ctx.online(number),
            busy=number in ctx.busy_exts, ringing=number in ctx.ringing_exts,
        ),
        "answered_today": ctx.answered_today.get((queue_name, queue_interface(ctx.tenant_code, number)), 0),
    }


async def _queue_item(
    queue: Queue, *, session: AsyncSession, tenant_id: str, queue_entries: list[dict], now: datetime, ctx: _LiveCtx,
) -> dict:
    queue_name = queue_asterisk_name(ctx.tenant_code, str(queue.id))
    agents = [item for m in queue.members if (item := _agent_item(m, ctx=ctx, queue_name=queue_name)) is not None]
    return {
        "id": str(queue.id), "name": queue.name,
        "number": await dial_number_for_target(session, tenant_id, str(queue.target_id)),
        "waiting": build_waiting_items(queue_entries, queue_name, now), "agents": agents,
    }


def _extension_item(extension: Extension, *, ctx: _LiveCtx) -> dict:
    return {
        "number": extension.number, "name": extension.name, "dnd": extension.dnd,
        "state": extension_live_state(
            dnd=extension.dnd, online=ctx.online(extension.number),
            busy=extension.number in ctx.busy_exts, ringing=extension.number in ctx.ringing_exts,
        ),
    }


def _online_endpoint_set(endpoint_state_map: dict[str, dict]) -> set[str]:
    return {ep for ep, st in endpoint_state_map.items() if st.get("status") == "online"}


async def build_live_status(session: AsyncSession, ami, *, tenant_id: str, tenant_code: str,
                             tenant_tz: str) -> dict:
    now = datetime.now(timezone.utc)
    queues = (await session.execute(
        select(Queue).where(Queue.tenant_id == tenant_id).order_by(Queue.name)
        .options(selectinload(Queue.members).selectinload(QueueMember.extension))
    )).scalars().all()
    extensions = (await session.execute(
        select(Extension).where(Extension.tenant_id == tenant_id).order_by(Extension.number)
    )).scalars().all()

    channels, queue_entries, endpoint_state_map = await asyncio.gather(
        active_channels(ami),
        _safe_action_list(ami, "QueueStatus"),
        endpoint_states(ami, [e.number for e in extensions]),
    )
    asterisk_up = channels is not None
    channels = channels or []
    queue_entries = queue_entries or []

    queue_names = {queue_asterisk_name(tenant_code, str(q.id)): str(q.id) for q in queues}
    call_items = [
        build_call_item(g, now=now, queue_ids_by_name=queue_names)
        for g in group_channels_by_linkedid(channels)
    ]
    ctx = _LiveCtx(
        tenant_code=tenant_code,
        ringing_exts={c["extension"] for c in call_items if c["state"] == "ringing" and c["extension"]},
        busy_exts={c["extension"] for c in call_items if c["state"] == "up" and c["extension"]},
        online_endpoints=_online_endpoint_set(endpoint_state_map),
        answered_today=await _answered_today_counts(session, tenant_code=tenant_code, tz_name=tenant_tz, now=now),
    )

    queue_items = [
        await _queue_item(q, session=session, tenant_id=tenant_id, queue_entries=queue_entries, now=now, ctx=ctx)
        for q in queues
    ]
    extension_items = [_extension_item(e, ctx=ctx) for e in extensions]

    return {
        "at": now, "calls": call_items, "queues": queue_items, "extensions": extension_items,
        "asterisk": "up" if asterisk_up else "down",
    }
