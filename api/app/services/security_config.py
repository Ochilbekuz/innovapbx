"""M2c §1 — `system_settings.sip_guard` / `toll_fraud` / `telegram` JSONB shakli,
standart qiymatlar va chegaralar — YAGONA joy (API, fon vazifalari, compiler shu yerdan o'qiydi).

`parse_*` bazadagi (eski/qisman) JSON'ni to'liq konfiguratsiyaga aylantiradi —
noma'lum kalit e'tiborsiz, yetishmagani standart. `validate_*` PATCH payloadini
tekshiradi va 422 uchun `(field, message)` qaytaradi."""
from __future__ import annotations

import ipaddress
import re
from dataclasses import asdict, dataclass, field, replace

ALERT_KINDS = ("ip_banned", "toll_blocked", "concurrent_limit", "trunk_down", "trunk_up",
               "webhook_disabled", "recording_error",  # M3b
               "prov_bruteforce",  # M4a
               "backup_failed", "backup_stale")  # M4b
ALWAYS_TRUSTED = ("127.0.0.0/8",)
_CHAT_ID = re.compile(r"^-?\d{1,20}$")


@dataclass(frozen=True)
class SipGuardConfig:
    enabled: bool = True
    max_failures: int = 5
    window_s: int = 60
    ban_s: int = 3600          # 0 = muddatsiz
    trusted_nets: tuple[str, ...] = ()
    # LAN (RFC1918/ULA/link-local) qurilmalari avtomatik bloklanmaydi (FreePBX'dagi «Local» zona kabi):
    # telefonga noto'g'ri login yozilsa ofis IP'si 1 soat 403 olib, to'g'ri parol ham «xato» bo'lib qolardi.
    # Urinishlar baribir statistikada sanaladi; qo'lda bloklash mumkin.
    trust_lan: bool = True


@dataclass(frozen=True)
class TollFraudConfig:
    enabled: bool = True
    max_concurrent_outbound: int = 0       # 0 = cheksiz (dialplan qatorlari chiqmaydi)
    ext_max_per_hour: int = 60             # 0 = cheksiz
    ext_international_per_day: int = 20    # 0 = cheksiz


@dataclass(frozen=True)
class AlertConfig:
    chat_ids: tuple[str, ...] = ()
    dedup_s: int = 600
    events: dict[str, bool] = field(default_factory=lambda: {k: True for k in ALERT_KINDS})


# (min, max) — `0` alohida ruxsat etilganlar `_ZERO_OK`da.
_LIMITS: dict[str, tuple[int, int]] = {
    "sip_guard.max_failures": (3, 100),
    "sip_guard.window_s": (10, 3600),
    "sip_guard.ban_s": (10, 2_592_000),
    "toll_fraud.max_concurrent_outbound": (1, 500),
    "toll_fraud.ext_max_per_hour": (1, 10_000),
    "toll_fraud.ext_international_per_day": (1, 10_000),
    "telegram.dedup_s": (0, 86_400),
}
_ZERO_OK = {"sip_guard.ban_s", "toll_fraud.max_concurrent_outbound", "toll_fraud.ext_max_per_hour",
            "toll_fraud.ext_international_per_day"}


def _merge(defaults, raw: dict | None, *, tuples: tuple[str, ...] = ()):
    raw = raw or {}
    known = {k: v for k, v in raw.items() if k in asdict(defaults)}
    for k in tuples:
        if k in known:
            known[k] = tuple(known[k] or ())
    return replace(defaults, **known)


def parse_sip_guard(raw: dict | None) -> SipGuardConfig:
    return _merge(SipGuardConfig(), raw, tuples=("trusted_nets",))


def parse_toll_fraud(raw: dict | None) -> TollFraudConfig:
    return _merge(TollFraudConfig(), raw)


def parse_alerts(raw: dict | None) -> AlertConfig:
    cfg = _merge(AlertConfig(), raw, tuples=("chat_ids",))
    events = {k: True for k in ALERT_KINDS} | {k: bool(v) for k, v in (cfg.events or {}).items() if k in ALERT_KINDS}
    return replace(cfg, events=events)


def to_json(cfg) -> dict:
    """Bazaga yozish uchun (tuple → list)."""
    return {k: list(v) if isinstance(v, tuple) else v for k, v in asdict(cfg).items()}


def check_int(path: str, value) -> str | None:
    """Butun son chegarasi — xato matni yoki None."""
    if isinstance(value, bool) or not isinstance(value, int):
        return "Butun son bo'lishi kerak"
    if value == 0 and path in _ZERO_OK:
        return None
    lo, hi = _LIMITS[path]
    if not lo <= value <= hi:
        extra = " yoki 0" if path in _ZERO_OK else ""
        return f"{lo}..{hi}{extra} oralig'ida bo'lishi kerak"
    return None


def check_nets(nets: list[str]) -> str | None:
    if len(nets) > 50:
        return "Ko'pi bilan 50 ta tarmoq"
    for net in nets:
        try:
            ipaddress.ip_network(net, strict=False)
        except ValueError:
            return f"Noto'g'ri tarmoq: {net}"
    return None


def check_chat_ids(chat_ids: list[str]) -> str | None:
    if len(chat_ids) > 10:
        return "Ko'pi bilan 10 ta chat"
    bad = next((c for c in chat_ids if not _CHAT_ID.match(str(c))), None)
    return f"Noto'g'ri chat ID: {bad}" if bad is not None else None


def is_lan(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return addr.is_private or addr.is_link_local


def is_trusted(ip: str, trusted_nets: tuple[str, ...] | list[str]) -> bool:
    addr = ipaddress.ip_address(ip)
    for net in (*ALWAYS_TRUSTED, *trusted_nets):
        try:
            if addr in ipaddress.ip_network(net, strict=False):
                return True
        except ValueError:
            continue
    return False
