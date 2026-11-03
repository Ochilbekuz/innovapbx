"""`app/netd/ifupdown.py` — m8-network-contract.md bo'lim 3: parser round-trip,
render (dhcp->static, marshrut qo'shish/o'chirish), noma'lum qatorlar saqlanadi."""
from __future__ import annotations

import pytest

from app.netd.ifupdown import (
    DesiredInterface,
    RouteSpec,
    build_target,
    parse,
    plan_transition,
    render,
)
from app.netd.safety import UnsafeRenderError

DEBIAN_DEFAULT = """\
source /etc/network/interfaces.d/*
auto lo
iface lo inet loopback

allow-hotplug enp1s0
iface enp1s0 inet dhcp
"""

WITH_EXTRAS = """\
# izoh
auto eth0
allow-hotplug eth0
iface eth0 inet static
    address 10.0.0.5/24
    gateway 10.0.0.1
    mtu 1500
    dns-nameservers 10.0.0.1
    up ip route replace 10.1.0.0/24 via 10.0.0.254 dev eth0 metric 50  # innova-route
    down ip route del 10.1.0.0/24 via 10.0.0.254 dev eth0 metric 50  # innova-route
    # ichki izoh
"""


def test_round_trip_debian_default_is_byte_identical():
    assert render(parse(DEBIAN_DEFAULT)) == DEBIAN_DEFAULT


def test_round_trip_with_extras_is_byte_identical():
    assert render(parse(WITH_EXTRAS)) == WITH_EXTRAS


def test_round_trip_no_trailing_newline():
    text = "auto lo\niface lo inet loopback"
    assert render(parse(text)) == text


def test_parse_extracts_address_gateway_mtu_and_route():
    stanza = parse(WITH_EXTRAS).stanza("eth0")
    assert stanza.address == "10.0.0.5/24"
    assert stanza.gateway == "10.0.0.1"
    assert stanza.mtu == 1500
    assert stanza.routes == [RouteSpec("10.1.0.0/24", "10.0.0.254", "eth0", 50)]


def test_parse_combines_address_and_netmask_into_cidr():
    text = "iface eth1 inet static\n    address 192.168.1.5\n    netmask 255.255.255.0\n"
    stanza = parse(text).stanza("eth1")
    assert stanza.address == "192.168.1.5/24"


def test_render_dhcp_to_static_adds_address_and_auto_line():
    old = parse(DEBIAN_DEFAULT)
    desired = [DesiredInterface("enp1s0", "static", "192.168.1.10/24", "192.168.1.1", None)]
    new_text = render(build_target(old, desired))
    assert "auto enp1s0" in new_text
    assert "iface enp1s0 inet static" in new_text
    assert "address 192.168.1.10/24" in new_text
    assert "gateway 192.168.1.1" in new_text


def test_render_preserves_unknown_lines_inside_stanza():
    old = parse(WITH_EXTRAS)
    desired = [DesiredInterface("eth0", "static", "10.0.0.6/24", "10.0.0.1", 1500)]
    new_text = render(build_target(old, desired))
    assert "dns-nameservers 10.0.0.1" in new_text
    assert "# ichki izoh" in new_text
    assert "address 10.0.0.6/24" in new_text


def test_render_adds_route_pair():
    old = parse(DEBIAN_DEFAULT)
    route = RouteSpec("10.9.0.0/24", "192.168.1.1", "enp1s0", None)
    desired = [DesiredInterface("enp1s0", "static", "192.168.1.10/24", "192.168.1.1", None, [route])]
    new_text = render(build_target(old, desired))
    assert "up ip route replace 10.9.0.0/24 via 192.168.1.1 dev enp1s0  # innova-route" in new_text
    assert "down ip route del 10.9.0.0/24 via 192.168.1.1 dev enp1s0  # innova-route" in new_text


def test_render_removes_route_when_dropped():
    old = parse(WITH_EXTRAS)
    desired = [DesiredInterface("eth0", "static", "10.0.0.5/24", "10.0.0.1", 1500, [])]
    new_text = render(build_target(old, desired))
    assert "innova-route" not in new_text


def test_new_interface_not_in_file_is_appended():
    old = parse(DEBIAN_DEFAULT)
    desired = [DesiredInterface("eth1", "static", "10.1.0.5/24", None, None)]
    new_text = render(build_target(old, desired))
    assert "auto eth1" in new_text
    assert "iface eth1 inet static" in new_text


