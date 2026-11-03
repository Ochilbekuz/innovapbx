"""NetworkConfigIn tekshiruvi — m8-network-contract.md bo'lim 4 (har bir
qoida alohida sof funksiya — `check_access`/`permissions.py` uslubida unit
testlanadi). Chaqiruvchi (`service.py`) natijani 422 `ApiError.details` ga
yoki `/validate` javobiga quyadi."""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field

from app.netd.ifupdown import RouteSpec
from app.netd.live import LiveInterface

# `\Z` (mutlaq oxir), `$` EMAS — Python `re`da `$` oxirgi `\n`dan OLDIN ham
# mos keladi (`"a\n"` ga mos tushadi), bu orqali mezbon nomiga ortiqcha
# qatorli in'eksiya o'tib ketishi mumkin edi.
_HOSTNAME_LABEL_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\Z")
# Linux IFNAMSIZ = 16 (NUL bilan) -> 15 belgigacha nom; API `schemas.py`dagi
# `_IFACE_NAME_RE` bilan BIR XIL qoida — netd API'ga ishonmagani uchun shu
# yerda MUSTAQIL qayta tekshiradi.
_IFACE_NAME_RE = re.compile(r"^[a-zA-Z0-9._:-]{1,15}\Z")
DEFAULT_ROUTE = "0.0.0.0/0"
EDITABLE_KINDS = frozenset({"ethernet", "bond", "vlan"})
MTU_MIN, MTU_MAX = 68, 9000


@dataclass(frozen=True)
class FieldError:
    field: str
    message: str


