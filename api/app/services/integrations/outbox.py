"""Outbox (m3b-contract.md §0): hodisa + har mos obuna uchun yetkazish qatori BITTA tranzaksiyada.

Sof qismlar (unit-test): qayta urinish jadvali, holat o'tishi, obuna filtri, tartib tanlovi.
Tartib: bitta `(subscription_id, call_id)` uchun eng kichik `seq`li `pending` qator — «bosh»;
faqat bosh yetkaziladi (oldingisi `delivered`/`dead` bo'lmaguncha keyingisi olinmaydi).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IntegrationDelivery, IntegrationEvent, IntegrationSubscription
from app.services.integrations.providers import DeliveryResult

DEFAULT_SCHEDULE: tuple[int, ...] = (30, 120, 600, 1800, 3600, 10800, 21600, 43200)
CRM_KINDS = frozenset({"bitrix24", "amocrm"})
CALL_EVENT_TYPES = ("call.ringing", "call.answered", "call.ended")


# ------------------------------------------------------------ sof qoidalar
def parse_schedule(raw: str) -> tuple[int, ...]:
    try:
        values = tuple(int(part) for part in raw.split(",") if part.strip())
    except ValueError:
        return DEFAULT_SCHEDULE
    if not values or any(v <= 0 for v in values):
        return DEFAULT_SCHEDULE
    return values


@dataclass(frozen=True)
class Transition:
    status: str
    attempts: int
    next_attempt_at: datetime | None = None
    delivered_at: datetime | None = None


def transition(result: DeliveryResult, *, attempts: int, schedule: tuple[int, ...], now: datetime) -> Transition:
    if result.ok:
        return Transition("delivered", attempts + 1, delivered_at=now)
    if result.retry_after_s is not None:
        return Transition("pending", attempts, now + timedelta(seconds=result.retry_after_s))
    used = attempts + 1
    if result.permanent or used > len(schedule):
        return Transition("dead", used)
    return Transition("pending", used, now + timedelta(seconds=schedule[used - 1]))


def should_disable(failing_since: datetime | None, now: datetime, after_s: int) -> bool:
    return failing_since is not None and now - failing_since >= timedelta(seconds=after_s)


@dataclass(frozen=True)
class SubscriptionFilter:
    kind: str
    events: tuple[str, ...]
    include_internal: bool


def wants_event(sub: SubscriptionFilter, event_type: str, *, internal: bool) -> bool:
    """Ichki qo'ng'iroq: webhook'ga faqat `include_internal`, CRM'ga HECH QACHON."""
    if event_type not in sub.events:
        return False
    if internal:
        return sub.kind not in CRM_KINDS and sub.include_internal
    return True


@dataclass(frozen=True)
class Candidate:
    id: str
    subscription_id: str
    call_id: str | None
    seq: int


def pick_deliverable(candidates: list[Candidate], heads: dict[tuple[str, str], int]) -> Candidate | None:
    """`heads[(sub, call)]` — shu juftlikdagi eng kichik `pending` seq (qulflanganlari ham)."""
    for cand in candidates:
        if cand.call_id is None or heads.get((cand.subscription_id, cand.call_id), cand.seq) == cand.seq:
            return cand
    return None


def envelope(event_id: str, event_type: str, occurred_at: datetime, call: dict[str, Any] | None) -> dict[str, Any]:
    body: dict[str, Any] = {"id": event_id, "type": event_type, "occurred_at": iso_z(occurred_at)}
    if call is not None:
        body["call"] = call
    return body


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------ baza
async def _fan_out(session: AsyncSession, event: IntegrationEvent, subs: list[IntegrationSubscription]) -> int:
    rows = [{"tenant_id": event.tenant_id, "subscription_id": s.id, "event_id": event.id, "call_id": event.call_id}
            for s in subs]
    if rows:
        await session.execute(pg_insert(IntegrationDelivery).values(rows).on_conflict_do_nothing())
    return len(rows)


async def emit_event(
    session: AsyncSession, *, tenant_id: str, event_type: str, dedupe_key: str, call_id: str | None,
    internal: bool, call: dict[str, Any], occurred_at: datetime,
) -> IntegrationEvent | None:
    """Hodisa (takror `dedupe_key` — e'tiborsiz, `None`) + mos obunalar uchun yetkazishlar.
    Commit chaqiruvchida — hodisa va yetkazishlar bitta tranzaksiyada."""
    event_id = str(uuid.uuid4())
    stmt = pg_insert(IntegrationEvent).values(
        id=event_id, tenant_id=tenant_id, type=event_type, dedupe_key=dedupe_key, call_id=call_id,
        internal=internal, payload=envelope(event_id, event_type, occurred_at, call), occurred_at=occurred_at,
    ).on_conflict_do_nothing(index_elements=["tenant_id", "dedupe_key"]).returning(IntegrationEvent.id)
    if (await session.execute(stmt)).scalar_one_or_none() is None:
        return None
    event = await session.get(IntegrationEvent, event_id)
    subs = (await session.execute(select(IntegrationSubscription).where(
        IntegrationSubscription.tenant_id == tenant_id, IntegrationSubscription.enabled.is_(True),
    ))).scalars().all()
    matching = [s for s in subs if wants_event(
        SubscriptionFilter(s.kind, tuple(s.events or ()), s.include_internal), event_type, internal=internal)]
    await _fan_out(session, event, matching)
    return event


async def enqueue_test_ping(session: AsyncSession, sub: IntegrationSubscription) -> IntegrationEvent:
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    event = IntegrationEvent(id=event_id, tenant_id=sub.tenant_id, type="test.ping", dedupe_key=f"test:{event_id}",
                             call_id=None, internal=False, payload=envelope(event_id, "test.ping", now, None),
                             occurred_at=now)
    session.add(event)
    await session.flush()
    await _fan_out(session, event, [sub])
    return event


def reset_for_replay(delivery: IntegrationDelivery, now: datetime) -> None:
    delivery.status, delivery.attempts, delivery.next_attempt_at = "pending", 0, now
    delivery.delivered_at = None
