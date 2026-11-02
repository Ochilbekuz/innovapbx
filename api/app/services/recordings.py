"""Qo'ng'iroq yozuvlari (m3b-contract.md §1): fayllarni `call_recordings`ga olish, imzoli
havola, saqlash muddati tozalovchisi.

Fayl yo'li (dialplan `innova-rec-start`): `<recordings_dir>/innova/YYYY/MM/DD/<linkedid>-<uniqueid>.wav`
(UTC sana — yozuv BOSHLANGAN kun). Qo'ng'iroq tugagach (`call.ended` vaqtida, oxirgi kanal yopilgandan
≥ 2 s keyin — MixMonitor faylni yopgan) API shu linkedid fayllarini topib jadvalga yozadi.
"""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import logging
import uuid
import wave
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import CallRecording, Cdr, SystemSettings
from app.services.sip_identity import extension_from_channel

log = logging.getLogger(__name__)

RECORDING_SUBDIR = "innova"
_LINK_DOMAIN = b"innova-recording-link-v1"
DEFAULT_LINK_TTL_S = 7 * 24 * 3600


# ------------------------------------------------------------ imzoli havola (sof)
def _link_key(secret_key: str) -> bytes:
    """`SECRET_KEY`dan domen-ajratilgan kalit — JWT imzosi bilan aralashmaydi."""
    return hmac.new(secret_key.encode(), _LINK_DOMAIN, hashlib.sha256).digest()


def link_signature(recording_id: str, exp: int, secret_key: str) -> str:
    return hmac.new(_link_key(secret_key), f"{recording_id}.{exp}".encode(), hashlib.sha256).hexdigest()


def verify_link(recording_id: str, exp: int, sig: str, *, now_unix: int, secret_key: str) -> bool:
    if exp <= now_unix:
        return False
    return hmac.compare_digest(link_signature(recording_id, exp, secret_key), sig)


def signed_url(public_base_url: str, recording_id: str, *, ttl_s: int, now_unix: int, secret_key: str) -> str | None:
    base = public_base_url.rstrip("/")
    if not base:
        return None
    exp = now_unix + ttl_s
    return f"{base}/api/public/v1/recordings/{recording_id}?exp={exp}&sig={link_signature(recording_id, exp, secret_key)}"


# ------------------------------------------------------------ yo'llar (sof)
def date_dirs(started_at: datetime, ended_at: datetime) -> list[str]:
    """Yozuv boshlangan kun(lar) katalogi — yarim tundan o'tgan qo'ng'iroq ikkala kunda qidiriladi."""
    day = started_at.astimezone(timezone.utc).date()
    last = ended_at.astimezone(timezone.utc).date()
    out = []
    while day <= last:
        out.append(f"{RECORDING_SUBDIR}/{day:%Y/%m/%d}")
        day += timedelta(days=1)
    return out


def uniqueid_from_name(filename: str, linkedid: str) -> str | None:
    head = f"{linkedid}-"
    if not filename.startswith(head) or not filename.endswith(".wav"):
        return None
    return filename[len(head):-4] or None


def retention_cutoff(now: datetime, retention_days: int) -> datetime:
    return now - timedelta(days=retention_days)


def wav_duration_s(path: Path) -> int:
    try:
        with contextlib.closing(wave.open(str(path), "rb")) as wav:
            rate = wav.getframerate() or 1
            return round(wav.getnframes() / rate)
    except (wave.Error, EOFError, OSError):
        return 0


def absolute_path(relative: str) -> Path:
    return Path(settings.recordings_dir) / relative


# ------------------------------------------------------------ baza
def _scan(linkedid: str, dirs: Iterable[str]) -> list[tuple[str, str, Path]]:
    found = []
    for rel_dir in dirs:
        folder = absolute_path(rel_dir)
        for path in sorted(folder.glob(f"{linkedid}-*.wav")):
            uniqueid = uniqueid_from_name(path.name, linkedid)
            if uniqueid:
                found.append((f"{rel_dir}/{path.name}", uniqueid, path))
    return found


