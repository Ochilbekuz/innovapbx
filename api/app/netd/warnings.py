"""Ogohlantirishlar — m8-network-contract.md bo'lim 4: so'rov kelgan host IP
(Host sarlavhasi) o'zgaradigan interfeysda bo'lsa."""
from __future__ import annotations

import ipaddress

from app.netd.live import LiveInterface


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _owner_of(request_host: str, live: list[LiveInterface]) -> LiveInterface | None:
    for iface in live:
        addrs = [a.split("/")[0] for a in iface.live_ipv4 + iface.live_ipv6]
        if request_host in addrs:
            return iface
    return None


def host_ip_change_warnings(request_host: str | None, live: list[LiveInterface], config, timeout_s: int) -> list[str]:
    if not request_host or not _is_ip(request_host):
        return []
    owner = _owner_of(request_host, live)
    if owner is None:
        return []
    desired = next((i for i in config.interfaces if i.name == owner.name), None)
    if desired is None or desired.mode != "static" or not desired.address:
        return []
    new_ip = desired.address.split("/")[0]
    if new_ip == request_host:
        return []
    return [
        f"Siz ulangan manzil o'zgaradi. Yangi manzil: http://{new_ip}/ — "
        f"{timeout_s} s ichida o'sha yerdan kirib tasdiqlang"
    ]
