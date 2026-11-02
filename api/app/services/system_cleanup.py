"""Disk tozalash — `POST /system/cleanup[/preview]`. Uchta toifa: yozuvlar
(`recordings.py` qayta ishlatiladi), zaxiralar (`backup_retention.py` +
`backup_delete.py` qayta ishlatiladi), ko'chirish bog'lamlari (`migration.py`dagi
`delete_job` bilan BIR XIL "faol ishni tegma" qoidasi). Hech qanday faylga
tegmasdan (`preview`) ham, haqiqiy o'chirib (`execute`) ham BIR XIL hisoblash
qoidasidan foydalanadi — ikki marta yozilmasin (ub-mode dryer)."""
from __future__ import annotations

import asyncio
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import ApiError
from app.db.models import Backup, MigrationJob, RestoreJob
from app.schemas import CleanupCategoryOut, CleanupIn, CleanupResultOut
from app.services import backup_delete, recordings
from app.services.backup_retention import RetentionItem, ids_to_delete
from app.services.system_status import scan_dir_sync

_EMPTY: dict = {"files": 0, "bytes": 0}
_ACTIVE_MIGRATION_STATUSES = ("analyzing", "applying")


def validate_cleanup_payload(payload: CleanupIn) -> None:
    """Uchtasidan kamida bittasi tanlanishi SHART (hammasi bo'sh — tozalash
    yo'nalishi yo'q, 422)."""
    if payload.recordings_older_than_days is None and payload.backups_keep_last is None and not payload.migrations:
        raise ApiError(422, "empty_cleanup", "Kamida bitta tozalash parametri tanlanishi kerak",
                        field="recordings_older_than_days")


# --------------------------------------------------------------- yozuvlar
async def _recordings_preview(session: AsyncSession, tenant_id: str, days: int, now: datetime) -> dict:
    rows = await recordings.purge_candidates(session, tenant_id, days, now)
    return {"files": len(rows), "bytes": sum(r.size_bytes or 0 for r in rows)}


async def _recordings_cleanup(
    session: AsyncSession, tenant_id: str, days: int, now: datetime, errors: list[str],
) -> dict:
    """`purge_tenant` bir chaqiruvda ko'pi bilan `PURGE_BATCH_LIMIT` qatorni
    o'chiradi — shu sabab to'liq bo'lmagan qaytim (5000'ga teng) bo'lsa qaytadan
    chaqiriladi. Bayt hisobi — o'chirishdan OLDIN bitta so'rov bilan olingan
    yo'l→hajm xaritasidan (xatolangan yo'llar ayiriladi)."""
    candidates = await recordings.purge_candidates(session, tenant_id, days, now)
    if not candidates:
        return dict(_EMPTY)
    bytes_by_path = {r.path: r.size_bytes or 0 for r in candidates}
    total_files = 0
    while True:
        count, batch_errors = await recordings.purge_tenant(session, tenant_id, days, now)
        errors.extend(batch_errors)
        total_files += count
        # count == 0 — butun to'plam xato (masalan, faqat o'qish disk): qayta urinish cheksiz sikl bo'lardi
        if count == 0 or count + len(batch_errors) < recordings.PURGE_BATCH_LIMIT:
            break
    failed_paths = {e.split(":", 1)[0] for e in errors}
    total_bytes = sum(b for path, b in bytes_by_path.items() if path not in failed_paths)
    return {"files": total_files, "bytes": total_bytes}


# --------------------------------------------------------------- zaxiralar
async def _eligible_backups(session: AsyncSession, tenant_id: str) -> list[Backup]:
    """Ketayotgan zaxira (`status == "running"`) VA hozir biror tiklash ishi
    o'qiyotgan zaxira (`restore_jobs.status == "running"`, `backup_id` yoki
    `pre_restore_backup_id`) — tozalash TEGMAYDI."""
    busy_ids = select(RestoreJob.backup_id).where(RestoreJob.status == "running").union(
        select(RestoreJob.pre_restore_backup_id).where(RestoreJob.status == "running"))
    rows = (await session.execute(
        select(Backup).where(
            Backup.tenant_id == tenant_id, Backup.status != "running", Backup.id.notin_(busy_ids),
        ).options(selectinload(Backup.copies))
    )).scalars().all()
    return list(rows)


def _backups_to_delete(backups: list[Backup], keep_last: int) -> list[Backup]:
    items = [RetentionItem(id=str(b.id), created_at=b.started_at) for b in backups]
    doomed_ids = set(ids_to_delete(items, keep_last))
    return [b for b in backups if str(b.id) in doomed_ids]


async def _backups_preview(session: AsyncSession, tenant_id: str, keep_last: int) -> dict:
    doomed = _backups_to_delete(await _eligible_backups(session, tenant_id), keep_last)
    return {"files": len(doomed), "bytes": sum(b.size_bytes or 0 for b in doomed)}


