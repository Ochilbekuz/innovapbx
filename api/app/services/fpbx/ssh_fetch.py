"""M5a — FreePBX'dan SSH orqali avtomatik to'plam olish (m5a-contract.md §0/§3:
"host, port, user, parol YOKI kalit; host kaliti pin (M4b SFTP kabi)"). Host-key
barmoq izi hisoblash/pin uslubi `app/services/backup_targets.py` BILAN BIR XIL
(`host_key_fingerprint`, `known_hosts=None` + qo'lda tekshirish) — FARQI: bu yerda
masofada eksport skripti ishga tushiriladi va natija SFTP bilan tortib olinadi.

SSH sirlari (parol/xususiy kalit) HECH QAYERDA saqlanmaydi — faqat shu chaqiruv
davomida xotirada (`SshCredentials`), audit/logda ko'rinmaydi (chaqiruvchi ularni
audit `diff`ga qo'shmaydi)."""
from __future__ import annotations

import shlex
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.db.models import MigrationJob
from app.services.backup_targets import host_key_fingerprint
from app.services.fpbx import bundle as bundle_mod
from app.services.fpbx import intake

_EXPORT_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "resources" / "freepbx" / "innova-fpbx-export.sh"
)
_REMOTE_DIR_PREFIX = "/tmp/innova-fpbx-export-"
_SCRIPT_TIMEOUT_S = 1800  # eksport (baza + audio) uzoq davom etishi mumkin — 30 daqiqa.
_MAX_ERROR_MESSAGE = 500


class SshFetchError(Exception):
    """SSH ulanish/eksport/olish xatosi — `code` m5a-contract.md §0 misollariga mos
    (`ssh_auth_failed`, `ssh_unreachable`, `host_key_mismatch`, `export_failed`)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message[:_MAX_ERROR_MESSAGE]
        super().__init__(self.message)


@dataclass(frozen=True)
class SshCredentials:
    """Bir martalik — chaqiruvdan tashqarida saqlanmaydi. `password` YOKI
    `private_key`dan FAQAT bittasi to'ldirilgan bo'lishi router darajasida tekshiriladi."""

    host: str
    port: int
    username: str
    password: str | None = None
    private_key: str | None = None


def _timeout_s() -> float:
    """`backup_targets.py::_timeout_s` BILAN BIR XIL sozlama — alohida nom kerak emas."""
    return settings.backup_target_timeout_s


def _connect_kwargs(creds: SshCredentials) -> dict:
    import asyncssh

    return {
        "host": creds.host, "port": creds.port, "username": creds.username,
        "password": creds.password or None,
        "client_keys": [asyncssh.import_private_key(creds.private_key)] if creds.private_key else None,
        "known_hosts": None, "connect_timeout": _timeout_s(), "login_timeout": _timeout_s(),
    }


async def _connect(creds: SshCredentials):
    """`backup_targets.py::_sftp_connect` uslubidagi ingichka qobiq: muvaffaqiyatli
    ulanish -> `(conn, host_key_fp)`; xato -> `SshFetchError` (`ssh_auth_failed`/
    `ssh_unreachable`)."""
    import asyncio

    import asyncssh

    try:
        conn = await asyncssh.connect(**_connect_kwargs(creds))
    except asyncssh.PermissionDenied as exc:
        raise SshFetchError("ssh_auth_failed", str(exc)) from exc
    except (asyncssh.Error, OSError, asyncio.TimeoutError) as exc:
        raise SshFetchError("ssh_unreachable", str(exc)) from exc
    fp = host_key_fingerprint(conn.get_server_host_key().public_data)
    return conn, fp


async def test_connection(creds: SshCredentials) -> tuple[bool, str | None, str | None]:
    """`POST /ssh/test` — ulanib (haqiqiy auth bilan) host kalitini qaytaradi. Xato bo'lsa
    `(False, None, <kod>)`; muvaffaqiyat `(True, <fp>, None)`."""
    try:
        conn, fp = await _connect(creds)
    except SshFetchError as exc:
        return False, None, exc.code
    conn.close()
    await conn.wait_closed()
    return True, fp, None


def _parse_export_output(stdout: str) -> str | None:
    """Skript oxirgi qatori `Tayyor: <yo'l> (<hajm>)` (`innova-fpbx-export.sh`) —
    yo'lni ajratib oladi."""
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("Tayyor:"):
            rest = line[len("Tayyor:"):].strip()
            return rest.rsplit(" (", 1)[0].strip() or None
    return None


async def _run_export(conn, remote_dir: str) -> str:
    """Skriptni SFTP bilan yuklaydi, `bash` bilan ishga tushiradi, chiqargan arxiv
    yo'lini qaytaradi. Xato -> `SshFetchError("export_failed", ...)`."""
    import asyncssh

    remote_script = f"{remote_dir}/export.sh"
    try:
        async with conn.start_sftp_client() as sftp:
            await sftp.makedirs(remote_dir, exist_ok=True)
            await sftp.put(str(_EXPORT_SCRIPT_PATH), remote_script)
        result = await conn.run(
            f"bash {shlex.quote(remote_script)} {shlex.quote(remote_dir)}",
            timeout=_SCRIPT_TIMEOUT_S, check=False,
        )
    except (asyncssh.Error, OSError) as exc:
        raise SshFetchError("export_failed", str(exc)) from exc
    if result.exit_status != 0:
        detail = (result.stderr or result.stdout or "eksport skripti muvaffaqiyatsiz tugadi")
        raise SshFetchError("export_failed", str(detail))
    archive = _parse_export_output(str(result.stdout or ""))
    if archive is None:
        raise SshFetchError("export_failed", "eksport skripti chiqishi tushunarsiz")
    return archive


