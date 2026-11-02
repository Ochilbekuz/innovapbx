"""M4b — `/settings/backup` (zaxira sozlamalari). replica/m4b-contract.md §2.

Sirlar javobda HECH QACHON ochiq ko'rinmaydi — `has_passphrase`/`has_secret_key`/
`has_password`/`has_key` bayroqlari, `UpdateBackupSettingsPayload`da esa YANGI
qiymat berilmasa (`None`) eski shifrlangan qiymat SAQLANIB QOLADI (faqat berilgan
sirlar qayta shifrlanadi, bo'shlardan tozalanmaydi)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_access
from app.api.v1.settings import get_settings_row
from app.core.errors import ApiError
from app.core.optimistic import check_not_stale
from app.db.models import SystemSettings, User
from app.schemas_backup import (
    BackupLocalTargetOut,
    BackupS3TargetOut,
    BackupScheduleOut,
    BackupSettingsOut,
    BackupSftpTargetOut,
    BackupTargetsOut,
    TestBackupTargetResult,
    TrustSftpHostKeyPayload,
    UpdateBackupPassphrasePayload,
    UpdateBackupSettingsPayload,
)
from app.services.audit import record_audit
from app.services.backup_settings import s3_target_from_settings, sftp_target_from_settings
from app.services.backup_targets import test_s3, test_sftp
from app.services.crypto import decrypt_secret, encrypt_secret

router = APIRouter(prefix="/settings/backup", tags=["settings"])


def _settings_out(row: SystemSettings) -> BackupSettingsOut:
    cfg = row.backup
    local, s3, sftp = cfg["targets"]["local"], cfg["targets"]["s3"], cfg["targets"]["sftp"]
    return BackupSettingsOut(
        has_passphrase=bool(cfg.get("passphrase_enc")),
        schedule=BackupScheduleOut(**cfg["schedule"]),
        targets=BackupTargetsOut(
            local=BackupLocalTargetOut(keep_last=local["keep_last"]),
            s3=BackupS3TargetOut(
                enabled=s3["enabled"], endpoint=s3["endpoint"], region=s3["region"], bucket=s3["bucket"],
                prefix=s3["prefix"], access_key=s3["access_key"], has_secret_key=bool(s3.get("secret_key_enc")),
                path_style=s3["path_style"], keep_last=s3["keep_last"],
            ),
            sftp=BackupSftpTargetOut(
                enabled=sftp["enabled"], host=sftp["host"], port=sftp["port"], user=sftp["user"],
                has_password=bool(sftp.get("password_enc")), has_key=bool(sftp.get("key_enc")),
                folder=sftp["folder"], host_key_fp=sftp.get("host_key_fp"), keep_last=sftp["keep_last"],
            ),
        ),
        updated_at=row.updated_at,
    )


async def _merged_s3(session: AsyncSession, current: dict, payload) -> dict:
    secret_enc = current.get("secret_key_enc")
    if payload.secret_key:
        secret_enc = await encrypt_secret(session, payload.secret_key)
    return {"enabled": payload.enabled, "endpoint": payload.endpoint, "region": payload.region,
            "bucket": payload.bucket, "prefix": payload.prefix, "access_key": payload.access_key,
            "secret_key_enc": secret_enc, "path_style": payload.path_style, "keep_last": payload.keep_last}


async def _merged_sftp(session: AsyncSession, current: dict, payload) -> dict:
    password_enc = current.get("password_enc")
    if payload.password:
        password_enc = await encrypt_secret(session, payload.password)
    key_enc = current.get("key_enc")
    if payload.key:
        key_enc = await encrypt_secret(session, payload.key)
    # Host o'zgarsa — eski fingerprint YANGI xostga tegishli emas, tozalanadi
    # (aks holda keyingi test() yangi xostni eski bilan solishtirib xato
    # `host_key_mismatch` berardi yoki yomonroq — yolg'on ishonch).
    host_key_fp = current.get("host_key_fp") if payload.host == current.get("host") else None
    return {"enabled": payload.enabled, "host": payload.host, "port": payload.port, "user": payload.user,
            "password_enc": password_enc, "key_enc": key_enc, "folder": payload.folder,
            "host_key_fp": host_key_fp, "keep_last": payload.keep_last}


@router.get("", response_model=BackupSettingsOut)
async def get_backup_settings(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> BackupSettingsOut:
    row = await get_settings_row(session, str(user.tenant_id))
    return _settings_out(row)


@router.put("", response_model=BackupSettingsOut)
async def update_backup_settings(
    payload: UpdateBackupSettingsPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> BackupSettingsOut:
    tenant_id = str(user.tenant_id)
    row = await get_settings_row(session, tenant_id)
    check_not_stale(row.updated_at, payload.updated_at)
    cfg = row.backup
    diff: dict = {}

    if payload.schedule is not None:
        new_schedule = payload.schedule.model_dump()
        cfg = {**cfg, "schedule": new_schedule}
        diff["schedule"] = new_schedule
    if payload.targets is not None:
        new_targets = dict(cfg["targets"])
        if payload.targets.local is not None:
            new_targets["local"] = {"keep_last": payload.targets.local.keep_last}
            diff["targets.local"] = new_targets["local"]
        if payload.targets.s3 is not None:
            new_targets["s3"] = await _merged_s3(session, cfg["targets"]["s3"], payload.targets.s3)
            diff["targets.s3"] = {k: v for k, v in new_targets["s3"].items() if k != "secret_key_enc"}
        if payload.targets.sftp is not None:
            new_targets["sftp"] = await _merged_sftp(session, cfg["targets"]["sftp"], payload.targets.sftp)
            diff["targets.sftp"] = {k: v for k, v in new_targets["sftp"].items()
                                     if k not in ("password_enc", "key_enc")}
        cfg = {**cfg, "targets": new_targets}

    row.backup = cfg
    await session.flush()
    await session.refresh(row)  # updated_at — DB triggeri yangilaydi
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="backup.settings",
                        entity="backup_settings", entity_id=tenant_id, diff=diff)
    await session.commit()
    return _settings_out(row)


@router.put("/passphrase")
async def update_backup_passphrase(
    payload: UpdateBackupPassphrasePayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> dict:
    tenant_id = str(user.tenant_id)
    row = await get_settings_row(session, tenant_id)
    cfg = row.backup
    if cfg.get("passphrase_enc"):
        if not payload.current:
            raise ApiError(422, "current_required", "Joriy parol kerak", field="current")
        current_plain = await decrypt_secret(session, cfg["passphrase_enc"])
        if payload.current != current_plain:
            raise ApiError(422, "bad_passphrase", "Joriy parol noto'g'ri", field="current")
    new_enc = await encrypt_secret(session, payload.passphrase)
    row.backup = {**cfg, "passphrase_enc": new_enc}
    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="backup.passphrase",
                        entity="backup_settings", entity_id=tenant_id, diff={"passphrase_enc": "***"})
    await session.commit()
    return {"ok": True}


@router.post("/targets/{target}/test", response_model=TestBackupTargetResult)
async def test_backup_target(
    target: Literal["s3", "sftp"], session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> TestBackupTargetResult:
    """Joriy SAQLANGAN nishon sozlamasini sinaydi (admin avval `PUT`da saqlashi
    kerak — frontend body yubormaydi, faqat yo'lda `target`, `web/src/api/real.ts`)."""
    row = await get_settings_row(session, str(user.tenant_id))
    cfg = row.backup
    if target == "s3":
        ok, error = await test_s3(await s3_target_from_settings(session, cfg))
        return TestBackupTargetResult(ok=ok, error=error)
    ok, error, fingerprint = await test_sftp(await sftp_target_from_settings(session, cfg))
    return TestBackupTargetResult(ok=ok, error=error, host_key_fp=fingerprint)


@router.post("/targets/sftp/trust")
async def trust_sftp_host_key(
    payload: TrustSftpHostKeyPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> dict:
    tenant_id = str(user.tenant_id)
    row = await get_settings_row(session, tenant_id)
    cfg = row.backup
    new_sftp = {**cfg["targets"]["sftp"], "host_key_fp": payload.host_key_fp}
    row.backup = {**cfg, "targets": {**cfg["targets"], "sftp": new_sftp}}
    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="backup.sftp_trust",
                        entity="backup_settings", entity_id=tenant_id, diff={"host_key_fp": payload.host_key_fp})
    await session.commit()
    return {"ok": True}
