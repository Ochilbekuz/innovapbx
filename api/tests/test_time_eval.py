"""`state_now` hisoblash — sof funksiya, bazasiz (ub-mode: TDD)."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.services.time_eval import compute_state_now


def _fixed_now(iso: str):
    return datetime.fromisoformat(iso).replace(tzinfo=ZoneInfo("Asia/Tashkent"))


def test_force_open_override_ignores_schedule():
    assert compute_state_now(
        tz_name="Asia/Tashkent", override="force_open", ranges=[], honor_holidays=False,
        holidays_mmdd=set(),
    ) == "open"


def test_force_closed_override_ignores_schedule():
    assert compute_state_now(
        tz_name="Asia/Tashkent", override="force_closed", ranges=[([1, 2, 3, 4, 5], "00:00", "23:59")],
        honor_holidays=False, holidays_mmdd=set(),
    ) == "closed"


def test_auto_mode_open_during_working_hours():
    with patch("app.services.time_eval.datetime") as mock_dt:
        mock_dt.now.return_value = _fixed_now("2026-10-28T10:00:00")  # chorshanba
        result = compute_state_now(
            tz_name="Asia/Tashkent", override="auto",
            ranges=[([1, 2, 3, 4, 5], "09:00", "18:00")], honor_holidays=False, holidays_mmdd=set(),
        )
    assert result == "open"


def test_auto_mode_closed_outside_working_hours():
    with patch("app.services.time_eval.datetime") as mock_dt:
        mock_dt.now.return_value = _fixed_now("2026-10-28T20:00:00")
        result = compute_state_now(
            tz_name="Asia/Tashkent", override="auto",
            ranges=[([1, 2, 3, 4, 5], "09:00", "18:00")], honor_holidays=False, holidays_mmdd=set(),
        )
    assert result == "closed"


def test_auto_mode_closed_on_weekend_even_if_time_matches():
    with patch("app.services.time_eval.datetime") as mock_dt:
        mock_dt.now.return_value = _fixed_now("2026-10-31T10:00:00")  # shanba
        result = compute_state_now(
            tz_name="Asia/Tashkent", override="auto",
            ranges=[([1, 2, 3, 4, 5], "09:00", "18:00")], honor_holidays=False, holidays_mmdd=set(),
        )
    assert result == "closed"


def test_auto_mode_closed_on_holiday_even_during_working_hours():
    with patch("app.services.time_eval.datetime") as mock_dt:
        mock_dt.now.return_value = _fixed_now("2026-03-21T10:00:00")  # Navro'z, chorshanba
        result = compute_state_now(
            tz_name="Asia/Tashkent", override="auto",
            ranges=[([1, 2, 3, 4, 5, 6, 7], "09:00", "18:00")],
            honor_holidays=True, holidays_mmdd={(3, 21)},
        )
    assert result == "closed"


def test_auto_mode_ignores_holiday_when_honor_holidays_false():
    with patch("app.services.time_eval.datetime") as mock_dt:
        mock_dt.now.return_value = _fixed_now("2026-03-21T10:00:00")
        result = compute_state_now(
            tz_name="Asia/Tashkent", override="auto",
            ranges=[([1, 2, 3, 4, 5, 6, 7], "09:00", "18:00")],
            honor_holidays=False, holidays_mmdd={(3, 21)},
        )
    assert result == "open"
