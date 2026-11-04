"""Sana/vaqt — m12-contract.md B1: `timedatectl show` orqali holat, TZ/NTP
sozlash FAQAT `timedatectl set-timezone|set-ntp` (allowlist
`executor.py::_timedatectl_argv_ok`) + `/etc/systemd/timesyncd.conf.d/innova.conf`
atomik yozuv. TZ — `zoneinfo.available_timezones()` allowlist (ixtiyoriy
belgilar emas, ANIQ IANA nomi), NTP server — mezbon nomi (`validate.py`dagi
BIR XIL `is_valid_hostname`, `\\n`/in'eksiya himoyasi bilan) yoki IPv4."""
from __future__ import annotations

import asyncio
import ipaddress
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from zoneinfo import available_timezones

from app.netd.errors import NetdError
from app.netd.executor import CommandResult, Executor
from app.netd.validate import is_valid_hostname

TIMESYNCD_CONF_PATH = "/etc/systemd/timesyncd.conf.d/innova.conf"
MAX_NTP_SERVERS = 5
_CHRONY_CONF_PATH = "/etc/chrony/chrony.conf"
_TIMESYNCD_UNIT_PATHS = (
    "/lib/systemd/system/systemd-timesyncd.service",
    "/usr/lib/systemd/system/systemd-timesyncd.service",
)
# `available_timezones()` fayl tizimini skanerlaydi — modul yuklanganda BIR
# MARTA hisoblanadi (har so'rovda emas), chunki ro'yxat jarayon davomida
# o'zgarmaydi (tzdata paketi runtime'da yangilanmaydi).
_AVAILABLE_TIMEZONES = frozenset(available_timezones())

# Vaqt zonasi mintaqasi -> pool.ntp.org mintaqa zonasi (`FallbackNTP=`): admin
# server kiritmasa ham mashina zonasiga YAQIN internet NTP'dan sinxronlanadi.
_POOL_ZONE_BY_REGION = {"Asia": "asia", "Europe": "europe", "Africa": "africa",
                        "Australia": "oceania", "Pacific": "oceania", "America": "north-america"}
_SOUTH_AMERICA = frozenset({
    "Argentina", "Asuncion", "Bogota", "Caracas", "Cayenne", "Guayaquil", "La_Paz", "Lima",
    "Montevideo", "Paramaribo", "Punta_Arenas", "Santiago", "Sao_Paulo", "Recife", "Fortaleza",
    "Belem", "Manaus", "Cuiaba", "Campo_Grande", "Porto_Velho", "Boa_Vista", "Rio_Branco",
    "Maceio", "Araguaina", "Bahia", "Santarem", "Noronha", "Eirunepe",
})
_POOL_SIZE = 4
SYNC_WAIT_SECONDS = 10.0
_SYNC_POLL_SECONDS = 0.5
READ_TIMEOUT_S = 3.0

logger = logging.getLogger("netd")
_SYNC_UNITS = {"timesyncd": "systemd-timesyncd", "chrony": "chrony"}


@dataclass(frozen=True)
class FieldError:
    field: str
    message: str


