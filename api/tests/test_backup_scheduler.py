"""`app/services/backup_scheduler.py` -- sof vaqt/zona hisob-kitoblari (DB/tarmoqsiz)
va DB bilan ishlaydigan qismlar soxta session/lock orqali."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services import backup_job, backup_scheduler as mod
from app.services.job_lock import JobAlreadyRunningError


# ---------------------------------------------------------------- sof funksiyalar
def test_tz_offset_minutes_known_zone_no_dst():
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    assert mod.tz_offset_minutes("Asia/Tashkent", now) == 300


def test_tz_offset_minutes_unknown_zone_falls_back_to_utc():
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    assert mod.tz_offset_minutes("Not/ARealZone", now) == 0


@pytest.mark.parametrize("frequency,expected", [("daily", 86400), ("weekly", 7 * 86400)])
def test_period_seconds(frequency, expected):
    assert mod.period_seconds(frequency) == expected


def test_schedule_from_cfg_builds_schedule():
    sched = mod.schedule_from_cfg(
        {"enabled": True, "frequency": "daily", "weekday": 1, "time": "03:00",
         "components": ["config"]}, 300,
    )
    assert sched.enabled is True
    assert sched.tz_offset_minutes == 300


_NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
_DAY = 86400


@pytest.mark.parametrize("last_scheduled_at,last_ok,last_alert,expected", [
    (None, None, None, False),  # hali birorta urinish ham bo'lmagan -- erta
    (_NOW, _NOW - timedelta(seconds=_DAY), None, False),  # 1 davr oldin -- hali yaxshi
    (_NOW, _NOW - timedelta(seconds=3 * _DAY), None, True),  # 2 davrdan ko'p -- stale
    (_NOW, _NOW - timedelta(seconds=3 * _DAY), _NOW - timedelta(hours=1), False),  # bugun allaqachon ogohlantirildi
    (_NOW, _NOW - timedelta(seconds=3 * _DAY), _NOW - timedelta(days=2), True),  # oldingi ogohlantirish eskirgan
    (_NOW, None, None, True),  # umuman muvaffaqiyatli bo'lmagan, lekin urinilgan
])
def test_stale_check(last_scheduled_at, last_ok, last_alert, expected):
    assert mod.stale_check(_NOW, last_scheduled_at, last_ok, last_alert, _DAY) == expected


# ---------------------------------------------------------------- _run_due_backup
class _FakeSession:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


class _FakeLock:
    def __init__(self):
        self.released = 0

    async def release(self):
        self.released += 1


def _settings_row(**schedule_overrides):
    schedule = {"enabled": True, "frequency": "daily", "weekday": 1, "time": "03:00",
                "components": ["config"]}
    schedule.update(schedule_overrides)
    return SimpleNamespace(backup={"schedule": schedule, "last_scheduled_at": None,
                                    "last_scheduled_ok_at": None, "last_stale_alert_at": None})


@pytest.mark.asyncio
async def test_run_due_backup_skips_when_lock_busy(monkeypatch):
    async def fake_acquire(_engine):
        raise JobAlreadyRunningError()

    monkeypatch.setattr(mod, "try_acquire_job_lock", fake_acquire)
    created_tasks = []
    monkeypatch.setattr(mod.asyncio, "create_task", lambda coro: created_tasks.append(coro))

    session = _FakeSession()
    settings_row = _settings_row()
    await mod._run_due_backup(session, None, None, "t1", settings_row.backup["schedule"], settings_row, _NOW)

    assert session.commits == 0
    assert settings_row.backup["last_scheduled_at"] is None
    assert created_tasks == []


@pytest.mark.asyncio
async def test_run_due_backup_releases_lock_when_passphrase_missing(monkeypatch):
    lock = _FakeLock()

    async def fake_acquire(_engine):
        return lock

    async def fake_create(*_a, **_kw):
        raise backup_job.PassphraseRequiredError("yo'q")

    monkeypatch.setattr(mod, "try_acquire_job_lock", fake_acquire)
    monkeypatch.setattr(mod.backup_job, "create_backup_record", fake_create)
    created_tasks = []
    monkeypatch.setattr(mod.asyncio, "create_task", lambda coro: created_tasks.append(coro))

    session = _FakeSession()
    settings_row = _settings_row()
    await mod._run_due_backup(session, None, None, "t1", settings_row.backup["schedule"], settings_row, _NOW)

    assert lock.released == 1
    assert session.commits == 0
    assert created_tasks == []


@pytest.mark.asyncio
async def test_run_due_backup_starts_job_and_marks_last_scheduled_at(monkeypatch):
    lock = _FakeLock()

    async def fake_acquire(_engine):
        return lock

    backup = SimpleNamespace(id="b1")

    async def fake_create(_session, *, tenant_id, kind, components, created_by):
        assert kind == "scheduled"
        assert components == ["config"]
        return backup

    monkeypatch.setattr(mod, "try_acquire_job_lock", fake_acquire)
    monkeypatch.setattr(mod.backup_job, "create_backup_record", fake_create)
    created_tasks = []
    monkeypatch.setattr(mod.asyncio, "create_task", lambda coro: (created_tasks.append(coro), coro.close())[0])

    session = _FakeSession()
    settings_row = _settings_row()
    await mod._run_due_backup(session, None, None, "t1", settings_row.backup["schedule"], settings_row, _NOW)

    assert session.commits == 1
    assert settings_row.backup["last_scheduled_at"] == _NOW.isoformat()
    assert len(created_tasks) == 1


# ---------------------------------------------------------------- _run_and_mark_ok
class _FakeSessionFactory:
    def __init__(self, session):
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *_exc):
        return False


@pytest.mark.asyncio
@pytest.mark.parametrize("status,expect_commit", [("ok", True), ("partial", True), ("failed", False)])
async def test_run_and_mark_ok_updates_only_on_success(monkeypatch, status, expect_commit):
    async def fake_run(*_a, **_kw):
        return None

    monkeypatch.setattr(mod.backup_job, "run_backup_job", fake_run)

    backup_row = SimpleNamespace(status=status)
    settings_row = _settings_row()

    class _Session(_FakeSession):
        async def get(self, model, _pk):
            from app.db.models import Backup, SystemSettings
            if model is Backup:
                return backup_row
            if model is SystemSettings:
                return settings_row
            return None

    session = _Session()
    factory = _FakeSessionFactory(session)
    await mod._run_and_mark_ok(factory, None, _FakeLock(), "b1", "t1")

    assert session.commits == (1 if expect_commit else 0)
    assert (settings_row.backup["last_scheduled_ok_at"] is not None) == expect_commit


@pytest.mark.asyncio
async def test_run_and_mark_ok_swallows_unexpected_exception(monkeypatch, caplog):
    async def fake_run(*_a, **_kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(mod.backup_job, "run_backup_job", fake_run)
    await mod._run_and_mark_ok(None, None, _FakeLock(), "b1", "t1")  # raise bo'lmasligi -- sinovning o'zi


# ---------------------------------------------------------------- _tick_tenant / tick
@pytest.mark.asyncio
async def test_tick_tenant_skips_disabled_schedule(monkeypatch):
    calls = []
    monkeypatch.setattr(mod, "_maybe_alert_stale", lambda *_a: calls.append("alert"))
    monkeypatch.setattr(mod, "_run_due_backup", lambda *_a: calls.append("due"))

    tenant = SimpleNamespace(id="t1", timezone="UTC")
    settings_row = _settings_row(enabled=False)
    await mod._tick_tenant(None, None, None, tenant, settings_row, _NOW)
    assert calls == []


@pytest.mark.asyncio
async def test_tick_tenant_checks_stale_and_runs_due_backup(monkeypatch):
    calls = []

    async def fake_alert(*_a):
        calls.append("alert")

    async def fake_due(*_a):
        calls.append("due")

    monkeypatch.setattr(mod, "_maybe_alert_stale", fake_alert)
    monkeypatch.setattr(mod, "_run_due_backup", fake_due)

    tenant = SimpleNamespace(id="t1", timezone="UTC")
    settings_row = _settings_row(time="00:00")
    await mod._tick_tenant(None, None, None, tenant, settings_row, _NOW)
    assert calls == ["alert", "due"]


@pytest.mark.asyncio
async def test_tick_visits_every_tenant_with_settings(monkeypatch):
    visited = []

    async def fake_tick_tenant(_session, _factory, _engine, tenant, _settings_row, _now):
        visited.append(tenant.id)

    monkeypatch.setattr(mod, "_tick_tenant", fake_tick_tenant)

    tenants = [SimpleNamespace(id="t1", timezone="UTC"), SimpleNamespace(id="t2", timezone="UTC")]
    settings_by_tenant = {"t1": _settings_row(), "t2": None}

    class _Session:
        async def execute(self, _stmt):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: tenants))

        async def get(self, _model, pk):
            return settings_by_tenant.get(pk)

    factory = _FakeSessionFactory(_Session())
    await mod.tick(factory, None)
    assert visited == ["t1"]  # t2 -- settings yo'q (bo'lishi mumkin emas, lekin xavfsiz o'tkazib yuboriladi)


# ---------------------------------------------------------------- run_forever
@pytest.mark.asyncio
async def test_run_forever_calls_tick_each_sleep_tick(monkeypatch):
    calls = []

    async def fake_tick(*_a):
        calls.append(1)
    monkeypatch.setattr(mod, "tick", fake_tick)

    async def fake_sleep(_s):
        raise asyncio.CancelledError()
    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await mod.run_forever(None, None, 60)
    assert calls == [1]


@pytest.mark.asyncio
async def test_run_forever_skips_tick_during_maintenance(monkeypatch):
    from app.services import maintenance

    async def fail_tick(*_a):
        raise AssertionError("texnik xizmat paytida tick() chaqirilmasin")
    monkeypatch.setattr(mod, "tick", fail_tick)

    async def fake_sleep(_s):
        raise asyncio.CancelledError()
    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)

    maintenance.state.enabled = True
    try:
        with pytest.raises(asyncio.CancelledError):
            await mod.run_forever(None, None, 60)
    finally:
        maintenance.state.enabled = False


@pytest.mark.asyncio
async def test_run_forever_survives_tick_exception(monkeypatch):
    calls = []

    async def fake_tick(*_a):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
    monkeypatch.setattr(mod, "tick", fake_tick)

    sleep_n = {"n": 0}

    async def fake_sleep(_s):
        sleep_n["n"] += 1
        if sleep_n["n"] == 2:
            raise asyncio.CancelledError()
    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await mod.run_forever(None, None, 1)
    assert len(calls) == 2


# ---------------------------------------------------------------- _maybe_alert_stale
def _patch_alerts(monkeypatch):
    raised: list[tuple] = []

    async def fake_lang(_s, tenant_id):
        return f"lang-{tenant_id}"

    async def fake_raise(_s, tenant_id, kind, source, text):
        raised.append((tenant_id, kind, source, text))

    monkeypatch.setattr(mod, "tenant_language", fake_lang)
    monkeypatch.setattr(mod, "alert_text", lambda lang, kind, **kw: f"{lang}:{kind}:{kw}")
    monkeypatch.setattr(mod, "raise_alert", fake_raise)
    return raised


@pytest.mark.asyncio
@pytest.mark.parametrize("last_ok_days, expected_days", [(3, 3), (None, 0)])
async def test_maybe_alert_stale_raises_once_and_stamps(monkeypatch, last_ok_days, expected_days):
    raised = _patch_alerts(monkeypatch)
    settings_row = _settings_row()
    settings_row.backup["last_scheduled_at"] = _NOW.isoformat()
    if last_ok_days is not None:
        settings_row.backup["last_scheduled_ok_at"] = (_NOW - timedelta(days=last_ok_days)).isoformat()
    schedule = mod.schedule_from_cfg(settings_row.backup["schedule"], 0)
    session = _FakeSession()

    await mod._maybe_alert_stale(session, "t1", settings_row, schedule, _NOW)

    assert raised == [("t1", "backup_stale", "backup", f"lang-t1:backup_stale:{{'days': {expected_days}}}")]
    assert settings_row.backup["last_stale_alert_at"] == _NOW.isoformat()
    assert settings_row.backup["schedule"]["frequency"] == "daily"
    assert session.commits == 1


@pytest.mark.asyncio
async def test_maybe_alert_stale_noop_when_fresh(monkeypatch):
    raised = _patch_alerts(monkeypatch)
    settings_row = _settings_row()
    settings_row.backup.update(last_scheduled_at=_NOW.isoformat(),
                               last_scheduled_ok_at=(_NOW - timedelta(hours=2)).isoformat())
    schedule = mod.schedule_from_cfg(settings_row.backup["schedule"], 0)
    session = _FakeSession()

    await mod._maybe_alert_stale(session, "t1", settings_row, schedule, _NOW)

    assert raised == [] and session.commits == 0
    assert settings_row.backup["last_stale_alert_at"] is None


@pytest.mark.asyncio
async def test_maybe_alert_stale_uses_weekly_period(monkeypatch):
    """3 kun muvaffaqiyatsiz: kunlik jadvalda stale, haftalikda hali EMAS."""
    raised = _patch_alerts(monkeypatch)
    settings_row = _settings_row(frequency="weekly")
    settings_row.backup.update(last_scheduled_at=_NOW.isoformat(),
                               last_scheduled_ok_at=(_NOW - timedelta(days=3)).isoformat())
    schedule = mod.schedule_from_cfg(settings_row.backup["schedule"], 0)
    await mod._maybe_alert_stale(_FakeSession(), "t1", settings_row, schedule, _NOW)
    assert raised == []
