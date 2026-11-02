"""Zaxira yaratish — fon vazifa orkestratsiyasi (m4b-contract.md §0/§1).

`write_archive()` — DBsiz/tarmoqsiz, to'liq sinaladigan yurak (manifest + konteyner
freymlari + INNOVABK1). `dump_database()`/`stage_file_component()` — fayl tizimi/subprocess
bilan ishlaydigan ingichka qatlam. `run_backup_job()` — hammasini bog'laydigan async
orkestrator (haqiqiy Postgres/tarmoq kerak, `tests/test_backup_job_live.py` `live` belgisi).
"""
from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import tarfile
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.models import Backup, BackupCopy, SystemSettings
from app.db.raw_sql import libpq_env
from app.services import backup_parts
from app.services.alerts import alert_text, raise_alert, tenant_language
from app.services.backup_container import iter_bytes_frame, iter_file_frame
from app.services.backup_dbkey import encrypt_db_key
from app.services.backup_format import ArchiveWriter
from app.services.backup_manifest import Manifest, PartInfo, current_alembic_revision, db_key_fingerprint
from app.services.backup_retention import RetentionItem, ids_to_delete
from app.services.backup_settings import s3_target_from_settings, sftp_target_from_settings
from app.services.backup_targets import (
    BackupTargetError, delete_s3, delete_sftp, is_own_backup_file, list_own_s3, list_own_sftp,
    upload_s3, upload_sftp,
)
from app.services.crypto import decrypt_secret
from app.services.job_lock import JobLock

log = logging.getLogger("innova.backup_job")

PRODUCT_VERSION = "0.1.0"


class PassphraseRequiredError(Exception):
    """Zaxira paroli o'rnatilmagan (router — 409 `passphrase_required`)."""


def new_backup_file_name(host: str, now: datetime, id8: str) -> str:
    return f"innova-{host}-{now:%Y%m%d-%H%M%S}-{id8}.ibk"


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stage_file_component(src_dir: Path, dest_tar: Path) -> None:
    """`src_dir`ni (mavjud bo'lmasa — bo'sh tar) `dest_tar`ga joylaydi.

    `dereference=True` SHART: `moh.py`/`voicemail.py` MOH sinfi/ovozli pochta
    salomlashuvini ABSOLYUT yo'lli simvolik havola bilan ulaydi (`sounds_dir`
    ichida, hatto boshqa hajmga — voicemail spool — ishora qilishi mumkin).
    Havola sifatida saqlansa, tiklashda Python 3.12 `tarfile` xavfsiz `data`
    filtri HAR DOIM rad etadi (`AbsoluteLinkError`/`OutsideDestinationError` —
    PEP 706), tiklash ishi "restage_files" bosqichida muvaffaqiyatsiz bo'ladi.
    Nishonni (fayl MAZMUNINI) saqlasak — havola emas — filtr muammosi yo'q;
    tiklangach `sync_moh_class_files`/`sync_greeting` keyingi chaqiruvda
    havolani o'zi qayta tiklaydi (idempotent, is_symlink() endi False)."""
    with tarfile.open(dest_tar, "w", dereference=True) as tar:
        if src_dir.exists():
            tar.add(src_dir, arcname=".", recursive=False)
            for path in _staged_paths(src_dir):
                tar.add(path, arcname=f"./{path.relative_to(src_dir)}", recursive=False)


def _staged_paths(src_dir: Path) -> Iterator[Path]:
    """`src_dir` ichidagi papka/fayllar (havolali papkalar ham kuzatiladi). Nishoni yo'q
    (osilib qolgan) havola TASHLAB KETILADI: masalan MOH audio fayli o'chirilgan, sinf
    papkasidagi havola qolgan -- `dereference=True` bilan u butun zaxirani `failed` qilardi."""
    for root, dirnames, filenames in os.walk(src_dir, followlinks=True):
        dirnames.sort()
        for name in dirnames + sorted(filenames):
            path = Path(root) / name
            if path.exists():
                yield path
            else:
                log.warning("zaxira: nishoni yo'q havola o'tkazib yuborildi: %s", path)


def dump_database(dest: Path, components: list[str]) -> None:
    """`pg_dump -Fc` — haqiqiy Postgres kerak (unit sinovda emas)."""
    args = ["pg_dump", "-Fc", "-f", str(dest), *backup_parts.pg_dump_args(components)]
    subprocess.run(args, env=libpq_env(), check=True, capture_output=True, text=True)


