"""M3b — baza bilan ishlovchi servis/router funksiyalari soxta sessiya bilan (bazasiz)."""
from __future__ import annotations

import asyncio
import uuid
import wave
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.api import public
from app.api.v1 import integrations as integ
from app.api.v1 import recordings as rec_routes
from app.api.v1 import settings_integrations as sint
from app.core.errors import ApiError
from app.schemas_integrations import (
    CreateApiKeyPayload,
    OriginatePayload,
    UpdateIntegrationSettingsPayload,
    UpdateRecordingSettingsPayload,
    UpdateWebhookPayload,
)
from app.services import call_events as ce
from app.services import recordings
from app.services.integrations import dispatch, outbox, registry
from app.services.integrations import events as ev

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
UID = "11111111-2222-3333-4444-555555555555"


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self.value or []))

    def all(self):
        return list(self.value or [])

    def first(self):
        return self.value


class FakeSession:
    """`execute` natijalari navbat bilan; `get` — {(Model nomi, id): obyekt}."""

    def __init__(self, *results, objects=None):
        self.results = list(results)
        self.objects = objects or {}
        self.added, self.executed = [], []
        self.commits = self.rollbacks = 0

    async def execute(self, stmt, params=None):
        self.executed.append(stmt)
        return _Result(self.results.pop(0) if self.results else None)

    async def get(self, model, key):
        return self.objects.get((model.__name__, str(key)))

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, obj):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def factory(*sessions):
    queue = list(sessions)
    return lambda: queue.pop(0)


# ------------------------------------------------------------ call_events yordamchilari
@pytest.mark.asyncio
async def test_tenant_queue_origin_helpers():
    assert await ce._tenant_id(FakeSession(), None) is None
    assert await ce._tenant_id(FakeSession(None), "t1") is None
    assert await ce._tenant_id(FakeSession("tid"), "t1") == "tid"
    queue = SimpleNamespace(id=UID, name="Q", tenant_id="t")
    s = FakeSession(objects={("Queue", UID): queue})
    assert await ce._queue_ref(s, "t", None) is None
    assert await ce._queue_ref(s, "t", "not-uuid") is None
    assert await ce._queue_ref(s, "other", UID) is None
    assert await ce._queue_ref(s, "t", UID) == {"id": UID, "name": "Q"}
    req = SimpleNamespace(external_id="crm:1")
    s = FakeSession(objects={("ApiOriginateRequest", UID): req})
    assert await ce._origin(s, "1700.1") is None
    assert await ce._origin(s, UID) == {"source": "api", "external_id": "crm:1"}
    assert await ce._origin(FakeSession(), UID) is None


def _live(type_="call.ringing", **kw):
    base = dict(type=type_, code="t1", linkedid="L", dedupe_key="k", direction="inbound", from_="998901",
                to="101", extension="101", did="7120", queue_id=None)
    base.update(kw)
    return ev.LiveEvent(**base)


def test_merge_info_keeps_first_and_tracks_last_rung():
    info = ce._merge_info({}, _live())
    assert info == {"direction": "inbound", "did": "7120", "from": "998901", "extension": "101", "last_rung": "101"}
    info = ce._merge_info(info, _live(extension="102", did="999"))
    assert (info["extension"], info["did"], info["last_rung"]) == ("101", "7120", "102")
    info = ce._merge_info(info, _live("call.answered", extension="103"))
    assert info["last_rung"] == "102"


def _state(**kw):
    base = dict(linkedid="L", tenant_id="t", info={}, ringing_sent=False, answered_sent=False, ended_sent=False,
                finished_at=None, updated_at=None, created_at=NOW)
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def emitted(monkeypatch):
    calls = []

    async def fake_emit(session, **kw):
        calls.append(kw)
        return SimpleNamespace(id="e")

    monkeypatch.setattr(ce, "emit_event", fake_emit)
    return calls


@pytest.mark.asyncio
async def test_emit_live(monkeypatch, emitted):
    async def tenant(session, code):
        return None if code == "none" else "t"

    state = _state()

    async def locked(session, tenant_id, linkedid):
        return state

    monkeypatch.setattr(ce, "_tenant_id", tenant)
    monkeypatch.setattr(ce, "_locked_state", locked)
    assert await ce.emit_live(FakeSession(), _live(code="none")) is False
    s = FakeSession()
    assert await ce.emit_live(s, _live()) is True
    assert state.ringing_sent and not state.answered_sent and s.commits == 1
    assert emitted[0]["event_type"] == "call.ringing" and emitted[0]["call"]["did"] == "7120"
    await ce.emit_live(s, _live("call.answered"))
    assert state.answered_sent
    state.ended_sent = True
    assert await ce.emit_live(s, _live()) is False and len(emitted) == 2


