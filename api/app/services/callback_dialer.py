"""M10 A1 — fon vazifa: `callback_requests`dan bo'sh joy bo'yicha so'rov olib AMI
Originate qiladi (`campaign_dialer.py` BILAN BIR XIL qolip). Natija — dialplan hangup
handler -> `/internal/callback/result` -> `record_operator_result`/`record_customer_result`.

Ish vaqti (`offhours_mode="schedule"`): ANIQ "keyingi ochilish vaqti" kalendar hisobi
YOZILMAGAN — ataylab SODDALASHTIRISH: yopiq bo'lsa so'rov urinish sarflamay
`retry_interval_s`dan keyin qayta tekshiriladi (har dialer aylanishida `compute_state_now()`
qayta chaqiriladi, ochilgach keyingi aylanishda teriladi). Boshqa fon vazifalarning
so'rov oralig'i bilan mos, lekin aniqlik — shu oraliq darajasida (m10a-contract.md'da
ANIQ kalendar hisobi talab qilinmagan)."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import CallbackRequest, CallbackWidget, Tenant, TimeGroup
from app.services import callback_rules as rules
from app.services.holidays_calc import holidays_mmdd_set
from app.services.time_eval import compute_state_now

log = logging.getLogger("innova.callback_dialer")

_BATCH = 20
LOST_AFTER = timedelta(hours=1)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def is_open(session: AsyncSession, tenant: Tenant, widget: CallbackWidget) -> bool:
    """Vidjetning ish vaqti holati — `claim_due()` (schedule) VA `api/public_widget.py`
    intake (reject) ikkisi ham shu BIR XIL funksiyadan foydalanadi."""
    if widget.time_group_id is None:
        return True
    group = await session.get(TimeGroup, widget.time_group_id)
    if group is None:
        return True  # o'chirilgan guruh — cheklov yo'q deb hisoblanadi (xavfsiz tomon: terish davom etadi)
    ranges = [(r.weekdays, r.start_time.strftime("%H:%M"), r.end_time.strftime("%H:%M")) for r in group.ranges]
    holidays = await holidays_mmdd_set(session, str(tenant.id))
    state = compute_state_now(tz_name=tenant.timezone, override="none", ranges=ranges,
                              honor_holidays=True, holidays_mmdd=holidays)
    return state == "open"


async def _due_requests(session: AsyncSession, now: datetime) -> list[CallbackRequest]:
    due = (CallbackRequest.next_attempt_at.is_(None)) | (CallbackRequest.next_attempt_at <= now)
    return list((await session.execute(
        select(CallbackRequest).where(CallbackRequest.status == "pending", due)
        .order_by(CallbackRequest.next_attempt_at.nulls_first(), CallbackRequest.created_at)
        .limit(_BATCH).with_for_update(skip_locked=True))).scalars().all())


async def _reschedule(req: CallbackRequest, now: datetime, retry_interval_s: int) -> None:
    """Yopiq ish vaqti (`schedule`) — urinish sarflanmaydi, faqat keyingi tekshiruv vaqti suriladi."""
    req.next_attempt_at = now + timedelta(seconds=retry_interval_s)


async def claim_due(session: AsyncSession, now: datetime) -> list[tuple[CallbackRequest, CallbackWidget, Tenant]]:
    """Ish vaqti/vidjet holatini tekshirib, teriladigan so'rovlarni oladi (commit — chaqiruvchida)."""
    claimed: list[tuple[CallbackRequest, CallbackWidget, Tenant]] = []
    for req in await _due_requests(session, now):
        widget = await session.get(CallbackWidget, req.widget_id)
        if widget is None or not widget.enabled:
            req.status, req.last_error, req.updated_at = "cancelled", "widget_disabled", func.now()
            continue
        tenant = await session.get(Tenant, req.tenant_id)
        if tenant is None:
            req.status, req.last_error, req.updated_at = "cancelled", "tenant_missing", func.now()
            continue
        if widget.offhours_mode == "schedule" and not await is_open(session, tenant, widget):
            await _reschedule(req, now, widget.retry_interval_s)
            continue
        req.status, req.attempts, req.updated_at = "dialing", req.attempts + 1, func.now()
        claimed.append((req, widget, tenant))
    return claimed


async def _originate(ami, req: rules.CallbackDialRequest) -> bool:
    try:
        resp = await ami.action("Originate", **rules.originate_fields(req))
    except Exception:  # noqa: BLE001 — AMI uzilgan / xavfli qiymat
        log.exception("callback originate xato (so'rov %s)", req.request_id)
        return False
    return (resp or {}).get("Response") == "Success"


