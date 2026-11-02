"""`app/services/trunk_health.py` sof funksiyalari — `/trunks` VA
`/dashboard` AYNAN BIR XIL qoidani ishlatishini kafolatlaydi (ub-mode DRY)."""
from __future__ import annotations

from app.services.trunk_health import endpoint_id_for, state_from_db_health, state_from_registration


def test_state_from_registration_registered_is_ok():
    assert state_from_registration("registered") == "ok"


def test_state_from_registration_rejected_is_unreachable():
    assert state_from_registration("rejected") == "unreachable"


def test_state_from_registration_unregistered_is_unreachable():
    assert state_from_registration("unregistered") == "unreachable"


def test_state_from_registration_none_is_unknown():
    assert state_from_registration(None) == "unknown"


def test_state_from_db_health_ok():
    assert state_from_db_health("ok") == "ok"


def test_state_from_db_health_down_is_unreachable():
    assert state_from_db_health("down") == "unreachable"


def test_state_from_db_health_unknown_value_is_unknown():
    assert state_from_db_health("whatever") == "unknown"


def test_endpoint_id_for_matches_tenant_code_and_trunk_id():
    assert endpoint_id_for("t1", "abc-123") == "t1-trunk-abc-123"