@pytest.mark.asyncio
async def test_finalize_branches(monkeypatch, emitted):
    row = SimpleNamespace(accountcode="t1")
    assert await ce.finalize(FakeSession([]), "L") is False

    async def tenant(session, code):
        return "t" if code == "t1" else None

    monkeypatch.setattr(ce, "_tenant_id", tenant)
    assert await ce.finalize(FakeSession([SimpleNamespace(accountcode="x")]), "L") is False

    async def exists_yes(session, tenant_id, linkedid):
        return True

    monkeypatch.setattr(ce, "_ended_exists", exists_yes)
    assert await ce.finalize(FakeSession([row]), "L") is False

    async def exists_no(session, tenant_id, linkedid):
        return False

    state = _state(ended_sent=True)

    async def locked(session, tenant_id, linkedid):
        return state

    monkeypatch.setattr(ce, "_ended_exists", exists_no)
    monkeypatch.setattr(ce, "_locked_state", locked)
    s = FakeSession([row])
    assert await ce.finalize(s, "L") is False and s.rollbacks == 1

    facts = SimpleNamespace(started_at=NOW, ended_at=NOW, extension="101", queue_id=None, direction="internal")
    monkeypatch.setattr(ce.ev, "ended_facts", lambda rows: facts)
    monkeypatch.setattr(ce.ev, "ended_call", lambda linkedid, f, **kw: {"id": linkedid, **kw})

    async def ingest(session, **kw):
        return ["rec"]

    async def refs(session, tenant_id, recs):
        return [{"id": "r"}]

    monkeypatch.setattr(ce.recordings, "ingest_call", ingest)
    monkeypatch.setattr(ce.recordings, "recording_refs", refs)
    state.ended_sent = False
    s = FakeSession([row])
    assert await ce.finalize(s, "L") is True
    assert state.ended_sent and state.finished_at is not None and s.commits == 1
    assert emitted[-1]["internal"] is True and emitted[-1]["dedupe_key"] == "ended:L"
    assert emitted[-1]["call"]["recordings"] == [{"id": "r"}]


@pytest.mark.asyncio
async def test_force_close_marks_missed_or_answered(emitted):
    state = _state(info={"direction": "inbound", "from": "998", "last_rung": "101"}, answered_sent=True)
    await ce.force_close(FakeSession(), state)
    call = emitted[0]["call"]
    assert (call["status"], call["forced"], call["to"], state.ended_sent) == ("answered", True, "101", True)
    await ce.force_close(FakeSession(), _state())
    assert emitted[1]["call"]["status"] == "missed"


@pytest.mark.asyncio
async def test_sweep_once(monkeypatch):
    async def no_ami(ami):
        return None

    monkeypatch.setattr(ce, "active_channels", no_ami)
    assert await ce.sweep_once(factory(), None) == 0

    async def channels(ami):
        return [{"Linkedid": "LIVE"}]

    finalized, forced = [], []

    async def fin(session, linkedid):
        finalized.append(linkedid)
        return True

    async def force(session, state):
        forced.append(state.linkedid)

    async def has_cdr(session, linkedid):
        return linkedid == "WITHCDR"

    monkeypatch.setattr(ce, "active_channels", channels)
    monkeypatch.setattr(ce, "finalize", fin)
    monkeypatch.setattr(ce, "force_close", force)
    monkeypatch.setattr(ce, "_has_cdr", has_cdr)
    stuck = [_state(linkedid="LIVE"), _state(linkedid="WITHCDR"), _state(linkedid="GONE")]
    last = FakeSession(stuck)
    done = await ce.sweep_once(factory(FakeSession(["LIVE", "DONE"]), FakeSession(), last), None)
    assert (done, finalized, forced, last.commits) == (1, ["DONE"], ["GONE"], 1)


@pytest.mark.asyncio
async def test_has_cdr_and_ended_exists():
    assert await ce._has_cdr(FakeSession(("id",)), "L") is True
    assert await ce._has_cdr(FakeSession(None), "L") is False
    assert await ce._ended_exists(FakeSession(None), "t", "L") is False


def test_backoff_is_capped():
    assert [ce.backoff_s(a) for a in (0, 1, 3, 5, 9)] == [1.0, 2.0, 8.0, 30.0, 30.0]


