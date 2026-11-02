"""M5a — `analyze` fon vazifasi (`app/api/v1/migration.py::POST /jobs/{id}/analyze`
BILAN BIR XIL qolip: `app/services/backup_job.py::run_backup_job`). Hozircha FAQAT
`analyze` — `apply` (2-bosqich) shu modul YONIGA alohida `apply_job.py` sifatida
qo'shiladi (bu yerga aralashtirilmaydi, bitta masala — bitta modul)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.models import MigrationJob
from app.services.fpbx import plan as plan_mod
from app.services.job_lock import JobLock

_MAX_ERROR_MESSAGE = 500


async def run_analyze_job(
    session_factory: async_sessionmaker, engine: AsyncEngine, lock: JobLock, job_id: str, tenant_id: str,
) -> None:
    """Qulf FAQAT shu vazifa davomida ushlab turiladi (m5a-contract.md §0: bir
    vaqtda bitta M5a/M4b ishi) — muvaffaqiyat/xato farqsiz, `finally`da bo'shatiladi."""
    try:
        async with session_factory() as session:
            await _run_analyze_job(session, job_id, tenant_id)
    finally:
        await lock.release()


async def _run_analyze_job(session: AsyncSession, job_id: str, tenant_id: str) -> None:
    job = await session.get(MigrationJob, job_id)
    if job is None:
        return
    try:
        analysis = await plan_mod.analyze(Path(job.bundle_path), session, tenant_id)
    except Exception as exc:  # noqa: BLE001 — to'plam/DB kutilmagan xatosi -> ish `failed`, stekka YO'Q
        job.status = "failed"
        job.error = {"code": "analyze_failed", "message": str(exc)[:_MAX_ERROR_MESSAGE]}
        job.finished_at = datetime.now(timezone.utc)
        await session.commit()
        return

    job.plan = {
        "items": [entry.public_dict() for entry in analysis.items],
        "ignored": analysis.ignored,
        "warnings": analysis.warnings,
    }
    job.status = "analyzed"
    job.step = None
    job.progress = 100
    job.finished_at = datetime.now(timezone.utc)
    await session.commit()
