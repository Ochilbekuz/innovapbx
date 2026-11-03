"""`app/schemas.py` M8 tarmoq maydonlari (~1300-1400-qatorlar) — CONFIRMED
CRITICAL admin -> root RCE: IPv6 scope-id (`fe80::1%zone`) ichida bo'sh
joy/qator ko'chirish taqiqlanmagan, `ipaddress.ip_interface`/`ip_address`
buni QABUL QILADI va xom satrni o'zgartirmay saqlardi — `netd` keyinroq shu
satrni `/etc/network/interfaces`ga to'g'ridan-to'g'ri yozib, `pre-up` qatori
in'eksiya qilishga imkon berardi. Bu modul — BIRINCHI himoya chizig'i
(API chegarasi); ikkinchisi `app/netd/validate.py`/renderlarda."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import NetworkConfigIn, NetworkDnsIn, NetworkInterfaceIn, NetworkRouteIn

SCOPE_ID_INJECTION = "fe80::1%eth0\n    pre-up touch /tmp/pwned #/64"


def test_interface_address_rejects_ipv6_scope_id_newline():
    with pytest.raises(ValidationError):
        NetworkInterfaceIn(name="eth0", mode="static", address=SCOPE_ID_INJECTION)


def test_interface_gateway_rejects_ipv6_scope_id_newline():
    with pytest.raises(ValidationError):
        NetworkInterfaceIn(name="eth0", mode="static", address="10.0.0.5/24", gateway=SCOPE_ID_INJECTION)


def test_route_gateway_rejects_injection_even_with_interface_set():
    with pytest.raises(ValidationError):
        NetworkRouteIn(destination="10.1.0.0/24", gateway=SCOPE_ID_INJECTION, interface="eth1")


def test_route_destination_rejects_injection():
    with pytest.raises(ValidationError):
        NetworkRouteIn(destination="10.1.0.0/24\n    pre-up touch /tmp/pwned #")


def test_dns_servers_rejects_ipv6_scope_id_newline():
    with pytest.raises(ValidationError):
        NetworkDnsIn(servers=[SCOPE_ID_INJECTION])


def test_dns_search_rejects_trailing_newline():
    with pytest.raises(ValidationError):
        NetworkDnsIn(search=["example.com\n    pre-up touch /tmp/pwned #"])


def test_dns_search_rejects_non_hostname():
    with pytest.raises(ValidationError):
        NetworkDnsIn(search=["-bad.example.com"])


def test_hostname_rejects_trailing_newline():
    with pytest.raises(ValidationError):
        NetworkConfigIn(hostname="host1\n", interfaces=[])


def test_hostname_rejects_invalid_rfc1123():
    with pytest.raises(ValidationError):
        NetworkConfigIn(hostname="-bad", interfaces=[])


@pytest.mark.parametrize("bad_ip", ["fe80::1", "::1", "10.0.0.5 ", "10.0.0.5\t", "10.0.0.5\x00"])
def test_ip_field_rejects_non_ipv4_or_control_chars(bad_ip):
    """Konfiguratsiya yozuvchi tomon (netd/ifupdown.py) faqat IPv4
    (klassik `address`/`netmask`) qo'llab-quvvatlaydi — IPv6 (scope-id'siz
    ham) va boshqaruv belgili/bo'sh joyli satrlar rad etiladi."""
    with pytest.raises(ValidationError):
        NetworkInterfaceIn(name="eth0", mode="static", address=f"{bad_ip}/24")


def test_valid_interface_is_canonicalized():
    iface = NetworkInterfaceIn(name="eth0", mode="static", address="10.0.0.5/24", gateway="10.0.0.1")
    assert iface.address == "10.0.0.5/24"
    assert iface.gateway == "10.0.0.1"


def test_valid_route_is_canonicalized():
    route = NetworkRouteIn(destination="10.1.0.0/24", gateway="10.0.0.254")
    assert route.destination == "10.1.0.0/24"
    assert route.gateway == "10.0.0.254"


def test_valid_dns_is_canonicalized():
    dns = NetworkDnsIn(servers=["1.1.1.1", "8.8.8.8"], search=["example.com", "corp.local"])
    assert dns.servers == ["1.1.1.1", "8.8.8.8"]
    assert dns.search == ["example.com", "corp.local"]


def test_valid_hostname_accepted():
    cfg = NetworkConfigIn(hostname="innova-pbx", interfaces=[])
    assert cfg.hostname == "innova-pbx"