# ------------------------------------------------------------ CallEventService
@pytest.mark.asyncio
async def test_service_on_event_filters_and_drops(monkeypatch):
    monkeypatch.setattr(ce, "QUEUE_MAX", 1)
    svc = ce.CallEventService(factory(), None)
    svc.on_event({"Event": "Newstate"})
    svc.on_event({"Event": "VarSet", "Variable": "INNOVA_BL_NUM", "Linkedid": "L"})
    svc.on_event({"Event": "VarSet", "Variable": "__INNOVA_DID", "Linkedid": "L", "Value": "7"})
    svc.on_event({"Event": "Hangup"})
    assert (svc.queue.qsize(), svc.dropped) == (1, 1)
    assert svc.stream.events == "call,dialplan" and svc.stream.event_filters == ce.AMI_FILTERS


def test_service_remember_var_is_bounded(monkeypatch):
    monkeypatch.setattr(ce, "VARS_MAX", 2)
    svc = ce.CallEventService(factory(), None)
    svc.remember_var("A", "INNOVA_DID", "1")
    svc.remember_var("B", "INNOVA_DID", "2")
    svc.remember_var("A", "INNOVA_QUEUE", "q")
    assert svc._vars == {"A": {"INNOVA_DID": "1", "INNOVA_QUEUE": "q"}, "B": {"INNOVA_DID": "2"}}
    svc.remember_var("C", "INNOVA_DID", "3")
    assert list(svc._vars) == ["B", "C"]


@pytest.mark.asyncio
async def test_service_handle_hangup_and_live(monkeypatch):
    svc = ce.CallEventService(factory(FakeSession()), None)
    scheduled, live = [], []
    monkeypatch.setattr(svc, "_schedule_finalize", scheduled.append)

    async def fake_emit_live(session, item):
        live.append(item)

    monkeypatch.setattr(ce, "emit_live", fake_emit_live)
    await svc.handle({"Event": "VarSet", "Variable": "__INNOVA_DID", "Linkedid": "L", "Value": "712000"})
    await svc.handle({"Event": "Hangup", "Linkedid": "L"})
    await svc.handle({"Event": "DialEnd", "DialStatus": "NOANSWER"})
    await svc.handle({"Event": "DialBegin", "Channel": "PJSIP/t1-trunk-x-01", "DestChannel": "PJSIP/t1-101-02",
                      "Linkedid": "L", "CallerIDNum": "998901"})
    assert scheduled == ["L"] and len(live) == 1 and (live[0].type, live[0].did) == ("call.ringing", "712000")


@pytest.mark.asyncio
async def test_service_finalize_later(monkeypatch):
    monkeypatch.setattr(ce.settings, "call_events_settle_s", 0)
    finalized = []

    async def fin(session, linkedid):
        finalized.append(linkedid)
        if linkedid == "BOOM":
            raise RuntimeError("x")
        return True

    channel_sets = {"ALIVE": [{"Linkedid": "ALIVE"}], "NOAMI": None}

    async def channels(ami):
        return channel_sets.get(svc.current, [])

    monkeypatch.setattr(ce, "finalize", fin)
    monkeypatch.setattr(ce, "active_channels", channels)
    svc = ce.CallEventService(factory(FakeSession(), FakeSession()), None)
    for linkedid in ("ALIVE", "NOAMI", "L", "BOOM"):
        svc.remember_var(linkedid, "INNOVA_DID", "1")
        svc.current = linkedid
        await svc._finalize_later(linkedid)
    assert finalized == ["L", "BOOM"] and set(svc._vars) == {"ALIVE", "NOAMI"}
    svc._schedule_finalize("")
    assert svc._timers == {}
    monkeypatch.setattr(ce.settings, "call_events_settle_s", 30)
    svc._schedule_finalize("X")
    first = svc._timers["X"]
    svc._schedule_finalize("X")
    await asyncio.sleep(0)
    assert first.cancelled() and svc._timers["X"] is not first
    svc._timers["X"].cancel()


