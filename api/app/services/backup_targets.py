"""Masofaviy saqlash nishonlari — S3 (boto3) va SFTP (asyncssh), m4b-contract.md §0/§1.

SOF qism (bu moduldagi hech qanday tashqi tarmoqqa chiqmaydigan funksiyalar —
kalit nomi qurish, o'z fayllarimizni aniqlash, barmoq izi hisoblash) ALOHIDA,
chunki ular `tests/test_backup_targets.py`da to'liq, tarmoqsiz sinaladi.
Haqiqiy I/O (`boto3`/`asyncssh` chaqiruvlari) — ingichka qobiq, `asyncio.to_thread`
orqali (boto3 sinxron), xatolar `BackupTargetError` ga aylantiriladi."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.services.backup_retention import RetentionItem

OWN_FILE_RE = re.compile(r"^innova-.*\.ibk$")


class BackupTargetError(Exception):
    """S3/SFTP bilan bog'lanish/amal xatosi — chaqiruvchi `error`/`partial`ga aylantiradi."""


@dataclass(frozen=True)
class S3Target:
    endpoint: str
    region: str
    bucket: str
    prefix: str
    access_key: str
    secret_key: str
    path_style: bool
    keep_last: int = 14


@dataclass(frozen=True)
class SftpTarget:
    host: str
    port: int
    user: str
    folder: str
    password: str | None = None
    key: str | None = None
    host_key_fp: str | None = None
    keep_last: int = 7


def is_own_backup_file(name: str) -> bool:
    """Faqat o'zimiz yozgan `innova-*.ibk` fayllar — saqlash muddati BEGONA fayllarga tegmaydi."""
    return bool(OWN_FILE_RE.match(name))


def s3_key(target: S3Target, file_name: str) -> str:
    prefix = target.prefix.strip("/")
    return f"{prefix}/{file_name}" if prefix else file_name


def sftp_remote_path(target: SftpTarget, file_name: str) -> str:
    folder = target.folder.rstrip("/")
    return f"{folder}/{file_name}" if folder else f"/{file_name}"


def host_key_fingerprint(public_data: bytes) -> str:
    """OpenSSH uslubidagi `SHA256:<base64, '='siz>` barmoq izi."""
    digest = hashlib.sha256(public_data).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def pinned_client_factory(expected_fp: str | None):
    """`asyncssh.connect(known_hosts=([], [], []), client_factory=...)` bilan
    ishlatiladi — shunda asyncssh AUTENTIFIKATSIYADAN OLDIN (parol/xususiy kalit
    yuborilishidan OLDIN) shu klassning `validate_host_public_key`sini chaqiradi.
    Avvalgi xato: `known_hosts=None` bilan ulanib, parol/kalit YUBORILGANDAN KEYIN
    barmoq izi solishtirilardi — MITM parolni allaqachon olib bo'lgan bo'lardi.
    `backup_targets.py` VA `ssh_fetch.py` BIR XIL qolip (DRY)."""
    import asyncssh

    class _PinnedHostKeyClient(asyncssh.SSHClient):
        def validate_host_public_key(self, host: str, addr: str, port: int, key) -> bool:
            return expected_fp is not None and host_key_fingerprint(key.public_data) == expected_fp

    return _PinnedHostKeyClient


def retention_items_from_names(names: dict[str, datetime]) -> list[RetentionItem]:
    """`{fayl_nomi: created_at}` — faqat o'ziniki bo'lganlarini `RetentionItem`ga aylantiradi
    (id = fayl nomi, chunki nishonda boshqa identifikator yo'q)."""
    return [RetentionItem(id=name, created_at=created_at)
            for name, created_at in names.items() if is_own_backup_file(name)]


# ------------------------------------------------------------------ S3 (boto3, ingichka qobiq)
def _s3_client(target: S3Target):
    import boto3
    from botocore.config import Config as BotoConfig

    return boto3.client(
        "s3", endpoint_url=target.endpoint or None, region_name=target.region or None,
        aws_access_key_id=target.access_key, aws_secret_access_key=target.secret_key,
        config=BotoConfig(
            s3={"addressing_style": "path" if target.path_style else "auto"},
            connect_timeout=_timeout_s(), read_timeout=_timeout_s(),
            retries={"total_max_attempts": 2, "mode": "standard"},
        ),
    )


async def test_s3(target: S3Target) -> tuple[bool, str | None]:
    def _check() -> None:
        _s3_client(target).head_bucket(Bucket=target.bucket)

    try:
        await asyncio.to_thread(_check)
        return True, None
    except Exception as exc:  # noqa: BLE001 — har qanday boto3/tarmoq xatosi `error` matniga
        return False, str(exc)[:500]


