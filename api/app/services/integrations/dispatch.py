"""`integration_dispatch` fon vazifasi (m3b-contract.md §0/§3) — `alert_dispatch` qolipi.

Har aylanishda bitta yetkazish: `pending` + vaqti kelgan + obuna yoqilgan, `FOR UPDATE SKIP LOCKED`;
`(subscription_id, call_id)` bo'yicha faqat «bosh» qator (eng kichik `seq`) — QAT'IY tartib.
Natija `outbox.transition` bilan; obunaning 24 soat uzluksiz xatosi → avtomatik o'chirish + alert.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import IntegrationDelivery, IntegrationEvent, IntegrationSubscription
from app.services.crypto import decrypt_secret
from app.services.integrations import outbox, providers
from app.services.integrations.providers import DeliveryContext, DeliveryResult, EventView, SubscriptionView

log = logging.getLogger(__name__)
BATCH = 20


async def _candidates(session: AsyncSession, now: datetime) -> list[outbox.Candidate]:
    rows = (await session.execute(
        select(IntegrationDelivery.id, IntegrationDelivery.subscription_id, IntegrationDelivery.call_id,
               IntegrationDelivery.seq)
        .join(IntegrationSubscription, IntegrationSubscription.id == IntegrationDelivery.subscription_id)
        .where(IntegrationDelivery.status == "pending", IntegrationDelivery.next_attempt_at <= now,
               IntegrationSubscription.enabled.is_(True))
        .order_by(IntegrationDelivery.next_attempt_at, IntegrationDelivery.seq)
        .limit(BATCH).with_for_update(of=IntegrationDelivery, skip_locked=True)
    )).all()
    return [outbox.Candidate(id=str(r[0]), subscription_id=str(r[1]), call_id=r[2], seq=r[3]) for r in rows]


async def _heads(session: AsyncSession, cands: list[outbox.Candidate]) -> dict[tuple[str, str], int]:
    calls = {c.call_id for c in cands if c.call_id is not None}
    if not calls:
        return {}
    rows = (await session.execute(
        select(IntegrationDelivery.subscription_id, IntegrationDelivery.call_id, func.min(IntegrationDelivery.seq))
        .where(IntegrationDelivery.status == "pending", IntegrationDelivery.call_id.in_(calls),
               IntegrationDelivery.subscription_id.in_({c.subscription_id for c in cands}))
        .group_by(IntegrationDelivery.subscription_id, IntegrationDelivery.call_id)
    )).all()
    return {(str(sub), call): seq for sub, call, seq in rows}


async def _subscription_view(session: AsyncSession, sub: IntegrationSubscription) -> SubscriptionView:
    secret = await decrypt_secret(session, sub.secret_enc) if sub.secret_enc else None
    return SubscriptionView(id=str(sub.id), tenant_id=str(sub.tenant_id), kind=sub.kind, name=sub.name,
                            config=dict(sub.config or {}), secret=secret)


async def _deliver(session: AsyncSession, delivery: IntegrationDelivery, sub: IntegrationSubscription) -> DeliveryResult:
    event = await session.get(IntegrationEvent, delivery.event_id)
    ctx = DeliveryContext(
        delivery_id=str(delivery.id), attempt=delivery.attempts + 1,
        subscription=await _subscription_view(session, sub),
        event=EventView(id=str(event.id), type=event.type, call_id=event.call_id, payload=event.payload),
        session=session,
    )
    try:
        return await providers.deliver(sub.kind, ctx)
    except Exception as exc:  # noqa: BLE001 — yetkazuvchi xatosi navbatni to'xtatmasin (vaqtinchalik)
        log.exception("integration_dispatch: %s yetkazuvchisi yiqildi", sub.kind)
        return DeliveryResult(ok=False, error=f"{type(exc).__name__}"[:200])


async def _update_subscription(session: AsyncSession, sub: IntegrationSubscription, result: DeliveryResult,
                               now: datetime) -> None:
    if result.ok:
        sub.failing_since, sub.last_success_at, sub.last_error = None, now, None
        return
    sub.failing_since = sub.failing_since or now
    sub.last_error = (result.error or f"HTTP {result.status_code}")[:500]
    if outbox.should_disable(sub.failing_since, now, settings.integration_disable_after_s):
        from app.services.alerts import alert_text, raise_alert, tenant_language

        sub.enabled = False
        sub.disabled_reason = f"24 soat uzluksiz xato: {result.error or result.status_code}"[:300]
        sub.updated_at = now
        lang = await tenant_language(session, str(sub.tenant_id))
        await raise_alert(session, str(sub.tenant_id), "webhook_disabled", str(sub.id),
                          alert_text(lang, "webhook_disabled", name=sub.name, reason=sub.disabled_reason))


def _apply(delivery: IntegrationDelivery, result: DeliveryResult, now: datetime) -> None:
    step = outbox.transition(result, attempts=delivery.attempts,
                             schedule=outbox.parse_schedule(settings.integration_retry_schedule_s), now=now)
    delivery.status, delivery.attempts = step.status, step.attempts
    delivery.next_attempt_at = step.next_attempt_at or delivery.next_attempt_at
    delivery.delivered_at = step.delivered_at
    delivery.last_attempt_at = now
    delivery.last_status_code = result.status_code
    delivery.last_error = None if result.ok else (result.error or f"HTTP {result.status_code}")[:500]
    delivery.response_body = result.response_body


async def dispatch_once(session_factory) -> bool:
    """`True` — bitta yetkazish bajarildi (navbatda yana bo'lishi mumkin)."""
    async with session_factory() as session:
        now = datetime.now(timezone.utc)
        cands = await _candidates(session, now)
        pick = outbox.pick_deliverable(cands, await _heads(session, cands))
        if pick is None:
            await session.commit()
            return False
        delivery = await session.get(IntegrationDelivery, pick.id)
        sub = await session.get(IntegrationSubscription, delivery.subscription_id)
        result = await _deliver(session, delivery, sub)
        now = datetime.now(timezone.utc)
        _apply(delivery, result, now)
        await _update_subscription(session, sub, result, now)
        await session.commit()
        return True


async def run_forever(session_factory, interval_s: float) -> None:
    from app.services import maintenance
    from app.services.integrations import registry

    registry.load_providers()
    while True:
        if maintenance.state.enabled:
            await asyncio.sleep(interval_s)
            continue
        try:
            while await dispatch_once(session_factory):
                pass
        except Exception:  # noqa: BLE001 — fon vazifa yiqilmasin
            log.exception("integration_dispatch xatosi")
        await asyncio.sleep(interval_s)
