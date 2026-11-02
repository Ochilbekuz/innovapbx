"""`app/services/trunk_monitor.py` — M2c §5: sof o'tish qoidasi (`transition_kind`)
va aylanish (`trunk_monitor_cycle`, DB/AMI'siz soxta obyektlar)."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.services import trunk_monitor as mod
from app.services.trunk_health import TrunkHealthResult


@pytest.mark.parametrize("prev,current,expected", [
    (None, "ok", None),               # birinchi kuzatuv -- hech qachon ogohlantirmaydi
    (None, "unreachable", None),
    ("ok", "ok", None),               # o'zgarish yo'q
    ("ok", "unreachable", "trunk_down"),
    ("unreachable", "ok", "trunk_up"),
    ("ok", "unknown", None),          # unknown -- o'tish EMAS (manba HAM, maqsad HAM)
    ("unknown", "ok", None),
    ("disabled", "ok", None),         # disabled -- kuzatilgan holatlar to'plamida EMAS
])
def test_transition_kind(prev, current, expected):
    assert mod.transition_kind(prev, current) == expected


@pytest.mark.parametrize("state,raw", [("ok", "ok"), ("unreachable", "down"), ("unknown", "unknown")])
def test_raw_state_for_round_trips_safely(state, raw):
    assert mod._RAW_STATE_FOR.get(state, "unknown") == raw


class _FakeRow:
    def __init__(self):
        self.state = self.registration = self.reason = self.qualify_rtt_ms = None
        self.checked_at = None


class _FakeSession:
    def __init__(self, trunks, health_row=None):
        self._trunks = trunks
        self._health_row = health_row
        self.added: list = []
        self.commits = 0

    async def execute(self, _stmt):
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: self._trunks))

    async def get(self, _model, _pk):
        return self._health_row

    def add(self, obj):
        self.added.append(obj)
        self._health_row = obj

    async def commit(self):
        self.commits += 1


def _trunk(tid="tr1", enabled=True):
    return SimpleNamespace(id=tid, tenant_id="t1", name="Trunk1", enabled=enabled)


@pytest.mark.asyncio
async def test_monitor_trunk_first_observation_no_alert(monkeypatch):
    async def fake_health(_session, _ami, _trunk):
        return TrunkHealthResult(state="ok", rtt_ms=None, checked_at=None)
    monkeypatch.setattr(mod, "compute_trunk_health", fake_health)

    async def fail_if_called(*_a):
        raise AssertionError("birinchi kuzatuv ogohlantirmasligi kerak")
    monkeypatch.setattr(mod, "_alert_transition", fail_if_called)

    session = _FakeSession([])
    last_state: dict[str, str] = {}
    await mod._monitor_trunk(session, ami=None, trunk=_trunk(), last_state=last_state)
    assert last_state["tr1"] == "ok"


@pytest.mark.asyncio
async def test_monitor_trunk_transition_fires_alert(monkeypatch):
    async def fake_health(_session, _ami, _trunk):
        return TrunkHealthResult(state="unreachable", rtt_ms=None, checked_at=None, reason="timeout")
    monkeypatch.setattr(mod, "compute_trunk_health", fake_health)

    fired = []

    async def fake_alert(_session, trunk, kind, result):
        fired.append((trunk.id, kind, result.reason))

    monkeypatch.setattr(mod, "_alert_transition", fake_alert)

    session = _FakeSession([])
    last_state = {"tr1": "ok"}
    await mod._monitor_trunk(session, ami=None, trunk=_trunk(), last_state=last_state)
    assert last_state["tr1"] == "unreachable"
    assert fired == [("tr1", "trunk_down", "timeout")]


@pytest.mark.asyncio
async def test_write_trunk_health_maps_result_state_to_raw_db_state():
    session = _FakeSession([])
    result = TrunkHealthResult(state="unreachable", rtt_ms=12, checked_at=None, reason="x")
    await mod._write_trunk_health(session, "tr1", result)
    row = session.added[0]
    assert row.state == "down"  # XOM qiymat -- `state_from_db_health` keyingi safar TO'G'RI o'qisin
    assert row.qualify_rtt_ms == 12


@pytest.mark.asyncio
async def test_trunk_monitor_cycle_only_visits_enabled_trunks(monkeypatch):
    calls = []

    async def fake_monitor(_session, _ami, trunk, _last_state):
        calls.append(trunk.id)

    monkeypatch.setattr(mod, "_monitor_trunk", fake_monitor)
    session = _FakeSession([_trunk("a"), _trunk("b")])

    class _Factory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return session

        async def __aexit__(self, *exc):
            return False

    await mod.trunk_monitor_cycle(_Factory(), ami=None, last_state={})
    assert calls == ["a", "b"]
    assert session.commits == 1


# ---------------------------------------------------------------- _alert_transition
async def _lang():
    return "uz"


@pytest.mark.asyncio
async def test_alert_transition_trunk_down_includes_reason(monkeypatch):
    monkeypatch.setattr(mod, "tenant_language", lambda *_a: _lang())
    monkeypatch.setattr(mod, "alert_text", lambda lang, kind, **kw: f"{kind}:{kw.get('reason')}")
    raised = []

    async def fake_raise(_session, tenant_id, kind, key, text):
        raised.append((tenant_id, kind, key, text))
    monkeypatch.setattr(mod, "raise_alert", fake_raise)

    result = mod.TrunkHealthResult(state="unreachable", rtt_ms=None, checked_at=None, reason="timeout")
    await mod._alert_transition(session=None, trunk=_trunk(), kind="trunk_down", result=result)
    assert raised == [("t1", "trunk_down", "tr1", "trunk_down:timeout")]


@pytest.mark.asyncio
async def test_alert_transition_trunk_up_falls_back_to_state_when_no_reason(monkeypatch):
    monkeypatch.setattr(mod, "tenant_language", lambda *_a: _lang())
    monkeypatch.setattr(mod, "alert_text", lambda lang, kind, **kw: f"{kind}:{kw.get('name')}")
    raised = []

    async def fake_raise(_session, tenant_id, kind, key, text):
        raised.append((tenant_id, kind, key, text))
    monkeypatch.setattr(mod, "raise_alert", fake_raise)

    result = mod.TrunkHealthResult(state="ok", rtt_ms=None, checked_at=None)
    await mod._alert_transition(session=None, trunk=_trunk(), kind="trunk_up", result=result)
    assert raised == [("t1", "trunk_up", "tr1", "trunk_up:Trunk1")]


# ---------------------------------------------------------------- run_forever
@pytest.mark.asyncio
async def test_run_forever_calls_cycle_each_sleep_tick(monkeypatch):
    calls = []

    async def fake_cycle(*_a):
        calls.append(1)
    monkeypatch.setattr(mod, "trunk_monitor_cycle", fake_cycle)

    async def fake_sleep(_s):
        raise asyncio.CancelledError()
    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await mod.run_forever(session_factory=None, ami=None, interval_s=3)
    assert calls == [1]


@pytest.mark.asyncio
async def test_run_forever_skips_cycle_during_maintenance(monkeypatch):
    from app.services import maintenance

    async def fail_cycle(*_a):
        raise AssertionError("texnik xizmat paytida trunk_monitor_cycle chaqirilmasin")
    monkeypatch.setattr(mod, "trunk_monitor_cycle", fail_cycle)

    async def fake_sleep(_s):
        raise asyncio.CancelledError()
    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)

    maintenance.state.enabled = True
    try:
        with pytest.raises(asyncio.CancelledError):
            await mod.run_forever(session_factory=None, ami=None, interval_s=3)
    finally:
        maintenance.state.enabled = False


@pytest.mark.asyncio
async def test_run_forever_survives_cycle_exception_and_keeps_looping(monkeypatch):
    calls = []

    async def fake_cycle(*_a):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
    monkeypatch.setattr(mod, "trunk_monitor_cycle", fake_cycle)

    sleep_n = {"n": 0}

    async def fake_sleep(_s):
        sleep_n["n"] += 1
        if sleep_n["n"] == 2:
            raise asyncio.CancelledError()
    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await mod.run_forever(session_factory=None, ami=None, interval_s=1)
    assert len(calls) == 2