def write_archive(
    ibk_path: Path, passphrase: str, db_key: str, *, alembic_revision: str,
    components: list[str], parts: list[tuple[str, Path]], source_host: str | None = None,
) -> tuple[Manifest, str]:
    """Manifestni quradi va BITTA INNOVABK1 arxivni (`ibk_path`) oqimli yozadi: birinchi
    konteyner freymi `manifest.json`, keyin har bir qism (`parts` tartibida), so'ngra
    `db_key.enc` (disaster recovery). Qaytaradi: (`Manifest`, arxiv sha256)."""
    part_infos = tuple(
        PartInfo(name=name, size=path.stat().st_size, sha256=sha256_file(path)) for name, path in parts
    )
    manifest = Manifest(
        product_version=PRODUCT_VERSION, alembic_revision=alembic_revision,
        created_at=datetime.now(timezone.utc), source_host=source_host or socket.gethostname(),
        components=tuple(components), parts=part_infos, db_key_fp=db_key_fingerprint(db_key),
    )
    db_key_blob = encrypt_db_key(passphrase, db_key)

    def _frames() -> Iterator[bytes]:
        yield from iter_bytes_frame("manifest.json", json.dumps(manifest.to_dict()).encode("utf-8"))
        for name, path in parts:
            yield from iter_file_frame(name, path)
        yield from iter_bytes_frame("db_key.enc", db_key_blob)

    with ibk_path.open("wb") as fh:
        writer = ArchiveWriter(fh, passphrase)
        writer.write_stream(_frames())
        archive_sha256 = writer.sha256()
    return manifest, archive_sha256


def stage_all_parts(stage_dir: Path, components: list[str]) -> list[tuple[str, Path]]:
    """`components`dan DB dump (DOIM) + tanlangan fayl-komponentlar uchun vaqtinchalik
    fayllarni (`stage_dir` ichida) yaratadi va `write_archive()` kutgan `(nom, yo'l)` ro'yxatini
    qaytaradi. DB qismi — chaqiruvchi (`run_backup_job`) `dump_database()` orqali to'ldiradi,
    bu funksiya FAQAT fayl-komponentlarni (sof fayl tizimi, sinaladigan) tayyorlaydi."""
    parts: list[tuple[str, Path]] = []
    for component in backup_parts.FILE_COMPONENTS:
        if component in components:
            dest = stage_dir / f"{component}.tar"
            stage_file_component(Path(backup_parts.FILE_COMPONENTS[component]), dest)
            parts.append((f"{component}.tar", dest))
    return parts


async def create_backup_record(
    session: AsyncSession, *, tenant_id: str, kind: str, components: list[str], created_by: str | None,
) -> Backup:
    """So'rov vaqtida (fon ishdan OLDIN) chaqiriladi: qismlarni tekshiradi, parol
    o'rnatilganini tekshiradi, `Backup` qatorini `running` holatida yaratadi."""
    components = backup_parts.validate_components(list(components))
    row = await session.get(SystemSettings, tenant_id)
    backup_cfg = (row.backup if row else None) or {}
    if not backup_cfg.get("passphrase_enc"):
        raise PassphraseRequiredError("zaxira paroli o'rnatilmagan")
    backup = Backup(tenant_id=tenant_id, kind=kind, status="running", components=components,
                     created_by=created_by)
    session.add(backup)
    await session.flush()
    return backup


def _own_local_items(backups_dir: Path) -> list[RetentionItem]:
    items = []
    if backups_dir.exists():
        for path in backups_dir.iterdir():
            if path.is_file() and is_own_backup_file(path.name):
                items.append(RetentionItem(
                    id=path.name, created_at=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)))
    return items


async def _apply_retention(
    session: AsyncSession, target: str, items: list[RetentionItem], keep_last: int, delete_one,
) -> None:
    for remote_id in ids_to_delete(items, keep_last):
        try:
            await delete_one(remote_id)
        except BackupTargetError as exc:  # noqa: BLE001 — eskisini o'chira olmaslik yangi nusxani buzmasin
            log.warning("retention(%s) o'chirishda xato: %s", target, exc)
            continue
        db_copy = (await session.execute(
            select(BackupCopy).where(BackupCopy.target == target, BackupCopy.remote_path == remote_id)
        )).scalar_one_or_none()
        if db_copy is not None:
            db_copy.status = "deleted"


async def _upload_one(
    session: AsyncSession, backup: Backup, target: str, local_path: Path, upload, keep_last: int,
    list_own, delete_one,
) -> bool:
    """Bitta nishonga yuklaydi, `BackupCopy` qatorini yozadi, muvaffaqiyat bo'lsa retention
    qo'llaydi. Qaytaradi: muvaffaqiyat (`True`)/xato (`False`)."""
    copy = BackupCopy(backup_id=backup.id, target=target, status="pending")
    session.add(copy)
    await session.flush()
    try:
        remote_path = await upload(local_path, backup.file_name)
    except BackupTargetError as exc:
        copy.status, copy.error = "failed", str(exc)[:500]
        return False
    copy.status = "ok"
    copy.remote_path = remote_path
    copy.size_bytes = local_path.stat().st_size
    copy.uploaded_at = datetime.now(timezone.utc)
    try:
        items = await list_own()
    except BackupTargetError as exc:  # noqa: BLE001 — retention ishlamasa ham yuklash muvaffaqiyatli
        log.warning("retention(%s) ro'yxatlashda xato: %s", target, exc)
        return True
    await _apply_retention(session, target, items, keep_last, delete_one)
    return True


