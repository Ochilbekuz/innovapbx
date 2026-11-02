"""`/etc/network/interfaces` parser/renderer — m8-network-contract.md bo'lim 3.

Ikki mustaqil kafolat:
  * `render(parse(text)) == text` — HAR QANDAY kirish uchun (lossless: har bir
    qator o'z asl matnini saqlaydi, hech narsa qayta hisoblanmaydi).
  * `build_target(old, desired)` — YAGONA funksiya semantik o'zgarish kiritadi:
    faqat o'zi boshqaradigan qatorlarni (address/gateway/mtu va
    `# innova-route` bilan belgilangan marshrut juftlari) qayta quradi;
    boshqa HAMMA narsa (izohlar, `dns-*`, `bridge_*`, boshqa `up`/`down`,
    bo'sh qatorlar, `source`) ASL HOLATDA, ASL O'RNIDA qoladi.
"""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Literal

BodyKind = Literal["address", "gateway", "mtu", "netmask", "route_up", "route_down", "other"]

_IFACE_RE = re.compile(r"^iface\s+(\S+)\s+(\S+)\s+(\S+)\s*$")
_ADDRESS_RE = re.compile(r"^\s*address\s+(\S+)\s*$")
_GATEWAY_RE = re.compile(r"^\s*gateway\s+(\S+)\s*$")
_MTU_RE = re.compile(r"^\s*mtu\s+(\d+)\s*$")
_NETMASK_RE = re.compile(r"^\s*netmask\s+(\S+)\s*$")
_AUTO_RE = re.compile(r"^\s*auto\s+(.+)$")
_HOTPLUG_RE = re.compile(r"^\s*allow-hotplug\s+(.+)$")
ROUTE_TAG = "innova-route"
_ROUTE_UP_RE = re.compile(
    r"^\s*up\s+ip\s+route\s+replace\s+(\S+)(?:\s+via\s+(\S+))?\s+dev\s+(\S+)"
    r"(?:\s+metric\s+(\d+))?\s*#\s*" + ROUTE_TAG + r"\s*$"
)
_ROUTE_DOWN_RE = re.compile(
    r"^\s*down\s+ip\s+route\s+del\s+(\S+)(?:\s+via\s+(\S+))?\s+dev\s+(\S+)"
    r"(?:\s+metric\s+(\d+))?\s*#\s*" + ROUTE_TAG + r"\s*$"
)


@dataclass(frozen=True)
class RouteSpec:
    destination: str
    gateway: str | None
    interface: str
    metric: int | None

    def up_line(self) -> str:
        return f"    up ip route replace {self._cmd_tail()}  # {ROUTE_TAG}"

    def down_line(self) -> str:
        return f"    down ip route del {self._cmd_tail()}  # {ROUTE_TAG}"

    def _cmd_tail(self) -> str:
        parts = [self.destination]
        if self.gateway:
            parts += ["via", self.gateway]
        parts += ["dev", self.interface]
        if self.metric is not None:
            parts += ["metric", str(self.metric)]
        return " ".join(parts)


@dataclass(frozen=True)
class BodyLine:
    raw: str
    kind: BodyKind
    route: RouteSpec | None = None


@dataclass
class IfaceStanza:
    header_raw: str
    name: str
    family: str
    method: str
    body: list[BodyLine] = field(default_factory=list)

    def _first(self, kind: BodyKind) -> str | None:
        for line in self.body:
            if line.kind == kind:
                return line.raw.strip().split(None, 1)[1].strip()
        return None

    @property
    def gateway(self) -> str | None:
        return self._first("gateway")

    @property
    def mtu(self) -> int | None:
        value = self._first("mtu")
        return int(value) if value is not None else None

    @property
    def address(self) -> str | None:
        """CIDR shaklida — `address A/P` to'g'ridan-to'g'ri, yoki
        `address A` + `netmask M` birlashtirilib hisoblanadi. Netmask
        topilmasa (kamdan-kam, klassik standart emas) — xost marshruti
        sifatida `/32` qabul qilinadi (xavfsiz, kattalashtirmaydigan tomon)."""
        raw = self._first("address")
        if raw is None:
            return None
        if "/" in raw:
            return raw
        mask = self._first("netmask")
        if mask is None:
            return f"{raw}/32"
        return str(ipaddress.ip_interface(f"{raw}/{mask}"))

    @property
    def routes(self) -> list[RouteSpec]:
        return [line.route for line in self.body if line.kind == "route_up" and line.route is not None]


