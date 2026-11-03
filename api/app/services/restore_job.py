"""Tiklash orkestratsiyasi -- ikki bosqich (m4b-contract.md §0).

`inspect()` -- arxivni parol bilan ochadi, manifestni o'qiydi, BARCHA qismning
sha256'ini streaming tekshiradi (xotiraga yuklamasdan), joriy alembic reviziyasi
bilan solishtiradi. HECH NARSANI o'zgartirmaydi (sof o'qish, DB yozmaydi).

`precheck_and_create_job()` -- restore so'rovining SINXRON qismi (router to'g'ridan
to'g'ri kutadi, javob 202/409/422 shunga qarab tanlanadi): parol/manifest/versiya
tekshiradi (422 `bad_passphrase`/`backup_corrupt`/`backup_newer`), faol qo'ng'iroqni
tekshiradi (409 `active_calls`), `pg_advisory_lock` oladi (409 `job_running` --
`JobAlreadyRunningError` job_lock.py'dan), `RestoreJob` qatorini yaratadi.

`run_restore_job()` -- ASINXRON fon vazifa (router `asyncio.create_task` bilan
ishga tushiradi, qulf ALLAQACHON OLINGAN holda): avtomatik `pre_restore` zaxira ->
texnik xizmat rejimi yoqiladi -> `pg_restore --single-transaction` (xato -> avtomatik
qaytadi, eski holat buzilmaydi) -> `alembic upgrade head` -> kerak bo'lsa re-key
(`crypto_registry.rekey_all`) -> fayl qismlari almashtiriladi -> `regen_all.py` ->
barcha refresh tokenlar bekor qilinadi -> audit -> texnik xizmat rejimi o'chadi.
Har qanday xato -- `RestoreJob.status="failed"` + `.error`, qulf HAR DOIM bo'shaydi
(`finally`), texnik xizmat rejimi HAR DOIM o'chadi (`finally`)."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import shutil
import subprocess
import tarfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from cryptography.exceptions import InvalidTag
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.models import RestoreJob, Tenant, User
from app.db.raw_sql import libpq_env
from app.db.session import engine as _db_engine
from app.services import backup_job, backup_parts, crypto_registry
from app.services.audit import record_audit
from app.services.backup_container import FrameReader
from app.services.backup_dbkey import decrypt_db_key
from app.services.backup_format import ArchiveReader, BackupCorruptError
from app.services.backup_manifest import (
    ALEMBIC_INI, Manifest, ManifestError, current_alembic_revision, db_key_fingerprint,
    is_revision_newer, load_script_directory,
)
from app.services.job_lock import JobLock, try_acquire_job_lock
from app.services.live_status import active_calls_live
from app.services.regen_all import regenerate_all
from app.services.tokens import revoke_all_refresh_tokens

log = logging.getLogger("innova.restore_job")


class RestoreNewerError(Exception):
    """Manifest alembic reviziyasi joriydan yangiroq (router -- 422 `backup_newer`)."""


class PreRestoreBackupError(Exception):
    """Tiklashdan oldingi avtomatik zaxira muvaffaqiyatsiz -- bekor qilish nuqtasi yo'q,
    shu sabab tiklash HECH NARSA o'zgartirilmasdan to'xtatiladi."""


@dataclass
class ActiveCallsError(Exception):
    """Faol qo'ng'iroqlar bor, `force` berilmagan (router -- 409 `active_calls`,
    `details.count`; `count=None` -- AMI javob bermadi, xavfsiz tomon: rad etish)."""

    count: int | None

    def __str__(self) -> str:  # pragma: no cover -- faqat log/debug uchun
        return f"faol qo'ng'iroqlar bor (count={self.count})"


# ---------------------------------------------------------------- arxivni o'qish
def _frame_iterator(path: Path, passphrase: str) -> Iterator[tuple[str, int, FrameReader]]:
    with path.open("rb") as fh:
        reader = ArchiveReader(fh, passphrase)  # BadPassphraseError/BackupCorruptError
        frames = FrameReader(reader.read_chunks())
        while True:
            header = frames.read_header()
            if header is None:
                return
            name, size = header
            yield name, size, frames


def _parse_manifest(data: bytes) -> Manifest:
    try:
        return Manifest.from_dict(json.loads(data))
    except (ManifestError, ValueError) as exc:
        raise BackupCorruptError(f"manifest o'qilmadi: {exc}") from exc


def _hashing_stream(chunks: Iterator[bytes], digest: "hashlib._Hash") -> Iterator[bytes]:
    for chunk in chunks:
        digest.update(chunk)
        yield chunk


def _drain(_name: str, chunks: Iterator[bytes]) -> None:
    for _chunk in chunks:
        pass


# Arxiv ichida kutilgan BARCHA qism nomlari -- hujumchi nazorat qiladigan `name`
# (walk_archive uni MANIFEST TASDIQLANISHIDAN OLDIN `on_part()`ga -- demak diskka
# yozishga -- beradi) shu ro'yxatdan TASHQARI bo'lsa darhol rad etiladi, yo'l-chiqish
# (`../`, absolyut yo'l, `\\`, NUL) hech qachon `on_part` chaqiruvchisiga yetib bormaydi.
_ALLOWED_PART_NAMES: frozenset[str] = frozenset({"db_key.enc", "database.dump"}) | frozenset(
    f"{component}.tar" for component in backup_parts.FILE_COMPONENTS
)


def _validate_part_name(name: str) -> None:
    if name not in _ALLOWED_PART_NAMES:
        raise BackupCorruptError(f"kutilmagan qism nomi: {name!r}")


def walk_archive(path: Path, passphrase: str, on_part=_drain) -> Manifest:
    """Manifestni (BIRINCHI freym) o'qiydi, so'ng har bir keyingi qismni
    `on_part(name, chunks)` orqali OQIMLI ko'rsatadi va (`db_key.enc`dan tashqari)
    manifestdagi sha256/hajm bilan solishtiradi -- mos kelmasa `BackupCorruptError`.
    `on_part` chaqiruvchining tanlovi: sukut -- shunchaki oqizadi (`inspect`), yoki
    diskka yozadi (`extract_archive`, tiklash paytida). `name` MANIFEST tasdiqlanishidan
    OLDIN (sha256 solishtirishdan oldin) `on_part`ga beriladi -- shu sabab nom
    `_validate_part_name` orqali OLDIN-DAN (allowlist) tekshiriladi, aks holda
    `extract_archive` manifest hali tasdiqlanmasdan turib ixtiyoriy yo'lga yozardi
    (yo'l-chiqish hujumi)."""
    manifest: Manifest | None = None
    parts_by_name: dict[str, object] = {}
    for name, size, frames in _frame_iterator(path, passphrase):
        if manifest is None:
            if name != "manifest.json":
                raise BackupCorruptError("manifest.json kutilgan edi (birinchi freym)")
            manifest = _parse_manifest(frames.read_exact(size))
            parts_by_name = {part.name: part for part in manifest.parts}
            continue
        _validate_part_name(name)
        digest = hashlib.sha256()
        on_part(name, _hashing_stream(frames.read_stream(size), digest))
        if name == "db_key.enc":
            continue
        expected = parts_by_name.get(name)
        if expected is None or expected.size != size or expected.sha256 != digest.hexdigest():
            raise BackupCorruptError(f"qism buzilgan yoki mos kelmaydi: {name}")
    if manifest is None:
        raise BackupCorruptError("arxiv bo'sh -- manifest topilmadi")
    return manifest


def extract_archive(path: Path, passphrase: str, stage_dir: Path) -> tuple[Manifest, bytes]:
    """`walk_archive()` ustiga: `database.dump`/`<component>.tar` qismlarini
    `stage_dir`ga yozadi, `db_key.enc` tarkibini (shifrlangan, re-key uchun) qaytaradi.
    `name` allaqachon `walk_archive._validate_part_name` orqali o'tgan (faqat ma'lum
    qism nomlari), lekin ikkinchi himoya qatlami sifatida yakuniy yo'l HAR DOIM
    `stage_dir` ICHIDA qolishi `resolve().is_relative_to()` bilan tasdiqlanadi."""
    captured: dict[str, bytes] = {}
    resolved_stage = stage_dir.resolve()

    def on_part(name: str, chunks: Iterator[bytes]) -> None:
        if name == "db_key.enc":
            captured["db_key.enc"] = b"".join(chunks)
            return
        dest = stage_dir / name
        if not dest.resolve().is_relative_to(resolved_stage):
            raise BackupCorruptError(f"xavfli qism yo'li: {name!r}")
        with dest.open("wb") as out:
            for chunk in chunks:
                out.write(chunk)

    manifest = walk_archive(path, passphrase, on_part)
    return manifest, captured.get("db_key.enc", b"")


# ---------------------------------------------------------------- inspect (sof o'qish)
async def inspect(session: AsyncSession, path: Path, passphrase: str) -> dict:
    """`POST /backups/{id}/inspect` -- hech narsani o'zgartirmaydi. Qaytaradi:
    `{"manifest": Manifest, "checks": {"sha256": "ok"}, "compatible": bool, "warnings": [...]}`.
    Parol noto'g'ri/arxiv buzilgan -- `BadPassphraseError`/`BackupCorruptError` ko'tariladi
    (router -- 422); bular HECH QACHON shu funksiya ichida yutilmaydi."""
    manifest = await asyncio.to_thread(walk_archive, path, passphrase)
    current_revision = await current_alembic_revision(session)
    newer = is_revision_newer(load_script_directory(), manifest.alembic_revision, current_revision)
    warnings: list[str] = []
    if manifest.db_key_fp != db_key_fingerprint(settings.require_db_key()):
        warnings.append("boshqa server kaliti bilan yaratilgan -- tiklashda sirlar qayta shifrlanadi")
    return {"manifest": manifest, "checks": {"sha256": "ok"}, "compatible": not newer, "warnings": warnings}


# ---------------------------------------------------------------- sinxron precheck
def restore_source(backup_kind: str) -> str:
    """Tiklash tarixidagi manba. Yuklangan arxiv ham `backups` qatoriga aylanadi (`kind="uploaded"`),
    shuning uchun manbani `backup_id` borligidan emas, zaxira turidan aniqlaymiz (m4b real-check
    2026-10-29: fayldan tiklash tarixda «Roʻyxatdagi zaxiradan» deb chiqardi)."""
    return "upload" if backup_kind == "uploaded" else "local"


async def precheck_and_create_job(
    session: AsyncSession, engine: AsyncEngine, *, backup_id: str | None, source: str, archive_path: Path,
    passphrase: str, force: bool, tenant_id: str, user_id: str | None, ami,
) -> tuple[RestoreJob, JobLock]:
    """Router so'rov ichida KUTADI (javob 202/409/422 shu yerdagi tekshiruvlarga
    qarab tanlanadi). Muvaffaqiyatli bo'lsa: qulf OLINGAN, `RestoreJob` qatori
    `session.flush()`langan (router commit qiladi) -- chaqiruvchi SHART `lock.release()`
    chaqirishi (muvaffaqiyatsiz holatda ham, masalan keyinroq commit xato bersa)."""
    manifest = await asyncio.to_thread(walk_archive, archive_path, passphrase)
    current_revision = await current_alembic_revision(session)
    if is_revision_newer(load_script_directory(), manifest.alembic_revision, current_revision):
        raise RestoreNewerError("zaxira joriy versiyadan yangiroq")

    if not force:
        live_calls = await active_calls_live(ami)
        if live_calls is None or len(live_calls) > 0:
            raise ActiveCallsError(count=None if live_calls is None else len(live_calls))

    lock = await try_acquire_job_lock(engine)  # band -- JobAlreadyRunningError (409 job_running)
    job = RestoreJob(
        tenant_id=tenant_id, backup_id=backup_id, source=source,
        status="running", step="pre_restore_backup", progress=0, force=force, started_by=user_id,
    )
    session.add(job)
    await session.flush()
    return job, lock


# ---------------------------------------------------------------- fon vazifa
async def run_restore_job(
    session_factory: async_sessionmaker, engine: AsyncEngine, lock: JobLock, restore_job_id: str,
    *, tenant_id: str, tenant_code: str, ami, archive_path: Path, passphrase: str,
) -> None:
    from app.services import maintenance

    try:
        async with session_factory() as session:
            await _run_restore(session, tenant_id=tenant_id, tenant_code=tenant_code, ami=ami,
                                restore_job_id=restore_job_id, archive_path=archive_path,
                                passphrase=passphrase)
    finally:
        maintenance.state.enabled = False
        await lock.release()


async def _mark(session: AsyncSession, job: RestoreJob, step: str, progress: int) -> None:
    job.step, job.progress = step, progress
    await session.commit()


async def _create_pre_restore_backup(session: AsyncSession, tenant_id: str):
    """Tiklashdan OLDIN avtomatik lokal zaxira (bekor qilish imkoniyati).
    `_run_backup_job` (PRIVATE) ATAYLAB to'g'ridan-to'g'ri chaqiriladi -- restore
    allaqachon `job_lock`ni ushlab turibdi, `run_backup_job` (PUBLIC) esa YANGI qulf
    olishga urinardi (o'z-o'ziga qarshi `JobAlreadyRunningError`). Zaxira paroli
    o'rnatilmagan bo'lsa (`PassphraseRequiredError`) -- pre_restore'siz davom etiladi
    (admin aniq `TIKLASH` deb tasdiqlagan, bu ortiqcha to'siq bo'lardi). Zaxira o'zi
    `failed` bo'lsa -- `PreRestoreBackupError` (bekor qilish nuqtasisiz tiklanmaydi)."""
    try:
        backup = await backup_job.create_backup_record(
            session, tenant_id=tenant_id, kind="pre_restore",
            components=list(backup_parts.DEFAULT_COMPONENTS), created_by=None,
        )
    except backup_job.PassphraseRequiredError:
        return None
    await session.commit()
    await backup_job._run_backup_job(session, backup.id, tenant_id)
    if backup.status == "failed":
        raise PreRestoreBackupError(f"pre_restore zaxira muvaffaqiyatsiz: {backup.error}")
    return backup


async def _resolve_tenant(session: AsyncSession, tenant_id: str) -> tuple[str, str]:
    """`pg_restore`dan KEYIN chaqiriladi. Falokatdan tiklash (m4b-contract.md §4
    band 5): BOSHQA serverda yangi (bo'sh) stack bootstrap qilinganda `tenants.id`
    TASODIFIY yangi UUID oladi; tiklanayotgan zaxira esa ASL serverning tenant
    qatorini (BOSHQA UUID) qaytaradi -- `pg_restore --clean` bootstrap tenantni
    O'CHIRIB, o'rniga ASL qatorni qo'yadi. Shu sabab so'rov boshida ushlangan
    `tenant_id` (router -- `user.tenant_id`, hali RESTOREdan OLDINGI holat) endi
    bazada MAVJUD BO'LMAYDI -- keyingi bosqichlar (`regenerate_all`/
    `revoke_all_refresh_tokens`/audit) shu ESKI id bilan chaqirilsa
    `build_snapshot()` "Tenant topilmadi" bilan ko'tarib, tiklash ishi "regenerate"
    bosqichida HAR DOIM muvaffaqiyatsiz bo'ladi. Oddiy (bir xil server) holatda
    `tenant_id` o'zgarmagan -- `session.get` tezkor yo'l bilan topadi, qo'shimcha
    so'rov shart emas; faqat u YO'QOLGAN taqdirda yagona (bitta-tenant) qatordan
    haqiqiy id/kod qayta olinadi."""
    tenant = await session.get(Tenant, tenant_id)
    if tenant is not None:
        return str(tenant.id), tenant.code
    tenant = (await session.execute(select(Tenant))).scalars().first()
    if tenant is None:
        raise ValueError("Tiklangan zaxirada tenant qatori topilmadi")
    return str(tenant.id), tenant.code


def _excluded_table_fk_defs() -> list[tuple[str, str, str, str, str]]:
    """`ALWAYS_EXCLUDED_TABLES` (backups/backup_copies/restore_jobs) jadvallaridan config
    jadvallariga (masalan users/tenants) ISHORA qiluvchi FOREIGN KEY'lar -- bu jadvallar
    dump'da YO'Q (ataylab chiqarib tashlangan, "tarix yo'qolmasin"), shu sabab ularning
    FK'si dump TOC'sida ham yo'q. `pg_restore --clean` esa users/tenants PK'sini DROP
    qilishga urinadi -> jonli (dumpga kirmagan) FK buni to'sadi: "cannot drop constraint
    users_pkey ... other objects depend on it". Qaytadi: (jadval, cheklov nomi,
    cheklov ta'rifi, ustun, O'CHIRISH qoidasi: 'n'=SET NULL / 'c'=CASCADE)."""
    env = libpq_env()
    excluded = ",".join(f"'{t}'" for t in backup_parts.ALWAYS_EXCLUDED_TABLES)
    query = (
        "select conrelid::regclass::text, conname, pg_get_constraintdef(oid), confdeltype, "
        "(select attname from pg_attribute where attrelid=conrelid and attnum=conkey[1]) "
        f"from pg_constraint where contype='f' and conrelid::regclass::text in ({excluded}) "
        f"and confrelid::regclass::text not in ({excluded}) order by 1, 2"
    )
    result = subprocess.run(["psql", "-AtF", "\t", "-v", "ON_ERROR_STOP=1", "-c", query],
                             env=env, check=True, capture_output=True, text=True)
    return [tuple(line.split("\t")) for line in result.stdout.splitlines() if line]  # type: ignore[misc]


def _drop_excluded_fks(fk_defs: list[tuple[str, str, str, str, str]]) -> None:
    env = libpq_env()
    for table, name, _defn, _delrule, _col in fk_defs:
        subprocess.run(["psql", "-v", "ON_ERROR_STOP=1",
                        "-c", f'alter table "{table}" drop constraint "{name}"'],
                       env=env, check=True, capture_output=True, text=True)


def _restore_excluded_fks(fk_defs: list[tuple[str, str, str, str, str]]) -> None:
    """`_drop_excluded_fks`ning teskarisi -- cheklovni `NOT VALID` bilan qaytadi, YA'NI
    MAVJUD qatorlarni TEKSHIRMAYDI/O'ZGARTIRMAYDI (faqat keyingi yozuvlarga amal qiladi).

    MUHIM: bu yerda avval "yetim qiymatlarni ON DELETE qoidasiga ko'ra tozalash" (UPDATE
    SET NULL / DELETE) qilingan EDI -- lekin bu NOTO'G'RI: tiklash DAVOMIDA `tenants`/`users`
    jadvali ZAXIRADAGI eski holatga almashtiriladi, shu payt `restore_jobs`/`backups`dagi
    HOZIRGI (jonli) qatorlar -- jumladan AYNAN SHU ishlayotgan tiklash ishini kuzatuvchi
    qator! -- "yetim" bo'lib qoladi va O'CHIRILIB KETARDI. Bu `ALWAYS_EXCLUDED_TABLES`ning
    butun maqsadini (zaxira/tiklash TARIXI yo'qolmasin) buzardi. `NOT VALID` -- Postgres
    kelgusi yozuvlarni tekshiradi, lekin eski (endi mos kelmay qolgan) qatorlarga TEGMAYDI."""
    env = libpq_env()
    for table, name, defn, _delrule, _col in fk_defs:
        subprocess.run(["psql", "-v", "ON_ERROR_STOP=1",
                        "-c", f'alter table "{table}" add constraint "{name}" {defn} not valid'],
                       env=env, check=True, capture_output=True, text=True)


def _pg_restore(dump_path: Path) -> None:
    env = libpq_env()
    fk_defs = _excluded_table_fk_defs()
    _drop_excluded_fks(fk_defs)
    try:
        subprocess.run(
            ["pg_restore", "--clean", "--if-exists", "--single-transaction", "--no-owner",
             "-d", env["PGDATABASE"], str(dump_path)],
            env=env, check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"{exc}: {exc.stderr}") from exc
    finally:
        _restore_excluded_fks(fk_defs)


def _alembic_upgrade_head() -> None:
    subprocess.run(["alembic", "upgrade", "head"], cwd=str(ALEMBIC_INI.parent),
                    check=True, capture_output=True, text=True)


async def _maybe_rekey(session: AsyncSession, manifest: Manifest, passphrase: str, db_key_blob: bytes) -> None:
    current_key = settings.require_db_key()
    if manifest.db_key_fp == db_key_fingerprint(current_key):
        return
    try:
        old_key = decrypt_db_key(passphrase, db_key_blob)
    except InvalidTag as exc:
        raise BackupCorruptError("db_key.enc ochilmadi") from exc
    await crypto_registry.rekey_all(session, old_key, current_key)


def _clear_dir_contents(target: Path) -> None:
    """`shutil.rmtree(target)` TARGET papkaning O'ZINI emas, FAQAT ICHINI tozalaydi --
    bug: `backup_parts.FILE_COMPONENTS` nishonlari (`/var/lib/innova/sounds` va h.k.)
    `deploy/docker-compose.yml`da ulangan Docker HAJM (volume) ILDIZI; ildizning o'zini
    o'chirish har doim `OSError: [Errno 16] Device or resource busy` bilan rad etiladi
    (mount nuqtasi o'chirilmaydi), shu sabab tiklash ishi HAR DOIM shu bosqichda
    muvaffaqiyatsiz bo'lardi."""
    for entry in target.iterdir():
        if entry.is_symlink() or entry.is_file():
            entry.unlink()
        else:
            shutil.rmtree(entry)


def _restage_file_components(stage_dir: Path) -> None:
    """Har bir arxivda MAVJUD fayl-komponent (`<component>.tar`) uchun: nishon
    papka ICHI BUTUNLAY tozalanadi (ildizning o'zi -- hajm mount nuqtasi -- SAQLANADI),
    so'ngra tar ichidagi fayllar o'rniga qo'yiladi (`filter="data"` -- xavfsiz
    chiqarish, yo'l-chiqish hujumisiz)."""
    for component, target_dir in backup_parts.FILE_COMPONENTS.items():
        tar_path = stage_dir / f"{component}.tar"
        if not tar_path.exists():
            continue
        target = Path(target_dir)
        target.mkdir(parents=True, exist_ok=True)
        _clear_dir_contents(target)
        with tarfile.open(tar_path) as tar:
            tar.extractall(target, filter="data")


async def _existing_user_id(session: AsyncSession, user_id: str | None) -> str | None:
    """Audit muallifi tiklangan bazada bo'lmasligi mumkin (falokatdan tiklash: ishni
    yangi stekning vaqtinchalik admini boshlagan) -- u holda `audit_log.user_id` FK
    buzilmasin, muallifsiz yoziladi."""
    if user_id is None:
        return None
    return user_id if await session.get(User, user_id) is not None else None


async def _mark_failed(session: AsyncSession, restore_job_id: str, exc: Exception) -> None:
    """Xatodan keyin sessiya `rollback` talab qiladi -- busiz `commit` ham yiqilib, ish
    abadiy `running` bo'lib qolardi. Qator qayta o'qiladi (rollback obyektni eskirtiradi)."""
    await session.rollback()
    job = await session.get(RestoreJob, restore_job_id)
    job.status, job.error = "failed", str(exc)[:500]
    job.finished_at = datetime.now(timezone.utc)
    await session.commit()


async def _run_restore(
    session: AsyncSession, *, tenant_id: str, tenant_code: str, ami, restore_job_id: str,
    archive_path: Path, passphrase: str,
) -> None:
    from app.services import maintenance

    job = await session.get(RestoreJob, restore_job_id)
    try:
        await _mark(session, job, "pre_restore_backup", 5)
        pre_backup = await _create_pre_restore_backup(session, tenant_id)
        job.pre_restore_backup_id = pre_backup.id if pre_backup else None
        await session.commit()

        maintenance.state.enabled = True
        await _mark(session, job, "pg_restore", 20)
        with TemporaryDirectory() as stage_dir_name:
            stage_dir = Path(stage_dir_name)
            manifest, db_key_blob = await asyncio.to_thread(extract_archive, archive_path, passphrase, stage_dir)
            await asyncio.to_thread(_pg_restore, stage_dir / "database.dump")
            # `pg_restore --clean` deyarli HAMMA jadvalni DROP+QAYTA YARATADI (yangi OID) --
            # ulashiladigan havuzdagi BOSHQA (jonli) ulanishlar hali ESKI sxema uchun
            # keshlangan tayyorlangan rejalarni ushlab turadi; ulardan birinchi so'rov
            # `asyncpg.exceptions.InvalidCachedStatementError` bilan BIR MARTA 500 beradi
            # (SQLAlchemy keshni FAQAT xatodan KEYIN tozalaydi). Havuzni shu yerda
            # tashlab yuborish -- tiklashdan KEYINGI birinchi so'rovchiga bu xato
            # tegmasin (joriy sessiya o'zining ulanishini davom ettirishda bemalol,
            # `dispose()` faqat BO'SH/qaytarilgan ulanishlarni yopadi).
            await _db_engine.dispose()

            await _mark(session, job, "alembic_upgrade", 50)
            await asyncio.to_thread(_alembic_upgrade_head)
            tenant_id, tenant_code = await _resolve_tenant(session, tenant_id)

            await _mark(session, job, "rekey", 60)
            await _maybe_rekey(session, manifest, passphrase, db_key_blob)
            await session.commit()

            await _mark(session, job, "restage_files", 70)
            await asyncio.to_thread(_restage_file_components, stage_dir)

        await _mark(session, job, "regenerate", 85)
        await regenerate_all(session, tenant_id=tenant_id, tenant_code=tenant_code, ami=ami)
        await session.commit()

        await _mark(session, job, "revoke_sessions", 95)
        await revoke_all_refresh_tokens(session, tenant_id)
        await record_audit(session, tenant_id=tenant_id, user_id=await _existing_user_id(session, job.started_by),
                            action="backup.restore",
                            entity="restore_job", entity_id=job.id,
                            diff={"backup_id": job.backup_id, "pre_restore_backup_id": job.pre_restore_backup_id})
        job.status, job.step, job.progress = "ok", "done", 100
        job.finished_at = datetime.now(timezone.utc)
        job.result = {"alembic_revision": manifest.alembic_revision}
        await session.commit()
    except Exception as exc:  # noqa: BLE001 -- tiklash ishi hech qachon kutilmasdan osilib qolmasin
        log.exception("tiklash ishi (%s) muvaffaqiyatsiz", restore_job_id)
        await _mark_failed(session, restore_job_id, exc)
    finally:
        maintenance.state.enabled = False