@dataclass
class ValidationResult:
    errors: list[FieldError] = field(default_factory=list)
    resolved_routes: dict[str, list[RouteSpec]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def is_valid_iface_name(name: object) -> bool:
    return isinstance(name, str) and bool(_IFACE_NAME_RE.match(name))


def is_valid_hostname(name: str) -> bool:
    """RFC1123: har bir label 1..63 belgi, alfa-raqamli + chiziqcha (boshi/
    oxiri chiziqcha emas), to'liq nom <=253 belgi."""
    if not name or len(name) > 253:
        return False
    return all(_HOSTNAME_LABEL_RE.match(label) for label in name.split("."))


def _ipv4_network_of(cidr: object) -> ipaddress.IPv4Network | None:
    """Faqat IPv4 CIDR qabul qiladi (scope-id'li IPv6 — masalan
    `fe80::1%zone\\npre-up ...` — `ipaddress.ip_interface` orqali O'TIB
    KETARDI, chunki IPv6 scope-id ichida bo'sh joy/qator ko'chirish
    taqiqlanmagan; `IPv4Interface` bunday satrni umuman tushunmaydi)."""
    if not isinstance(cidr, str):
        return None
    try:
        return ipaddress.IPv4Interface(cidr).network
    except ValueError:
        return None


def _ipv4_address_of(value: object) -> ipaddress.IPv4Address | None:
    if not isinstance(value, str):
        return None
    try:
        return ipaddress.IPv4Address(value)
    except ValueError:
        return None


def _is_safe_mtu(mtu: object) -> bool:
    return isinstance(mtu, int) and not isinstance(mtu, bool) and MTU_MIN <= mtu <= MTU_MAX


def _validate_mtu(prefix: str, mtu: object, errors: list[FieldError]) -> None:
    if mtu is not None and not _is_safe_mtu(mtu):
        errors.append(FieldError(f"{prefix}.mtu", f"MTU butun son bo'lishi va {MTU_MIN}..{MTU_MAX} oralig'ida bo'lishi kerak"))


def _validate_dns(cfg, errors: list[FieldError]) -> None:
    """API qatlamiga ishonmaydi — `dns.servers`/`dns.search` shu yerda
    QAYTA tekshiriladi (soketdan to'g'ridan-to'g'ri `SimpleNamespace`
    sifatida kelgan bo'lishi mumkin)."""
    dns = getattr(cfg, "dns", None)
    if dns is None:
        return
    for idx, server in enumerate(getattr(dns, "servers", None) or []):
        if _ipv4_address_of(server) is None:
            errors.append(FieldError(f"dns.servers[{idx}]", "DNS server manzili yaroqsiz IPv4"))
    for idx, domain in enumerate(getattr(dns, "search", None) or []):
        if not isinstance(domain, str) or not is_valid_hostname(domain):
            errors.append(FieldError(f"dns.search[{idx}]", "Domen nomi RFC1123 talablariga mos emas"))


def _validate_hostname(cfg, errors: list[FieldError]) -> None:
    if not is_valid_hostname(cfg.hostname):
        errors.append(FieldError("hostname", "Mezbon nomi RFC1123 talablariga mos emas"))


def _validate_one_interface(idx: int, iface, known: dict[str, LiveInterface],
                             errors: list[FieldError]) -> tuple[str, str] | None:
    """Bitta interfeysni tekshiradi. Muvaffaqiyatli statik interfeys —
    `(nom, subnet)`; aks holda `None` (xato allaqachon `errors`ga qo'shilgan,
    yoki interfeys dhcp bo'lib subnetga ega bo'lmaydi)."""
    prefix = f"interfaces[{idx}]"
    if not is_valid_iface_name(iface.name):
        errors.append(FieldError(f"{prefix}.name", "Interfeys nomi yaroqsiz"))
        return None
    live = known.get(iface.name)
    if live is None:
        errors.append(FieldError(f"{prefix}.name", f"Interfeys topilmadi: {iface.name}"))
        return None
    if live.kind not in EDITABLE_KINDS:
        errors.append(FieldError(f"{prefix}.name", "Bu interfeys tahrirlanmaydi"))
        return None
    if iface.mode not in ("static", "dhcp"):
        errors.append(FieldError(f"{prefix}.mode", "Rejim \"dhcp\" yoki \"static\" bo'lishi kerak"))
        return None
    if iface.mode != "static":
        _validate_mtu(prefix, iface.mtu, errors)
        return None
    if not iface.address:
        errors.append(FieldError(f"{prefix}.address", "Statik interfeys uchun manzil majburiy"))
        return None
    net = _ipv4_network_of(iface.address)
    if net is None:
        errors.append(FieldError(f"{prefix}.address", "Manzil yaroqsiz IPv4 CIDR bo'lishi kerak"))
        return None
    if iface.gateway:
        gateway = _ipv4_address_of(iface.gateway)
        if gateway is None:
            errors.append(FieldError(f"{prefix}.gateway", "Shlyuz manzili yaroqsiz IPv4 bo'lishi kerak"))
        elif gateway not in net:
            errors.append(FieldError(f"{prefix}.gateway", "Shlyuz interfeys subnetiga tushmaydi"))
    _validate_mtu(prefix, iface.mtu, errors)
    return (iface.name, str(net))


def _validate_interfaces(cfg, known: dict[str, LiveInterface], errors: list[FieldError]) -> dict[str, str]:
    """Interfeys tekshiruvlari; natija — `name -> subnet` xaritasi (marshrut
    shlyuzini mos interfeysga bog'lash uchun)."""
    gateway_count = 0
    subnets: dict[str, str] = {}
    for idx, iface in enumerate(cfg.interfaces):
        resolved = _validate_one_interface(idx, iface, known, errors)
        if resolved is None:
            continue
        name, net = resolved
        subnets[name] = net
        if iface.gateway:
            gateway_count += 1
    if gateway_count > 1:
        errors.append(FieldError("interfaces", "Butun konfiguratsiyada faqat bitta shlyuz bo'lishi mumkin"))
    if not cfg.interfaces:
        errors.append(FieldError("interfaces", "Kamida bitta interfeys manzilli qolishi kerak"))
    return subnets


def _resolve_route_interface(route, subnets: dict[str, str], gateway: ipaddress.IPv4Address | None,
                              idx: int, errors: list[FieldError]) -> str | None:
    """`gateway` chaqiruvchi tomonidan ALLAQACHON formatga tekshirilgan
    (`None` yoki yaroqli `IPv4Address`) — interfeys aniq berilganda ham
    shlyuz formati O'TKAZIB YUBORILMAYDI (ilgari shunday bo'lgan: `interface`
    berilsa, yaroqsiz `gateway` hech qachon tekshirilmay qolardi)."""
    prefix = f"routes[{idx}]"
    if route.interface:
        if not is_valid_iface_name(route.interface) or route.interface not in subnets:
            errors.append(FieldError(f"{prefix}.interface", "Marshrut interfeysi statik emas yoki topilmadi"))
            return None
        return route.interface
    if gateway is None:
        return None
    for name, cidr in subnets.items():
        if gateway in ipaddress.ip_network(cidr):
            return name
    errors.append(FieldError(f"{prefix}.gateway", "Shlyuz biror interfeys subnetiga tushmaydi"))
    return None


def _validate_route_metric(prefix: str, metric: object, errors: list[FieldError]) -> bool:
    if metric is None:
        return True
    if isinstance(metric, int) and not isinstance(metric, bool) and 0 <= metric <= 65535:
        return True
    errors.append(FieldError(f"{prefix}.metric", "Metrika 0..65535 oralig'ida butun son bo'lishi kerak"))
    return False


def _validate_routes(cfg, subnets: dict[str, str], errors: list[FieldError]) -> dict[str, list[RouteSpec]]:
    resolved: dict[str, list[RouteSpec]] = {}
    seen: set[tuple[str, int | None]] = set()
    for idx, route in enumerate(cfg.routes):
        prefix = f"routes[{idx}]"
        net = _ipv4_network_of(route.destination)
        if net is None:
            errors.append(FieldError(f"{prefix}.destination", "Marshrut manzili yaroqsiz IPv4 CIDR bo'lishi kerak"))
            continue
        destination = str(net)
        if destination == DEFAULT_ROUTE:
            errors.append(FieldError(f"{prefix}.destination", "Standart marshrut (0.0.0.0/0) taqiqlangan"))
            continue
        if not route.gateway and not route.interface:
            errors.append(FieldError(f"{prefix}.gateway", "Shlyuz yoki interfeys majburiy"))
            continue
        gateway = None
        if route.gateway:
            gateway = _ipv4_address_of(route.gateway)
            if gateway is None:
                errors.append(FieldError(f"{prefix}.gateway", "Shlyuz manzili yaroqsiz IPv4 bo'lishi kerak"))
                continue
        if not _validate_route_metric(prefix, route.metric, errors):
            continue
        key = (destination, route.metric)
        if key in seen:
            errors.append(FieldError(f"{prefix}.destination", "Dublikat marshrut (manzil+metrika)"))
            continue
        seen.add(key)
        iface_name = _resolve_route_interface(route, subnets, gateway, idx, errors)
        if iface_name is None:
            continue
        resolved.setdefault(iface_name, []).append(
            RouteSpec(destination, str(gateway) if gateway else None, iface_name, route.metric)
        )
    return resolved


def validate_config(cfg, known: list[LiveInterface]) -> ValidationResult:
    errors: list[FieldError] = []
    _validate_hostname(cfg, errors)
    known_by_name = {i.name: i for i in known}
    subnets = _validate_interfaces(cfg, known_by_name, errors)
    resolved = _validate_routes(cfg, subnets, errors)
    _validate_dns(cfg, errors)
    return ValidationResult(errors, resolved)