async def _download_and_cleanup(conn, remote_archive: str, dest_path: Path, remote_dir: str, max_bytes: int) -> None:
    import asyncssh

    try:
        async with conn.start_sftp_client() as sftp:
            size = (await sftp.stat(remote_archive)).size or 0
            if size > max_bytes:
                raise SshFetchError("export_failed", "to'plam hajmi chegaradan katta")
            await sftp.get(remote_archive, str(dest_path))
    except (asyncssh.Error, OSError) as exc:
        raise SshFetchError("export_failed", str(exc)) from exc
    finally:
        await _cleanup_remote(conn, remote_dir)


async def _cleanup_remote(conn, remote_dir: str) -> None:
    """Masofadagi vaqtinchalik skript/arxiv papkasini o'chiradi — xato bo'lsa HAM
    (m5a-contract.md §0: "masofadagi vaqtinchalik skript/arxiv o'chiriladi"), shu
    sabab chaqiruvchida `finally` ichida chaqiriladi."""
    try:
        await conn.run(f"rm -rf {shlex.quote(remote_dir)}", check=False, timeout=_timeout_s())
    except Exception:  # noqa: BLE001 — tozalash xatosi asosiy natijani bosmaydi
        pass


async def fetch_bundle(creds: SshCredentials, expected_host_key_fp: str, dest_path: Path, *, max_bytes: int) -> None:
    """To'liq oqim: ulanish (fp tekshiruvi bilan) -> skriptni yuklab ishga tushirish ->
    arxivni SFTP bilan `dest_path`ga olish -> masofadagi vaqtinchalik narsalarni
    o'chirish (`finally`). Xato -> `SshFetchError`."""
    conn, observed_fp = await _connect(creds)
    if observed_fp != expected_host_key_fp:
        conn.close()
        await conn.wait_closed()
        raise SshFetchError("host_key_mismatch", "Host kaliti mos kelmadi")

    remote_dir = f"{_REMOTE_DIR_PREFIX}{uuid.uuid4().hex}"
    try:
        remote_archive = await _run_export(conn, remote_dir)
        await _download_and_cleanup(conn, remote_archive, dest_path, remote_dir, max_bytes)
    finally:
        conn.close()
        await conn.wait_closed()


# ------------------------------------------------------------------ fon vazifa (DB)
async def run_ssh_fetch_job(
    session_factory: async_sessionmaker, job_id: str,
    creds: SshCredentials, expected_host_key_fp: str,
) -> None:
    """`app/services/fpbx/analyze_job.py::run_analyze_job` BILAN BIR XIL qolip — alohida
    sessiya, muvaffaqiyat/xato job holatini belgilaydi. Qulf (`job_lock`) kerak EMAS —
    bu faqat to'plam tortib olish, Innova holatini o'zgartirmaydi (`upload` kabi)."""
    async with session_factory() as session:
        await _run_ssh_fetch_job(session, job_id, creds, expected_host_key_fp)


async def _fail_job(session, work_dir: Path, job: MigrationJob, code: str, message: str) -> None:
    """`work_dir` (hali qo'zg'almagan, `migrations_dir/<job_id>`ga ko'chirilmagan) butunlay
    o'chiriladi — yarim yuklangan arxiv diskda qolmaydi."""
    shutil.rmtree(work_dir, ignore_errors=True)
    job.status, job.step = "failed", None
    job.error = {"code": code, "message": message[:_MAX_ERROR_MESSAGE]}
    job.finished_at = datetime.now(timezone.utc)
    await session.commit()


async def _run_ssh_fetch_job(
    session, job_id: str, creds: SshCredentials, expected_host_key_fp: str,
) -> None:
    job = await session.get(MigrationJob, job_id)
    if job is None:
        return
    migrations_dir = Path(settings.migrations_dir)
    migrations_dir.mkdir(parents=True, exist_ok=True)
    work_dir = migrations_dir / f"ssh-{uuid.uuid4().hex}"
    work_dir.mkdir(parents=True, exist_ok=True)
    archive_path = work_dir / "bundle.tar.gz"
    try:
        await fetch_bundle(creds, expected_host_key_fp, archive_path, max_bytes=settings.migration_upload_max_bytes)
    except SshFetchError as exc:
        await _fail_job(session, work_dir, job, exc.code, exc.message)
        return
    try:
        bundle_root, meta = intake.extract_and_read_meta(archive_path, work_dir)
    except bundle_mod.BundleInvalidError as exc:
        await _fail_job(session, work_dir, job, "bundle_invalid", str(exc))
        return

    size = archive_path.stat().st_size
    job.source_meta = intake.build_source_meta(meta, size_bytes=size, extra={"host": creds.host})
    job.bundle_path = str(intake.place_bundle_dir(str(job.id), work_dir, bundle_root))
    job.status, job.step, job.progress = "uploaded", None, 100
    job.finished_at = datetime.now(timezone.utc)
    await session.commit()
