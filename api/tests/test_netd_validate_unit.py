"""`app/netd/validate.py` — m8-network-contract.md bo'lim 4: hamma tekshiruv
qoidalari (sof funksiya, soxta `LiveInterface` ro'yxati bilan)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.netd.live import LiveInterface
from app.netd.validate import is_valid_hostname, validate_config

ETH0 = LiveInterface("eth0", "aa:bb", "ethernet", "up", True, 1000, 1500)
ETH1 = LiveInterface("eth1", "cc:dd", "ethernet", "up", True, 1000, 1500)
WLAN0 = LiveInterface("wlan0", "ee:ff", "wireless", "up", True, None, 1500)


def _iface(name="eth0", mode="static", address="10.0.0.5/24", gateway="10.0.0.1", mtu=None):
    return SimpleNamespace(name=name, mode=mode, address=address, gateway=gateway, mtu=mtu)


def _route(destination="10.1.0.0/24", gateway="10.0.0.254", interface=None, metric=None):
    return SimpleNamespace(destination=destination, gateway=gateway, interface=interface, metric=metric)


def _cfg(interfaces=None, routes=None, hostname="innova-pbx", dns=None):
    return SimpleNamespace(hostname=hostname, interfaces=interfaces or [], routes=routes or [], dns=dns)


INJECTED = "fe80::1%eth0\n    pre-up touch /tmp/pwned #/64"


@pytest.mark.parametrize("name,valid", [
    ("innova-pbx", True), ("a", True), ("pbx.local", True),
    ("-bad", False), ("bad-", False), ("", False), ("a" * 300, False), ("bad_underscore", False),
])
def test_is_valid_hostname(name, valid):
    assert is_valid_hostname(name) is valid


def test_valid_config_ok():
    cfg = _cfg([_iface()])
    result = validate_config(cfg, [ETH0])
    assert result.ok
    assert result.errors == []


def test_bad_hostname_rejected():
    cfg = _cfg([_iface()], hostname="-bad")
    result = validate_config(cfg, [ETH0])
    assert not result.ok
    assert any(e.field == "hostname" for e in result.errors)


def test_static_without_address_rejected():
    cfg = _cfg([_iface(address=None)])
    result = validate_config(cfg, [ETH0])
    assert any(e.field == "interfaces[0].address" for e in result.errors)


def test_unknown_interface_rejected():
    cfg = _cfg([_iface(name="eth9")])
    result = validate_config(cfg, [ETH0])
    assert any(e.field == "interfaces[0].name" for e in result.errors)


def test_non_editable_kind_rejected():
    cfg = _cfg([_iface(name="wlan0")])
    result = validate_config(cfg, [WLAN0])
    assert any(e.field == "interfaces[0].name" for e in result.errors)


def test_gateway_outside_subnet_rejected():
    cfg = _cfg([_iface(gateway="192.168.9.1")])
    result = validate_config(cfg, [ETH0])
    assert any(e.field == "interfaces[0].gateway" for e in result.errors)


def test_two_gateways_rejected():
    cfg = _cfg([
        _iface(name="eth0", address="10.0.0.5/24", gateway="10.0.0.1"),
        _iface(name="eth1", address="10.0.1.5/24", gateway="10.0.1.1"),
    ])
    result = validate_config(cfg, [ETH0, ETH1])
    assert any(e.field == "interfaces" for e in result.errors)


def test_empty_interfaces_rejected():
    cfg = _cfg([])
    result = validate_config(cfg, [ETH0])
    assert any(e.field == "interfaces" for e in result.errors)


def test_default_route_rejected():
    cfg = _cfg([_iface()], [_route(destination="0.0.0.0/0")])
    result = validate_config(cfg, [ETH0])
    assert any(e.field == "routes[0].destination" for e in result.errors)


def test_route_without_gateway_or_interface_rejected():
    cfg = _cfg([_iface()], [_route(gateway=None, interface=None)])
    result = validate_config(cfg, [ETH0])
    assert any(e.field == "routes[0].gateway" for e in result.errors)


def test_duplicate_route_rejected():
    cfg = _cfg([_iface()], [_route(), _route()])
    result = validate_config(cfg, [ETH0])
    assert any(e.field == "routes[1].destination" for e in result.errors)


def test_route_gateway_outside_any_subnet_rejected():
    cfg = _cfg([_iface()], [_route(gateway="192.168.9.254")])
    result = validate_config(cfg, [ETH0])
    assert any(e.field == "routes[0].gateway" for e in result.errors)


def test_route_resolved_to_matching_interface():
    cfg = _cfg([_iface()], [_route()])
    result = validate_config(cfg, [ETH0])
    assert result.ok
    assert result.resolved_routes["eth0"][0].destination == "10.1.0.0/24"


def test_route_with_explicit_interface():
    cfg = _cfg([_iface(name="eth0"), _iface(name="eth1", address="10.0.1.5/24", gateway=None)],
                [_route(destination="10.2.0.0/24", gateway=None, interface="eth1")])
    result = validate_config(cfg, [ETH0, ETH1])
    assert result.ok
    assert result.resolved_routes["eth1"][0].interface == "eth1"


def test_route_unknown_interface_rejected():
    cfg = _cfg([_iface()], [_route(gateway=None, interface="eth9")])
    result = validate_config(cfg, [ETH0])
    assert any(e.field == "routes[0].interface" for e in result.errors)


# --------------------------------------------------------------------------
# CONFIRMED CRITICAL: admin -> root RCE. `netd` API'ga ishonmaydi — har bir
# chekka holat shu yerda MUSTAQIL ravishda rad etilishi kerak (hatto
# `app/schemas.py` ishdan chiqsa ham, soketga to'g'ridan-to'g'ri yozilgan
# `config`ni netd o'zi ushlashi SHART).
def test_hostname_with_trailing_newline_rejected():
    cfg = _cfg([_iface()], hostname="innova-pbx\n")
    result = validate_config(cfg, [ETH0])
    assert any(e.field == "hostname" for e in result.errors)


def test_address_with_ipv6_scope_id_newline_rejected():
    cfg = _cfg([_iface(address=INJECTED)])
    result = validate_config(cfg, [ETH0])
    assert any(e.field == "interfaces[0].address" for e in result.errors)


def test_gateway_with_ipv6_scope_id_newline_rejected():
    cfg = _cfg([_iface(gateway=INJECTED)])
    result = validate_config(cfg, [ETH0])
    assert any(e.field == "interfaces[0].gateway" for e in result.errors)


def test_route_gateway_with_scope_id_newline_rejected_even_when_interface_set():
    """Ilgari: `route.interface` berilsa, `route.gateway` formati HECH QACHON
    tekshirilmasdi (409-108-qatorlar) — shlyuzga in'eksiya shu yo'l bilan
    o'tib ketardi."""
    cfg = _cfg([_iface(name="eth0"), _iface(name="eth1", address="10.0.1.5/24", gateway=None)],
                [_route(destination="10.2.0.0/24", gateway=INJECTED, interface="eth1")])
    result = validate_config(cfg, [ETH0, ETH1])
    assert not result.ok
    assert any(e.field == "routes[0].gateway" for e in result.errors)


