"""M4b — `/backups` (zaxira nusxa va tiklash). replica/m4b-contract.md §2.

`GET /backups/jobs/{id}` — m4b-contract.md §0: texnik xizmat rejimida HAM ochiq,
avtorizatsiyasiz (`app/services/maintenance.py::_JOB_STATUS_RE`) — shu sabab bu
YAGONA endpoint `require_access` ISHLATMAYDI va tenant-skopsiz (job id'sining o'zi
"sir" — uni taxmin qilish amalda mumkin emas, UUID).

Fon ishlar (`backup_job.run_backup_job`/`restore_job.run_restore_job`) `pg_advisory_lock`
BILAN ishga tushiriladi (`job_lock.try_acquire_job_lock`) — qulf band bo'lsa 409
`job_running`; so'rov ICHIDA FAQAT tekshiruv+qator yaratish kutiladi, haqiqiy ish
`asyncio.create_task` bilan fonda (javob — 202 + `{job:{kind,id}}`, holat
`GET /backups/jobs/{id}`dan)."""
from __future__ import annotations

import asyncio
import hashlib
import socket
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_ami, get_session, require_access
from app.core.config import settings
from app.core.errors import ApiError
from app.core.ids import parse_uuid
from app.core.lookups import get_tenant_code, get_tenant_scoped_or_404, usernames_by_id
from app.db.models import Backup, BackupCopy, RestoreJob, SystemSettings, User
from app.db.session import SessionLocal
from app.db.session import engine as db_engine
from app.schemas_backup import (
    BackupCopyOut,
    BackupItem,
    BackupJobOut,
    BackupJobResponse,
    BackupJobState,
    BackupList,
    BackupManifestOut,
    BackupOut,
    CreateBackupPayload,
    InspectBackupPayload,
    InspectBackupResult,
    RestoreBackupPayload,
    RestoreJobList,
    RestoreJobOut,
    UserRef,
)
from app.services import backup_job
from app.services import restore_job as rj
from app.services.audit import record_audit
from app.services.backup_format import BackupCorruptError, BadPassphraseError
from app.services.backup_settings import s3_target_from_settings, sftp_target_from_settings
from app.services.backup_targets import BackupTargetError, delete_s3, delete_sftp, fetch_s3, fetch_sftp
from app.services.crypto import decrypt_secret
from app.services.job_lock import JobAlreadyRunningError, try_acquire_job_lock

router = APIRouter(prefix="/backups", tags=["backups"])

UPLOAD_CHUNK_SIZE = 1 << 20  # 1 MiB — audio.py'dagi `.read(max+1)` (butunini xotiraga
# yuklaydi) BU YERDA YARAMAYDI, 50 GB arxiv uchun chindan oqimli bo'lishi shart.


# ------------------------------------------------------------------ DTO quruvchilar
def _copy_out(copy: BackupCopy) -> BackupCopyOut:
    return BackupCopyOut(target=copy.target, status=copy.status, remote_path=copy.remote_path,
                          size_bytes=copy.size_bytes, error=copy.error, uploaded_at=copy.uploaded_at)


def _backup_out(backup: Backup, login: str | None) -> BackupOut:
    return BackupOut(
        id=str(backup.id), kind=backup.kind, status=backup.status, components=list(backup.components),
        step=backup.step, progress=backup.progress, file_name=backup.file_name, sha256=backup.sha256,
        manifest=BackupManifestOut(**backup.manifest) if backup.manifest else None,
        size_bytes=backup.size_bytes, copies=[_copy_out(c) for c in backup.copies],
        created_by=UserRef(id=str(backup.created_by), login=login) if backup.created_by and login else None,
        created_at=backup.started_at,
    )


async def _backups_out(session: AsyncSession, backups: list[Backup]) -> list[BackupOut]:
    logins = await usernames_by_id(session, {str(b.created_by) for b in backups if b.created_by})
    return [_backup_out(b, logins.get(str(b.created_by))) for b in backups]


async def _backup_item(session: AsyncSession, backup: Backup) -> BackupItem:
    return BackupItem(item=(await _backups_out(session, [backup]))[0])


async def _resolve_passphrase(session: AsyncSession, tenant_id: str, payload_passphrase: str | None) -> str:
    """Admin aniq parol kiritgan bo'lsa — shu ishlatiladi (masalan `uploaded` zaxira
    boshqa server kaliti bilan yaratilgan bo'lishi mumkin); aks holda joriy tizim
    zaxira paroli (`system_settings.backup.passphrase_enc`) deshifrlanadi."""
    if payload_passphrase:
        return payload_passphrase
    row = await session.get(SystemSettings, tenant_id)
    cfg = (row.backup if row else None) or {}
    if not cfg.get("passphrase_enc"):
        raise ApiError(422, "passphrase_required", "Zaxira paroli kerak")
    return await decrypt_secret(session, cfg["passphrase_enc"])