async def upload_s3(target: S3Target, local_path: Path, file_name: str) -> str:
    key = s3_key(target, file_name)

    def _upload() -> None:
        _s3_client(target).upload_file(str(local_path), target.bucket, key)

    try:
        await asyncio.to_thread(_upload)
    except Exception as exc:  # noqa: BLE001
        raise BackupTargetError(str(exc)[:500]) from exc
    return key


async def fetch_s3(target: S3Target, remote_path: str, local_path: Path) -> None:
    def _fetch() -> None:
        _s3_client(target).download_file(target.bucket, remote_path, str(local_path))

    try:
        await asyncio.to_thread(_fetch)
    except Exception as exc:  # noqa: BLE001
        raise BackupTargetError(str(exc)[:500]) from exc


async def delete_s3(target: S3Target, remote_path: str) -> None:
    def _delete() -> None:
        _s3_client(target).delete_object(Bucket=target.bucket, Key=remote_path)

    try:
        await asyncio.to_thread(_delete)
    except Exception as exc:  # noqa: BLE001
        raise BackupTargetError(str(exc)[:500]) from exc


async def list_own_s3(target: S3Target) -> list[RetentionItem]:
    prefix = target.prefix.strip("/")
    list_prefix = f"{prefix}/" if prefix else ""

    def _list() -> list[dict]:
        client = _s3_client(target)
        contents: list[dict] = []
        token = None
        while True:
            kwargs = {"Bucket": target.bucket, "Prefix": list_prefix}
            if token:
                kwargs["ContinuationToken"] = token
            resp = client.list_objects_v2(**kwargs)
            contents.extend(resp.get("Contents", []))
            if not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")
        return contents

    try:
        objects = await asyncio.to_thread(_list)
    except Exception as exc:  # noqa: BLE001
        raise BackupTargetError(str(exc)[:500]) from exc
    names = {obj["Key"].rsplit("/", 1)[-1]: obj["LastModified"] for obj in objects}
    items = retention_items_from_names(names)
    # id = fayl nomi edi — endi to'liq masofaviy kalit kerak (o'chirish uchun).
    by_name = {obj["Key"].rsplit("/", 1)[-1]: obj["Key"] for obj in objects}
    return [RetentionItem(id=by_name[item.id], created_at=item.created_at) for item in items]


# ------------------------------------------------------------------ SFTP (asyncssh, ingichka qobiq)
def _timeout_s() -> float:
    """Masofaviy nishon ulanish/o'qish chegarasi (`BACKUP_TARGET_TIMEOUT_S`) — o'chiq
    nishon zaxira/tiklash ishini cheksiz ushlab turmasin."""
    from app.core.config import settings

    return settings.backup_target_timeout_s


def _sftp_connect_kwargs(target: SftpTarget) -> dict:
    """`test_sftp` va `_sftp_connect` uchun umumiy `asyncssh.connect` argumentlari
    (host kaliti `host_key_fingerprint` bilan qo'lda tekshiriladi — `known_hosts=None`)."""
    import asyncssh

    return {
        "host": target.host, "port": target.port, "username": target.user,
        "password": target.password or None,
        "client_keys": [asyncssh.import_private_key(target.key)] if target.key else None,
        "known_hosts": None, "connect_timeout": _timeout_s(), "login_timeout": _timeout_s(),
    }


async def _sftp_connect(target: SftpTarget):
    """Haqiqiy yuklash/olish/o'chirish/sanash YO'Li — `test_sftp()`dan FARQLI, bu yerda
    host kaliti pin MAJBURIY tekshiriladi (m4b-contract.md §0: "mos kelmasa
    `host_key_mismatch`, jim qabul YO'Q") VA bu tekshiruv AUTENTIFIKATSIYADAN OLDIN
    sodir bo'ladi (`pinned_client_factory` + `known_hosts=([], [], [])`) — avval
    ulanib (parol/kalit yuborib) KEYIN solishtirish MITM'ga parolni oshkor qilardi.
    `host_key_fp` hali tasdiqlanmagan (admin «Ulanishni tekshirish» + `trust`
    qilmagan) bo'lsa ham rad etiladi (`host_key_not_trusted`), `_upload_one` buni
    nishon xatosiga aylantiradi (zaxira holati `partial`)."""
    import asyncssh

    kwargs = dict(_sftp_connect_kwargs(target))
    kwargs["known_hosts"] = ([], [], [])
    kwargs["client_factory"] = pinned_client_factory(target.host_key_fp)
    try:
        return await asyncssh.connect(**kwargs)
    except asyncssh.HostKeyNotVerifiable as exc:
        code = "host_key_mismatch" if target.host_key_fp else "host_key_not_trusted"
        raise BackupTargetError(code) from exc