@pytest.mark.asyncio
async def test_service_listener_reconnects_with_backoff(monkeypatch):
    svc = ce.CallEventService(factory(), None)
    calls, sleeps = [], []

    async def ensure_connected():
        calls.append(1)
        if len(calls) == 1:
            raise OSError("refused")
        if len(calls) == 2:
            svc.stream.connected = False
            return
        raise asyncio.CancelledError

    async def close():
        return None

    async def fake_sleep(s):
        sleeps.append(s)

    svc.stream = SimpleNamespace(ensure_connected=ensure_connected, close=close, connected=False)
    monkeypatch.setattr(ce.asyncio, "sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        await svc.run_listener()
    assert sleeps == [1.0, 1.0] and svc.resync.is_set()


@pytest.mark.asyncio
async def test_service_consumer_survives_errors(monkeypatch):
    svc = ce.CallEventService(factory(), None)
    seen = []

    async def handle(msg):
        seen.append(msg["n"])
        if msg["n"] == 1:
            raise RuntimeError("x")

    monkeypatch.setattr(svc, "handle", handle)
    svc.queue.put_nowait({"n": 1})
    svc.queue.put_nowait({"n": 2})
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(svc.run_consumer(), 0.05)
    assert seen == [1, 2]


@pytest.mark.asyncio
async def test_service_sweeper_survives_errors(monkeypatch):
    svc = ce.CallEventService(factory(), None)
    runs = []

    async def sweep(session_factory, ami):
        runs.append(1)
        raise RuntimeError("x")

    monkeypatch.setattr(ce, "sweep_once", sweep)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(svc.run_sweeper(0.01), 0.05)
    assert len(runs) >= 2


# ------------------------------------------------------------ yozuvlar servisi
def _rec(**kw):
    base = dict(id=UID, tenant_id="t", deleted_at=None, linkedid="L", uniqueid="U", path="innova/a.wav",
                extension="101", duration_s=5)
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_get_active():
    s = FakeSession(objects={("CallRecording", UID): _rec()})
    assert await recordings.get_active(s, "t", "bad") is None
    assert await recordings.get_active(s, "other", UID) is None
    assert (await recordings.get_active(s, "t", UID)).id == UID
    s.objects[("CallRecording", UID)] = _rec(deleted_at=NOW)
    assert await recordings.get_active(s, "t", UID) is None
    assert await recordings.get_active(FakeSession(), "t", UID) is None


@pytest.mark.asyncio
async def test_link_settings_defaults_and_values():
    assert await recordings.link_settings(FakeSession(), "t") == ("", recordings.DEFAULT_LINK_TTL_S)
    row = SimpleNamespace(integrations={"public_base_url": "https://p", "recording_link_ttl_s": 60})
    assert await recordings.link_settings(FakeSession(objects={("SystemSettings", "t"): row}), "t") == ("https://p", 60)


@pytest.mark.asyncio
async def test_operator_can_access():
    rec = _rec(extension="101")
    assert await recordings.operator_can_access(FakeSession(), rec, code="t1", number=None) is False
    assert await recordings.operator_can_access(FakeSession(), rec, code="t1", number="101") is True
    rows = [("998", "s", "PJSIP/t1-trunk-1-01", "PJSIP/t1-102-0a")]
    assert await recordings.operator_can_access(FakeSession(rows), rec, code="t1", number="102") is True
    assert await recordings.operator_can_access(FakeSession(rows), rec, code="t1", number="103") is False


def _wav(path, seconds):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\0\0" * 8000 * seconds)


@pytest.mark.asyncio
async def test_scan_and_ingest(tmp_path, monkeypatch):
    monkeypatch.setattr(recordings.settings, "recordings_dir", str(tmp_path))
    day = tmp_path / "innova/2026/10/29"
    day.mkdir(parents=True)
    _wav(day / "1700.1-1700.2.wav", 3)
    (day / "1700.1-.wav").write_bytes(b"")
    (day / "1700.9-1700.3.wav").write_bytes(b"")
    found = recordings._scan("1700.1", ["innova/2026/10/29", "innova/2026/10/30"])
    assert [(rel, uid) for rel, uid, _ in found] == [("innova/2026/10/29/1700.1-1700.2.wav", "1700.2")]

    async def active(session, tenant_id, linkedids):
        return ["row"]

    monkeypatch.setattr(recordings, "active_for", active)
    s = FakeSession()
    out = await recordings.ingest_call(s, tenant_id="t", linkedid="1700.1", started_at=NOW, ended_at=NOW,
                                       extension="101")
    assert out == ["row"] and len(s.executed) == 1
    params = s.executed[0].compile().params
    assert (params["duration_s"], params["uniqueid"], params["extension"]) == (3, "1700.2", "101")


@pytest.mark.asyncio
async def test_active_for_and_attach():
    assert await recordings.active_for(FakeSession(), "t", []) == []
    calls = [SimpleNamespace(linkedid="L", recordings=None), SimpleNamespace(linkedid=None, recordings=None)]
    await recordings.attach_recordings(FakeSession([_rec()]), "t", calls)
    assert calls[0].recordings == [{"id": UID, "duration_s": 5}] and calls[1].recordings == []


@pytest.mark.asyncio
async def test_recording_refs_signed_or_null(monkeypatch):
    monkeypatch.setattr(recordings.settings, "secret_key", "k" * 40)
    row = SimpleNamespace(integrations={"public_base_url": "https://p"})
    refs = await recordings.recording_refs(FakeSession(objects={("SystemSettings", "t"): row}), "t", [_rec()])
    assert refs[0]["url"].startswith(f"https://p/api/public/v1/recordings/{UID}?exp=")
    assert (await recordings.recording_refs(FakeSession(), "t", [_rec()]))[0]["url"] is None


@pytest.mark.asyncio
async def test_purge_tenant_and_once(tmp_path, monkeypatch):
    monkeypatch.setattr(recordings.settings, "recordings_dir", str(tmp_path))
    (tmp_path / "old.wav").write_bytes(b"x")
    ok, missing, broken = _rec(path="old.wav"), _rec(path="gone.wav"), _rec(path="dir")
    (tmp_path / "dir").mkdir()
    (tmp_path / "dir" / "f").write_bytes(b"")  # katalog — unlink OSError
    count, errors = await recordings.purge_tenant(FakeSession([ok, missing, broken]), "t", 30, NOW)
    assert count == 2 and len(errors) == 1 and errors[0].startswith("dir:")
    assert ok.deleted_at == NOW and missing.deleted_at == NOW and broken.deleted_at is None
    assert not (tmp_path / "old.wav").exists()

    alerts = []

    async def fake_alert(session, tenant_id, kind, key, text):
        alerts.append((kind, key))

    async def fake_lang(session, tenant_id):
        return "uz"

    import app.services.alerts as alerts_mod
    monkeypatch.setattr(alerts_mod, "raise_alert", fake_alert)
    monkeypatch.setattr(alerts_mod, "tenant_language", fake_lang)
    broken2 = _rec(path="dir")
    s = FakeSession([("t", None)], [broken2])
    assert await recordings.purge_once(factory(s)) == 0
    assert alerts == [("recording_error", "purge")] and s.commits == 1


@pytest.mark.asyncio
async def test_purge_run_forever_survives(monkeypatch):
    calls = []

    async def purge(sf):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("x")
        return 2

    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)
        if len(sleeps) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(recordings, "purge_once", purge)
    monkeypatch.setattr(recordings.asyncio, "sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        await recordings.run_forever(None, 5)
    assert (len(calls), sleeps) == (2, [5, 5])


@pytest.mark.asyncio
async def test_purge_run_forever_skips_during_maintenance(monkeypatch):
    from app.services import maintenance

    async def fail_purge(_sf):
        raise AssertionError("texnik xizmat paytida purge_once chaqirilmasin")

    async def fake_sleep(_s):
        raise asyncio.CancelledError

    monkeypatch.setattr(recordings, "purge_once", fail_purge)
    monkeypatch.setattr(recordings.asyncio, "sleep", fake_sleep)
    maintenance.state.enabled = True
    try:
        with pytest.raises(asyncio.CancelledError):
            await recordings.run_forever(None, 5)
    finally:
        maintenance.state.enabled = False


# ------------------------------------------------------------ outbox / dispatch / registry
@pytest.mark.asyncio
async def test_emit_event_duplicate_and_fan_out(monkeypatch):
    assert await outbox.emit_event(FakeSession(None), tenant_id="t", event_type="call.ended", dedupe_key="k",
                                   call_id="L", internal=False, call={}, occurred_at=NOW) is None
    fanned = []

    async def fan_out(session, event, subs):
        fanned.append([s.name for s in subs])

    monkeypatch.setattr(outbox, "_fan_out", fan_out)
    subs = [SimpleNamespace(name="a", kind="webhook", events=["call.ended"], include_internal=False),
            SimpleNamespace(name="b", kind="webhook", events=["call.ringing"], include_internal=False),
            SimpleNamespace(name="c", kind="webhook", events=["call.ended"], include_internal=True)]

    class S(FakeSession):
        async def get(self, model, key):
            return SimpleNamespace(id=key)

    await outbox.emit_event(S("eid", subs), tenant_id="t", event_type="call.ended", dedupe_key="k", call_id="L",
                            internal=True, call={}, occurred_at=NOW)
    assert fanned == [["c"]]


@pytest.mark.asyncio
async def test_dispatch_run_forever_survives(monkeypatch):
    rounds = iter([True, False])
    calls = []

    async def once(sf):
        calls.append(1)
        if len(calls) == 3:
            raise RuntimeError("x")
        return next(rounds, False)

    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)
        if len(sleeps) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(dispatch, "dispatch_once", once)
    monkeypatch.setattr(dispatch.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(registry, "load_providers", lambda: [])
    with pytest.raises(asyncio.CancelledError):
        await dispatch.run_forever(None, 1.0)
    assert len(calls) == 3 and sleeps == [1.0, 1.0]


@pytest.mark.asyncio
async def test_dispatch_run_forever_skips_during_maintenance(monkeypatch):
    from app.services import maintenance

    async def fail_once(_sf):
        raise AssertionError("texnik xizmat paytida dispatch_once chaqirilmasin")

    async def fake_sleep(_s):
        raise asyncio.CancelledError

    monkeypatch.setattr(dispatch, "dispatch_once", fail_once)
    monkeypatch.setattr(dispatch.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(registry, "load_providers", lambda: [])
    maintenance.state.enabled = True
    try:
        with pytest.raises(asyncio.CancelledError):
            await dispatch.run_forever(None, 1.0)
    finally:
        maintenance.state.enabled = False


def test_load_providers_skips_missing_only(monkeypatch):
    monkeypatch.setattr(registry, "PROVIDER_MODULES", ("app.services.integrations.webhook",
                                                       "app.services.integrations.nope_m3b"))
    assert registry.load_providers() == ["app.services.integrations.webhook"]
    monkeypatch.setattr(registry, "PROVIDER_MODULES", ("app.services.integrations.nope_pkg.x",))
    with pytest.raises(ModuleNotFoundError):
        registry.load_providers()


# ------------------------------------------------------------ admin router
ADMIN = SimpleNamespace(id="u1", tenant_id="t")


@pytest.fixture
def audits(monkeypatch):
    log = []

    async def fake_audit(session, **kw):
        log.append(kw["action"])

    monkeypatch.setattr(integ, "record_audit", fake_audit)
    monkeypatch.setattr(sint, "record_audit", fake_audit)
    return log


@pytest.mark.asyncio
async def test_create_api_key(audits):
    with pytest.raises(ApiError) as exc:
        await integ.create_api_key(CreateApiKeyPayload(name="k", scopes=["calls:read"],
                                                       expires_at=NOW - timedelta(days=1)), FakeSession(), ADMIN)
    assert exc.value.field == "expires_at"
    with pytest.raises(ApiError) as exc:
        await integ.create_api_key(CreateApiKeyPayload.model_construct(name="k", scopes=["calls:nuke"],
                                                                       expires_at=None), FakeSession(), ADMIN)
    assert exc.value.code == "bad_scope"
    s = _CreatedSession()
    created = await integ.create_api_key(CreateApiKeyPayload(name="k", scopes=["calls:read", "calls:read"]), s, ADMIN)
    assert created.key.startswith("ipk_") and created.item.scopes == ["calls:read"]
    assert audits == ["api_key.create"] and s.commits == 1
    assert s.added[0].key_hash != created.key and created.key.startswith(s.added[0].prefix, 4)


def test_api_key_scope_literal_matches_runtime_scopes():
    """Regressiya (M10 B3 jonli isbotda topilgan): `schemas_integrations.ApiKeyScope`
    (Pydantic validatsiya) va `app.services.api_keys.SCOPES` (runtime tekshiruv)
    IKKI alohida ro'yxat — biri yangilanib, ikkinchisi unutilsa, yangi skop
    (masalan `events:read`) 422 bilan rad etiladi, lekin `has_scope()` baribir
    uni tanigani ko'rinmasdan qoladi (faqat jonli WS isbotda ushlangan)."""
    from typing import get_args

    from app.schemas_integrations import ApiKeyScope
    from app.services.api_keys import SCOPES

    assert set(get_args(ApiKeyScope)) == set(SCOPES)


class _CreatedSession(FakeSession):
    async def flush(self):
        for obj in self.added:
            obj.id = uuid.uuid4()
            obj.created_at = NOW
            obj.last_used_at = obj.revoked_at = None


@pytest.mark.asyncio
async def test_webhook_changes(monkeypatch):
    async def ok(url):
        return url.strip()

    monkeypatch.setattr(integ, "check_webhook_url", ok)
    payload = UpdateWebhookPayload(url=" http://10.0.0.1/h ", events=["call.ended", "call.ringing", "call.ended"],
                                   name=None, updated_at=NOW)
    changes = await integ._webhook_changes(None, payload)
    assert changes == {"url": "http://10.0.0.1/h", "events": ["call.ended", "call.ringing"]}
    assert await integ._webhook_changes(None, UpdateWebhookPayload(enabled=False, updated_at=NOW)) == {"enabled": False}


# ------------------------------------------------------------ sozlamalar router
def _settings_row():
    return SimpleNamespace(integrations={"public_base_url": "https://old"}, recording={"format": "wav"},
                           recording_retention_days=365, updated_at=NOW)


@pytest.mark.asyncio
async def test_update_integration_and_recording_settings(monkeypatch, audits):
    row = _settings_row()

    async def get_row(session, tenant_id):
        return row

    monkeypatch.setattr(sint, "get_settings_row", get_row)
    out = await sint.update_integration_settings(
        UpdateIntegrationSettingsPayload(public_base_url="https://pbx.uz/", recording_link_ttl_s=3600, updated_at=NOW),
        FakeSession(), ADMIN)
    assert (out.public_base_url, out.recording_link_ttl_s) == ("https://pbx.uz", 3600)
    out = await sint.update_integration_settings(UpdateIntegrationSettingsPayload(updated_at=NOW), FakeSession(), ADMIN)
    assert out.public_base_url == "https://pbx.uz"
    out = await sint.update_recording_settings(
        UpdateRecordingSettingsPayload(external_only=True, retention_days=30, updated_at=NOW), FakeSession(), ADMIN)
    assert (out.external_only, out.retention_days, row.recording) == (True, 30, {"format": "wav", "external_only": True})
    out = await sint.update_recording_settings(UpdateRecordingSettingsPayload(updated_at=NOW), FakeSession(), ADMIN)
    assert out.retention_days == 30
    assert audits == ["settings_integrations.update"] * 2 + ["settings_recording.update"] * 2
    with pytest.raises(ApiError) as exc:
        await sint.update_recording_settings(
            UpdateRecordingSettingsPayload(updated_at=NOW - timedelta(seconds=5)), FakeSession(), ADMIN)
    assert exc.value.status_code == 409
    assert (await sint.get_integration_settings(FakeSession(), ADMIN)).public_base_url == "https://pbx.uz"
    assert (await sint.get_recording_settings(FakeSession(), ADMIN)).retention_days == 30


# ------------------------------------------------------------ ochiq API marshrutlari
KEY = public.KeyContext(key_id="k1", prefix="abcd1234", tenant_id="t", tenant_code="t1")


def test_call_keys_query_filters_and_cursor():
    stmt = public._call_keys_query("t1", from_="2026-10-01", to="2026-10-29", number="+998 90 1",
                                   cursor=public.encode_cursor(NOW, "1700.5"), limit=10)
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "cdr.calldate >=" in sql and "cdr.calldate <=" in sql and "'998901'" in sql
    assert "(anon_1.started, anon_1.uid) <" in sql and "LIMIT 10" in sql
    plain = str(public._call_keys_query("t1", from_=None, to=None, number=None, cursor=None, limit=5).compile())
    assert "calldate >=" not in plain and "<" not in plain.split("ORDER BY")[0].split("GROUP BY")[1]


@pytest.mark.asyncio
async def test_recording_tenant():
    assert await public._recording_tenant(FakeSession(), "bad") is None
    assert await public._recording_tenant(FakeSession(), UID) is None
    s = FakeSession(objects={("CallRecording", UID): _rec(tenant_id="tX")})
    assert await public._recording_tenant(s, UID) == "tX"


@pytest.mark.asyncio
async def test_public_recording_paths(monkeypatch):
    monkeypatch.setattr(public, "audio_response", lambda rec: ("audio", rec.id))
    monkeypatch.setattr(public, "link_is_valid", lambda rid, exp, sig: sig == "good")
    s = FakeSession(objects={("CallRecording", UID): _rec()})
    req = SimpleNamespace(headers={})
    for exp, sig in ((None, "good"), (1, None), (1, "bad")):
        with pytest.raises(ApiError) as exc:
            await public.public_recording(req, UID, exp, sig, s)
        assert exc.value.code == "invalid_signature"
    assert await public.public_recording(req, UID, 1, "good", s) == ("audio", UID)
    with pytest.raises(ApiError) as exc:
        await public.public_recording(req, "bad-id", 1, "good", s)
    assert exc.value.status_code == 404

    async def auth(session, plaintext, scope):
        assert scope == "recordings:read"
        return KEY

    monkeypatch.setattr(public, "authenticate", auth)
    assert await public.public_recording(req, UID, None, None, s) == ("audio", UID)
    s.objects.clear()
    with pytest.raises(ApiError) as exc:
        await public.public_recording(req, UID, None, None, s)
    assert exc.value.status_code == 404


class _Ami:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.sent = response, error, []

    async def action(self, name, **fields):
        self.sent.append((name, fields))
        if self.error:
            raise self.error
        return self.response


@pytest.mark.asyncio
async def test_public_originate(monkeypatch):
    audits = []

    async def fake_audit(session, **kw):
        audits.append(kw)

    monkeypatch.setattr(public, "record_audit", fake_audit)
    payload = OriginatePayload(extension="101", to="+998 90 111-22-33", external_id="crm:1")
    with pytest.raises(ApiError) as exc:
        await public.public_originate(payload, FakeSession(None), _Ami(), KEY)
    assert exc.value.code == "unknown_extension"
    with pytest.raises(ApiError) as exc:
        await public.public_originate(payload, FakeSession(SimpleNamespace(enabled=False, number="101")), _Ami(), KEY)
    assert exc.value.code == "unknown_extension"
    ext = SimpleNamespace(enabled=True, number="101")
    with pytest.raises(ApiError) as exc:
        await public.public_originate(payload, FakeSession(ext), _Ami(error=ConnectionError()), KEY)
    assert (exc.value.status_code, exc.value.code) == (502, "originate_failed")
    with pytest.raises(ApiError) as exc:
        await public.public_originate(payload, FakeSession(ext), _Ami({"Response": "Error", "Message": "no"}), KEY)
    assert exc.value.message == "no"
    ami = _Ami({"Response": "Success"})
    s = FakeSession(ext)
    resp = await public.public_originate(payload, s, ami, KEY)
    assert resp.status_code == 202 and s.commits == 1
    fields = ami.sent[0][1]
    assert (fields["Exten"], fields["Channel"]) == ("998901112233", "PJSIP/101")
    assert audits[-1]["action"] == "api.originate" and audits[-1]["user_id"] is None
    assert s.added[0].to_number == "998901112233" and s.added[0].external_id == "crm:1"


# ------------------------------------------------------------ yozuv router (admin/operator)
@pytest.fixture
def rec_env(monkeypatch, tmp_path):
    monkeypatch.setattr(recordings.settings, "recordings_dir", str(tmp_path))
    (tmp_path / "a.wav").write_bytes(b"RIFF")
    row = _rec(path="a.wav")

    async def get_active(session, tenant_id, rid):
        return row if rid == UID else None

    monkeypatch.setattr(rec_routes.recordings, "get_active", get_active)
    return SimpleNamespace(row=row, dir=tmp_path)


def _user(admin: bool):
    return SimpleNamespace(id="u1", tenant_id="t", tenant=SimpleNamespace(code="t1"), admin=admin)


@pytest.mark.asyncio
async def test_recording_audio_permissions(monkeypatch, rec_env):
    monkeypatch.setattr(rec_routes, "_require_calls_permission", lambda user: user.admin)

    async def own(session, user):
        return "101"

    async def access(session, rec, *, code, number):
        return number == "102"

    monkeypatch.setattr(rec_routes, "_own_extension_number", own)
    monkeypatch.setattr(rec_routes.recordings, "operator_can_access", access)
    with pytest.raises(ApiError) as exc:
        await rec_routes.recording_audio("nope", FakeSession(), _user(True))
    assert exc.value.status_code == 404
    assert (await rec_routes.recording_audio(UID, FakeSession(), _user(True))).media_type == "audio/wav"
    with pytest.raises(ApiError) as exc:
        await rec_routes.recording_audio(UID, FakeSession(), _user(False))
    assert exc.value.status_code == 403
    rec_env.row.path = "missing.wav"
    with pytest.raises(ApiError) as exc:
        await rec_routes.recording_audio(UID, FakeSession(), _user(True))
    assert exc.value.code == "file_missing"


@pytest.mark.asyncio
async def test_delete_recording(monkeypatch, rec_env):
    actions = []

    async def fake_audit(session, **kw):
        actions.append((kw["action"], kw["entity_id"]))

    monkeypatch.setattr(rec_routes, "record_audit", fake_audit)
    with pytest.raises(ApiError) as exc:
        await rec_routes.delete_recording("nope", FakeSession(), _user(True))
    assert exc.value.status_code == 404
    s = FakeSession()
    assert (await rec_routes.delete_recording(UID, s, _user(True))).status_code == 204
    assert rec_env.row.deleted_at is not None and not (rec_env.dir / "a.wav").exists()
    assert actions == [("recording.delete", UID)] and s.commits == 1

    def boom(path):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(rec_routes.recordings, "unlink_file", boom)
    with pytest.raises(ApiError) as exc:
        await rec_routes.delete_recording(UID, FakeSession(), _user(True))
    assert exc.value.code == "recording_delete_failed" and "Permission denied" in exc.value.message


# ------------------------------------------------------------ AMI sessiya filtri
@pytest.mark.asyncio
async def test_ami_add_filters(monkeypatch):
    from app.services.ami import AmiClient, AmiError

    client = AmiClient("h", 1, "u", "p", event_filters=("Event: X", "Variable: Y"))
    sent, replies = [], [{"Response": "Success"}, {"Response": "Success"}]

    async def action(name, **fields):
        sent.append((name, fields))
        return replies.pop(0)

    monkeypatch.setattr(client, "action", action)
    await client._add_filters()
    assert sent == [("Filter", {"Operation": "Add", "Filter": "Event: X"}),
                    ("Filter", {"Operation": "Add", "Filter": "Variable: Y"})]
    replies[:] = [{"Response": "Error", "Message": "Permission denied"}]
    with pytest.raises(AmiError, match="Permission denied"):
        await client._add_filters()
    assert AmiClient("h", 1, "u", "p").event_filters == ()
