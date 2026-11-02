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


def _cfg(interfaces=None, routes=None, hostname="innova-pbx"):
    return SimpleNamespace(hostname=hostname, interfaces=interfaces or [], routes=routes or [])


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