@dataclass(frozen=True)
class Line:
    raw: str


Entry = Line | IfaceStanza


@dataclass
class IfupdownFile:
    entries: list[Entry] = field(default_factory=list)
    trailing_newline: bool = True

    def stanza(self, name: str) -> IfaceStanza | None:
        for entry in self.entries:
            if isinstance(entry, IfaceStanza) and entry.name == name:
                return entry
        return None

    def declared_auto_names(self) -> set[str]:
        return _names_from_directives(self.entries, _AUTO_RE)

    def declared_hotplug_names(self) -> set[str]:
        return _names_from_directives(self.entries, _HOTPLUG_RE)

    def all_routes(self) -> list[RouteSpec]:
        return [r for e in self.entries if isinstance(e, IfaceStanza) for r in e.routes]


def _names_from_directives(entries: list[Entry], pattern: re.Pattern) -> set[str]:
    names: set[str] = set()
    for entry in entries:
        if isinstance(entry, Line):
            match = pattern.match(entry.raw)
            if match:
                names.update(match.group(1).split())
    return names


def _classify_body_line(raw: str) -> BodyLine:
    if _ADDRESS_RE.match(raw):
        return BodyLine(raw, "address")
    if _GATEWAY_RE.match(raw):
        return BodyLine(raw, "gateway")
    if _MTU_RE.match(raw):
        return BodyLine(raw, "mtu")
    if _NETMASK_RE.match(raw):
        return BodyLine(raw, "netmask")
    match = _ROUTE_UP_RE.match(raw)
    if match:
        dst, gw, dev, metric = match.groups()
        spec = RouteSpec(dst, gw, dev, int(metric) if metric else None)
        return BodyLine(raw, "route_up", spec)
    if _ROUTE_DOWN_RE.match(raw):
        return BodyLine(raw, "route_down")
    return BodyLine(raw, "other")


def parse(text: str) -> IfupdownFile:
    trailing_newline = text.endswith("\n")
    lines = text.split("\n")
    if trailing_newline:
        lines = lines[:-1]
    entries: list[Entry] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        match = _IFACE_RE.match(raw.strip())
        if match and not raw[:1].isspace():
            name, fam, method = match.groups()
            i += 1
            body: list[BodyLine] = []
            while i < len(lines) and lines[i] and lines[i][:1].isspace():
                body.append(_classify_body_line(lines[i]))
                i += 1
            entries.append(IfaceStanza(raw, name, fam, method, body))
            continue
        entries.append(Line(raw))
        i += 1
    return IfupdownFile(entries, trailing_newline)


def render(file: IfupdownFile) -> str:
    parts: list[str] = []
    for entry in file.entries:
        if isinstance(entry, Line):
            parts.append(entry.raw)
        else:
            parts.append(entry.header_raw)
            parts.extend(line.raw for line in entry.body)
    text = "\n".join(parts)
    return text + "\n" if file.trailing_newline else text


@dataclass(frozen=True)
class DesiredInterface:
    name: str
    mode: Literal["dhcp", "static"]
    address: str | None
    gateway: str | None
    mtu: int | None
    routes: list[RouteSpec] = field(default_factory=list)


def _managed_body_lines(desired: DesiredInterface) -> list[BodyLine]:
    lines: list[BodyLine] = []
    if desired.mode == "static":
        lines.append(_classify_body_line(f"    address {desired.address}"))
        if desired.gateway:
            lines.append(_classify_body_line(f"    gateway {desired.gateway}"))
    if desired.mtu is not None:
        lines.append(_classify_body_line(f"    mtu {desired.mtu}"))
    for route in desired.routes:
        lines.append(BodyLine(route.up_line(), "route_up", route))
        lines.append(BodyLine(route.down_line(), "route_down"))
    return lines


def _rebuilt_stanza(old: IfaceStanza | None, desired: DesiredInterface) -> IfaceStanza:
    kept = [line for line in (old.body if old else []) if line.kind == "other"]
    header = f"iface {desired.name} inet {desired.mode}"
    return IfaceStanza(header, desired.name, "inet", desired.mode, _managed_body_lines(desired) + kept)


