"""`app/services/report_defs.py` — Analitika (S13, m2b-contract.md bo'lim 5)
sof hisoblash funksiyalari (bazasiz, ub-mode TDD, mutator nishoni)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.errors import ApiError
from app.db.models import AgentEvent, Cdr, QueueLog
from app.services.report_defs import (
    AgentQueueStats,
    active_seconds,
    agent_queue_stats,
    build_agent_report_row,
    build_daily,
    build_hourly,
    build_queue_report_row,
    build_summary,
    busiest_hour,
    filter_calls_by_linkedid,
    login_pause_seconds,
    queue_stats_from_log,
    queue_wait_samples,
    range_bounds_utc,
    report_calls_from_rows,
    sla_percent,
    validate_range,
)

TZ_TASHKENT = "Asia/Tashkent"  # UTC+5, DST yo'q


def _cdr(**kw) -> Cdr:
    defaults = dict(
        calldate=datetime(2026, 10, 28, 10, 0, 0), clid=None, src="912345678", dst="998901234567",
        dcontext="t1-dest-x", channel="PJSIP/t1-trunk-1-00000000", dstchannel=None,
        lastapp="Dial", lastdata=None, duration=20, billsec=15, disposition="NO ANSWER",
        amaflags=None, accountcode="t1", uniqueid="1.0", linkedid="1.0", userfield=None,
        peeraccount=None, sequence=0, recordingfile=None,
    )
    defaults.update(kw)
    return Cdr(**defaults)


def _ext_answered(**kw) -> Cdr:
    """Haqiqiy ichki raqamga ANSWERED oyoq (trunk EMAS, billsec>0)."""
    defaults = dict(dstchannel="PJSIP/t1-101-00000001", disposition="ANSWERED", duration=20, billsec=15)
    defaults.update(kw)
    return _cdr(**defaults)


def _qlog(**kw) -> QueueLog:
    defaults = dict(
        time=datetime(2026, 10, 28, 10, 0, 0), callid="1.0", queuename="t1-q-1", agent=None,
        event="ENTERQUEUE", data=None, data1=None, data2=None, data3=None, data4=None, data5=None,
    )
    defaults.update(kw)
    return QueueLog(**defaults)


def _agent_event(**kw) -> AgentEvent:
    defaults = dict(
        tenant_id="t1", extension_id="e1", queue_id=None, event="login", reason=None,
        source="agi", at=datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc),
    )
    defaults.update(kw)
    return AgentEvent(**defaults)


# --------------------------------------------------------------- oraliq
def test_validate_range_accepts_single_day():
    validate_range(date(2026, 10, 28), date(2026, 10, 28))


def test_validate_range_accepts_92_days():
    validate_range(date(2026, 1, 1), date(2026, 4, 2))  # 92 kun


def test_validate_range_rejects_more_than_92_days():
    with pytest.raises(ApiError) as exc_info:
        validate_range(date(2026, 1, 1), date(2026, 4, 3))  # 93 kun
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "bad_range"
    assert exc_info.value.field == "to"


def test_validate_range_rejects_to_before_from():
    with pytest.raises(ApiError):
        validate_range(date(2026, 10, 28), date(2026, 10, 27))


def test_range_bounds_utc_to_is_fully_inclusive():
    start, end = range_bounds_utc(TZ_TASHKENT, date(2026, 10, 28), date(2026, 10, 28))
    assert start == datetime(2026, 10, 27, 19, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 10, 28, 19, 0, tzinfo=timezone.utc)
    assert (end - start).total_seconds() == 86400


# --------------------------------------------------------------- report_calls_from_rows
def test_report_calls_groups_by_linkedid_not_uniqueid():
    rows = [
        _cdr(uniqueid="a", linkedid="L1"),
        _cdr(uniqueid="b", linkedid="L1"),  # transfer/forward davomi
        _cdr(uniqueid="c", linkedid="L2"),
    ]
    calls = report_calls_from_rows(rows)
    assert len(calls) == 2
    assert {c.linkedid for c in calls} == {"L1", "L2"}


def test_report_calls_ivr_own_answer_does_not_count_as_answered():
    # IVR o'z Answer()i — dstchannel bo'sh/trunk, "answered" EMAS (B-M1a-05)
    rows = [_cdr(disposition="ANSWERED", billsec=5, dstchannel=None)]
    calls = report_calls_from_rows(rows)
    assert calls[0].answered is False


def test_report_calls_trunk_dstchannel_does_not_count_as_answered():
    rows = [_cdr(disposition="ANSWERED", billsec=5, dstchannel="PJSIP/t1-trunk-1-00000002")]
    calls = report_calls_from_rows(rows)
    assert calls[0].answered is False


def test_report_calls_real_extension_leg_answered_counts():
    rows = [_ext_answered()]
    calls = report_calls_from_rows(rows)
    assert calls[0].answered is True
    assert calls[0].talk_seconds == 15


def test_report_calls_billsec_zero_does_not_count_as_answered():
    rows = [_ext_answered(billsec=0)]
    calls = report_calls_from_rows(rows)
    assert calls[0].answered is False


def test_report_calls_blocked_from_userfield_blacklisted():
    rows = [_cdr(userfield="blacklisted", disposition="NO ANSWER")]
    calls = report_calls_from_rows(rows)
    assert calls[0].blocked is True


def test_report_calls_wait_seconds_from_duration_minus_billsec():
    rows = [_ext_answered(duration=20, billsec=15)]
    calls = report_calls_from_rows(rows)
    assert calls[0].wait_seconds == 5


def test_filter_calls_by_linkedid_keeps_only_matching():
    calls = report_calls_from_rows([_cdr(linkedid="L1"), _cdr(uniqueid="x", linkedid="L2")])
    filtered = filter_calls_by_linkedid(calls, {"L1"})
    assert [c.linkedid for c in filtered] == ["L1"]


# --------------------------------------------------------------- SLA/busiest_hour
def test_sla_percent_empty_samples_is_none():
    assert sla_percent([]) is None


def test_sla_percent_computes_hit_ratio():
    assert sla_percent([(10, 20), (30, 20), (5, 20)]) == pytest.approx(200 / 3)


def test_busiest_hour_none_without_calls():
    assert busiest_hour([], TZ_TASHKENT) is None


def test_busiest_hour_picks_hour_with_most_calls_in_tenant_tz():
    rows = [
        _cdr(uniqueid="1", linkedid="1", calldate=datetime(2026, 10, 28, 5, 0)),   # 10:00 Tashkent
        _cdr(uniqueid="2", linkedid="2", calldate=datetime(2026, 10, 28, 5, 30)),  # 10:30 Tashkent
        _cdr(uniqueid="3", linkedid="3", calldate=datetime(2026, 10, 28, 6, 0)),   # 11:00 Tashkent
    ]
    calls = report_calls_from_rows(rows)
    assert busiest_hour(calls, TZ_TASHKENT) == 10


# --------------------------------------------------------------- build_summary/hourly/daily
def test_build_summary_counts_by_direction_and_status():
    rows = [
        _ext_answered(uniqueid="1", linkedid="1", channel="PJSIP/t1-trunk-1-x"),  # in, answered
        _cdr(uniqueid="2", linkedid="2", channel="PJSIP/t1-trunk-1-x", disposition="NO ANSWER"),  # in, missed
        _cdr(uniqueid="3", linkedid="3", channel="PJSIP/t1-trunk-1-x", userfield="blacklisted"),  # in, blocked
    ]
    calls = report_calls_from_rows(rows)
    summary = build_summary(calls, TZ_TASHKENT, [])
    assert summary["total"] == 3
    assert summary["inbound"] == 3
    assert summary["answered"] == 1
    assert summary["missed"] == 1
    assert summary["blocked"] == 1


def test_build_summary_avg_wait_and_talk_only_from_answered():
    rows = [_ext_answered(duration=20, billsec=15)]
    calls = report_calls_from_rows(rows)
    summary = build_summary(calls, TZ_TASHKENT, [])
    assert summary["avg_wait_seconds"] == 5
    assert summary["avg_talk_seconds"] == 15


def test_build_summary_sla_percent_from_samples():
    summary = build_summary([], TZ_TASHKENT, [(10, 20), (30, 20)])
    assert summary["sla_percent"] == 50.0


def test_build_hourly_always_returns_24_rows():
    assert len(build_hourly([], TZ_TASHKENT)) == 24


def test_build_hourly_sum_equals_summary_counts():
    rows = [
        _ext_answered(uniqueid="1", linkedid="1", channel="PJSIP/t1-trunk-1-x",
                      calldate=datetime(2026, 10, 28, 5, 0)),
        _cdr(uniqueid="2", linkedid="2", channel="PJSIP/t1-trunk-1-x", disposition="NO ANSWER",
             calldate=datetime(2026, 10, 28, 6, 0)),
    ]
    calls = report_calls_from_rows(rows)
    hourly = build_hourly(calls, TZ_TASHKENT)
    summary = build_summary(calls, TZ_TASHKENT, [])
    assert sum(h["inbound"] for h in hourly) == summary["inbound"]
    assert sum(h["answered"] for h in hourly) == summary["answered"]
    assert sum(h["missed"] for h in hourly) == summary["missed"]


def test_build_daily_includes_empty_days_as_zero():
    daily = build_daily([], TZ_TASHKENT, date(2026, 10, 26), date(2026, 10, 28))
    assert [d["date"] for d in daily] == ["2026-10-26", "2026-10-27", "2026-10-28"]
    assert all(d["total"] == 0 for d in daily)


def test_build_daily_buckets_by_tenant_local_date():
    rows = [_cdr(uniqueid="1", linkedid="1", calldate=datetime(2026, 10, 28, 20, 0))]  # 2026-10-29 01:00 Tashkent
    calls = report_calls_from_rows(rows)
    daily = build_daily(calls, TZ_TASHKENT, date(2026, 10, 28), date(2026, 10, 29))
    by_date = {d["date"]: d["total"] for d in daily}
    assert by_date["2026-10-29"] == 1
    assert by_date["2026-10-28"] == 0


# --------------------------------------------------------------- queue_log -> navbat
def test_queue_log_wait_ignores_non_numeric_data_defensively():
    # Haqiqiy Asterisk har doim butun son yozadi, lekin himoya uchun:
    # noto'g'ri qiymat qulamasdan 0 deb hisoblanadi.
    row = _qlog(event="CONNECT", data1="not-a-number")
    stats = queue_stats_from_log([row])
    assert stats.waits == [0]


def test_queue_stats_from_log_counts_events():
    rows = [
        _qlog(event="ENTERQUEUE"),
        _qlog(event="CONNECT", data1="7"),
        _qlog(event="ABANDON", data3="12"),
        _qlog(event="EXITWITHTIMEOUT"),
    ]
    stats = queue_stats_from_log(rows)
    assert stats.entered == 1
    assert stats.answered == 1
    assert stats.abandoned == 1
    assert stats.timeout == 1
    assert sorted(stats.waits) == [7, 12]


def test_build_queue_report_row_sla_and_avg_max_wait():
    rows = [_qlog(event="CONNECT", data1="10"), _qlog(event="CONNECT", data1="30")]
    stats = queue_stats_from_log(rows)
    row = build_queue_report_row(stats, sla_seconds=20)
    assert row["avg_wait_seconds"] == 20
    assert row["max_wait_seconds"] == 30
    assert row["sla_percent"] == 50.0


def test_build_queue_report_row_no_waits_is_zero_not_error():
    row = build_queue_report_row(queue_stats_from_log([]), sla_seconds=20)
    assert row["avg_wait_seconds"] == 0
    assert row["max_wait_seconds"] == 0
    assert row["sla_percent"] is None


def test_queue_wait_samples_pairs_each_row_with_its_own_queue_sla():
    rows = [_qlog(event="CONNECT", data1="10", queuename="t1-q-1"),
            _qlog(event="CONNECT", data1="30", queuename="t1-q-2")]
    samples = queue_wait_samples(rows, {"t1-q-1": 20, "t1-q-2": 60})
    assert set(samples) == {(10, 20), (30, 60)}


def test_queue_wait_samples_skips_unknown_queuename():
    rows = [_qlog(event="CONNECT", data1="10", queuename="unknown")]
    assert queue_wait_samples(rows, {"t1-q-1": 20}) == []


# --------------------------------------------------------------- agent login/pauza
def test_active_seconds_counts_time_in_active_state():
    start = datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)
    events = [(datetime(2026, 10, 28, 8, 30, tzinfo=timezone.utc), True),
              (datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc), False)]
    assert active_seconds(events, start, end) == 1800  # 08:30-09:00


def test_active_seconds_open_session_counts_through_to_window_end():
    start = datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)
    events = [(datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc), True)]  # logout yo'q -> ochiq
    assert active_seconds(events, start, end) == 3600  # 09:00-10:00


def test_active_seconds_state_before_window_start_is_respected():
    start = datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)
    events = [(datetime(2026, 10, 28, 7, 0, tzinfo=timezone.utc), True)]  # oynadan oldin login
    assert active_seconds(events, start, end) == 7200  # butun oyna


def test_login_pause_seconds_from_agent_events():
    events = [
        _agent_event(event="login", at=datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc)),
        _agent_event(event="pause", at=datetime(2026, 10, 28, 8, 30, tzinfo=timezone.utc)),
        _agent_event(event="unpause", at=datetime(2026, 10, 28, 8, 45, tzinfo=timezone.utc)),
        _agent_event(event="logout", at=datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)),
    ]
    start = datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)
    login_seconds, pause_seconds = login_pause_seconds(events, start, end)
    assert login_seconds == 3600
    assert pause_seconds == 900


def test_login_pause_seconds_dedups_duplicate_events_from_multi_queue_membership():
    at = datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc)
    events = [_agent_event(event="login", at=at, queue_id="q1"), _agent_event(event="login", at=at, queue_id="q2")]
    start = datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)
    login_seconds, _ = login_pause_seconds(events, start, end)
    assert login_seconds == 3600


def test_agent_queue_stats_keyed_by_membername():
    rows = [
        _qlog(event="CONNECT", agent="Operator Ali"),
        _qlog(event="RINGNOANSWER", agent="Operator Ali"),
        _qlog(event="COMPLETECALLER", agent="Operator Ali", data2="42"),
        _qlog(event="CONNECT", agent="NONE"),  # e'tiborsiz
    ]
    stats = agent_queue_stats(rows)
    assert set(stats) == {"Operator Ali"}
    assert stats["Operator Ali"].answered == 1
    assert stats["Operator Ali"].missed_ring == 1
    assert stats["Operator Ali"].talk_seconds == 42


def test_build_agent_report_row_avg_talk_none_without_answered():
    row = build_agent_report_row(
        extension_number="101", extension_name="Operator Ali", queue_stats=AgentQueueStats(),
        login_seconds=100, pause_seconds=10,
    )
    assert row["avg_talk_seconds"] is None
    assert row["login_seconds"] == 100


def test_build_agent_report_row_avg_talk_from_answered_and_talk_seconds():
    stats = AgentQueueStats(answered=2, missed_ring=0, talk_seconds=100)
    row = build_agent_report_row(
        extension_number="101", extension_name="Operator Ali", queue_stats=stats,
        login_seconds=0, pause_seconds=0,
    )
    assert row["avg_talk_seconds"] == 50
