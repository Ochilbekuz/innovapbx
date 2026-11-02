"""`app/services/toll_fraud.py` sof qismi (`decide`, `window_start`) —
bazasiz (ub-mode TDD). Nosof qism (`check_outbound`) ni'l: hali to'liq
oqim jonli isbotda (`scripts/m2c-proof.sh` ssenariy 5/6) tekshiriladi."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.toll_fraud import decide, window_start

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


def test_decide_disabled_always_allowed():
    allowed, reason = decide(enabled=False, already_blocked=False, intl=False,
                             hour_count=999, hour_limit=1, intl_count=999, intl_limit=1)
    assert (allowed, reason) == (True, None)


def test_decide_already_blocked_denies_without_new_reason():
    allowed, reason = decide(enabled=True, already_blocked=True, intl=False,
                             hour_count=0, hour_limit=60, intl_count=0, intl_limit=20)
    assert (allowed, reason) == (False, None)


def test_decide_under_hour_limit_allowed():
    allowed, reason = decide(enabled=True, already_blocked=False, intl=False,
                             hour_count=1, hour_limit=2, intl_count=0, intl_limit=20)
    assert (allowed, reason) == (True, None)


def test_decide_at_hour_limit_blocks_per_hour():
    allowed, reason = decide(enabled=True, already_blocked=False, intl=False,
                             hour_count=2, hour_limit=2, intl_count=0, intl_limit=20)
    assert (allowed, reason) == (False, "per_hour")


def test_decide_hour_limit_zero_means_unlimited():
    allowed, reason = decide(enabled=True, already_blocked=False, intl=False,
                             hour_count=10_000, hour_limit=0, intl_count=0, intl_limit=20)
    assert (allowed, reason) == (True, None)


def test_decide_local_call_ignores_intl_limit_even_if_exceeded():
    allowed, reason = decide(enabled=True, already_blocked=False, intl=False,
                             hour_count=0, hour_limit=60, intl_count=99, intl_limit=1)
    assert (allowed, reason) == (True, None)


def test_decide_intl_call_at_intl_limit_blocks_international_per_day():
    allowed, reason = decide(enabled=True, already_blocked=False, intl=True,
                             hour_count=0, hour_limit=60, intl_count=1, intl_limit=1)
    assert (allowed, reason) == (False, "international_per_day")


def test_decide_hour_limit_checked_before_intl_limit():
    """Ikkalasi ham oshgan bo'lsa — soatlik SABABI birinchi (umumiyroq)."""
    allowed, reason = decide(enabled=True, already_blocked=False, intl=True,
                             hour_count=2, hour_limit=2, intl_count=1, intl_limit=1)
    assert (allowed, reason) == (False, "per_hour")


def test_window_start_without_unblocked_at_is_now_minus_span():
    assert window_start(NOW, span=timedelta(hours=1), unblocked_at=None) == NOW - timedelta(hours=1)


def test_window_start_floors_at_unblocked_at_when_more_recent():
    unblocked = NOW - timedelta(minutes=10)
    assert window_start(NOW, span=timedelta(hours=1), unblocked_at=unblocked) == unblocked


def test_window_start_ignores_unblocked_at_when_older_than_span():
    unblocked = NOW - timedelta(days=5)
    assert window_start(NOW, span=timedelta(hours=1), unblocked_at=unblocked) == NOW - timedelta(hours=1)