async def test_sftp(target: SftpTarget) -> tuple[bool, str | None, str | None]:
    """`host_key_fp` berilmagan bo'lsa — ulanib, kuzatilgan barmoq izini qaytaradi
    (`trust` oqimi uchun); berilgan bo'lsa va mos kelmasa — `host_key_mismatch`.

    m4b-contract.md §2: `POST .../sftp/test` "yozib-o'qib-o'chirib sinaydi" — ILGARI
    buyruq qobig'ida `conn.run("true")` ishlatilardi, bu FAQAT ixtiyoriy buyruq
    bajarishga ruxsat beruvchi serverlarda ishlaydi; ko'pchilik haqiqiy SFTP serverlari
    (masalan `atmoz/sftp`, `ForceCommand internal-sftp` — xavfsizlik amaliyoti, faqat
    SFTP protokoliga ruxsat, qobiq YO'Q) buni HAR DOIM `ProcessError`/chiqish holati 1
    bilan rad etardi, garchi haqiqiy yuklash/olish/o'chirish ishlagan bo'lsa ham. Endi
    o'zi vaqtinchalik probe faylni SFTP orqali yozib-o'qib-o'chiradi (shu sabab qobiqsiz
    serverlarda ham to'g'ri ishlaydi)."""
    import tempfile
    import uuid

    import asyncssh

    probe_name = f".innova-probe-{uuid.uuid4().hex}"
    probe_path = sftp_remote_path(target, probe_name)
    try:
        async with asyncssh.connect(**_sftp_connect_kwargs(target)) as conn:
            observed = host_key_fingerprint(conn.get_server_host_key().public_data)
            async with conn.start_sftp_client() as sftp:
                with tempfile.NamedTemporaryFile() as tmp_write:
                    tmp_write.write(b"innova-probe")
                    tmp_write.flush()
                    await sftp.put(tmp_write.name, probe_path)
                with tempfile.NamedTemporaryFile() as tmp_read:
                    await sftp.get(probe_path, tmp_read.name)
                await sftp.remove(probe_path)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:500], None
    if target.host_key_fp and target.host_key_fp != observed:
        return False, "host_key_mismatch", observed
    return True, None, observed


async def upload_sftp(target: SftpTarget, local_path: Path, file_name: str) -> str:
    import asyncssh

    remote_path = sftp_remote_path(target, file_name)
    try:
        async with await _sftp_connect(target) as conn:
            async with conn.start_sftp_client() as sftp:
                await sftp.put(str(local_path), remote_path)
    except (asyncssh.Error, OSError) as exc:
        raise BackupTargetError(str(exc)[:500]) from exc
    return remote_path


async def fetch_sftp(target: SftpTarget, remote_path: str, local_path: Path) -> None:
    import asyncssh

    try:
        async with await _sftp_connect(target) as conn:
            async with conn.start_sftp_client() as sftp:
                await sftp.get(remote_path, str(local_path))
    except (asyncssh.Error, OSError) as exc:
        raise BackupTargetError(str(exc)[:500]) from exc


async def delete_sftp(target: SftpTarget, remote_path: str) -> None:
    import asyncssh

    try:
        async with await _sftp_connect(target) as conn:
            async with conn.start_sftp_client() as sftp:
                await sftp.remove(remote_path)
    except (asyncssh.Error, OSError) as exc:
        raise BackupTargetError(str(exc)[:500]) from exc


async def list_own_sftp(target: SftpTarget) -> list[RetentionItem]:
    import asyncssh

    try:
        async with await _sftp_connect(target) as conn:
            async with conn.start_sftp_client() as sftp:
                entries = await sftp.readdir(target.folder or "/")
    except (asyncssh.Error, OSError) as exc:
        raise BackupTargetError(str(exc)[:500]) from exc
    names = {entry.filename: datetime.fromtimestamp(entry.attrs.mtime, tz=timezone.utc)
             for entry in entries if entry.filename not in (".", "..")}
    items = retention_items_from_names(names)
    return [RetentionItem(id=sftp_remote_path(target, item.id), created_at=item.created_at) for item in items]
