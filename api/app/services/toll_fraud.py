"""M2c §3 — toll-fraud: ichki raqam limitlari (`/internal/toll/check`) va
bir vaqtdagi chiquvchi limit hodisasi (`/internal/toll/event`).

Sof qoida (`decide`) — nosof qism (`check_outbound`, `record_concurrent_limit`)
dan ALOHIDA (ub-mode TDD: `decide` bazasiz sinaladi)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Extension, OutboundAttempt, SecurityEvent
from app.services.alerts import alert_text, raise_alert, tenant_language
from app.services.security_config import TollFraudConfig

_HOUR = timedelta(hours=1)
_DAY = timedelta(hours=24)


def decide(
    *, enabled: bool, already_blocked: bool, intl: bool,
    hour_count: int, hour_limit: int, intl_count: int, intl_limit: int,
) -> tuple[bool, str | None]:
    """Sof qoida -> `(allowed, block_reason)`. `block_reason` faqat HOZIR
    bloklanayotganda (allaqachon bloklangan bo'lsa — `None`, chunki sabab
    o'zgarmaydi). Soatlik limit BARCHA (mahalliy+xalqaro) urinishlarni
    sanaydi; kunlik xalqaro limit FAQAT xalqaro urinishni (`intl=True`
    bo'lganda) — ikkisi bir-biridan MUSTAQIL, ikkalasi ham tekshiriladi."""
    if not enabled:
        return True, None
    if already_blocked:
        return False, None
    if hour_limit > 0 and hour_count >= hour_limit:
        return False, "per_hour"
    if intl and intl_limit > 0 and intl_count >= intl_limit:
        return False, "international_per_day"
    return True, None


def window_start(now: datetime, *, span: timedelta, unblocked_at: datetime | None) -> datetime:
    """Hisob oynasi boshlanishi — `max(now - span, toll_unblocked_at)`
    (m2c-contract.md §3: blokdan chiqarilgandan OLDINGI urinishlar hisobga
    kirmasligi uchun)."""
    floor = now - span
    if unblocked_at is None:
        return floor
    return max(floor, unblocked_at)


async def _count_allowed(
    session: AsyncSession, extension_id: str, since: datetime, *, international: bool | None = None,
) -> int:
    stmt = select(func.count()).select_from(OutboundAttempt).where(
        OutboundAttempt.extension_id == extension_id, OutboundAttempt.allowed.is_(True),
        OutboundAttempt.at >= since,
    )
    if international is not None:
        stmt = stmt.where(OutboundAttempt.international.is_(international))
    return (await session.execute(stmt)).scalar_one()


_REASON_LIMIT = {"per_hour": "ext_max_per_hour", "international_per_day": "ext_international_per_day"}


async def check_outbound(
    session: AsyncSession, *, tenant_id: str, extension: Extension, number: str, intl: bool,
    cfg: TollFraudConfig,
) -> bool:
    """`/internal/toll/check` asosiy mantiqi — `outbound_attempts`ga yozadi,
    limit oshsa ext'ni bloklaydi (`security_events` + ogohlantirish).
    Chaqiruvchi (router) COMMIT qilishi SHART emas — bu funksiya o'zi
    `session.commit()` chaqiradi (ichki endpoint — alohida tranzaksiya)."""
    now = datetime.now(timezone.utc)
    already_blocked = extension.toll_blocked_at is not None
    hour_count = 0
    intl_count = 0
    if not already_blocked and cfg.enabled:
        hour_since = window_start(now, span=_HOUR, unblocked_at=extension.toll_unblocked_at)
        hour_count = await _count_allowed(session, extension.id, hour_since)
        if intl:
            intl_since = window_start(now, span=_DAY, unblocked_at=extension.toll_unblocked_at)
            intl_count = await _count_allowed(session, extension.id, intl_since, international=True)

    allowed, reason = decide(
        enabled=cfg.enabled, already_blocked=already_blocked, intl=intl,
        hour_count=hour_count, hour_limit=cfg.ext_max_per_hour,
        intl_count=intl_count, intl_limit=cfg.ext_international_per_day,
    )
    session.add(OutboundAttempt(
        tenant_id=tenant_id, extension_id=extension.id, number=number, international=intl, allowed=allowed,
    ))
    if reason is not None:
        await _block_extension(session, tenant_id=tenant_id, extension=extension, reason=reason, cfg=cfg)
    await session.commit()
    return allowed


async def _block_extension(
    session: AsyncSession, *, tenant_id: str, extension: Extension, reason: str, cfg: TollFraudConfig,
) -> None:
    extension.toll_blocked_at = datetime.now(timezone.utc)
    extension.toll_block_reason = reason
    session.add(SecurityEvent(
        tenant_id=tenant_id, kind="toll_blocked", extension_id=extension.id,
        details={"number": extension.number, "reason": reason},
    ))
    limit = getattr(cfg, _REASON_LIMIT[reason])
    language = await tenant_language(session, tenant_id)
    text = alert_text(language, "toll_blocked", number=extension.number, limit=limit, reason=reason)
    await raise_alert(session, tenant_id, "toll_blocked", extension.number, text)


async def record_concurrent_limit(
    session: AsyncSession, *, tenant_id: str, extension_number: str | None, max_concurrent: int,
) -> None:
    """`/internal/toll/event?kind=concurrent_limit` — javob e'tiborsiz
    (dialplan tekshirmaydi), shu sabab bu yerda xato ko'tarilmaydi (chaqiruvchi
    endpoint bari bir "0" qaytaradi)."""
    session.add(SecurityEvent(
        tenant_id=tenant_id, kind="concurrent_limit", extension_id=None,
        details={"extension_number": extension_number, "max_concurrent_outbound": max_concurrent},
    ))
    language = await tenant_language(session, tenant_id)
    text = alert_text(language, "concurrent_limit", number=extension_number or "?", limit=max_concurrent)
    await raise_alert(session, tenant_id, "concurrent_limit", extension_number or "", text)
    await session.commit()
