"""WS hodisalar sof qoidalari — m10-onlinepbx-contract.md Bo'lak B3."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services import events_ws as ws_mod
from app.services.events_ws import (
    MAX_CONNECTIONS_PER_KEY,
    MAX_CONNECTIONS_PER_TENANT,
    MAX_REPLAY_EVENTS,
    ConnectionLimiter,
    clamp_since_seq,
    event_matches,
    replay_cutoff,
    validate_subscribe,
    wants_ws_event,
)


def test_event_matches_wildcard():
    assert event_matches(("*",), "call.ended") is True


def test_event_matches_explicit_list():
    assert event_matches(("call.ended", "call.ringing"), "call.ended") is True
    assert event_matches(("call.ended",), "call.ringing") is False


def test_wants_ws_event_internal_blocked_without_include_internal():
    assert wants_ws_event(("*",), False, "call.ended", internal=True) is False


def test_wants_ws_event_internal_allowed_with_include_internal():
    assert wants_ws_event(("*",), True, "call.ended", internal=True) is True


def test_wants_ws_event_non_internal_ignores_include_internal_flag():
    assert wants_ws_event(("*",), False, "call.ended", internal=False) is True


def test_wants_ws_event_still_respects_subscription_filter():
    assert wants_ws_event(("call.ringing",), True, "call.ended", internal=False) is False


def test_validate_subscribe_empty_means_wildcard():
    assert validate_subscribe(None) == ("*",)
    assert validate_subscribe([]) == ("*",)


def test_validate_subscribe_explicit_list():
    assert validate_subscribe(["call.ended", "call.ringing"]) == ("call.ended", "call.ringing")


def test_validate_subscribe_rejects_blank_entries():
    assert validate_subscribe(["call.ended", ""]) is None
    assert validate_subscribe(["   "]) is None


def test_clamp_since_seq_none_passthrough():
    assert clamp_since_seq(None, 5000) is None


def test_clamp_since_seq_within_bound_unchanged():
    assert clamp_since_seq(4990, 5000) == 4990


def test_clamp_since_seq_too_far_back_is_raised_to_floor():
    # latest=5000, so'rov 0 -> floor = 5000-1000 = 4000
    assert clamp_since_seq(0, 5000) == 4000


def test_clamp_since_seq_latest_below_max_replay_floor_is_zero():
    assert clamp_since_seq(0, 500) == 0


def test_replay_cutoff_is_24h_before_now():
    now = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)
    assert replay_cutoff(now) == now - timedelta(hours=24)


def test_connection_limiter_allows_up_to_max_per_key():
    limiter = ConnectionLimiter()
    for _ in range(MAX_CONNECTIONS_PER_KEY):
        assert limiter.can_connect(key_id="k1", tenant_id="t1") is True
        limiter.register(key_id="k1", tenant_id="t1")
    assert limiter.can_connect(key_id="k1", tenant_id="t1") is False


def test_connection_limiter_allows_up_to_max_per_tenant_across_keys():
    limiter = ConnectionLimiter()
    for i in range(MAX_CONNECTIONS_PER_TENANT):
        key = f"k{i}"
        assert limiter.can_connect(key_id=key, tenant_id="t1") is True
        limiter.register(key_id=key, tenant_id="t1")
    assert limiter.can_connect(key_id="k_extra", tenant_id="t1") is False


def test_connection_limiter_release_frees_slot():
    limiter = ConnectionLimiter()
    limiter.register(key_id="k1", tenant_id="t1")
    limiter.release(key_id="k1", tenant_id="t1")
    assert limiter.can_connect(key_id="k1", tenant_id="t1") is True
    assert "k1" not in limiter.per_key
    assert "t1" not in limiter.per_tenant


def test_connection_limiter_different_tenants_independent():
    """GLOBAL chegaradan (M12 C M2) PASTDA — tenant'lar bir-biridan mustaqil."""
    limiter = ConnectionLimiter()
    for i in range(MAX_CONNECTIONS_PER_TENANT - 1):
        limiter.register(key_id=f"k{i}", tenant_id="t1")
    assert limiter.can_connect(key_id="other", tenant_id="t2") is True


def test_connection_limiter_global_cap_blocks_even_new_tenant(monkeypatch):
    """M12 C M2: GLOBAL chegara (`MAX_CONNECTIONS_TOTAL`) tenant/kalit bo'yicha
    chegaralardan QAT'I NAZAR ishlaydi — bitta tenant to'lsa, YANGI tenant ham
    ulana olmaydi (DB pool/jarayon resursini ko'p tenant birgalikda tugata
    olmasligi uchun, pastroq sinov qiymati bilan — testlar sekin bo'lmasin)."""
    monkeypatch.setattr(ws_mod, "MAX_CONNECTIONS_TOTAL", 3)
    limiter = ConnectionLimiter()
    for i in range(3):
        limiter.register(key_id=f"k{i}", tenant_id="t1")
    assert limiter.can_connect(key_id="new-key", tenant_id="t2-yangi") is False


def test_connection_limiter_global_cap_release_frees_slot_for_other_tenant(monkeypatch):
    monkeypatch.setattr(ws_mod, "MAX_CONNECTIONS_TOTAL", 3)
    limiter = ConnectionLimiter()
    for i in range(3):
        limiter.register(key_id=f"k{i}", tenant_id="t1")
    limiter.release(key_id="k0", tenant_id="t1")
    assert limiter.can_connect(key_id="new-key", tenant_id="t2-yangi") is True