@dataclass
class TimeValidationResult:
    errors: list[FieldError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def is_valid_timezone(value: object) -> bool:
    return isinstance(value, str) and value in _AVAILABLE_TIMEZONES


def is_valid_ntp_server(value: object) -> bool:
    """IPv4 manzil YOKI RFC1123 mezbon nomi — `validate.py`dagi hostname
    qoidasi bilan BIR XIL (`\\Z` anchor, qator ko'chirish/maxsus belgi
    in'eksiyasidan himoyalangan)."""
    if not isinstance(value, str) or not value:
        return False
    try:
        ipaddress.IPv4Address(value)
        return True
    except ValueError:
        return is_valid_hostname(value)


def validate_time_config(cfg: Any) -> TimeValidationResult:
    errors: list[FieldError] = []
    if not is_valid_timezone(getattr(cfg, "timezone", None)):
        errors.append(FieldError("timezone", "Vaqt zonasi IANA ro'yxatida topilmadi"))
    servers = getattr(cfg, "ntp_servers", None) or []
    if len(servers) > MAX_NTP_SERVERS:
        errors.append(FieldError("ntp_servers", f"Ko'pi bilan {MAX_NTP_SERVERS} ta NTP server bo'lishi mumkin"))
    else:
        for idx, server in enumerate(servers):
            if not is_valid_ntp_server(server):
                errors.append(FieldError(f"ntp_servers[{idx}]", f"Yaroqsiz NTP server: {server!r}"))
    if not isinstance(getattr(cfg, "ntp_enabled", None), bool):
        errors.append(FieldError("ntp_enabled", "ntp_enabled bool bo'lishi kerak"))
    return TimeValidationResult(errors)


def _pool_zone(tz: str) -> str | None:
    region, _, rest = tz.partition("/")
    if region == "America" and rest.split("/", 1)[0] in _SOUTH_AMERICA:
        return "south-america"
    return _POOL_ZONE_BY_REGION.get(region)


def default_ntp_servers(tz: str) -> list[str]:
    """Vaqt zonasi mintaqasidagi pool.ntp.org serverlari (`0..3.<zona>.pool.ntp.org`);
    mintaqa noma'lum (UTC, Etc/*, Atlantic/*) — global `pool.ntp.org`."""
    zone = _pool_zone(tz)
    suffix = f"{zone}.pool.ntp.org" if zone else "pool.ntp.org"
    return [f"{i}.{suffix}" for i in range(_POOL_SIZE)]


def render_timesyncd_conf(servers: list[str], fallback: list[str]) -> str:
    """`NTP=` — admin serverlari (bo'sh bo'lishi mumkin), `FallbackNTP=` — mintaqa
    pool'i: admin ro'yxati bo'sh/javobsiz bo'lsa timesyncd shularga o'tadi."""
    return "[Time]\nNTP=" + " ".join(servers) + "\nFallbackNTP=" + " ".join(fallback) + "\n"


def ntp_reply_server(text: str) -> str | None:
    """`timedatectl show-timesync` — NTP serverdan JAVOB kelgan bo'lsa (`NTPMessage`
    to'la) uning nomi, aks holda None."""
    props = parse_timedatectl_show(text)
    if not props.get("NTPMessage"):
        return None
    return props.get("ServerName") or props.get("ServerAddress") or None


def parse_timesyncd_conf(text: str) -> list[str]:
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("NTP="):
            return stripped[len("NTP="):].split()
    return []


def parse_timedatectl_show(text: str) -> dict[str, str]:
    props: dict[str, str] = {}
    for raw_line in text.splitlines():
        key, sep, value = raw_line.partition("=")
        if sep:
            props[key.strip()] = value.strip()
    return props


def detect_backend(executor: Executor) -> str:
    if executor.exists(_CHRONY_CONF_PATH):
        return "chrony"
    if any(executor.exists(p) for p in _TIMESYNCD_UNIT_PATHS):
        return "timesyncd"
    return "none"


class TimeService:
    """`m12-contract.md` B1 — o'z holatini o'zi boshqaradigan kichik servis
    (`NetdService.time`), tarmoq/firewall pending mexanizmidan MUSTAQIL —
    vaqt o'zgarishi commit-confirm talab qilmaydi (kontraktda ko'rsatilmagan,
    xavfi tarmoq/firewall'dan past: noto'g'ri TZ admin'ni qulflamaydi)."""

    def __init__(self, executor: Executor, *, readonly: bool, now_fn: Callable[[], datetime],
                 sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self.executor = executor
        self.readonly = readonly
        self._now = now_fn
        self._sleep = sleep_fn

    def _readonly_reason(self) -> str | None:
        if self.readonly:
            return "Bu serverda sana/vaqtni tahrirlash o'chirilgan (NETD_READONLY)"
        return None

    async def _read(self, argv: list[str]) -> str | None:
        """Faqat o'qiydigan `timedatectl` — qotsa yoki xato bersa `None`: holat sahifasi
        bitta yordamchi ma'lumot uchun yiqilmasin. Ikki chaqiruv (2×READ_TIMEOUT_S) API
        mijozining 10 s chegarasidan qisqa bo'lishi SHART."""
        try:
            result = await self.executor.run(argv, timeout=READ_TIMEOUT_S)
        except TimeoutError:
            logger.warning("%s %s s ichida javob bermadi", " ".join(argv), READ_TIMEOUT_S)
            return None
        return result.stdout if result.ok else None

    async def _props(self) -> dict[str, str]:
        return parse_timedatectl_show(await self._read(["timedatectl", "show"]) or "")

    async def _timesync_server(self) -> str | None:
        return ntp_reply_server(await self._read(["timedatectl", "show-timesync"]) or "")

    async def state(self) -> dict[str, Any]:
        props = await self._props()
        tz = props.get("Timezone") or "UTC"
        backend = detect_backend(self.executor)
        return {
            "now_utc": self._now().astimezone(timezone.utc).isoformat(),
            "timezone": tz,
            "ntp_enabled": props.get("NTP") == "yes",
            "ntp_servers": parse_timesyncd_conf(self.executor.read_text(TIMESYNCD_CONF_PATH) or ""),
            "default_ntp_servers": default_ntp_servers(tz),
            "synced": props.get("NTPSynchronized") == "yes",
            "sync_server": await self._timesync_server() if backend == "timesyncd" else None,
            "backend": backend,
            "readonly_reason": self._readonly_reason(),
        }

    def _ensure_writable(self) -> None:
        if self.readonly:
            # `self.readonly` True bo'lganda `_readonly_reason()` doim xabar qaytaradi.
            raise NetdError("readonly", self._readonly_reason())

    async def _must_run(self, argv: list[str]) -> CommandResult:
        result = await self.executor.run(argv, timeout=10.0)
        if not result.ok:
            raise NetdError("command_failed", f"{' '.join(argv)}: {result.stderr.strip() or 'xato'}")
        return result

    async def _restart_sync_unit(self) -> None:
        unit = _SYNC_UNITS.get(detect_backend(self.executor))
        if unit is None:
            raise NetdError("unsupported", "Serverda vaqt sinxronlash xizmati (timesyncd/chrony) topilmadi")
        await self._must_run(["systemctl", "restart", unit])

    async def apply(self, config: Any) -> dict[str, Any]:
        self._ensure_writable()
        result = validate_time_config(config)
        if not result.ok:
            raise NetdError("invalid_config", "Sana/vaqt sozlamasi yaroqsiz",
                             [{"field": e.field, "message": e.message} for e in result.errors])
        await self._must_run(["timedatectl", "set-timezone", config.timezone])
        self.executor.write_text_atomic(TIMESYNCD_CONF_PATH, render_timesyncd_conf(
            list(config.ntp_servers or []), default_ntp_servers(config.timezone)))
        await self._must_run(["timedatectl", "set-ntp", "true" if config.ntp_enabled else "false"])
        if config.ntp_enabled and detect_backend(self.executor) in _SYNC_UNITS:
            # Yangi server ro'yxati faqat qayta ishga tushganda o'qiladi.
            await self._restart_sync_unit()
        return await self.state()

    async def sync_now(self) -> dict[str, Any]:
        """«Hozir sinxronlash»: xizmatni qayta ishga tushirib, timesyncd'da NTP
        serverdan haqiqiy JAVOB kelguncha (`SYNC_WAIT_SECONDS`) kutadi."""
        self._ensure_writable()
        if (await self._props()).get("NTP") != "yes":
            raise NetdError("ntp_disabled", "Avval NTP sinxronlashni yoqing va saqlang")
        await self._restart_sync_unit()
        if detect_backend(self.executor) == "timesyncd" and not await self._wait_ntp_reply():
            raise NetdError("sync_failed", "NTP serverdan javob kelmadi — internet va UDP 123 portini tekshiring")
        return await self.state()

    async def _wait_ntp_reply(self) -> bool:
        for _ in range(int(SYNC_WAIT_SECONDS / _SYNC_POLL_SECONDS)):
            if await self._timesync_server():
                return True
            await self._sleep(_SYNC_POLL_SECONDS)
        return False
