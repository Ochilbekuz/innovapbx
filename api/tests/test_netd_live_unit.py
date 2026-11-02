"""`app/netd/live.py` — `ip -j` tahlili, virtual interfeyslarni (`docker*`,
`br-*`, `veth*`, `lo`) yashirish (m8-network-contract.md bo'lim 1)."""
from __future__ import annotations

import json

import pytest

from app.netd.executor import CommandResult
from app.netd.live import gather_default_gateway, gather_interfaces, gather_routes, is_virtual

LINKS = [
    {"ifname": "lo", "address": "00:00:00:00:00:00", "operstate": "UNKNOWN", "mtu": 65536, "link_type": "loopback"},
    {"ifname": "eth0", "address": "aa:bb:cc:dd:ee:ff", "operstate": "UP", "mtu": 1500, "link_type": "ether"},
    {"ifname": "docker0", "address": "02:aa", "operstate": "DOWN", "mtu": 1500, "link_type": "ether"},
    {"ifname": "veth1234", "address": "02:bb", "operstate": "UP", "mtu": 1500, "link_type": "ether"},
    {"ifname": "br-abc123", "address": "02:cc", "operstate": "UP", "mtu": 1500, "link_type": "ether"},
    {"ifname": "wlan0", "address": "02:dd", "operstate": "UP", "mtu": 1500, "link_type": "ether"},
    {"ifname": "vlan10", "address": "02:ee", "operstate": "UP", "mtu": 1500, "link_type": "ether",
     "linkinfo": {"info_kind": "vlan"}},
]

ADDRS = [
    {"ifname": "eth0", "addr_info": [{"family": "inet", "local": "10.0.0.5", "prefixlen": 24},
                                       {"family": "inet6", "local": "fe80::1", "prefixlen": 64}]},
]

ROUTES = [
    {"dst": "default", "gateway": "10.0.0.1", "dev": "eth0", "protocol": "dhcp"},
    {"dst": "10.1.0.0/24", "dev": "eth0", "metric": 50, "protocol": "static"},
]


class _Fs:
    def __init__(self, link_json, addr_json, route_json, sysfs: dict[str, str] | None = None):
        self._link_json = link_json
        self._addr_json = addr_json
        self._route_json = route_json
        self.sysfs = sysfs or {}

    async def run(self, argv, *, timeout=5.0):
        if argv[:3] == ["ip", "-j", "-d"] and "link" in argv:
            return CommandResult(0, json.dumps(self._link_json), "")
        if argv == ["ip", "-j", "addr"]:
            return CommandResult(0, json.dumps(self._addr_json), "")
        if argv == ["ip", "-j", "route"]:
            return CommandResult(0, json.dumps(self._route_json), "")
        return CommandResult(1, "", "noma'lum")

    def exists(self, path: str) -> bool:
        return path in self.sysfs

    def read_text(self, path: str) -> str | None:
        return self.sysfs.get(path)


def test_is_virtual():
    assert is_virtual("lo") is True
    assert is_virtual("docker0") is True
    assert is_virtual("br-abc") is True
    assert is_virtual("veth1234") is True
    assert is_virtual("eth0") is False


@pytest.mark.asyncio
async def test_gather_interfaces_hides_virtual_and_lo():
    fs = _Fs(LINKS, ADDRS, ROUTES, sysfs={
        "/sys/class/net/eth0/carrier": "1", "/sys/class/net/eth0/speed": "1000",
        "/sys/class/net/wlan0/wireless": "", "/sys/class/net/vlan10/carrier": "1",
    })
    out = await gather_interfaces(fs)
    names = {i.name for i in out}
    assert names == {"eth0", "wlan0", "vlan10"}


@pytest.mark.asyncio
async def test_gather_interfaces_fills_addresses_and_kind():
    fs = _Fs(LINKS, ADDRS, ROUTES)
    out = await gather_interfaces(fs)
    eth0 = next(i for i in out if i.name == "eth0")
    assert eth0.kind == "ethernet"
    assert eth0.live_ipv4 == ["10.0.0.5/24"]
    assert eth0.live_ipv6 == ["fe80::1/64"]
    wlan0 = next(i for i in out if i.name == "wlan0")
    assert wlan0.kind == "ethernet"  # sysfs `wireless` yo'q bu testda -> link_type=ether -> "ethernet"


@pytest.mark.asyncio
async def test_gather_interfaces_detects_wireless_via_sysfs():
    fs = _Fs(LINKS, ADDRS, ROUTES, sysfs={"/sys/class/net/wlan0/wireless": ""})
    out = await gather_interfaces(fs)
    wlan0 = next(i for i in out if i.name == "wlan0")
    assert wlan0.kind == "wireless"


@pytest.mark.asyncio
async def test_gather_interfaces_detects_vlan_via_linkinfo():
    fs = _Fs(LINKS, ADDRS, ROUTES)
    out = await gather_interfaces(fs)
    vlan10 = next(i for i in out if i.name == "vlan10")
    assert vlan10.kind == "vlan"


@pytest.mark.asyncio
async def test_gather_interfaces_sysfs_einval_treated_as_missing():
    """Haqiqiy yadro xulq-atvori: `carrier`/`speed` havola pastda yoki
    drayver qo'llamasa, fayl bo'lsa ham `read()` `OSError: Invalid
    argument` tashlaydi (`FileNotFoundError` EMAS) — bu "qiymat yo'q" deb
    talqin qilinishi kerak, qotib qolmasligi kerak (M8 integratsiya sinovida
    `dummy` interfeysda topilgan haqiqiy xato)."""
    class _EinvalFs(_Fs):
        def read_text(self, path: str) -> str | None:
            if path.endswith("/speed"):
                raise OSError(22, "Invalid argument")
            return super().read_text(path)

    fs = _EinvalFs(LINKS, ADDRS, ROUTES, sysfs={"/sys/class/net/eth0/carrier": "1"})
    out = await gather_interfaces(fs)
    eth0 = next(i for i in out if i.name == "eth0")
    assert eth0.speed_mbps is None
    assert eth0.carrier is True


@pytest.mark.asyncio
async def test_gather_interfaces_on_ip_failure_returns_empty():
    class _Broken(_Fs):
        async def run(self, argv, *, timeout=5.0):
            return CommandResult(1, "", "xato")

    out = await gather_interfaces(_Broken(LINKS, ADDRS, ROUTES))
    assert out == []


@pytest.mark.asyncio
async def test_gather_routes_translates_default_destination():
    fs = _Fs(LINKS, ADDRS, ROUTES)
    routes = await gather_routes(fs)
    default = next(r for r in routes if r.gateway == "10.0.0.1")
    assert default.destination == "0.0.0.0/0"
    static = next(r for r in routes if r.destination == "10.1.0.0/24")
    assert static.metric == 50 and static.interface == "eth0"


@pytest.mark.asyncio
async def test_gather_default_gateway_found():
    fs = _Fs(LINKS, ADDRS, ROUTES)
    gw = await gather_default_gateway(fs)
    assert gw.address == "10.0.0.1" and gw.interface == "eth0"


@pytest.mark.asyncio
async def test_gather_default_gateway_missing():
    fs = _Fs(LINKS, ADDRS, [])
    gw = await gather_default_gateway(fs)
    assert gw.address is None and gw.interface is None