def _dial_request(tenant_code: str, widget: CallbackWidget, request: CallbackRequest) -> rules.CallbackDialRequest:
    return rules.CallbackDialRequest(
        code=tenant_code, request_id=str(request.id), dest_ctx=f"{tenant_code}-dest-{widget.target_id}",
        phone=request.phone, callerid_prefix=widget.callerid_prefix)


async def _revert(session_factory: async_sessionmaker, request_id: str) -> None:
    """Originate amalga oshmadi — urinish hisoblanmaydi."""
    async with session_factory() as session:
        await session.execute(update(CallbackRequest).where(CallbackRequest.id == request_id).values(
            status="pending", attempts=CallbackRequest.attempts - 1, updated_at=func.now()))
        await session.commit()


async def dialer_cycle(session_factory: async_sessionmaker, ami, now: datetime | None = None) -> int:
    now = now or utcnow()
    async with session_factory() as session:
        await sweep_lost(session, now)
        await session.commit()
        claimed = await claim_due(session, now)
        requests = [(_dial_request(t.code, w, r), str(r.id)) for r, w, t in claimed]
        await session.commit()
    dialed = 0
    for dial_req, request_id in requests:
        if await _originate(ami, dial_req):
            dialed += 1
        else:
            await _revert(session_factory, request_id)
    return dialed


async def sweep_lost(session: AsyncSession, now: datetime) -> int:
    """Uzoq vaqt `dialing`da qolgan (hangup handler kelmadi — AMI uzilishi) so'rovlar qayta urinishga."""
    stale = (await session.execute(select(CallbackRequest).where(
        CallbackRequest.status == "dialing", CallbackRequest.updated_at < now - LOST_AFTER)
        .with_for_update(skip_locked=True))).scalars().all()
    for req in stale:
        widget = await session.get(CallbackWidget, req.widget_id)
        max_attempts = widget.max_attempts if widget else 1
        retry_interval_s = widget.retry_interval_s if widget else 120
        decision = rules.lost_result(req.attempts, max_attempts, now, retry_interval_s)
        req.status, req.next_attempt_at, req.last_error = decision.status, decision.next_attempt_at, decision.last_error
        req.updated_at = func.now()
    return len(stale)


async def _get_dialing(session: AsyncSession, request_id: str) -> CallbackRequest | None:
    req = await session.get(CallbackRequest, request_id, with_for_update=True)
    return req if req is not None and req.status == "dialing" else None


async def record_operator_result(session: AsyncSession, request_id: str, raw_status: str,
                                 now: datetime | None = None) -> bool:
    """`<code>-callback-ophang`. Operator javob bergan bo'lsa — `None` (o'zgarish yo'q,
    mijoz terish bosqichi davom etadi/etgan). Idempotent: so'rov allaqachon yopilgan — `False`."""
    req = await _get_dialing(session, request_id)
    if req is None:
        return False
    widget = await session.get(CallbackWidget, req.widget_id)
    if widget is None:
        return False
    decision = rules.operator_result(raw_status, req.attempts, widget.max_attempts, now or utcnow(),
                                     widget.retry_interval_s)
    if decision is not None:
        req.status, req.next_attempt_at, req.last_error = decision.status, decision.next_attempt_at, decision.last_error
        req.updated_at = func.now()
    return True


async def record_customer_result(session: AsyncSession, request_id: str, raw_status: str, linkedid: str,
                                  now: datetime | None = None) -> bool:
    """`<code>-callback-custhang` — faqat operator javob bergandan keyin ishga tushadi, doim yakuniy."""
    req = await _get_dialing(session, request_id)
    if req is None:
        return False
    widget = await session.get(CallbackWidget, req.widget_id)
    if widget is None:
        return False
    decision = rules.customer_result(raw_status, req.attempts, widget.max_attempts, now or utcnow(),
                                     widget.retry_interval_s)
    req.status, req.next_attempt_at, req.last_error = decision.status, decision.next_attempt_at, decision.last_error
    req.updated_at = func.now()
    if decision.status == "connected" and linkedid:
        req.linkedid = linkedid
    return True


async def run_forever(session_factory: async_sessionmaker, ami, interval_s: float) -> None:
    from app.services import maintenance

    while True:
        if not maintenance.state.enabled:
            try:
                await dialer_cycle(session_factory, ami)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 — fon vazifa hech qachon o'lmasin
                log.exception("callback_dialer aylanishida xato")
        await asyncio.sleep(interval_s)
