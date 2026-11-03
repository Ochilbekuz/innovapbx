"""M10 A2 — fon vazifa: `integration_events` outbox'dan (`type='call.ended'`,
`status='missed'`) o'qib, mos qoidalar (`missed_call_rules`) bo'yicha Telegram/
email bildirishnoma yaratadi va yuboradi (`main.py` lifespan, §2 shablon
`vm_notify.py`/`alerts.py` BILAN BIR XIL: claim -> yetkazish -> yakun, bitta
tranzaksiya; yuborish navbati — alohida, `alert_dispatch` qolipi)."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.models import (
    Extension,
    IntegrationEvent,
    MissedCallNotice,
    MissedCallRule,
    MissedNotifyCursor,
    RingGroup,
    RingGroupMember,
    Tenant,
)
from app.services import missed_call_rules as rules
from app.services import vm_notify
from app.services.integrations.outbox import parse_schedule, transition
from app.services.integrations.providers import DeliveryResult

log = logging.getLogger("innova.missed_call_notify")

_EVENTS_BATCH = 200


async def _ring_group_numbers(session: AsyncSession, tenant_id: str, ring_group_id: str) -> frozenset[str]:
    rg = await session.get(RingGroup, ring_group_id)
    if rg is None or str(rg.tenant_id) != tenant_id:
        return frozenset()
    members = list((await session.execute(
        select(RingGroupMember).where(RingGroupMember.ring_group_id == ring_group_id))).scalars().all())
    numbers = {m.external_number for m in members if m.external_number}
    ext_ids = [m.extension_id for m in members if m.extension_id]
    if ext_ids:
        numbers |= set((await session.execute(
            select(Extension.number).where(Extension.id.in_(ext_ids)))).scalars().all())
    return frozenset(numbers)


async def _matching_rules(
    session: AsyncSession, tenant_id: str, rules_: list[MissedCallRule], call: dict,
) -> list[MissedCallRule]:
    """Har qoidaning o'z `include_internal`i tekshiriladi — shu sabab filtr
    pastdagi `for` ichida, qoidama-qoida."""
    cache: dict[str, frozenset[str]] = {}
    out: list[MissedCallRule] = []
    for rule in rules_:
        if not rule.enabled or not rules.rule_included(rule.include_internal, call.get("direction", "")):
            continue
        ring_numbers = frozenset()
        if rule.scope_kind == "ring_group" and rule.scope_value:
            if rule.scope_value not in cache:
                cache[rule.scope_value] = await _ring_group_numbers(session, tenant_id, rule.scope_value)
            ring_numbers = cache[rule.scope_value]
        if rules.rule_matches(rule.scope_kind, rule.scope_value, call, ring_group_numbers=ring_numbers):
            out.append(rule)
    return out


async def _cursor(session: AsyncSession, tenant_id: str, max_seq_if_missing: int) -> MissedNotifyCursor:
    row = await session.get(MissedNotifyCursor, tenant_id)
    if row is None:
        # Birinchi marta — tarixni «yutib» yubormaslik uchun joriy eng katta `seq`dan boshlanadi.
        row = MissedNotifyCursor(tenant_id=tenant_id, last_seq=max_seq_if_missing)
        session.add(row)
        await session.flush()
    return row


async def _max_seq(session: AsyncSession) -> int:
    return (await session.execute(select(IntegrationEvent.seq).order_by(IntegrationEvent.seq.desc()).limit(1)
                                  )).scalar_one_or_none() or 0


async def _create_notices(session: AsyncSession, tenant_id: str, event: IntegrationEvent,
                          matched: list[MissedCallRule]) -> None:
    for rule in matched:
        await session.execute(pg_insert(MissedCallNotice).values(
            tenant_id=tenant_id, rule_id=rule.id, call_id=event.call_id or event.id,
            status="pending", attempts=0,
        ).on_conflict_do_nothing(index_elements=["rule_id", "call_id"]))


async def _tenants_with_rules(session: AsyncSession) -> list[str]:
    return list((await session.execute(
        select(MissedCallRule.tenant_id).where(MissedCallRule.enabled.is_(True)).distinct())).scalars().all())


async def advance_cursor_cycle(session_factory: async_sessionmaker) -> int:
    """Har tenant uchun oxirgi `seq`dan keyingi `call.ended`/`missed` hodisalarni
    ko'rib, mos qoidalar uchun bildirishnoma qatori yaratadi (idempotent)."""
    created = 0
    async with session_factory() as session:
        tenant_ids = await _tenants_with_rules(session)
        for tenant_id in tenant_ids:
            max_seq = await _max_seq(session)
            cursor = await _cursor(session, tenant_id, max_seq)
            events = list((await session.execute(
                select(IntegrationEvent).where(
                    IntegrationEvent.tenant_id == tenant_id, IntegrationEvent.type == "call.ended",
                    IntegrationEvent.seq > cursor.last_seq,
                ).order_by(IntegrationEvent.seq).limit(_EVENTS_BATCH))).scalars().all())
            if not events:
                continue
            rule_rows = list((await session.execute(
                select(MissedCallRule).where(MissedCallRule.tenant_id == tenant_id,
                                             MissedCallRule.enabled.is_(True)))).scalars().all())
            for event in events:
                call = (event.payload or {}).get("call") or {}
                if rules.is_missed(call):
                    matched = await _matching_rules(session, tenant_id, rule_rows, call)
                    await _create_notices(session, tenant_id, event, matched)
                    created += len(matched)
                cursor.last_seq = event.seq
            await session.commit()
    return created


