"""Webhook URL tekshiruvi (m3b-contract.md §3) — SSRF himoyasi.

Ruxsat: http/https, ommaviy va LAN (10/8, 172.16/12, 192.168/16 — on-prem 1C/CRM).
Taqiq: loopback, link-local (169.254/16, fe80::/10, metadata 169.254.169.254, fd00:ec2::254),
0.0.0.0/::, multicast/zahira, URL ichida login/parol va PBX'ning o'z xizmatlari
(nomlari + resolve qilingan IP'lari). Yaratishda VA har yuborishda (DNS rebinding) tekshiriladi.
"""
from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterable
from urllib.parse import urlsplit

Resolver = Callable[[str], list[str]]

_METADATA = frozenset({"169.254.169.254", "fd00:ec2::254"})


class UrlForbidden(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"url_forbidden:{reason}")
        self.reason = reason


def system_resolve(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return sorted({info[4][0] for info in infos})


def is_forbidden_ip(raw: str, own: frozenset[str]) -> bool:
    ip = ipaddress.ip_address(raw.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return (str(ip) in own or str(ip) in _METADATA or ip.is_loopback or ip.is_link_local
            or ip.is_unspecified or ip.is_multicast or ip.is_reserved)


def own_ips(hosts: Iterable[str], *, resolve: Resolver = system_resolve) -> frozenset[str]:
    """PBX xizmatlari IP'lari — resolve bo'lmagan nom e'tiborsiz (masalan `web` hali turmagan)."""
    found: set[str] = set()
    for host in hosts:
        try:
            found.update(resolve(host))
        except OSError:
            continue
    return frozenset(found)


def _host_of(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UrlForbidden("scheme")
    if parts.username or parts.password:
        raise UrlForbidden("credentials")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise UrlForbidden("host")
    return host


def _literal_ip(host: str) -> str | None:
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        return None


def check_url(url: str, *, resolve: Resolver, own_ips: frozenset[str], blocked_hosts: frozenset[str]) -> None:
    host = _host_of(url)
    if host in blocked_hosts:
        raise UrlForbidden("host")
    literal = _literal_ip(host)
    try:
        addresses = [literal] if literal else resolve(host)
    except OSError as exc:
        raise UrlForbidden("resolve") from exc
    if not addresses or any(is_forbidden_ip(a, own_ips) for a in addresses):
        raise UrlForbidden("address")


def check_url_default(url: str) -> None:
    """Ilova sozlamalari bilan (`INTEGRATION_BLOCKED_HOSTS`) — API va yuborish paytida."""
    from app.core.config import settings

    hosts = frozenset(h.strip().lower() for h in settings.integration_blocked_hosts.split(",") if h.strip())
    own = own_ips(hosts | {socket.gethostname()})
    check_url(url, resolve=system_resolve, own_ips=own, blocked_hosts=hosts)