async def run_backup_job(
    session_factory: async_sessionmaker, engine: AsyncEngine, lock: JobLock, backup_id: str, tenant_id: str,
) -> None:
    """Fon vazifa: `pg_dump` + tanlangan fayl-komponentlar -> bitta `.ibk` (lokal `backups_dir`)
    -> yoqilgan masofaviy nishonlarga yuklash -> holat (`ok`/`partial`/`failed`). Xato bo'lsa
    (lokal bosqich) `failed` + `backup_failed` ogohlantirish."""
    try:
        async with session_factory() as session:
            await _run_backup_job(session, backup_id, tenant_id)
    finally:
        await lock.release()


def uploads_to_remotes(kind: str) -> bool:
    """`pre_restore`/`pre_import` — faqat lokal: tiklash/ko'chirishni bekor qilish
    shu serverda kerak, o'chiq masofaviy nishon tiklash ishini kutib turmasin."""
    return kind not in ("pre_restore", "pre_import")


async def _run_backup_job(session: AsyncSession, backup_id: str, tenant_id: str) -> None:
    backup = await session.get(Backup, backup_id)
    settings_row = await session.get(SystemSettings, tenant_id)
    backup_cfg = settings_row.backup
    passphrase = await decrypt_secret(session, backup_cfg["passphrase_enc"])
    backups_dir = Path(settings.backups_dir)
    backups_dir.mkdir(parents=True, exist_ok=True)
    file_name = new_backup_file_name(socket.gethostname(), datetime.now(timezone.utc), uuid.uuid4().hex[:8])
    ibk_path = backups_dir / file_name

    try:
        with TemporaryDirectory(dir=backups_dir) as stage_dir_name:
            stage_dir = Path(stage_dir_name)
            db_dump_path = stage_dir / "database.dump"
            dump_database(db_dump_path, backup.components)
            parts = [("database.dump", db_dump_path)] + stage_all_parts(stage_dir, backup.components)
            alembic_revision = await current_alembic_revision(session)
            manifest, archive_sha256 = write_archive(
                ibk_path, passphrase, settings.require_db_key(), alembic_revision=alembic_revision,
                components=backup.components, parts=parts,
            )
    except Exception as exc:  # noqa: BLE001 — lokal bosqich xatosi -> butun zaxira `failed`
        ibk_path.unlink(missing_ok=True)
        backup.status, backup.error = "failed", str(exc)[:500]
        backup.finished_at = datetime.now(timezone.utc)
        await session.commit()
        await _alert_backup_failed(session, tenant_id, backup.error)
        return

    backup.file_name = file_name
    backup.sha256 = archive_sha256
    backup.size_bytes = ibk_path.stat().st_size
    backup.manifest = manifest.to_dict()
    local_copy = BackupCopy(backup_id=backup.id, target="local", status="ok", remote_path=file_name,
                             size_bytes=backup.size_bytes, uploaded_at=datetime.now(timezone.utc))
    session.add(local_copy)
    await session.flush()
    await _apply_retention(session, "local", _own_local_items(backups_dir),
                            backup_cfg["targets"]["local"]["keep_last"],
                            lambda name: _delete_local(backups_dir, name))

    any_remote_failed = (uploads_to_remotes(backup.kind)
                         and await _upload_to_remote_targets(session, backup, backup_cfg, ibk_path))

    backup.status = "partial" if any_remote_failed else "ok"
    backup.finished_at = datetime.now(timezone.utc)
    await session.commit()
    if any_remote_failed:
        await _alert_backup_failed(session, tenant_id, "masofaviy nishonga yuklashda xato (partial)")


async def _delete_local(backups_dir: Path, file_name: str) -> None:
    (backups_dir / file_name).unlink(missing_ok=True)


async def _upload_to_remote_targets(
    session: AsyncSession, backup: Backup, backup_cfg: dict, ibk_path: Path,
) -> bool:
    any_failed = False
    s3_cfg = backup_cfg["targets"]["s3"]
    if s3_cfg.get("enabled"):
        target = await s3_target_from_settings(session, backup_cfg)
        ok = await _upload_one(
            session, backup, "s3", ibk_path, lambda path, name: upload_s3(target, path, name),
            target.keep_last, lambda: list_own_s3(target), lambda remote: delete_s3(target, remote),
        )
        any_failed = any_failed or not ok
    sftp_cfg = backup_cfg["targets"]["sftp"]
    if sftp_cfg.get("enabled"):
        target = await sftp_target_from_settings(session, backup_cfg)
        ok = await _upload_one(
            session, backup, "sftp", ibk_path, lambda path, name: upload_sftp(target, path, name),
            target.keep_last, lambda: list_own_sftp(target), lambda remote: delete_sftp(target, remote),
        )
        any_failed = any_failed or not ok
    return any_failed


async def _alert_backup_failed(session: AsyncSession, tenant_id: str, detail: str) -> None:
    lang = await tenant_language(session, tenant_id)
    text = alert_text(lang, "backup_failed", detail=detail[:200])
    await raise_alert(session, tenant_id, "backup_failed", "backup", text)
    await session.commit()
