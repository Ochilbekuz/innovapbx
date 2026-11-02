"""Zaxira jadvali -- fon vazifa (m4b-contract.md Β§0).

Har `interval_s` soniyada barcha tenantlar ko'rib chiqiladi: `system_settings.backup.schedule`
yoqilgan va navbatdagi slot kelgan bo'lsa (`backup_schedule.is_due()`, `Tenant.timezone`
IANA nomi `zoneinfo` orqali amaldagi UTC siljishiga aylantirilib) yangi `kind="scheduled"`
zaxira boshlanadi. Server o'chiq bo'lib bir slot o'tkazib yuborilsa -- ishga tushgach bir
marta "catch-up" (`is_due()`ning o'zi ta'minlaydi, bu modulda qo'shimcha mantiq shart emas).

`job_lock` band bo'lsa (boshqa zaxira/tiklash allaqachon ketayotgan edi) -- bu tsiklni
shunchaki o'tkazib yuboradi (xato EMAS, band bo'lish normal holat; keyingi tiketda qayta
urinadi, `last_scheduled_at` YANGILANMAYDI shu sabab).

`backup_stale`: muvaffaqiyatli (`last_scheduled_ok_at`) zaxira 2x jadval davridan ko'p
vaqt bo'lmasa -- kuniga bir marta (`last_stale_alert_at`) ogohlantirish. Hali birorta
urinish ham bo'lmagan tenant (`last_scheduled_at is None`) uchun ogohlantirilmaydi -- aks
holda jadval endigina yoqilgan zahoti soxta signal berardi."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.models import Backup, SystemSettings, Tenant
from app.services import backup_job
from app.services.alerts import alert_text, raise_alert, tenant_language
from app.services.backup_schedule import Schedule, is_due
from app.services.job_lock import JobAlreadyRunningError, JobLock, try_acquire_job_lock

log = logging.getLogger("innova.backup_scheduler")

_STALE_ALERT_INTERVAL_S = 86400  # kuniga bir marta


def tz_offset_minutes(tz_name: str, now: datetime) -> int:
    """IANA zona nomini `now` paytidagi UTC siljishiga (daqiqada) aylantiradi.
    Noma'lum/bo'sh zona nomi -- UTC (`0`), ishni to'xtatmaydi."""
    try:
        zone = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001 -- noto'g'ri zona nomi fon vazifani buzmasin
        return 0
    offset = now.astimezone(zone).utcoffset()
    return int(offset.total_seconds() // 60) if offset else 0


def period_seconds(frequency: str) -> int:
    return 86400 if frequency == "daily" else 7 * 86400


def schedule_from_cfg(sched_cfg: dict, tz_offset_minutes_value: int) -> Schedule:
    return Schedule(
        enabled=sched_cfg["enabled"], frequency=sched_cfg["frequency"],
        weekday=sched_cfg["weekday"], time=sched_cfg["time"],
        tz_offset_minutes=tz_offset_minutes_value,
    )


def _parse_iso(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def stale_check(
    now: datetime, last_scheduled_at: datetime | None, last_ok: datetime | None,
    last_stale_alert_at: datetime | None, period_s: int,
) -> bool:
    """`True` -- hozir `backup_stale` ogohlantirish yuborish kerak (sof funksiya, DB/vaqtsiz).
    Birorta urinish ham bo'lmagan (`last_scheduled_at is None`) bo'lsa -- hali erta."""
    if last_scheduled_at is None:
        return False
    if last_ok is not None and (now - last_ok).total_seconds() < 2 * period_s:
        return False
    if last_stale_alert_at is not None and (now - last_stale_alert_at).total_seconds() < _STALE_ALERT_INTERVAL_S:
        return False
    return True


async def _maybe_alert_stale(
    session: AsyncSession, tenant_id: str, settings_row: SystemSettings, schedule: Schedule, now: datetime,
) -> None:
    cfg = settings_row.backup
    last_scheduled_at = _parse_iso(cfg.get("last_scheduled_at"))
    last_ok = _parse_iso(cfg.get("last_scheduled_ok_at"))
    last_stale_alert_at = _parse_iso(cfg.get("last_stale_alert_at"))
    if not stale_check(now, last_scheduled_at, last_ok, last_stale_alert_at, period_seconds(schedule.frequency)):
        return
    days = (now - last_ok).days if last_ok else 0
    lang = await tenant_language(session, tenant_id)
    text = alert_text(lang, "backup_stale", days=days)
    await raise_alert(session, tenant_id, "backup_stale", "backup", text)
    settings_row.backup = {**cfg, "last_stale_alert_at": now.isoformat()}
    await session.commit()


async def _run_and_mark_ok(
    session_factory: async_sessionmaker, engine: AsyncEngine, lock: JobLock, backup_id: str, tenant_id: str,
) -> None:
    try:
        await backup_job.run_backup_job(session_factory, engine, lock, backup_id, tenant_id)
        async with session_factory() as session:
            backup = await session.get(Backup, backup_id)
            if backup is not None and backup.status in ("ok", "partial"):
                settings_row = await session.get(SystemSettings, tenant_id)
                settings_row.backup = {
                    **settings_row.backup, "last_scheduled_ok_at": datetime.now(timezone.utc).isoformat(),
                }
                await session.commit()
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001 -- fon vazifa (create_task) hech qachon kuzatilmasdan o'lmasin
        log.exception("rejalashtirilgan zaxira (%s) tugatishda xato", backup_id)


async def _run_due_backup(
    session: AsyncSession, session_factory: async_sessionmaker, engine: AsyncEngine,
    tenant_id: str, sched_cfg: dict, settings_row: SystemSettings, now: datetime,
) -> None:
    try:
        lock = await try_acquire_job_lock(engine)
    except JobAlreadyRunningError:
        return  # band -- keyingi tiketda qayta urinamiz, last_scheduled_at YANGILANMAYDI
    try:
        backup = await backup_job.create_backup_record(
            session, tenant_id=tenant_id, kind="scheduled",
            components=list(sched_cfg["components"]), created_by=None,
        )
    except backup_job.PassphraseRequiredError:
        await lock.release()
        return
    settings_row.backup = {**settings_row.backup, "last_scheduled_at": now.isoformat()}
    await session.commit()
    asyncio.create_task(_run_and_mark_ok(session_factory, engine, lock, backup.id, tenant_id))


async def _tick_tenant(
    session: AsyncSession, session_factory: async_sessionmaker, engine: AsyncEngine,
    tenant: Tenant, settings_row: SystemSettings, now: datetime,
) -> None:
    sched_cfg = settings_row.backup["schedule"]
    schedule = schedule_from_cfg(sched_cfg, tz_offset_minutes(tenant.timezone, now))
    if not schedule.enabled:
        return
    await _maybe_alert_stale(session, tenant.id, settings_row, schedule, now)
    last_run_at = _parse_iso(settings_row.backup.get("last_scheduled_at"))
    if is_due(now, schedule, last_run_at):
        await _run_due_backup(session, session_factory, engine, tenant.id, sched_cfg, settings_row, now)


async def tick(session_factory: async_sessionmaker, engine: AsyncEngine) -> None:
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        tenants = (await session.execute(select(Tenant))).scalars().all()
        for tenant in tenants:
            settings_row = await session.get(SystemSettings, tenant.id)
            if settings_row is None:
                continue
            await _tick_tenant(session, session_factory, engine, tenant, settings_row, now)


async def run_forever(session_factory: async_sessionmaker, engine: AsyncEngine, interval_s: float) -> None:
    from app.services import maintenance

    while True:
        if maintenance.state.enabled:
            await asyncio.sleep(interval_s)
            continue
        try:
            await tick(session_factory, engine)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 -- fon vazifa hech qachon o'lmasin
            log.exception("backup_scheduler tsiklida xato")
        await asyncio.sleep(interval_s)
