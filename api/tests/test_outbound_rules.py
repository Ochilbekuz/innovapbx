"""`app/services/outbound_rules.py` — sof funksiyalar, bazasiz test (ub-mode TDD).
m1b-contract.md bo'lim 2: simulyator va dialplan BIR XIL qoidadan foydalanadi —
shu modul ikkisi uchun ham yagona manba."""
from __future__ import annotations

from app.services.outbound_rules import (
    PatternRule,
    RouteRule,
    TrunkRef,
    international_blocked,
    match_number_against_route,
    pattern_matches,
    resolve_callerid,
    resolve_route,
    strip_number,
    validate_pattern,
)


# --------------------------------------------------------------------- naqsh
def test_validate_pattern_accepts_contract_example():
    assert validate_pattern("998XXXXXXXXX").ok
    assert validate_pattern("XXXXXXXXX").ok


def test_validate_pattern_rejects_empty():
    result = validate_pattern("")
    assert not result.ok and result.reason


def test_validate_pattern_rejects_bad_char():
    result = validate_pattern("998ABC")
    assert not result.ok


def test_validate_pattern_dot_only_at_end():
    assert not validate_pattern("9.8").ok
    assert validate_pattern("998.").ok


def test_validate_pattern_range_must_be_ordered():
    assert not validate_pattern("[5-1]23").ok
    assert validate_pattern("[1-5]23").ok


def test_pattern_matches_classes():
    assert pattern_matches("XXXXXXXXX", "901234567")
    assert not pattern_matches("XXXXXXXXX", "90123456")  # qisqa
    assert pattern_matches("Z0XXXXXXX", "901234567")
    assert not pattern_matches("Z0XXXXXXX", "001234567")  # Z 1-9, 0 emas


def test_pattern_matches_dot_is_greedy_tail():
    assert pattern_matches("998.", "998901234567")
    assert not pattern_matches("998.", "997901234567")


# ------------------------------------------------------------- strip/prefix
def test_strip_number_by_character_count():
    """m1b-contract.md misoli: strip_prefix='0', '0901234567' -> '901234567'."""
    assert strip_number("0", "0901234567") == "901234567"
    assert strip_number("", "0901234567") == "0901234567"
    assert strip_number("00", "0098712345") == "98712345"


# --------------------------------------------------------------- xalqaro
def test_international_blocked_when_not_international_and_not_uz():
    assert international_blocked("0044201234567", international=False)
    assert international_blocked("+44201234567", international=False)


def test_international_not_blocked_for_uz_or_when_allowed():
    assert not international_blocked("00998901234567", international=False)
    assert not international_blocked("0044201234567", international=True)
    assert not international_blocked("901234567", international=False)


# --------------------------------------------------------- marshrut tanlash
def _uz_route(priority=1, enabled=True, international=False, allowed=None) -> RouteRule:
    return RouteRule(
        id="r-uz", name="UZ", priority=priority, enabled=enabled, international=international,
        patterns=(PatternRule(strip_prefix="0", pattern="XXXXXXXXX", add_prefix="998"),),
        trunks=(TrunkRef(id="tA", name="Trunk A"), TrunkRef(id="tB", name="Trunk B")),
        allowed_extension_ids=allowed,
    )


def test_match_number_against_route_full_worked_example():
    """m1b-contract.md misoli: 101 -> '0901234567' -> strip '0' -> 'XXXXXXXXX' mos
    -> add_prefix '998' -> '998901234567'."""
    match, step = match_number_against_route(_uz_route(), "0901234567", extension_id="e-101")
    assert match is not None and match.dialed == "998901234567"
    assert step.result == "match"


def test_match_disabled_route_short_circuits():
    _, step = match_number_against_route(_uz_route(enabled=False), "0901234567", extension_id="e-101")
    assert step.result == "disabled"


def test_match_ext_not_allowed():
    route = _uz_route(allowed=("e-999",))
    _, step = match_number_against_route(route, "0901234567", extension_id="e-101")
    assert step.result == "ext_not_allowed"


def test_match_international_blocked_before_pattern_check():
    route = _uz_route()
    _, step = match_number_against_route(route, "0044201234567", extension_id="e-101")
    assert step.result == "international_blocked"


def test_match_no_pattern():
    _, step = match_number_against_route(_uz_route(), "123", extension_id="e-101")
    assert step.result == "no_pattern"


def test_resolve_route_priority_order_first_match_wins():
    low_priority_catch_all = RouteRule(
        id="r-any", name="Catch-all", priority=2, enabled=True, international=True,
        patterns=(PatternRule(strip_prefix="", pattern=".", add_prefix=""),),
        trunks=(TrunkRef(id="tC", name="Trunk C"),),
    )
    outcome = resolve_route([low_priority_catch_all, _uz_route(priority=1)], "0901234567", extension_id="e-101")
    assert outcome.allowed and outcome.route.id == "r-uz" and outcome.dialed == "998901234567"
    assert [s.route for s in outcome.steps] == ["UZ"]  # priority=1 birinchi tekshiriladi, mos keldi


def test_resolve_route_falls_through_when_first_route_rejects():
    outcome = resolve_route([_uz_route(priority=1, allowed=("e-999",))], "0901234567", extension_id="e-101")
    assert not outcome.allowed and outcome.reason


def test_resolve_route_no_routes_at_all():
    outcome = resolve_route([], "0901234567", extension_id="e-101")
    assert not outcome.allowed and outcome.route is None and outcome.trunks == ()


# ------------------------------------------------------------- CallerID
def test_resolve_callerid_tier_a_override_wins():
    assert resolve_callerid(
        route_callerid="+998 71 000 00 00", override_extension_callerid=True,
        extension_outbound_callerid="101", trunk_outbound_callerid="trunk-cid",
    ) == "+998 71 000 00 00"


def test_resolve_callerid_tier_b_extension_wins_over_route():
    assert resolve_callerid(
        route_callerid="route-cid", override_extension_callerid=False,
        extension_outbound_callerid="ext-cid", trunk_outbound_callerid="trunk-cid",
    ) == "ext-cid"


def test_resolve_callerid_tier_c_route_when_no_extension_cid():
    assert resolve_callerid(
        route_callerid="route-cid", override_extension_callerid=False,
        extension_outbound_callerid=None, trunk_outbound_callerid="trunk-cid",
    ) == "route-cid"


def test_resolve_callerid_tier_d_trunk_fallback():
    assert resolve_callerid(
        route_callerid=None, override_extension_callerid=False,
        extension_outbound_callerid=None, trunk_outbound_callerid="trunk-cid",
    ) == "trunk-cid"


def test_resolve_callerid_all_none():
    assert resolve_callerid(
        route_callerid=None, override_extension_callerid=False,
        extension_outbound_callerid=None, trunk_outbound_callerid=None,
    ) is None