def test_route_destination_injection_rejected():
    cfg = _cfg([_iface()], [_route(destination="10.1.0.0/24\n    pre-up touch /tmp/pwned #")])
    result = validate_config(cfg, [ETH0])
    assert any(e.field == "routes[0].destination" for e in result.errors)


def test_mtu_string_injection_rejected():
    cfg = _cfg([_iface(mtu="9000\n0 pre-up touch /tmp/pwned #")])
    result = validate_config(cfg, [ETH0])
    assert any(e.field == "interfaces[0].mtu" for e in result.errors)


def test_mtu_out_of_range_rejected():
    cfg = _cfg([_iface(mtu=67)])
    result = validate_config(cfg, [ETH0])
    assert any(e.field == "interfaces[0].mtu" for e in result.errors)


def test_mode_injection_rejected():
    cfg = _cfg([_iface(mode="dhcp\n    pre-up touch /tmp/pwned #")])
    result = validate_config(cfg, [ETH0])
    assert any(e.field == "interfaces[0].mode" for e in result.errors)


def test_dns_server_with_scope_id_newline_rejected():
    cfg = _cfg([_iface()], dns=SimpleNamespace(servers=[INJECTED], search=[]))
    result = validate_config(cfg, [ETH0])
    assert any(e.field == "dns.servers[0]" for e in result.errors)


def test_dns_search_with_trailing_newline_rejected():
    cfg = _cfg([_iface()], dns=SimpleNamespace(servers=[], search=["example.com\n    pre-up touch /tmp/pwned #"]))
    result = validate_config(cfg, [ETH0])
    assert any(e.field == "dns.search[0]" for e in result.errors)


def test_dns_valid_servers_and_search_accepted():
    cfg = _cfg([_iface()], dns=SimpleNamespace(servers=["1.1.1.1", "8.8.8.8"], search=["example.com"]))
    result = validate_config(cfg, [ETH0])
    assert result.ok


def test_dns_absent_is_skipped_not_crashed():
    """Eski chaqiruvchilar (yoki `dns`siz test fixture) `cfg.dns` berishi
    shart EMAS — bu holatda DNS tekshiruvi jim o'tkazib yuboriladi, lekin
    `AttributeError` bilan yiqilmaydi."""
    cfg = _cfg([_iface()])
    result = validate_config(cfg, [ETH0])
    assert result.ok
