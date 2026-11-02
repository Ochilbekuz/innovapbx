"""Zaxira jadvali — vaqt hisoblash (m4b-contract.md §0/§4 6-band: catch-up, qayta urinmaslik)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.backup_schedule import Schedule, is_due, last_slot_at_or_before

UTC = timezone.utc


def test_disabled_schedule_is_never_due():
    schedule = Schedule(enabled=False, frequency="daily", weekday=0, time="03:00")
    now = datetime(2026, 10, 29, 3, 1, tzinfo=UTC)
    assert last_slot_at_or_before(now, schedule) is None
    assert is_due(now, schedule, None) is False


def test_daily_due_right_after_slot_with_no_previous_run():
    schedule = Schedule(enabled=True, frequency="daily", weekday=0, time="03:00")
    now = datetime(2026, 10, 29, 3, 1, tzinfo=UTC)
    assert is_due(now, schedule, None) is True


def test_daily_not_due_again_same_slot_after_running():
    schedule = Schedule(enabled=True, frequency="daily", weekday=0, time="03:00")
    slot = datetime(2026, 10, 29, 3, 0, tzinfo=UTC)
    now = datetime(2026, 10, 29, 3, 30, tzinfo=UTC)
    assert is_due(now, schedule, last_run_at=slot) is False


def test_daily_not_due_before_slot_time():
    schedule = Schedule(enabled=True, frequency="daily", weekday=0, time="03:00")
    now = datetime(2026, 10, 29, 2, 59, tzinfo=UTC)
    last_run = datetime(2026, 10, 28, 3, 0, tzinfo=UTC)
    assert is_due(now, schedule, last_run_at=last_run) is False


def test_catch_up_runs_once_after_missed_slot_server_was_off():
    schedule = Schedule(enabled=True, frequency="daily", weekday=0, time="03:00")
    last_run = datetime(2026, 10, 27, 3, 0, tzinfo=UTC)  # 2 kun oldin ishlagan
    now = datetime(2026, 10, 29, 10, 0, tzinfo=UTC)  # server shunchaki kech ko'tarilgan
    assert is_due(now, schedule, last_run_at=last_run) is True
    # Birinchi ishga tushgandan keyin darhol qayta so'ralmasligi kerak:
    new_last_run = last_slot_at_or_before(now, schedule)
    assert is_due(now, schedule, last_run_at=new_last_run) is False


def test_weekly_picks_correct_weekday():
    # 2026-10-29 — payshanba (weekday=3). Dushanba (0) kuni 03:00 rejalashtirilgan.
    schedule = Schedule(enabled=True, frequency="weekly", weekday=0, time="03:00")
    now = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
    slot = last_slot_at_or_before(now, schedule)
    assert slot.weekday() == 0
    assert slot <= now
    assert now - slot < timedelta(days=7)


def test_timezone_offset_shifts_slot():
    # Tashkentda (UTC+5) 03:00 = UTC 22:00 (oldingi kun).
    schedule = Schedule(enabled=True, frequency="daily", weekday=0, time="03:00",
                        tz_offset_minutes=5 * 60)
    now = datetime(2026, 10, 29, 22, 30, tzinfo=UTC)
    slot = last_slot_at_or_before(now, schedule)
    assert slot == datetime(2026, 10, 29, 22, 0, tzinfo=UTC)


def test_invalid_frequency_rejected():
    with pytest.raises(ValueError):
        Schedule(enabled=True, frequency="monthly", weekday=0, time="03:00")
