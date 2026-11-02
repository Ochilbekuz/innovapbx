"""Qotib qolgan fon ishlarini tiklash — API qayta ishga tushganda.

Zaxira, tiklash va FreePBX ko'chirish ishlari API jarayoni ichida `asyncio` vazifa sifatida ketadi.
Jarayon o'lsa (restart, OOM, deploy) yozuv `running`/`applying` holatida abadiy qoladi: UI «ketyapti»
deb ko'rsatadi, ishni o'chirib ham bo'lmaydi. Ishga tushishda umumiy qulf (`job_lock`) olinadi —
olinsa, hech bir jarayonda ish ketmayapti, demak bu holatlar eskirgan → `failed` + «uzildi» xatosi.
Qulf band bo'lsa (boshqa jarayon haqiqatan ishlayapti) hech narsa o'zgartirilmaydi."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.models import Backup, MigrationJob, RestoreJob
from app.services.job_lock import JobAlreadyRunningError, try_acquire_job_lock

log = logging.getLogger(__name__)

INTERRUPTED = "interrupted"
MIGRATION_RUNNING = ("fetching", "analyzing", "applying")
INTERRUPTED_MESSAGE = ("API qayta ishga tushganda ish uzildi — qaytadan boshlang "
                       "(ko'chirish qo'llanayotgan bo'lsa, pre_import zaxirasini tekshiring)")


async def recover_stale_jobs(session_factory, engine: AsyncEngine, now: datetime | None = None) -> int:
    """Qaytaradi: `failed` ga o'tkazilgan yozuvlar soni (qulf band bo'lsa 0)."""
    try:
        lock = await try_acquire_job_lock(engine)
    except JobAlreadyRunningError:
        return 0
    now = now or datetime.now(timezone.utc)
    try:
        async with session_factory() as session:
            counts = [
                await session.execute(update(MigrationJob).where(MigrationJob.status.in_(MIGRATION_RUNNING)).values(
                    status="failed", step=None, error={"code": INTERRUPTED, "message": INTERRUPTED_MESSAGE})),
                await session.execute(update(Backup).where(Backup.status == "running").values(
                    status="failed", error=INTERRUPTED_MESSAGE, finished_at=now)),
                await session.execute(update(RestoreJob).where(RestoreJob.status == "running").values(
                    status="failed", error=INTERRUPTED_MESSAGE, finished_at=now)),
            ]
            await session.commit()
    finally:
        await lock.release()
    total = sum(r.rowcount or 0 for r in counts)
    if total:
        log.warning("qotib qolgan fon ishlari: %d ta yozuv failed ga o'tkazildi", total)
    return total
