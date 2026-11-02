"""`GET /system/status` — tizim holati (disk/trunk/internet/SIP). Router faqat
ma'lumot YIG'ADI (4 bo'limni `asyncio.gather` bilan bir vaqtda), BUTUN hisoblash
mantiqi/parsing shu yerda — testlash uchun (ub-mode: sof funksiyalar alohida)."""
from __future__ import annotations

import asyncio
import os
import re
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Extension
from app.schemas import DiskCategoryOut, SipTransportOut, SystemDiskOut, SystemInternetOut, SystemSipOut
from app.services.health import asterisk_health
from app.services.live_status import endpoint_states, run_command

_BYTES_PER_GB = 1024 ** 3


# --------------------------------------------------------------- disk
def scan_dir_sync(path: str) -> tuple[int, int]:
    """Papkani REKURSIV skanerlaydi (umumiy bayt, fayl soni) — `os.scandir`
    bloklaydi, shu sabab chaqiruvchi `asyncio.to_thread` ichida chaqirsin.
    Papka yo'q/o'qib bo'lmasa — `(0, 0)` (ro'yxatni to'xtatmaydi)."""
    total_bytes = 0
    total_files = 0
    try:
        entries = list(os.scandir(path))
    except OSError:
        return 0, 0
    for entry in entries:
        try:
            if entry.is_dir(follow_symlinks=False):
                sub_bytes, sub_files = scan_dir_sync(entry.path)
                total_bytes += sub_bytes
                total_files += sub_files
            elif entry.is_file(follow_symlinks=False):
                total_bytes += entry.stat(follow_symlinks=False).st_size
                total_files += 1
        except OSError:
            continue
    return total_bytes, total_files


# (key, papka yo'lini sozlamalardan olish, tozalash mumkinmi)
_CATEGORY_DEFS = (
    ("recordings", lambda s: s.recordings_dir, True),
    ("backups", lambda s: s.backups_dir, True),
    ("migrations", lambda s: s.migrations_dir, True),
    ("voicemail", lambda s: s.voicemail_spool_dir, False),
    ("logs", lambda s: str(Path(s.security_log_path).parent), False),
)


async def disk_categories(settings) -> list[DiskCategoryOut]:
    """Har bir toifa papkasi BIR VAQTDA (`asyncio.gather`) skanerlanadi —
    5 ta ketma-ket rekursiv skaner javobni sezilarli sekinlashtirardi."""
    dirs = [dir_fn(settings) for _, dir_fn, _ in _CATEGORY_DEFS]
    results = await asyncio.gather(*(asyncio.to_thread(scan_dir_sync, d) for d in dirs))
    return [
        DiskCategoryOut(key=key, bytes=b, files=f, cleanable=cleanable)
        for (key, _, cleanable), (b, f) in zip(_CATEGORY_DEFS, results, strict=True)
    ]


def disk_status_out(total_bytes: int, free_bytes: int, categories: list[DiskCategoryOut]) -> SystemDiskOut:
    """Sof qoida — `shutil.disk_usage` natijasi + toifalar ro'yxatidan `SystemDiskOut` quradi."""
    used_bytes = total_bytes - free_bytes
    used_pct = round(used_bytes / total_bytes * 100) if total_bytes else 0
    return SystemDiskOut(
        total_gb=round(total_bytes / _BYTES_PER_GB, 1), used_gb=round(used_bytes / _BYTES_PER_GB, 1),
        free_gb=round(free_bytes / _BYTES_PER_GB, 1), used_pct=used_pct, categories=categories,
    )


# --------------------------------------------------------------- internet
# Asterisk konteynerida DNS-resolver bo'lishi shart emas — shu sabab DNS
# VA tashqi TCP ulanish ALOHIDA tekshiriladi (ikkisi BIR VAQTDA, `asyncio.gather`).
_DNS_HOST = "google.com"
_PRIMARY_TARGET = ("1.1.1.1", 443)
_FALLBACK_TARGET = ("8.8.8.8", 53)
_CONNECT_TIMEOUT_S = 3.0


