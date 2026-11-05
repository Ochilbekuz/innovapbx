"""M4a §1 — `system_settings.provisioning` (jsonb) bo'limi: sukutlar, o'qish va maydon validatsiyasi (SOF, bazasiz).

`prov_token` — 32 hex belgi (tenant uchun bitta, URL'ning maxfiy segmenti). `admin_password_enc` — pgcrypto shifr
(faqat yoziladi; API `has_admin_password` qaytaradi). `extra` — vendor uchun xom qatorlar (admin o'z xavfi bilan),
lekin QATOR FORMATI tekshiriladi:
  * Yealink — `key = value` (kalit `[A-Za-z0-9_.]+`), `#` izoh qatorlari ruxsat;
  * Grandstream — `Pnnn=value` (`P` + raqam; kengaytirilgan XML aliaslar M4a da yo'q);
  * Fanvil — Fanvil fayl formati: `<BO'LIM NOMI>` sarlavhasi yoki `Kalit nomi :qiymat` (Fanvil `=` emas, `:` ishlatadi —
    shartnomadagi «`key = value`» dan ongli chetlanish: aks holda apparat qatorni tushunmaydi).
"""
from __future__ import annotations

import ipaddress
import re
import secrets
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.services.prov_catalog import VENDORS

DEFAULT_NETWORKS: tuple[str, ...] = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
LANGUAGES = ("uz", "ru", "en")
TRANSPORTS = ("udp", "tcp", "tls")
MAX_EXTRA_LINES = 200
MAX_NETWORKS = 50

_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")
_HOST_RE = re.compile(r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$")
_EXTRA_LINE_RE = {
    "yealink": re.compile(r"^(#.*|[A-Za-z0-9_.]+\s*=\s*.*)$"),
    "grandstream": re.compile(r"^P\d{1,5}\s*=.*$"),
    "fanvil": re.compile(r"^(<[A-Z0-9 _<>-]+>|[A-Za-z0-9][A-Za-z0-9 _.-]*:.*)$"),
}


# bo'sh/yo'q qiymat → dataclass sukuti (`from_raw`)
_DEFAULTED_FIELDS = ("admin_password_enc", "language", "timezone", "ntp_server", "sip_transport", "sip_server_host")


class ProvSettingsError(ValueError):
    def __init__(self, field_name: str, message: str) -> None:
        super().__init__(message)
        self.field = field_name
        self.message = message


def new_token() -> str:
    return secrets.token_hex(16)


@dataclass(frozen=True)
class ProvSettings:
    prov_token: str
    allowed_networks: tuple[str, ...] = DEFAULT_NETWORKS
    admin_password_enc: str | None = None
    language: str = "uz"
    timezone: str = "Asia/Tashkent"
    ntp_server: str = "pool.ntp.org"
    sip_transport: str = "udp"
    sip_server_host: str | None = None
    extra: dict[str, str] = field(default_factory=lambda: {vendor: "" for vendor in VENDORS})

    @classmethod
    def from_raw(cls, raw: dict | None) -> "ProvSettings":
        """Bazadagi jsonb → sukutlar bilan to'ldirilgan qiymat (0020 dan oldingi/qisman qatorlar ham ishlaydi)."""
        data = dict(raw or {})
        nets = data.get("allowed_networks")
        extra = data.get("extra") or {}
        return cls(
            prov_token=str(data.get("prov_token") or ""),
            allowed_networks=DEFAULT_NETWORKS if nets is None else tuple(nets),
            extra={vendor: str(extra.get(vendor) or "") for vendor in VENDORS},
            **{name: data.get(name) or getattr(cls, name) for name in _DEFAULTED_FIELDS},
        )

    def to_raw(self) -> dict:
        return {"prov_token": self.prov_token, "allowed_networks": list(self.allowed_networks),
                "admin_password_enc": self.admin_password_enc, "language": self.language,
                "timezone": self.timezone, "ntp_server": self.ntp_server, "sip_transport": self.sip_transport,
                "sip_server_host": self.sip_server_host, "extra": dict(self.extra)}

    def has_valid_token(self) -> bool:
        return bool(_TOKEN_RE.fullmatch(self.prov_token))


# ------------------------------------------------------------------ validatsiya
def validate_networks(values: list[str]) -> tuple[str, ...]:
    """CIDR ro'yxati → normallashtirilgan (`10.1.2.3/8` → `10.0.0.0/8`), dublikatsiz, tartib saqlanadi."""
    if len(values) > MAX_NETWORKS:
        raise ProvSettingsError("allowed_networks", f"Ko'pi bilan {MAX_NETWORKS} ta tarmoq")
    out: list[str] = []
    for value in values:
        try:
            net = str(ipaddress.ip_network(str(value).strip(), strict=False))
        except ValueError as exc:
            raise ProvSettingsError("allowed_networks", f"Noto'g'ri CIDR: {value}") from exc
        if net not in out:
            out.append(net)
    return tuple(out)


def validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ProvSettingsError("timezone", f"Noma'lum vaqt zonasi: {value}") from exc
    return value


def effective_timezone(raw: dict | None, cfg: ProvSettings, tenant_timezone: str) -> str:
    """Admin provizioning vaqt zonasini ANIQ tanlamagan bo'lsa (`raw`da yo'q/bo'sh — `from_raw`
    shunda sukut `"Asia/Tashkent"`ni qo'yadi) — qattiq Toshkent o'rniga HAQIQIY tizim/tenant
    vaqt zonasiga bog'laymiz (`Tenant.timezone`, "Sana va vaqt" sahifasida tanlangan). Admin buni
    ANIQ oʻzgartirgan bo'lsa — oʻz tanlovi saqlanadi (bog'lanish faqat sukut holatda ishlaydi)."""
    return cfg.timezone if (raw or {}).get("timezone") else tenant_timezone


def is_host(value: str) -> bool:
    """Hostname yoki IP manzil (port/sxema/yo'l YO'Q)."""
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return bool(_HOST_RE.fullmatch(value))


def validate_host(field_name: str, value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if not is_host(text):
        raise ProvSettingsError(field_name, "Host nomi yoki IP manzil kutilgan (sxema/port/yo'lsiz)")
    return text


def validate_extra(vendor: str, text: str) -> str:
    """Har bo'sh bo'lmagan qator vendor formatiga mos bo'lishi shart; `\\r` olib tashlanadi."""
    lines = [line.rstrip("\r") for line in (text or "").split("\n")]
    meaningful = [line for line in lines if line.strip()]
    if len(meaningful) > MAX_EXTRA_LINES:
        raise ProvSettingsError(f"extra.{vendor}", f"Ko'pi bilan {MAX_EXTRA_LINES} qator")
    pattern = _EXTRA_LINE_RE[vendor]
    for number, line in enumerate(lines, start=1):
        if line.strip() and not pattern.fullmatch(line.strip()):
            raise ProvSettingsError(f"extra.{vendor}", f"{number}-qator formati noto'g'ri")
    return "\n".join(meaningful)


def ip_allowed(ip: str | None, networks: tuple[str, ...]) -> bool:
    """Bo'sh ro'yxat = hammasi ruxsat. IP aniqlanmasa (yoki yaroqsiz) — rad (xavfsiz tomonga)."""
    if not networks:
        return True
    try:
        address = ipaddress.ip_address(ip or "")
    except ValueError:
        return False
    return any(address in ipaddress.ip_network(net, strict=False) for net in networks)
