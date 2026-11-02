"""Jonli tarmoq holati — `ip -j` buyruqlari + `/sys/class/net/*`
(m8-network-contract.md bo'lim 1 — interfeyslar/marshrutlar/standart shlyuz)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.netd.executor import Executor

_VIRTUAL_PREFIXES = ("docker", "br-", "veth")


def is_virtual(name: str) -> bool:
    """`lo`, `docker0`, `br-*`, `veth*` va boshqa konteyner virtual
    qurilmalari — kontrakt: «KO'RSATILMAYDI»."""
    return name == "lo" or name.startswith(_VIRTUAL_PREFIXES)


@dataclass(frozen=True)
class LiveInterface:
    name: str
    mac: str | None
    kind: str
    oper_state: str
    carrier: bool
    speed_mbps: int | None
    mtu: int
    live_ipv4: list[str] = field(default_factory=list)
    live_ipv6: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LiveRoute:
    destination: str
    gateway: str | None
    interface: str | None
    metric: int | None
    protocol: str | None


@dataclass(frozen=True)
class DefaultGateway:
    address: str | None
    interface: str | None


async def _ip_json(executor: Executor, *args: str) -> list[dict]:
    result = await executor.run(["ip", "-j", *args], timeout=5.0)
    if not result.ok or not result.stdout.strip():
        return []
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return []


def _sysfs_int(executor: Executor, name: str, attr: str) -> int | None:
    """`carrier`/`speed` kabi sukut-ixtiyoriy sysfs atributlari: havola
    pastda bo'lsa yoki drayver qo'llab-quvvatlamasa, fayl MAVJUD bo'lsa ham
    `read()` chaqirig'i `FileNotFoundError` emas, `OSError: [Errno 22]
    Invalid argument` tashlaydi (haqiqiy yadro xulq-atvori — integratsiya
    sinovida `dummy` interfeysda, real uskunada esa kabel ulanmagan portda
    takrorlanadigan holat). Shu sabab — har qanday `OSError`ni "qiymat yo'q"
    deb o'qiymiz, qotib qolmaymiz."""
    try:
        raw = executor.read_text(f"/sys/class/net/{name}/{attr}")
    except OSError:
        return None
    if raw is None:
        return None
    try:
        value = int(raw.strip())
    except ValueError:
        return None
    return value if value >= 0 else None


def _kind_of(executor: Executor, link: dict) -> str:
    info_kind = (link.get("linkinfo") or {}).get("info_kind")
    if info_kind in ("vlan", "bond", "bridge"):
        return info_kind
    if executor.exists(f"/sys/class/net/{link['ifname']}/wireless"):
        return "wireless"
    if link.get("link_type") == "ether":
        return "ethernet"
    return "other"


def _addrs_for(addrs: list[dict], name: str) -> tuple[list[str], list[str]]:
    v4, v6 = [], []
    entry = next((a for a in addrs if a.get("ifname") == name), None)
    for info in (entry or {}).get("addr_info", []):
        cidr = f"{info.get('local')}/{info.get('prefixlen')}"
        (v4 if info.get("family") == "inet" else v6).append(cidr)
    return v4, v6


async def gather_interfaces(executor: Executor) -> list[LiveInterface]:
    links = await _ip_json(executor, "-d", "link")
    addrs = await _ip_json(executor, "addr")
    out = []
    for link in links:
        name = link.get("ifname", "")
        if not name or is_virtual(name):
            continue
        v4, v6 = _addrs_for(addrs, name)
        out.append(LiveInterface(
            name=name,
            mac=link.get("address"),
            kind=_kind_of(executor, link),
            oper_state=(link.get("operstate") or "unknown").lower(),
            carrier=bool(_sysfs_int(executor, name, "carrier")),
            speed_mbps=_sysfs_int(executor, name, "speed"),
            mtu=link.get("mtu") or 1500,
            live_ipv4=v4, live_ipv6=v6,
        ))
    return out


async def gather_routes(executor: Executor) -> list[LiveRoute]:
    routes = await _ip_json(executor, "route")
    out = []
    for r in routes:
        dst = r.get("dst", "default")
        out.append(LiveRoute(
            destination="0.0.0.0/0" if dst == "default" else dst,
            gateway=r.get("gateway"), interface=r.get("dev"),
            metric=r.get("metric") or r.get("priority"), protocol=r.get("protocol"),
        ))
    return out


async def gather_default_gateway(executor: Executor) -> DefaultGateway:
    routes = await _ip_json(executor, "route")
    for r in routes:
        if r.get("dst") == "default":
            return DefaultGateway(r.get("gateway"), r.get("dev"))
    return DefaultGateway(None, None)