async def dns_ok(host: str = _DNS_HOST) -> bool:
    try:
        await asyncio.get_running_loop().getaddrinfo(host, 443)
    except OSError:
        return False
    return True


async def tcp_latency_ms(host: str, port: int) -> int | None:
    """`host:port`ga TCP ulanib ko'radi — muvaffaqiyat bo'lsa RTT (ms), bo'lmasa `None`
    (ulana olmaslik ham, 3s'dan ortiq kutish ham — bitta natija: ulanish yo'q)."""
    started = time.monotonic()
    try:
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=_CONNECT_TIMEOUT_S,
        )
    except (OSError, TimeoutError):
        return None
    writer.close()
    return round((time.monotonic() - started) * 1000)


async def check_internet() -> SystemInternetOut:
    """`dns_ok()`/`tcp_latency_ms()` — moslab (monkeypatch) testlash uchun ATAYLAB
    alohida, shu moduldagi public funksiyalar (testlar ularni almashtiradi)."""
    is_dns_ok, primary_ms = await asyncio.gather(dns_ok(), tcp_latency_ms(*_PRIMARY_TARGET))
    if primary_ms is not None:
        return SystemInternetOut(up=True, dns_ok=is_dns_ok, latency_ms=primary_ms,
                                  target=f"{_PRIMARY_TARGET[0]}:{_PRIMARY_TARGET[1]}", error=None)
    fallback_ms = await tcp_latency_ms(*_FALLBACK_TARGET)
    target = f"{_FALLBACK_TARGET[0]}:{_FALLBACK_TARGET[1]}"
    if fallback_ms is not None:
        return SystemInternetOut(up=True, dns_ok=is_dns_ok, latency_ms=fallback_ms, target=target, error=None)
    return SystemInternetOut(up=False, dns_ok=is_dns_ok, latency_ms=None, target=target,
                              error="Internetga ulanib bo'lmadi")


# --------------------------------------------------------------- SIP
# Jonli tasdiqlangan (`innova-m0-asterisk-1`, 2026-11-02) `pjsip show transports` chiqishi:
# "Transport:  transport-tcp             tcp      0      0  0.0.0.0:5060" — sarlavha qatori
# (`<TransportId...>`/`<Type>` literal) `\d+\s+\d+` (cos/tos) mos kelmagani sabab o'tkazib yuboriladi.
_TRANSPORT_RE = re.compile(
    r"^Transport:\s+(?P<name>\S+)\s+(?P<protocol>\S+)\s+\d+\s+\d+\s+(?P<bind>\S+)\s*$", re.MULTILINE,
)


def parse_transports(output: str) -> list[SipTransportOut]:
    return [
        SipTransportOut(name=m.group("name"), protocol=m.group("protocol"), bind=m.group("bind"))
        for m in _TRANSPORT_RE.finditer(output)
    ]


async def sip_status(ami, session: AsyncSession, tenant_id: str) -> SystemSipOut:
    """`asterisk_up` — mavjud `asterisk_health` bilan BIR XIL qoida (ub-mode DRY).
    Endpoint soni — FAQAT shu tenant ichki raqamlari (m-sip-login-plain-number:
    endpoint id = raqamning o'zi)."""
    numbers = list((await session.execute(
        select(Extension.number).where(Extension.tenant_id == tenant_id)
    )).scalars().all())
    asterisk = await asterisk_health(ami)
    transports_output = await run_command(ami, "pjsip show transports")
    transports = parse_transports(transports_output) if transports_output else []
    states = await endpoint_states(ami, numbers) if numbers else {}
    online = sum(1 for n in numbers if states.get(n, {}).get("status") == "online")
    return SystemSipOut(asterisk_up=asterisk.up, transports=transports,
                         endpoints_total=len(numbers), endpoints_online=online)
