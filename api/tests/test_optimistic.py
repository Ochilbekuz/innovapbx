"""`app.core.optimistic` — sof funksiyalar, bazasiz test qilinadi."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.errors import ApiError
from app.core.optimistic import check_not_stale, naive_utc


def test_naive_utc_strips_tzinfo_and_microseconds():
    aware = datetime(2026, 1, 1, 12, 0, 0, 500000, tzinfo=timezone.utc)
    assert naive_utc(aware) == datetime(2026, 1, 1, 12, 0, 0)


def test_naive_utc_passthrough_for_naive_value():
    naive = datetime(2026, 1, 1, 12, 0, 0, 500000)
    assert naive_utc(naive) == datetime(2026, 1, 1, 12, 0, 0)


def test_check_not_stale_passes_when_equal():
    current = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    expected = datetime(2026, 1, 1, 12, 0, 0)
    check_not_stale(current, expected)  # ko'tarmasligi kerak


def test_check_not_stale_raises_409_when_different():
    current = datetime(2026, 1, 1, 12, 0, 1, tzinfo=timezone.utc)
    expected = datetime(2026, 1, 1, 12, 0, 0)
    with pytest.raises(ApiError) as exc_info:
        check_not_stale(current, expected)
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "stale"