def build_target(old: IfupdownFile, desired: list[DesiredInterface]) -> IfupdownFile:
    """Eski faylni yangi `NetworkConfigIn.interfaces` + marshrutlarga mos holga
    keltiradi: mavjud stanza — o'rnida qayta quriladi (noma'lum qatorlar
    saqlanadi); yangi (fayl ichida yo'q) interfeys — oxiriga qo'shiladi.
    Statik bo'lib, hali `auto`da yo'q interfeysga `auto NAME` qatori qo'shiladi."""
    by_name = {d.name: d for d in desired}
    declared_auto = old.declared_auto_names()
    new_entries: list[Entry] = []
    for entry in old.entries:
        if isinstance(entry, IfaceStanza) and entry.name in by_name:
            target = by_name.pop(entry.name)
            if target.mode == "static" and target.name not in declared_auto:
                new_entries.append(Line(f"auto {target.name}"))
                declared_auto.add(target.name)
            new_entries.append(_rebuilt_stanza(entry, target))
        else:
            new_entries.append(entry)
    for target in by_name.values():
        if target.mode == "static" and target.name not in declared_auto:
            new_entries.append(Line(f"auto {target.name}"))
            declared_auto.add(target.name)
        new_entries.append(_rebuilt_stanza(None, target))
    return IfupdownFile(new_entries, old.trailing_newline)


@dataclass(frozen=True)
class Transition:
    """Ikki interfeyslar fayli (joriy, nishon) orasidagi farq: `restart_ifaces`
    — `ifdown --force X; ifup X` talab qiladigan interfeyslar (manzil/rejim/
    shlyuz/MTU o'zgargan); `route_live_cmds` — FAQAT marshrut o'zgargan
    (interfeys konfiguratsiyasi bir xil qolgan) interfeyslar uchun jonli `ip
    route` argv ro'yxatlari (ifdown/ifup'siz)."""
    restart_ifaces: list[str]
    route_live_cmds: list[list[str]]


def _iface_signature(stanza: IfaceStanza | None) -> tuple:
    if stanza is None:
        return (None, None, None, None)
    return (stanza.method, stanza.address, stanza.gateway, stanza.mtu)


def _route_key(route: RouteSpec) -> tuple:
    return (route.destination, route.metric)


def _route_cmds_for_diff(current: list[RouteSpec], target: list[RouteSpec], iface: str) -> list[list[str]]:
    current_by_key = {_route_key(r): r for r in current}
    target_by_key = {_route_key(r): r for r in target}
    cmds: list[list[str]] = []
    for key, route in target_by_key.items():
        if current_by_key.get(key) != route:
            cmds.append(_replace_route_argv(route))
    for key, route in current_by_key.items():
        if key not in target_by_key:
            cmds.append(_del_route_argv(route))
    return cmds


def _route_argv(verb: str, route: RouteSpec) -> list[str]:
    argv = ["ip", "route", verb, route.destination]
    if route.gateway:
        argv += ["via", route.gateway]
    argv += ["dev", route.interface]
    if route.metric is not None:
        argv += ["metric", str(route.metric)]
    return argv


def _replace_route_argv(route: RouteSpec) -> list[str]:
    return _route_argv("replace", route)


def _del_route_argv(route: RouteSpec) -> list[str]:
    return _route_argv("del", route)


def plan_transition(current: IfupdownFile, target: IfupdownFile) -> Transition:
    names = {e.name for e in current.entries if isinstance(e, IfaceStanza)}
    names |= {e.name for e in target.entries if isinstance(e, IfaceStanza)}
    restart: list[str] = []
    route_cmds: list[list[str]] = []
    for name in sorted(names):
        cur_stanza = current.stanza(name)
        tgt_stanza = target.stanza(name)
        if _iface_signature(cur_stanza) != _iface_signature(tgt_stanza):
            restart.append(name)
            continue
        cur_routes = cur_stanza.routes if cur_stanza else []
        tgt_routes = tgt_stanza.routes if tgt_stanza else []
        route_cmds.extend(_route_cmds_for_diff(cur_routes, tgt_routes, name))
    return Transition(restart, route_cmds)