def _safe_error(exc: Exception, secret: str | None) -> str:
    text = str(exc) if isinstance(exc, vm_notify.NotifyError) else f"{type(exc).__name__}: {exc}"
    return (text.replace(secret, "***") if secret else text)[:500]


async def _send_email(cfg: vm_notify.NotifyConfig, to: str, body: str) -> None:
    em = EmailMessage()
    em["From"], em["To"], em["Subject"] = cfg.from_email or "", to, "Innova PBX — o'tkazib yuborilgan qo'ng'iroq"
    em.set_content(body)
    await asyncio.to_thread(vm_notify.send_email_sync, cfg, em)


async def send_notice(cfg: vm_notify.NotifyConfig, rule: MissedCallRule, call: dict, language: str) -> str | None:
    """Qoidaning barcha qabul qiluvchilariga yuboradi (Telegram/email). Hech biri
    sozlanmagan yoki biri muvaffaqiyatsiz bo'lsa ham — xato matnini qaytaradi
    (chaqiruvchida qayta urinish/`ok` holati sifatida ishlatiladi). Admin
    router `/missed-call-rules/{id}/test` ham shuni chaqiradi (sinov xabari)."""
    body = rules.missed_call_text(language, call)
    if not rule.telegram_chat_ids and not rule.emails:
        return "no_recipients"
    error: str | None = None
    for chat_id in rule.telegram_chat_ids:
        try:
            await vm_notify.send_telegram(cfg, chat_id, body, None)
        except Exception as exc:  # noqa: BLE001
            error = _safe_error(exc, cfg.telegram_token)
    for email in rule.emails:
        try:
            await _send_email(cfg, email, body)
        except Exception as exc:  # noqa: BLE001
            error = _safe_error(exc, cfg.smtp_password)
    return error


async def _send_one(session: AsyncSession, notice: MissedCallNotice, now: datetime) -> None:
    rule = await session.get(MissedCallRule, notice.rule_id)
    tenant = await session.get(Tenant, notice.tenant_id)
    if rule is None or tenant is None:
        notice.status, notice.last_error = "failed", "rule_or_tenant_missing"
        return
    event = (await session.execute(select(IntegrationEvent).where(
        IntegrationEvent.tenant_id == notice.tenant_id, IntegrationEvent.call_id == notice.call_id,
        IntegrationEvent.type == "call.ended",
    ).order_by(IntegrationEvent.seq.desc()).limit(1))).scalar_one_or_none()
    call = (event.payload or {}).get("call") if event else None
    if call is None:
        notice.status, notice.last_error = "failed", "event_missing"
        return
    cfg = await vm_notify.load_config(session, notice.tenant_id)
    error = await send_notice(cfg, rule, call, tenant.language)
    schedule = parse_schedule(settings.missed_notify_retry_schedule_s)
    step = transition(DeliveryResult(ok=error is None, error=error), attempts=notice.attempts,
                      schedule=schedule, now=now)
    notice.attempts = step.attempts
    notice.last_error = error
    if step.status == "delivered":
        notice.status, notice.sent_at = "sent", now
    elif step.status == "dead":
        notice.status = "failed"
    else:
        notice.status = "pending"
        # keyingi urinish — `attempts`ga qarab eskirgan rowlar FOR UPDATE SKIP LOCKED bilan qayta olinadi


async def dispatch_notices_cycle(session_factory: async_sessionmaker, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    sent = 0
    while True:
        async with session_factory() as session:
            notice = (await session.execute(
                select(MissedCallNotice).where(MissedCallNotice.status == "pending")
                .order_by(MissedCallNotice.id).with_for_update(skip_locked=True).limit(1)
            )).scalar_one_or_none()
            if notice is None:
                return sent
            await _send_one(session, notice, now)
            await session.commit()
            sent += 1


async def notify_cycle(session_factory: async_sessionmaker) -> None:
    await advance_cursor_cycle(session_factory)
    await dispatch_notices_cycle(session_factory)


async def run_forever(session_factory: async_sessionmaker, interval_s: float) -> None:
    from app.services import maintenance

    while True:
        if not maintenance.state.enabled:
            try:
                await notify_cycle(session_factory)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 — fon vazifa hech qachon o'lmasin
                log.exception("missed_call_notify aylanishida xato")
        await asyncio.sleep(interval_s)
