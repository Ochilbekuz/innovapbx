"""`app/services/dashboard.py` — `GET /dashboard` sof hisoblash funksiyalari
(bazasiz/AMI'siz), m1b-contract.md bo'lim 5."""
from __future__ import annotations

from datetime import datetime, timezone

from dataclasses import dataclass

from app.schemas import CallOut
from app.services.dashboard import (
    build_alerts,
    build_missed_calls,
    build_today_stats,
    build_trunk_dashboard_items,
    disk_health,
    today_bounds_utc,
)

TZ_TASHKENT = "Asia/Tashkent"  # UTC+5, DST yo'q


def _call(**kw) -> CallOut:
    defaults = dict(
        uniqueid="1", started_at=datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc), src="912345678",
        dst="998901234567", did=None, direction="in", disposition="answered", duration=20, billsec=15, trunk=None,
    )
    defaults.update(kw)
    return CallOut(**defaults)


def test_today_bounds_utc_converts_tashkent_midnight_to_utc():
    now = datetime(2026, 10, 28, 3, 0, tzinfo=timezone.utc)  # 08:00 Tashkent
    start, end = today_bounds_utc(TZ_TASHKENT, now)
    assert start == datetime(2026, 10, 27, 19, 0, tzinfo=timezone.utc)  # 2026-10-28 00:00 +05:00
    assert end == datetime(2026, 10, 28, 19, 0, tzinfo=timezone.utc)


def test_today_bounds_utc_is_exactly_24_hours():
    now = datetime(2026, 10, 28, 3, 0, tzinfo=timezone.utc)
    start, end = today_bounds_utc(TZ_TASHKENT, now)
    assert (end - start).total_seconds() == 86400


def test_build_today_stats_counts_totals_by_direction_and_disposition():
    calls = [
        _call(uniqueid="1", direction="in", disposition="answered", duration=20, billsec=15),
        _call(uniqueid="2", direction="in", disposition="no_answer", duration=10, billsec=0),
        _call(uniqueid="3", direction="out", disposition="answered", duration=30, billsec=25),
        _call(uniqueid="4", direction="internal", disposition="answered", duration=5, billsec=5),
    ]
    stats = build_today_stats(calls, TZ_TASHKENT)
    assert stats.total == 4
    assert stats.answered == 3
    assert stats.missed == 1
    assert stats.out == 1


def test_build_today_stats_avg_wait_s_only_counts_answered_calls():
    calls = [
        _call(uniqueid="1", disposition="answered", duration=20, billsec=15),  # wait 5
        _call(uniqueid="2", disposition="answered", duration=30, billsec=20),  # wait 10
        _call(uniqueid="3", disposition="no_answer", duration=10, billsec=0),
    ]
    stats = build_today_stats(calls, TZ_TASHKENT)
    assert stats.avg_wait_s == 8  # round((5+10)/2) = round(7.5) = 8 (banker's? -> round-half-even=8)


def test_build_today_stats_avg_wait_s_is_none_without_answered_calls():
    calls = [_call(disposition="no_answer", duration=10, billsec=0)]
    stats = build_today_stats(calls, TZ_TASHKENT)
    assert stats.avg_wait_s is None


def test_build_today_stats_by_hour_uses_tenant_timezone():
    # 2026-10-28 19:30 UTC == 2026-10-29 00:30 Tashkent -> hour 0, not 19
    calls = [_call(started_at=datetime(2026, 10, 28, 19, 30, tzinfo=timezone.utc))]
    stats = build_today_stats(calls, TZ_TASHKENT)
    assert stats.by_hour[0].in_ == 1
    assert stats.by_hour[19].in_ == 0


def test_build_missed_calls_filters_only_unanswered_inbound():
    calls = [
        _call(uniqueid="1", direction="in", disposition="no_answer"),
        _call(uniqueid="2", direction="in", disposition="answered"),
        _call(uniqueid="3", direction="out", disposition="no_answer"),
    ]
    missed = build_missed_calls(calls)
    assert [m.uniqueid for m in missed] == ["1"]


def test_build_missed_calls_marks_called_back_when_later_outbound_answered_same_number():
    missed_at = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)
    later = datetime(2026, 10, 28, 10, 5, tzinfo=timezone.utc)
    calls = [
        _call(uniqueid="1", direction="in", disposition="no_answer", src="912345678", started_at=missed_at),
        _call(uniqueid="2", direction="out", disposition="answered", dst="912345678", started_at=later),
    ]
    missed = build_missed_calls(calls)
    assert missed[0].called_back is True


def test_build_missed_calls_not_called_back_when_callback_is_earlier():
    missed_at = datetime(2026, 10, 28, 10, 5, tzinfo=timezone.utc)
    earlier = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)
    calls = [
        _call(uniqueid="1", direction="in", disposition="no_answer", src="912345678", started_at=missed_at),
        _call(uniqueid="2", direction="out", disposition="answered", dst="912345678", started_at=earlier),
    ]
    missed = build_missed_calls(calls)
    assert missed[0].called_back is False


