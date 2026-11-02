"""Zaxira nusxa fayllarini o'chirish — `app/api/v1/backups.py` DELETE bilan
BIR XIL qoida (ub-mode DRY): `POST /system/cleanup` (disk tozalash,
`backups_keep_last`) ENDI shu YERDAN chaqiradi, aks holda ikki joyda bir xil
mantiq ikki marta yozilgan bo'lardi."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BackupCopy, SystemSettings
from app.services.backup_settings import s3_target_from_settings, sftp_target_from_settings
from app.services.backup_targets import BackupTargetError, delete_s3, delete_sftp


async def backup_cfg_of(session: AsyncSession, tenant_id: str) -> dict:
    settings_row = await session.get(SystemSettings, tenant_id)
    return (settings_row.backup if settings_row else None) or {}


async def delete_one_copy(session: AsyncSession, backups_dir: Path, backup_cfg: dict, copy: BackupCopy) -> None:
    """Bitta nishon (`local`/`s3`/`sftp`) nusxasini o'chiradi — nishonga ulanib bo'lmasa
    (`BackupTargetError`) jim o'tkazib yuboradi (boshqa nishonlar/qatorlar to'xtamasin)."""
    if copy.status != "ok" or not copy.remote_path:
        return
    try:
        if copy.target == "local":
            (backups_dir / copy.remote_path).unlink(missing_ok=True)
        elif copy.target == "s3":
            await delete_s3(await s3_target_from_settings(session, backup_cfg), copy.remote_path)
        elif copy.target == "sftp":
            await delete_sftp(await sftp_target_from_settings(session, backup_cfg), copy.remote_path)
    except BackupTargetError:  # noqa: BLE001 — bitta nishonni o'chira olmaslik qolganlarini to'xtatmasin
        return
