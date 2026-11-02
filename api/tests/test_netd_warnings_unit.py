"""`app/netd/warnings.py` — ulangan Host IP o'zgarsa ogohlantirish matni
(m8-network-contract.md bo'lim 4)."""
from __future__ import annotations

from types import SimpleNamespace

from app.netd.live import LiveInterface
from app.netd.warnings import host_ip_change_warnings

ETH0 = LiveInterface(name="eth0", mac="aa", kind="ethernet", oper_state="up", carrier=True,
                      speed_mbps=1000, mtu=1500, live_ipv4=["10.0.0.5/24"], live_ipv6=[])


def _config(address="10.0.0.9/24"):
    return SimpleNamespace(interfaces=[SimpleNamespace(name="eth0", mode="static", address=address)])


def test_no_warning_when_host_not_an_ip():
    assert host_ip_change_warnings("api.example.com", [ETH0], _config(), 120) == []


def test_no_warning_when_host_ip_not_owned_by_any_interface():
    assert host_ip_change_warnings("192.168.99.1", [ETH0], _config(), 120) == []


def test_no_warning_when_target_interface_unchanged():
    assert host_ip_change_warnings("10.0.0.5", [ETH0], _config(address="10.0.0.5/24"), 120) == []


def test_no_warning_when_target_mode_is_dhcp():
    cfg = SimpleNamespace(interfaces=[SimpleNamespace(name="eth0", mode="dhcp", address=None)])
    assert host_ip_change_warnings("10.0.0.5", [ETH0], cfg, 120) == []


def test_warning_text_matches_contract_format():
    warnings = host_ip_change_warnings("10.0.0.5", [ETH0], _config("10.0.0.9/24"), 90)
    assert warnings == [
        "Siz ulangan manzil o'zgaradi. Yangi manzil: http://10.0.0.9/ — "
        "90 s ichida o'sha yerdan kirib tasdiqlang"
    ]


def test_no_warning_when_request_host_is_none():
    assert host_ip_change_warnings(None, [ETH0], _config(), 120) == []