def test_build_missed_calls_orders_not_called_back_first_then_recent_first():
    calls = [
        _call(uniqueid="old-called-back", direction="in", disposition="no_answer", src="1",
              started_at=datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc)),
        _call(uniqueid="cb", direction="out", disposition="answered", dst="1",
              started_at=datetime(2026, 10, 28, 8, 5, tzinfo=timezone.utc)),
        _call(uniqueid="newer-not-called-back", direction="in", disposition="no_answer", src="2",
              started_at=datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)),
        _call(uniqueid="oldest-not-called-back", direction="in", disposition="busy", src="3",
              started_at=datetime(2026, 10, 28, 7, 0, tzinfo=timezone.utc)),
    ]
    missed = build_missed_calls(calls)
    assert [m.uniqueid for m in missed] == [
        "newer-not-called-back", "oldest-not-called-back", "old-called-back",
    ]


def test_build_missed_calls_respects_limit():
    calls = [
        _call(uniqueid=str(i), direction="in", disposition="no_answer",
              started_at=datetime(2026, 10, 28, 1, 0, tzinfo=timezone.utc))
        for i in range(15)
    ]
    assert len(build_missed_calls(calls, limit=10)) == 10


def test_disk_health_computes_used_pct_and_free_gb():
    health = disk_health(total_bytes=100 * 1024 ** 3, free_bytes=20 * 1024 ** 3)
    assert health.used_pct == 80
    assert health.free_gb == 20.0


def test_build_alerts_empty_when_everything_healthy():
    alerts = build_alerts(asterisk_up=True, disk_used_pct=50, trunk_down=False,
                           has_outbound_route=True, last_revision_rolled_back=False)
    assert alerts == []


def test_build_alerts_asterisk_down():
    alerts = build_alerts(asterisk_up=False, disk_used_pct=50, trunk_down=False,
                           has_outbound_route=True, last_revision_rolled_back=False)
    assert [a.code for a in alerts] == ["asterisk_down"]


def test_build_alerts_includes_all_applicable_codes():
    alerts = build_alerts(asterisk_up=False, disk_used_pct=95, trunk_down=True,
                           has_outbound_route=False, last_revision_rolled_back=True)
    codes = {a.code for a in alerts}
    assert codes == {"asterisk_down", "trunk_down", "disk_low", "no_outbound_route", "revision_rolled_back"}


@dataclass
class _FakeTrunk:
    id: str
    name: str
    enabled: bool
    auth_mode: str


@dataclass
class _FakeDbHealth:
    state: str


def test_build_trunk_dashboard_items_disabled_trunk_ignores_health_inputs():
    trunks = [_FakeTrunk(id="1", name="T1", enabled=False, auth_mode="ip")]
    items = build_trunk_dashboard_items(trunks, db_health_by_id={}, reg_by_trunk_id={})
    assert items[0].state == "disabled"
    assert items[0].registration is None


def test_build_trunk_dashboard_items_register_mode_uses_reg_lookup():
    trunks = [_FakeTrunk(id="1", name="T1", enabled=True, auth_mode="register")]
    reg = {"1": {"registration": "registered", "reason": None}}
    items = build_trunk_dashboard_items(trunks, db_health_by_id={}, reg_by_trunk_id=reg)
    assert items[0].state == "ok"
    assert items[0].registration == "registered"


def test_build_trunk_dashboard_items_ip_mode_uses_db_health_lookup():
    trunks = [_FakeTrunk(id="1", name="T1", enabled=True, auth_mode="ip")]
    db_health = {"1": _FakeDbHealth(state="down")}
    items = build_trunk_dashboard_items(trunks, db_health_by_id=db_health, reg_by_trunk_id={})
    assert items[0].state == "unreachable"
    assert items[0].registration is None


def test_build_trunk_dashboard_items_ip_mode_missing_health_row_is_unknown():
    trunks = [_FakeTrunk(id="1", name="T1", enabled=True, auth_mode="ip")]
    items = build_trunk_dashboard_items(trunks, db_health_by_id={}, reg_by_trunk_id={})
    assert items[0].state == "unknown"


def test_build_alerts_disk_low_threshold_is_90_percent():
    assert build_alerts(asterisk_up=True, disk_used_pct=89, trunk_down=False,
                         has_outbound_route=True, last_revision_rolled_back=False) == []
    alerts = build_alerts(asterisk_up=True, disk_used_pct=90, trunk_down=False,
                           has_outbound_route=True, last_revision_rolled_back=False)
    assert [a.code for a in alerts] == ["disk_low"]


# Panel sahifa yo'llari (web/src/shell/screens.ts + router.tsx). Noma'lum yo'l «Ko'rish»ni
# bosh sahifaga qaytarardi (1.0.3: `/outbound-routes`, `/system` — mavjud emas edi).
_PANEL_PATHS = {"/trunks", "/outbound", "/settings/status", "/settings/revisions"}


def test_every_dashboard_alert_links_to_an_existing_panel_page():
    from app.services import dashboard

    alerts = [v for k, v in vars(dashboard).items() if k.isupper() and hasattr(v, "link")]
    assert len(alerts) >= 5
    assert {a.link for a in alerts} <= _PANEL_PATHS