async def ingest_call(session: AsyncSession, *, tenant_id: str, linkedid: str, started_at: datetime,
                      ended_at: datetime, extension: str | None) -> list[CallRecording]:
    """Diskdagi `<linkedid>-*.wav` fayllarini jadvalga (takror — e'tiborsiz) va faol yozuvlarni qaytaradi."""
    files = await asyncio.to_thread(_scan, linkedid, date_dirs(started_at, ended_at))
    for rel, uniqueid, path in files:
        stat = await asyncio.to_thread(path.stat)
        duration = await asyncio.to_thread(wav_duration_s, path)
        await session.execute(pg_insert(CallRecording).values(
            tenant_id=tenant_id, linkedid=linkedid, uniqueid=uniqueid, path=rel, extension=extension,
            started_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc) - timedelta(seconds=duration),
            duration_s=duration, size_bytes=stat.st_size,
        ).on_conflict_do_nothing(index_elements=["path"]))
    return await active_for(session, tenant_id, [linkedid])


async def active_for(session: AsyncSession, tenant_id: str, linkedids: list[str]) -> list[CallRecording]:
    if not linkedids:
        return []
    return list((await session.execute(select(CallRecording).where(
        CallRecording.tenant_id == tenant_id, CallRecording.linkedid.in_(linkedids),
        CallRecording.deleted_at.is_(None),
    ).order_by(CallRecording.started_at))).scalars().all())


async def attach_recordings(session: AsyncSession, tenant_id: str, calls: list) -> list:
    """`/calls`, `/me/calls` sahifasidagi qo'ng'iroqlarga `recordings: [{id, duration_s}]` (linkedid bo'yicha)."""
    by_linkedid: dict[str, list[dict]] = {}
    for rec in await active_for(session, tenant_id, sorted({c.linkedid for c in calls if c.linkedid})):
        by_linkedid.setdefault(rec.linkedid, []).append({"id": str(rec.id), "duration_s": rec.duration_s})
    for call in calls:
        call.recordings = by_linkedid.get(call.linkedid or "", [])
    return calls


async def link_settings(session: AsyncSession, tenant_id: str) -> tuple[str, int]:
    row = await session.get(SystemSettings, tenant_id)
    cfg = (row.integrations if row else None) or {}
    return str(cfg.get("public_base_url") or ""), int(cfg.get("recording_link_ttl_s") or DEFAULT_LINK_TTL_S)


async def recording_refs(session: AsyncSession, tenant_id: str, recs: list[CallRecording]) -> list[dict]:
    """Hodisa payload'i uchun `[{id, duration_s, url}]` (`url` — imzoli havola yoki `null`)."""
    base, ttl = await link_settings(session, tenant_id)
    now_unix = int(datetime.now(timezone.utc).timestamp())
    secret = settings.require_secret_key()
    return [{"id": str(r.id), "duration_s": r.duration_s,
             "url": signed_url(base, str(r.id), ttl_s=ttl, now_unix=now_unix, secret_key=secret)} for r in recs]


# ------------------------------------------------------------ kirish (admin/operator/ochiq API)
def leg_mentions(number: str, code: str, *, src: str | None, dst: str | None, channel: str | None,
                 dstchannel: str | None) -> bool:
    """CDR qatorida shu ichki raqam qatnashganmi (raqam yoki kanal nomida) —
    `code` endi kanal taqqoslashda ishlatilmaydi (imzo o'zgarmaydi, chaqiruvchilar
    ko'p): `sip_identity.extension_from_channel` YANGI (`PJSIP/103-...`) VA
    ESKI (`PJSIP/t1-103-...`) shakllarning ikkisini ham bir xil tanib oladi."""
    del code
    return number in (src, dst) or number in (extension_from_channel(channel), extension_from_channel(dstchannel))


async def operator_can_access(session: AsyncSession, rec: CallRecording, *, code: str, number: str | None) -> bool:
    """Operator — faqat o'z raqami qatnashgan qo'ng'iroq yozuvi (m3b-contract.md §1)."""
    if not number:
        return False
    if rec.extension == number:
        return True
    rows = (await session.execute(select(Cdr.src, Cdr.dst, Cdr.channel, Cdr.dstchannel).where(
        Cdr.accountcode == code, or_(Cdr.linkedid == rec.linkedid, Cdr.uniqueid == rec.linkedid)))).all()
    return any(leg_mentions(number, code, src=r[0], dst=r[1], channel=r[2], dstchannel=r[3]) for r in rows)