def test_existing_auto_line_not_duplicated():
    old = parse(WITH_EXTRAS)
    desired = [DesiredInterface("eth0", "static", "10.0.0.9/24", "10.0.0.1", 1500)]
    new_text = render(build_target(old, desired))
    assert new_text.count("auto eth0") == 1


# ---------------------------------------------------------------- Transition
def test_plan_transition_detects_address_change_as_restart():
    old = parse(DEBIAN_DEFAULT)
    new = build_target(old, [DesiredInterface("enp1s0", "static", "192.168.1.10/24", None, None)])
    transition = plan_transition(old, new)
    assert transition.restart_ifaces == ["enp1s0"]
    assert transition.route_live_cmds == []


def test_plan_transition_route_only_change_is_live_not_restart():
    old = parse(WITH_EXTRAS)
    route = RouteSpec("10.2.0.0/24", "10.0.0.254", "eth0", None)
    new = build_target(old, [DesiredInterface("eth0", "static", "10.0.0.5/24", "10.0.0.1", 1500, [route])])
    transition = plan_transition(old, new)
    assert transition.restart_ifaces == []
    assert ["ip", "route", "replace", "10.2.0.0/24", "via", "10.0.0.254", "dev", "eth0"] in transition.route_live_cmds


def test_plan_transition_route_removed_generates_del():
    old = parse(WITH_EXTRAS)
    new = build_target(old, [DesiredInterface("eth0", "static", "10.0.0.5/24", "10.0.0.1", 1500, [])])
    transition = plan_transition(old, new)
    assert transition.restart_ifaces == []
    assert transition.route_live_cmds == [
        ["ip", "route", "del", "10.1.0.0/24", "via", "10.0.0.254", "dev", "eth0", "metric", "50"]
    ]


def test_plan_transition_no_changes_is_empty():
    old = parse(WITH_EXTRAS)
    transition = plan_transition(old, old)
    assert transition.restart_ifaces == []
    assert transition.route_live_cmds == []


def test_plan_transition_is_symmetric_for_rollback():
    """Rollback — xuddi shu funksiya, faqat `current`/`target` ALMASHTIRILGAN
    holda chaqiriladi (ifupdown.py#L245 — `plan_transition`ning o'zi yo'nalishga
    bog'liq emas)."""
    old = parse(DEBIAN_DEFAULT)
    new = build_target(old, [DesiredInterface("enp1s0", "static", "192.168.1.10/24", None, None)])
    forward = plan_transition(old, new)
    backward = plan_transition(new, old)
    assert forward.restart_ifaces == backward.restart_ifaces == ["enp1s0"]


# --------------------------------------------------------------------------
# So'nggi himoya chizig'i (`render`): `validate.py` biror narsani o'tkazib
# yuborsa ham, qatorlar in'eksiyasi FAYLGA yetib bormasligi kerak (admin ->
# root RCE, m8-network-contract.md xavfsizlik eslatmasi).
INJECTED_ADDRESS = "fe80::1%eth0\n    pre-up touch /tmp/pwned #/64"


def test_render_rejects_injected_newline_in_address():
    old = parse(DEBIAN_DEFAULT)
    desired = [DesiredInterface("enp1s0", "static", INJECTED_ADDRESS, None, None)]
    with pytest.raises(UnsafeRenderError):
        render(build_target(old, desired))


def test_render_rejects_injected_newline_in_gateway():
    old = parse(DEBIAN_DEFAULT)
    desired = [DesiredInterface("enp1s0", "static", "10.0.0.5/24", "10.0.0.1\n    pre-up touch /tmp/pwned #", None)]
    with pytest.raises(UnsafeRenderError):
        render(build_target(old, desired))


def test_render_rejects_injected_newline_in_route_metric():
    old = parse(DEBIAN_DEFAULT)
    route = RouteSpec("10.9.0.0/24", "192.168.1.1", "enp1s0", "0\n    pre-up touch /tmp/pwned #")
    desired = [DesiredInterface("enp1s0", "static", "192.168.1.10/24", "192.168.1.1", None, [route])]
    with pytest.raises(UnsafeRenderError):
        render(build_target(old, desired))


def test_render_accepts_clean_values():
    """Guard faqat xavfli qatorlarni to'xtatadi — oddiy qiymatlar odatdagidek
    o'tadi (regressiyasiz)."""
    old = parse(DEBIAN_DEFAULT)
    desired = [DesiredInterface("enp1s0", "static", "192.168.1.10/24", "192.168.1.1", 1500)]
    new_text = render(build_target(old, desired))
    assert "address 192.168.1.10/24" in new_text
