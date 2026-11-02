"""`call_events` fon vazifasi (m3b-contract.md §0/§2): AMI hodisa ulanishi + CDR supurgichi → outbox.

- Alohida AMI ulanishi (`Events: call`): o'qish halqasi faqat `put_nowait` qiladi (sekin iste'molchi
  AMI'ni bloklamaydi, VoxBridge saboq), iste'molchi navbatdan oladi. Uzilsa — eksponensial kutish bilan
  qayta ulanish; ulangach supurgich darhol ishlaydi (`CoreShowChannels` bilan holat tiklanadi).
- `call.ringing`/`call.answered` — `DialBegin`/`DialEnd ANSWER` (eng yaxshi harakat).
- `call.ended` — `Hangup`dan `settle_s` keyin, linkedid'ning kanali qolmagan bo'lsa, `cdr`dan.
  Supurgich har 30 s oxirgi 6 soat CDR'ini tekshiradi: `ended` hodisasi yo'q va kanal yo'q → yuboradi
  (API o'chiq bo'lganda tugagan qo'ng'iroq ham). Takror — `integration_events (tenant_id, dedupe_key)` UNIQUE.
- `call_event_state` — kech hodisa tugagan qo'ng'iroqni tiriltirmaydi; tugagan holat 10 daqiqa TTL;
  osilib qolgan (CDR'siz, kanalsiz, 30 daqiqadan eski) qo'ng'iroq majburan yopiladi.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import ApiOriginateRequest, CallEventState, Cdr, Queue, Tenant
from app.services import recordings
from app.services.ami import AmiClient
from app.services.integrations import events as ev
from app.services.integrations.outbox import emit_event
from app.services.live import active_channels

log = logging.getLogger(__name__)

SWEEP_WINDOW = timedelta(hours=6)
STATE_TTL = timedelta(minutes=10)
STUCK_AFTER = timedelta(minutes=30)
QUEUE_MAX = 10000
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_INTERESTING = frozenset({"DialBegin", "DialEnd", "Hangup"})
VARS_MAX = 5000  # xotiradagi `linkedid -> {INNOVA_DID, INNOVA_QUEUE}` chegarasi (eng eskisi tashlanadi)
# AMI sessiya filtri (Asterisk tomonda saralanadi): `dialplan` sinfidan faqat kuzatilgan `VarSet`lar o'tadi.
AMI_FILTERS = ("Event: (DialBegin|DialEnd|Hangup)", "Variable: _*INNOVA_(DID|QUEUE)")


def backoff_s(attempt: int) -> float:
    return float(min(30, 2 ** min(attempt, 5)))


# ------------------------------------------------------------ yordamchi so'rovlar
async def _tenant_id(session: AsyncSession, code: str | None) -> str | None:
    if not code:
        return None
    row = (await session.execute(select(Tenant.id).where(Tenant.code == code))).scalar_one_or_none()
    return str(row) if row else None


async def _queue_ref(session: AsyncSession, tenant_id: str, queue_id: str | None) -> dict | None:
    if not queue_id or not _UUID_RE.match(queue_id):
        return None
    q = await session.get(Queue, queue_id)
    return {"id": str(q.id), "name": q.name} if q is not None and str(q.tenant_id) == tenant_id else None


async def _origin(session: AsyncSession, linkedid: str) -> dict | None:
    if not _UUID_RE.match(linkedid):
        return None
    req = await session.get(ApiOriginateRequest, linkedid)
    return {"source": "api", "external_id": req.external_id} if req is not None else None


async def _locked_state(session: AsyncSession, tenant_id: str, linkedid: str) -> CallEventState:
    await session.execute(pg_insert(CallEventState).values(linkedid=linkedid, tenant_id=tenant_id)
                          .on_conflict_do_nothing(index_elements=["linkedid"]))
    return (await session.execute(select(CallEventState).where(CallEventState.linkedid == linkedid)
                                  .with_for_update().execution_options(populate_existing=True))).scalar_one()


def _merge_info(info: dict, live: ev.LiveEvent) -> dict:
    merged = dict(info or {})
    for key, value in (("direction", live.direction), ("did", live.did), ("queue_id", live.queue_id),
                       ("from", live.from_), ("extension", live.extension)):
        if value and not merged.get(key):
            merged[key] = value
    if live.type == "call.ringing":
        merged["last_rung"] = live.extension
    return merged


# ------------------------------------------------------------ jonli hodisa
async def emit_live(session: AsyncSession, live: ev.LiveEvent) -> bool:
    tenant_id = await _tenant_id(session, live.code)
    if tenant_id is None:
        return False
    state = await _locked_state(session, tenant_id, live.linkedid)
    if state.ended_sent:
        return False  # kech hodisa — tugagan qo'ng'iroq tiriltirilmaydi
    state.info = _merge_info(state.info, live)
    state.ringing_sent = state.ringing_sent or live.type == "call.ringing"
    state.answered_sent = state.answered_sent or live.type == "call.answered"
    state.updated_at = datetime.now(timezone.utc)
    info = state.info
    call = ev.base_call(
        linkedid=live.linkedid, direction=info.get("direction", live.direction), from_=live.from_, to=live.to,
        did=info.get("did"), extension=live.extension,
        queue=await _queue_ref(session, tenant_id, info.get("queue_id")), origin=await _origin(session, live.linkedid),
    )
    event = await emit_event(session, tenant_id=tenant_id, event_type=live.type, dedupe_key=live.dedupe_key,
                             call_id=live.linkedid, internal=live.internal, call=call,
                             occurred_at=datetime.now(timezone.utc))
    await session.commit()
    return event is not None


# ------------------------------------------------------------ call.ended
async def _ended_exists(session: AsyncSession, tenant_id: str, linkedid: str) -> bool:
    return (await session.execute(text(
        "select 1 from integration_events where tenant_id = :t and dedupe_key = :k"),
        {"t": tenant_id, "k": f"ended:{linkedid}"})).first() is not None


async def finalize(session: AsyncSession, linkedid: str) -> bool:
    """CDR'dan `call.ended` (bir marta). Chaqiruvchi kanal qolmaganini tekshirgan bo'lishi SHART."""
    rows = list((await session.execute(select(Cdr).where(Cdr.linkedid == linkedid))).scalars().all())
    if not rows:
        return False
    tenant_id = await _tenant_id(session, rows[0].accountcode)
    if tenant_id is None or await _ended_exists(session, tenant_id, linkedid):
        return False
    state = await _locked_state(session, tenant_id, linkedid)
    if state.ended_sent:
        await session.rollback()
        return False
    facts = ev.ended_facts(rows)
    recs = await recordings.ingest_call(session, tenant_id=tenant_id, linkedid=linkedid, started_at=facts.started_at,
                                        ended_at=facts.ended_at + timedelta(minutes=1), extension=facts.extension)
    info = state.info or {}
    call = ev.ended_call(
        linkedid, facts, queue=await _queue_ref(session, tenant_id, facts.queue_id or info.get("queue_id")),
        origin=await _origin(session, linkedid), recordings=await recordings.recording_refs(session, tenant_id, recs),
        did_hint=info.get("did"),
    )
    await emit_event(session, tenant_id=tenant_id, event_type="call.ended", dedupe_key=f"ended:{linkedid}",
                     call_id=linkedid, internal=facts.direction == "internal", call=call, occurred_at=facts.ended_at)
    now = datetime.now(timezone.utc)
    state.ended_sent, state.finished_at, state.updated_at = True, now, now
    await session.commit()
    return True


async def force_close(session: AsyncSession, state: CallEventState) -> None:
    """CDR'siz osilib qolgan qo'ng'iroq — holatdagi ma'lumot bilan `call.ended` (status `failed`/`missed`)."""
    info = state.info or {}
    now = datetime.now(timezone.utc)
    call = ev.base_call(linkedid=state.linkedid, direction=info.get("direction", "inbound"), from_=info.get("from"),
                        to=info.get("last_rung"), did=info.get("did"), extension=info.get("last_rung"),
                        queue=await _queue_ref(session, str(state.tenant_id), info.get("queue_id")),
                        origin=await _origin(session, state.linkedid))
    call.update({"status": "answered" if state.answered_sent else "missed", "started_at": ev.iso_z(state.created_at),
                 "answered_at": None, "ended_at": ev.iso_z(now), "duration_s": 0, "billsec": 0,
                 "answered_by": None, "recordings": [], "forced": True})
    await emit_event(session, tenant_id=str(state.tenant_id), event_type="call.ended",
                     dedupe_key=f"ended:{state.linkedid}", call_id=state.linkedid,
                     internal=info.get("direction") == "internal", call=call, occurred_at=now)
    state.ended_sent, state.finished_at, state.updated_at = True, now, now


_SWEEP_SQL = text("""
select c.linkedid from cdr c join tenants t on t.code = c.accountcode
 where c.calldate > :since and c.linkedid is not null
 group by c.linkedid, t.id