async def _backups_cleanup(
    session: AsyncSession, tenant_id: str, backups_dir: Path, keep_last: int, errors: list[str],
) -> dict:
    """Har bir eskirgan zaxira — BARCHA nusxalari (lokal+masofaviy) VA o'zi
    (DB qatori) o'chiriladi, xuddi foydalanuvchi `DELETE /backups/{id}`ni qo'lda
    bosgandagidek (`backup_delete` — ub-mode dryer, ikki joyda bir xil mantiq yo'q)."""
    del errors  # bitta nishonni o'chira olmaslik `backup_delete.delete_one_copy` ichida jim o'tkaziladi
    doomed = _backups_to_delete(await _eligible_backups(session, tenant_id), keep_last)
    backup_cfg = await backup_delete.backup_cfg_of(session, tenant_id)
    total_bytes = 0
    for backup in doomed:
        for copy in backup.copies:
            await backup_delete.delete_one_copy(session, backups_dir, backup_cfg, copy)
        total_bytes += backup.size_bytes or 0
        await session.delete(backup)
    return {"files": len(doomed), "bytes": total_bytes}


# --------------------------------------------------------------- ko'chirish bog'lamlari
def _migration_job_dir(job_id: str) -> Path:
    return Path(settings.migrations_dir) / str(job_id)


async def _eligible_migration_jobs(session: AsyncSession, tenant_id: str) -> list[MigrationJob]:
    """Faol ish (`analyzing`/`applying`) — `migration.py:delete_job` bilan BIR XIL
    qoida, tozalash ulardan uzoq turadi."""
    rows = (await session.execute(select(MigrationJob).where(
        MigrationJob.tenant_id == tenant_id, MigrationJob.status.notin_(_ACTIVE_MIGRATION_STATUSES),
    ))).scalars().all()
    return list(rows)


async def _migrations_preview(session: AsyncSession, tenant_id: str) -> dict:
    jobs = await _eligible_migration_jobs(session, tenant_id)
    total_bytes = total_files = 0
    for job in jobs:
        b, f = await _scan_job_dir(job.id)
        total_bytes += b
        total_files += f
    return {"files": total_files, "bytes": total_bytes}


async def _scan_job_dir(job_id: str) -> tuple[int, int]:
    return await asyncio.to_thread(scan_dir_sync, str(_migration_job_dir(job_id)))


def _within_migrations_dir(job_dir: Path) -> bool:
    """Yo'l almashtirish himoyasi — `job.id` doim bazada yaratilgan UUID (xavf
    yo'q), lekin ikkinchi himoya qatlami arzon va aniq (ub-mode: xavfsizlik)."""
    base = Path(settings.migrations_dir).resolve()
    try:
        job_dir.resolve().relative_to(base)
    except ValueError:
        return False
    return True


async def _migrations_cleanup(session: AsyncSession, tenant_id: str, errors: list[str]) -> dict:
    jobs = await _eligible_migration_jobs(session, tenant_id)
    total_bytes = total_files = 0
    for job in jobs:
        job_dir = _migration_job_dir(job.id)
        if not _within_migrations_dir(job_dir):
            errors.append(f"{job.id}: ko'chirish papkasi tashqarida, o'tkazib yuborildi")
            continue
        b, f = await asyncio.to_thread(scan_dir_sync, str(job_dir))
        await asyncio.to_thread(shutil.rmtree, job_dir, True)
        total_bytes += b
        total_files += f
        await session.delete(job)
    return {"files": total_files, "bytes": total_bytes}


# --------------------------------------------------------------- orkestrator
async def preview(session: AsyncSession, tenant_id: str, payload: CleanupIn, now: datetime) -> CleanupResultOut:
    recordings_r = dict(_EMPTY)
    if payload.recordings_older_than_days is not None:
        recordings_r = await _recordings_preview(session, tenant_id, payload.recordings_older_than_days, now)
    backups_r = dict(_EMPTY)
    if payload.backups_keep_last is not None:
        backups_r = await _backups_preview(session, tenant_id, payload.backups_keep_last)
    migrations_r = dict(_EMPTY)
    if payload.migrations:
        migrations_r = await _migrations_preview(session, tenant_id)
    total = recordings_r["bytes"] + backups_r["bytes"] + migrations_r["bytes"]
    return CleanupResultOut(
        recordings=CleanupCategoryOut(**recordings_r), backups=CleanupCategoryOut(**backups_r),
        migrations=CleanupCategoryOut(**migrations_r), total_bytes=total, errors=[],
    )


async def execute(
    session: AsyncSession, tenant_id: str, backups_dir: Path, payload: CleanupIn, now: datetime,
) -> CleanupResultOut:
    errors: list[str] = []
    recordings_r = dict(_EMPTY)
    if payload.recordings_older_than_days is not None:
        recordings_r = await _recordings_cleanup(session, tenant_id, payload.recordings_older_than_days, now, errors)
    backups_r = dict(_EMPTY)
    if payload.backups_keep_last is not None:
        backups_r = await _backups_cleanup(session, tenant_id, backups_dir, payload.backups_keep_last, errors)
    migrations_r = dict(_EMPTY)
    if payload.migrations:
        migrations_r = await _migrations_cleanup(session, tenant_id, errors)
    total = recordings_r["bytes"] + backups_r["bytes"] + migrations_r["bytes"]
    return CleanupResultOut(
        recordings=CleanupCategoryOut(**recordings_r), backups=CleanupCategoryOut(**backups_r),
        migrations=CleanupCategoryOut(**migrations_r), total_bytes=total, errors=errors,
    )