async def get_active(session: AsyncSession, tenant_id: str, recording_id: str) -> CallRecording | None:
    try:
        rid = str(uuid.UUID(recording_id))
    except ValueError:
        return None
    rec = await session.get(CallRecording, rid)
    if rec is None or str(rec.tenant_id) != str(tenant_id) or rec.deleted_at is not None:
        return None
    return rec


def file_name(rec: CallRecording) -> str:
    return f"{rec.linkedid}-{rec.uniqueid}.wav"


# ------------------------------------------------------------ saqlash muddati
def unlink_file(path: Path) -> None:
    with contextlib.suppress(FileNotFoundError):
        path.unlink()


# `purge_tenant` bir chaqiruvda ko'pi bilan shuncha qatorni o'chiradi (juda katta
# tenant uchun bitta so'rov cheksiz uzoq ketmasin) — `/system/cleanup` shu
# chegaraga qarab natija to'liq bo'lmaganini aniqlaydi (loop kerakligini).
PURGE_BATCH_LIMIT = 5000


async def purge_candidates(session: AsyncSession, tenant_id: str, retention_days: int, now: datetime,
                            ) -> list[CallRecording]:
    """O'chirish NOMZODLARI — fayl/bazaga TEGMAYDI (faqat o'qiydi). `/system/cleanup/preview`
    bayt/fayl sonini shu ro'yxatdan hisoblaydi; haqiqiy o'chirish `purge_tenant`da."""
    return list((await session.execute(select(CallRecording).where(
        CallRecording.tenant_id == tenant_id, CallRecording.deleted_at.is_(None),
        CallRecording.started_at < retention_cutoff(now, retention_days),
    ))).scalars().all())


async def purge_tenant(session: AsyncSession, tenant_id: str, retention_days: int, now: datetime) -> tuple[int, list[str]]:
    """Muddati o'tgan fayllar o'chiriladi va `deleted_at` qo'yiladi; disk xatosi — qator qoladi, xato qaytadi."""
    rows = (await session.execute(select(CallRecording).where(
        CallRecording.tenant_id == tenant_id, CallRecording.deleted_at.is_(None),
        CallRecording.started_at < retention_cutoff(now, retention_days),
    ).limit(PURGE_BATCH_LIMIT))).scalars().all()
    errors: list[str] = []
    for row in rows:
        try:
            await asyncio.to_thread(unlink_file, absolute_path(row.path))
        except OSError as exc:
            errors.append(f"{row.path}: {exc.strerror or exc}")
            continue
        row.deleted_at = now
    return len(rows) - len(errors), errors


async def purge_once(session_factory) -> int:
    from app.services.alerts import alert_text, raise_alert, tenant_language

    now = datetime.now(timezone.utc)
    removed = 0
    async with session_factory() as session:
        tenants = (await session.execute(select(SystemSettings.tenant_id, SystemSettings.recording_retention_days))).all()
        for tenant_id, days in tenants:
            count, errors = await purge_tenant(session, str(tenant_id), int(days or 365), now)
            removed += count
            if errors:
                lang = await tenant_language(session, str(tenant_id))
                text = alert_text(lang, "recording_error", error=f"({len(errors)}) {errors[0]}"[:300])
                await raise_alert(session, str(tenant_id), "recording_error", "purge", text)
        await session.commit()
    return removed


async def run_forever(session_factory, interval_s: float) -> None:
    from app.services import maintenance

    while True:
        if maintenance.state.enabled:
            await asyncio.sleep(interval_s)
            continue
        try:
            removed = await purge_once(session_factory)
            if removed:
                log.info("recording_purge: %d fayl o'chirildi", removed)
        except Exception:  # noqa: BLE001 — fon vazifa yiqilmasin
            log.exception("recording_purge xatosi")
        await asyncio.sleep(interval_s)