having max(c.calldate + make_interval(secs => c.duration)) < :settled
   and not exists (select 1 from integration_events e where e.tenant_id = t.id and e.dedupe_key = 'ended:' || c.linkedid)
 limit 200
""")


async def sweep_once(session_factory, ami: AmiClient) -> int:
    channels = await active_channels(ami)
    if channels is None:
        return 0  # AMI yo'q — qaysi qo'ng'iroq tirikligini bilmaymiz, kutamiz
    live = {c.get("Linkedid") for c in channels}
    now = datetime.now(timezone.utc)
    done = 0
    async with session_factory() as session:
        pending = (await session.execute(_SWEEP_SQL, {
            "since": now - SWEEP_WINDOW, "settled": now - timedelta(seconds=settings.call_events_settle_s),
        })).scalars().all()
    for linkedid in pending:
        if linkedid in live:
            continue
        async with session_factory() as session:
            done += int(await finalize(session, linkedid))
    async with session_factory() as session:
        stuck = (await session.execute(select(CallEventState).where(
            CallEventState.ended_sent.is_(False), CallEventState.created_at < now - STUCK_AFTER,
        ).limit(100))).scalars().all()
        for state in stuck:
            if state.linkedid not in live and not await _has_cdr(session, state.linkedid):
                await force_close(session, state)
        await session.execute(delete(CallEventState).where(
            CallEventState.ended_sent.is_(True), CallEventState.finished_at < now - STATE_TTL))
        await session.commit()
    return done


async def _has_cdr(session: AsyncSession, linkedid: str) -> bool:
    return (await session.execute(select(Cdr.id).where(Cdr.linkedid == linkedid).limit(1))).first() is not None


# ------------------------------------------------------------ servis
class CallEventService:
    def __init__(self, session_factory, ami: AmiClient) -> None:
        self.session_factory = session_factory
        self.ami = ami
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=QUEUE_MAX)
        self.dropped = 0
        self.resync = asyncio.Event()
        self._timers: dict[str, asyncio.Task] = {}
        self._vars: dict[str, dict[str, str]] = {}
        self.stream = AmiClient(settings.ami_host, settings.ami_port, settings.ami_username, settings.ami_password,
                                events="call,dialplan", on_event=self.on_event, event_filters=AMI_FILTERS)

    def on_event(self, msg: dict[str, Any]) -> None:
        """O'qish halqasidan — bloklamaydi; navbat to'lsa hodisa tashlanadi (supurgich tiklaydi)."""
        if msg.get("Event") not in _INTERESTING and ev.var_update(msg) is None:
            return
        try:
            self.queue.put_nowait(msg)
        except asyncio.QueueFull:
            self.dropped += 1

    async def run_listener(self) -> None:
        attempt = 0
        while True:
            try:
                await self.stream.ensure_connected()
                attempt = 0
                self.resync.set()
                while self.stream.connected:
                    await asyncio.sleep(1.0)
                log.warning("call_events: AMI hodisa ulanishi uzildi, qayta ulanamiz")
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("call_events: AMI ulanmadi: %s", exc)
            await self.stream.close()
            await asyncio.sleep(backoff_s(attempt))
            attempt += 1

    async def run_consumer(self) -> None:
        while True:
            msg = await self.queue.get()
            try:
                await self.handle(msg)
            except Exception:  # noqa: BLE001 — bitta hodisa xatosi oqimni to'xtatmasin
                log.exception("call_events: hodisani qayta ishlashda xato")

    def remember_var(self, linkedid: str, name: str, value: str) -> None:
        if linkedid not in self._vars and len(self._vars) >= VARS_MAX:
            self._vars.pop(next(iter(self._vars)))
        self._vars.setdefault(linkedid, {})[name] = value

    async def handle(self, msg: dict[str, Any]) -> None:
        update = ev.var_update(msg)
        if update is not None:
            self.remember_var(*update)
            return
        if msg.get("Event") == "Hangup":
            self._schedule_finalize(msg.get("Linkedid") or "")
            return
        live = ev.live_event(msg, self._vars.get(msg.get("Linkedid") or msg.get("DestLinkedid") or ""))
        if live is not None:
            async with self.session_factory() as session:
                await emit_live(session, live)

    def _schedule_finalize(self, linkedid: str) -> None:
        if not linkedid:
            return
        previous = self._timers.pop(linkedid, None)
        if previous is not None:
            previous.cancel()
        self._timers[linkedid] = asyncio.create_task(self._finalize_later(linkedid))

    async def _finalize_later(self, linkedid: str) -> None:
        await asyncio.sleep(settings.call_events_settle_s)
        self._timers.pop(linkedid, None)
        channels = await active_channels(self.ami)
        if channels is None or any(c.get("Linkedid") == linkedid for c in channels):
            return  # hali tirik yoki AMI yo'q — supurgich keyin yopadi
        self._vars.pop(linkedid, None)
        try:
            async with self.session_factory() as session:
                await finalize(session, linkedid)
        except Exception:  # noqa: BLE001
            log.exception("call_events: %s yakunlanmadi", linkedid)

    async def run_sweeper(self, interval_s: float) -> None:
        while True:
            try:
                await sweep_once(self.session_factory, self.ami)
            except Exception:  # noqa: BLE001
                log.exception("call_events: supurgich xatosi")
            self.resync.clear()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self.resync.wait(), timeout=interval_s)


async def run_forever(session_factory, ami: AmiClient, interval_s: float) -> None:
    service = CallEventService(session_factory, ami)
    await asyncio.gather(service.run_listener(), service.run_consumer(), service.run_sweeper(interval_s))
