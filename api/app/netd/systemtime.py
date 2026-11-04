"""Sana/vaqt — m12-contract.md B1: `timedatectl show` orqali holat, TZ/NTP
sozlash FAQAT `timedatectl set-timezone|set-ntp` (allowlist
`executor.py::_timedatectl_argv_ok`) + `/etc/systemd/timesyncd.conf.d/innova.conf`
atomik yozuv. TZ — `zoneinfo.available_timezones()` allowlist (ixtiyoriy
belgilar emas, ANIQ IANA nomi), NTP server — mezbon nomi (`validate.py`dagi
BIR XIL `is_valid_hostname`, `\\n`/in'eksiya himoyasi bilan) yoki IPv4."""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from zoneinfo import available_timezones

from app.netd.errors import NetdError
from app.netd.executor import Executor
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


def render_timesyncd_conf(servers: list[str]) -> str:
    return "[Time]\nNTP=" + " ".join(servers) + "\n"


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

    def __init__(self, executor: Executor, *, readonly: bool, now_fn: Callable[[], datetime]) -> None:
        self.executor = executor
        self.readonly = readonly
        self._now = now_fn

    def _readonly_reason(self) -> str | None:
        if self.readonly:
            return "Bu serverda sana/vaqtni tahrirlash o'chirilgan (NETD_READONLY)"
        return None

    async def state(self) -> dict[str, Any]:
        result = await self.executor.run(["timedatectl", "show"], timeout=5.0)
        props = parse_timedatectl_show(result.stdout) if result.ok else {}
        ntp_servers = parse_timesyncd_conf(self.executor.read_text(TIMESYNCD_CONF_PATH) or "")
        return {
            "now_utc": self._now().astimezone(timezone.utc).isoformat(),
            "timezone": props.get("Timezone") or "UTC",
            "ntp_enabled": props.get("NTP") == "yes",
            "ntp_servers": ntp_servers,
            "synced": props.get("NTPSynchronized") == "yes",
            "backend": detect_backend(self.executor),
            "readonly_reason": self._readonly_reason(),
        }

    async def apply(self, config: Any) -> dict[str, Any]:
        if self.readonly:
            # `self.readonly` True bo'lganda `_readonly_reason()` doim xabar qaytaradi.
            raise NetdError("readonly", self._readonly_reason())
        result = validate_time_config(config)
        if not result.ok:
            raise NetdError("invalid_config", "Sana/vaqt sozlamasi yaroqsiz",
                             [{"field": e.field, "message": e.message} for e in result.errors])
        await self.executor.run(["timedatectl", "set-timezone", config.timezone], timeout=5.0)
        self.executor.write_text_atomic(TIMESYNCD_CONF_PATH, render_timesyncd_conf(list(config.ntp_servers or [])))
        await self.executor.run(["timedatectl", "set-ntp", "true" if config.ntp_enabled else "false"], timeout=5.0)
        return await self.state()
