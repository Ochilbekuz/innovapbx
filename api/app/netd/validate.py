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

_HOSTNAME_LABEL_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$")
DEFAULT_ROUTE = "0.0.0.0/0"
EDITABLE_KINDS = frozenset({"ethernet", "bond", "vlan"})


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


def is_valid_hostname(name: str) -> bool:
    """RFC1123: har bir label 1..63 belgi, alfa-raqamli + chiziqcha (boshi/
    oxiri chiziqcha emas), to'liq nom <=253 belgi."""
    if not name or len(name) > 253:
        return False
    return all(_HOSTNAME_LABEL_RE.match(label) for label in name.split("."))


def _subnet_of(cidr: str) -> ipaddress.IPv4Network | None:
    try:
        return ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return None


def _validate_hostname(cfg, errors: list[FieldError]) -> None:
    if not is_valid_hostname(cfg.hostname):
        errors.append(FieldError("hostname", "Mezbon nomi RFC1123 talablariga mos emas"))


def _validate_one_interface(idx: int, iface, known: dict[str, LiveInterface],
                             errors: list[FieldError]) -> tuple[str, str] | None:
    """Bitta interfeysni tekshiradi. Muvaffaqiyatli statik interfeys —
    `(nom, subnet)`; aks holda `None` (xato allaqachon `errors`ga qo'shilgan,
    yoki interfeys dhcp bo'lib subnetga ega bo'lmaydi)."""
    prefix = f"interfaces[{idx}]"
    live = known.get(iface.name)
    if live is None:
        errors.append(FieldError(f"{prefix}.name", f"Interfeys topilmadi: {iface.name}"))
        return None
    if live.kind not in EDITABLE_KINDS:
        errors.append(FieldError(f"{prefix}.name", "Bu interfeys tahrirlanmaydi"))
        return None
    if iface.mode != "static":
        return None
    if not iface.address:
        errors.append(FieldError(f"{prefix}.address", "Statik interfeys uchun manzil majburiy"))
        return None
    net = _subnet_of(iface.address)
    if net is None:
        errors.append(FieldError(f"{prefix}.address", "Manzil yaroqsiz"))
        return None
    if iface.gateway and ipaddress.ip_address(iface.gateway) not in net:
        errors.append(FieldError(f"{prefix}.gateway", "Shlyuz interfeys subnetiga tushmaydi"))
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


def _resolve_route_interface(route, subnets: dict[str, str], idx: int, errors: list[FieldError]) -> str | None:
    prefix = f"routes[{idx}]"
    if route.interface:
        if route.interface not in subnets:
            errors.append(FieldError(f"{prefix}.interface", "Marshrut interfeysi statik emas yoki topilmadi"))
            return None
        return route.interface
    if not route.gateway:
        return None
    for name, cidr in subnets.items():
        if ipaddress.ip_address(route.gateway) in ipaddress.ip_network(cidr):
            return name
    errors.append(FieldError(f"{prefix}.gateway", "Shlyuz biror interfeys subnetiga tushmaydi"))
    return None


def _validate_routes(cfg, subnets: dict[str, str], errors: list[FieldError]) -> dict[str, list[RouteSpec]]:
    resolved: dict[str, list[RouteSpec]] = {}
    seen: set[tuple[str, int | None]] = set()
    for idx, route in enumerate(cfg.routes):
        prefix = f"routes[{idx}]"
        if route.destination == DEFAULT_ROUTE:
            errors.append(FieldError(f"{prefix}.destination", "Standart marshrut (0.0.0.0/0) taqiqlangan"))
            continue
        if not route.gateway and not route.interface:
            errors.append(FieldError(f"{prefix}.gateway", "Shlyuz yoki interfeys majburiy"))
            continue
        key = (route.destination, route.metric)
        if key in seen:
            errors.append(FieldError(f"{prefix}.destination", "Dublikat marshrut (manzil+metrika)"))
            continue
        seen.add(key)
        iface_name = _resolve_route_interface(route, subnets, idx, errors)
        if iface_name is None:
            continue
        resolved.setdefault(iface_name, []).append(
            RouteSpec(route.destination, route.gateway, iface_name, route.metric)
        )
    return resolved


def validate_config(cfg, known: list[LiveInterface]) -> ValidationResult:
    errors: list[FieldError] = []
    _validate_hostname(cfg, errors)
    known_by_name = {i.name: i for i in known}
    subnets = _validate_interfaces(cfg, known_by_name, errors)
    resolved = _validate_routes(cfg, subnets, errors)
    return ValidationResult(errors, resolved)