# ------------------------------------------------------------------ ro'yxat/yaratish
@router.get("", response_model=BackupList)
async def list_backups(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> BackupList:
    rows = (await session.execute(
        select(Backup).where(Backup.tenant_id == user.tenant_id)
        .options(selectinload(Backup.copies)).order_by(Backup.started_at.desc())
    )).scalars().all()
    return BackupList(items=await _backups_out(session, rows))


@router.post("", status_code=202, response_model=BackupJobResponse)
async def create_backup(
    payload: CreateBackupPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> BackupJobResponse:
    tenant_id = str(user.tenant_id)
    try:
        lock = await try_acquire_job_lock(db_engine)
    except JobAlreadyRunningError as exc:
        raise ApiError(409, "job_running", "Boshqa zaxira/tiklash ishi ketayotgan edi") from exc
    try:
        backup = await backup_job.create_backup_record(
            session, tenant_id=tenant_id, kind="manual", components=list(payload.components),
            created_by=str(user.id),
        )
    except backup_job.PassphraseRequiredError as exc:
        await lock.release()
        raise ApiError(409, "passphrase_required", "Zaxira paroli o'rnatilmagan") from exc
    except ValueError as exc:
        await lock.release()
        raise ApiError(422, "bad_value", str(exc)) from exc
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="backup.create",
                        entity="backup", entity_id=backup.id, diff={"components": list(payload.components)})
    await session.commit()
    asyncio.create_task(backup_job.run_backup_job(SessionLocal, db_engine, lock, str(backup.id), tenant_id))
    return BackupJobResponse(job=BackupJobOut(kind="backup", id=str(backup.id)))


@router.get("/restores", response_model=RestoreJobList)
async def list_restores(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> RestoreJobList:
    rows = (await session.execute(
        select(RestoreJob).where(RestoreJob.tenant_id == user.tenant_id).order_by(RestoreJob.started_at.desc())
    )).scalars().all()
    logins = await usernames_by_id(session, {str(r.started_by) for r in rows if r.started_by})
    return RestoreJobList(items=[
        RestoreJobOut(
            id=str(r.id), backup_id=str(r.backup_id) if r.backup_id else None, source=r.source,
            status=r.status, step=r.step, progress=r.progress, error=r.error, force=r.force,
            pre_restore_backup_id=str(r.pre_restore_backup_id) if r.pre_restore_backup_id else None,
            started_by=(UserRef(id=str(r.started_by), login=logins[str(r.started_by)])
                        if r.started_by and str(r.started_by) in logins else None),
            started_at=r.started_at, finished_at=r.finished_at,
        )
        for r in rows
    ])


# ------------------------------------------------------------------ ish holati (sirsiz, ochiq)
@router.get("/jobs/{job_id}", response_model=BackupJobState)
async def get_backup_job_state(job_id: str, session: AsyncSession = Depends(get_session)) -> BackupJobState:
    valid_id = parse_uuid(job_id, not_found_message="Ish topilmadi")
    backup = await session.get(Backup, valid_id)
    if backup is not None:
        status = "ok" if backup.status in ("ok", "partial") else backup.status
        return BackupJobState(kind="backup", status=status, step=backup.step, progress=backup.progress,
                               error=backup.error)
    job = await session.get(RestoreJob, valid_id)
    if job is not None:
        return BackupJobState(kind="restore", status=job.status, step=job.step, progress=job.progress,
                               error=job.error)
    raise ApiError(404, "not_found", "Ish topilmadi")


# ------------------------------------------------------------------ yuklash (streaming, disaster recovery)
@router.post("/upload", response_model=BackupItem)
async def upload_backup(
    file: UploadFile = File(...), session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> BackupItem:
    """Butunini xotiraga yuklamasdan diskka yozadi (nginx `client_max_body_size 50g`/
    `proxy_request_buffering off` allaqachon sozlangan). `kind="uploaded"`,
    `components=[]`/`manifest=None` — `POST /{id}/inspect` to'ldiradi."""
    tenant_id = str(user.tenant_id)
    backups_dir = Path(settings.backups_dir)
    backups_dir.mkdir(parents=True, exist_ok=True)
    file_name = backup_job.new_backup_file_name(
        socket.gethostname(), datetime.now(timezone.utc), uuid.uuid4().hex[:8])
    dest = backups_dir / file_name
    digest = hashlib.sha256()
    size = 0
    with dest.open("wb") as out:
        while True:
            chunk = await file.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
            out.write(chunk)

    now = datetime.now(timezone.utc)
    backup = Backup(tenant_id=tenant_id, kind="uploaded", status="ok", components=[], file_name=file_name,
                     sha256=digest.hexdigest(), size_bytes=size, created_by=user.id, finished_at=now)
    session.add(backup)
    await session.flush()
    session.add(BackupCopy(backup_id=backup.id, target="local", status="ok", remote_path=file_name,
                            size_bytes=size, uploaded_at=now))
    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="backup.upload",
                        entity="backup", entity_id=backup.id, diff={"file_name": file_name, "size_bytes": size})
    await session.commit()
    await session.refresh(backup, attribute_names=["copies"])
    return await _backup_item(session, backup)


# ------------------------------------------------------------------ bitta zaxira
@router.get("/{backup_id}", response_model=BackupItem)
async def get_backup(
    backup_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> BackupItem:
    backup = await get_tenant_scoped_or_404(
        session, Backup, str(user.tenant_id), backup_id, not_found_message="Zaxira topilmadi",
        options=(selectinload(Backup.copies),))
    return await _backup_item(session, backup)


async def _delete_one_copy(session: AsyncSession, backups_dir: Path, backup_cfg: dict, copy: BackupCopy) -> None:
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


@router.delete("/{backup_id}", status_code=204, response_model=None)
async def delete_backup(
    backup_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> Response:
    """Barcha nusxalar (lokal + masofaviy) o'chiriladi — `pre_restore` ham eng so'nggi
    bo'lsa ham o'chirilishi mumkin (m4b-contract.md §2)."""
    tenant_id = str(user.tenant_id)
    backup = await get_tenant_scoped_or_404(
        session, Backup, tenant_id, backup_id, not_found_message="Zaxira topilmadi",
        options=(selectinload(Backup.copies),))
    backups_dir = Path(settings.backups_dir)
    backup_cfg = await _backup_cfg_of(session, tenant_id)
    for copy in backup.copies:
        await _delete_one_copy(session, backups_dir, backup_cfg, copy)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="backup.delete",
                        entity="backup", entity_id=backup.id, diff={"file_name": backup.file_name})
    await session.delete(backup)
    await session.commit()
    return Response(status_code=204)


@router.get("/{backup_id}/download")
async def download_backup(
    backup_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> FileResponse:
    backup = await get_tenant_scoped_or_404(
        session, Backup, str(user.tenant_id), backup_id, not_found_message="Zaxira topilmadi")
    if not backup.file_name:
        raise ApiError(409, "no_local_copy", "Lokal nusxa yo'q")
    path = Path(settings.backups_dir) / backup.file_name
    if not path.exists():
        raise ApiError(409, "no_local_copy", "Lokal nusxa yo'q")
    return FileResponse(path, media_type="application/octet-stream", filename=backup.file_name)


def _find_remote_copy(backup: Backup) -> BackupCopy | None:
    return next((c for c in backup.copies if c.target in ("s3", "sftp") and c.status == "ok"
                 and c.remote_path), None)


async def _backup_cfg_of(session: AsyncSession, tenant_id: str) -> dict:
    settings_row = await session.get(SystemSettings, tenant_id)
    return (settings_row.backup if settings_row else None) or {}


async def _fetch_remote_to_local(session: AsyncSession, backup_cfg: dict, remote: BackupCopy,
                                  local_path: Path) -> None:
    try:
        if remote.target == "s3":
            await fetch_s3(await s3_target_from_settings(session, backup_cfg), remote.remote_path, local_path)
        else:
            await fetch_sftp(await sftp_target_from_settings(session, backup_cfg), remote.remote_path, local_path)
    except BackupTargetError as exc:
        raise ApiError(502, "fetch_failed", str(exc)[:500]) from exc


def _upsert_local_copy(session: AsyncSession, backup: Backup, local_path: Path, now: datetime) -> None:
    local_copy = next((c for c in backup.copies if c.target == "local"), None)
    if local_copy is None:
        local_copy = BackupCopy(backup_id=backup.id, target="local")
        session.add(local_copy)
    local_copy.status, local_copy.error = "ok", None
    local_copy.remote_path = backup.file_name
    local_copy.size_bytes = local_path.stat().st_size
    local_copy.uploaded_at = now


@router.post("/{backup_id}/fetch", response_model=BackupItem)
async def fetch_backup_copy(
    backup_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> BackupItem:
    """Lokal nusxa retentsiya bilan o'chirilgan bo'lsa — masofaviy nishondan qayta
    tortib oladi (allaqachon lokalda bo'lsa — hech narsa qilmay qaytaradi, idempotent)."""
    tenant_id = str(user.tenant_id)
    backup = await get_tenant_scoped_or_404(
        session, Backup, tenant_id, backup_id, not_found_message="Zaxira topilmadi",
        options=(selectinload(Backup.copies),))
    if not backup.file_name:
        raise ApiError(409, "no_local_copy", "Zaxira fayli yo'q")
    backups_dir = Path(settings.backups_dir)
    local_path = backups_dir / backup.file_name
    if local_path.exists():
        return await _backup_item(session, backup)

    remote = _find_remote_copy(backup)
    if remote is None:
        raise ApiError(409, "no_remote_copy", "Masofaviy nusxa topilmadi")
    backup_cfg = await _backup_cfg_of(session, tenant_id)
    backups_dir.mkdir(parents=True, exist_ok=True)
    await _fetch_remote_to_local(session, backup_cfg, remote, local_path)

    _upsert_local_copy(session, backup, local_path, datetime.now(timezone.utc))
    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="backup.fetch",
                        entity="backup", entity_id=backup.id, diff={"from": remote.target})
    await session.commit()
    await session.refresh(backup, attribute_names=["copies"])
    return await _backup_item(session, backup)


@router.post("/{backup_id}/inspect", response_model=InspectBackupResult)
async def inspect_backup(
    backup_id: str, payload: InspectBackupPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> InspectBackupResult:
    tenant_id = str(user.tenant_id)
    backup = await get_tenant_scoped_or_404(
        session, Backup, tenant_id, backup_id, not_found_message="Zaxira topilmadi")
    if not backup.file_name:
        raise ApiError(409, "no_local_copy", "Zaxira fayli lokalda yo'q")
    path = Path(settings.backups_dir) / backup.file_name
    passphrase = await _resolve_passphrase(session, tenant_id, payload.passphrase)
    try:
        result = await rj.inspect(session, path, passphrase)
    except BadPassphraseError as exc:
        raise ApiError(422, "bad_passphrase", "Parol noto'g'ri") from exc
    except BackupCorruptError as exc:
        raise ApiError(422, "backup_corrupt", str(exc)[:500]) from exc

    manifest = result["manifest"]
    if backup.kind == "uploaded" and backup.manifest is None:
        # Hali tekshirilmagan yuklangan zaxira — model docstringi: "inspect to'ldiradi".
        backup.manifest = manifest.to_dict()
        backup.components = list(manifest.components)
        await session.commit()
    return InspectBackupResult(manifest=BackupManifestOut(**manifest.to_dict()), checks=result["checks"],
                                compatible=result["compatible"], warnings=result["warnings"])


@router.post("/{backup_id}/restore", status_code=202, response_model=BackupJobResponse)
async def restore_backup(
    backup_id: str, payload: RestoreBackupPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> BackupJobResponse:
    tenant_id = str(user.tenant_id)
    backup = await get_tenant_scoped_or_404(
        session, Backup, tenant_id, backup_id, not_found_message="Zaxira topilmadi")
    if not backup.file_name:
        raise ApiError(409, "no_local_copy", "Zaxira fayli lokalda yo'q")
    archive_path = Path(settings.backups_dir) / backup.file_name
    passphrase = await _resolve_passphrase(session, tenant_id, payload.passphrase)
    try:
        job, lock = await rj.precheck_and_create_job(
            session, db_engine, backup_id=backup.id, source=rj.restore_source(backup.kind),
            archive_path=archive_path, passphrase=passphrase,
            force=payload.force, tenant_id=tenant_id, user_id=str(user.id), ami=ami,
        )
    except rj.RestoreNewerError as exc:
        raise ApiError(422, "backup_newer", str(exc)) from exc
    except rj.ActiveCallsError as exc:
        raise ApiError(409, "active_calls", "Faol qo'ng'iroqlar mavjud", details={"count": exc.count}) from exc
    except JobAlreadyRunningError as exc:
        raise ApiError(409, "job_running", "Boshqa zaxira/tiklash ishi ketayotgan edi") from exc
    except BadPassphraseError as exc:
        raise ApiError(422, "bad_passphrase", "Parol noto'g'ri") from exc
    except BackupCorruptError as exc:
        raise ApiError(422, "backup_corrupt", str(exc)[:500]) from exc

    tenant_code = await get_tenant_code(session, tenant_id)
    await session.commit()
    asyncio.create_task(rj.run_restore_job(
        SessionLocal, db_engine, lock, str(job.id), tenant_id=tenant_id, tenant_code=tenant_code,
        ami=ami, archive_path=archive_path, passphrase=passphrase,
    ))
    return BackupJobResponse(job=BackupJobOut(kind="restore", id=str(job.id)))
