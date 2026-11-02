"""`system_settings.backup` JSONB <-> `S3Target`/`SftpTarget` (m4b-contract.md §1).

Ustun HAR DOIM to'liq shaklda (0021 migratsiya `server_default`/`not null`) — bu modul
hech qanday standart qiymat TAKRORLAMAYDI (dryer), faqat ustundagi qiymatlarni
o'qiydi/sirlarni deshifrlaydi (`decrypt_secret` — DB chaqiruvi, shu sabab `AsyncSession` kerak)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.backup_targets import S3Target, SftpTarget
from app.services.crypto import decrypt_secret


async def s3_target_from_settings(session: AsyncSession, backup_raw: dict) -> S3Target:
    cfg = backup_raw["targets"]["s3"]
    secret = await decrypt_secret(session, cfg["secret_key_enc"]) if cfg.get("secret_key_enc") else ""
    return S3Target(
        endpoint=cfg["endpoint"], region=cfg["region"], bucket=cfg["bucket"], prefix=cfg["prefix"],
        access_key=cfg["access_key"], secret_key=secret, path_style=cfg["path_style"],
        keep_last=cfg["keep_last"],
    )


async def sftp_target_from_settings(session: AsyncSession, backup_raw: dict) -> SftpTarget:
    cfg = backup_raw["targets"]["sftp"]
    password = await decrypt_secret(session, cfg["password_enc"]) if cfg.get("password_enc") else None
    key = await decrypt_secret(session, cfg["key_enc"]) if cfg.get("key_enc") else None
    return SftpTarget(
        host=cfg["host"], port=cfg["port"], user=cfg["user"], folder=cfg["folder"],
        password=password, key=key, host_key_fp=cfg.get("host_key_fp"), keep_last=cfg["keep_last"],
    )
