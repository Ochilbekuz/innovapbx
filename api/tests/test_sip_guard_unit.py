"""`app/services/sip_guard.py` — M2c §2 (S33): oyna/ban/muddat/ACL
reconciliation. DB/AMI'siz soxta sessiya (`test_security_v1_unit.py` BILAN
BIR XIL qolip)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services import sip_guard as mod
from app.services.security_config import SipGuardConfig
from app.services.acl_apply import AclApplyResult
from app.services.security_log_tail import SecurityLogEvent

TENANT = "t1"


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return SimpleNamespace(all=lambda: self._rows)


class _Session:
    """`execute()` chaqiruvlar KETMA-KETLIGI muhim — har test o'z
    stsenariysi uchun navbatni to'liq nazorat qiladi (xira "birinchi/keyingi"
    gipotezasi o'rniga aniq navbat, ub-mode: Make it Right)."""

    def __init__(self, *, exec_queue: list[list] | None = None, get_row=None):
        self._exec_queue = list(exec_queue or [])
        self.added: list = []
        self.commits = self.flushes = 0
        self._get_row = get_row
        self.get_calls: list = []

    async def get(self, model, pk):
        self.get_calls.append((model, pk))
        return self._get_row  # sukut None -> SystemSettings/SipAttackStat yo'q

    async def execute(self, _stmt):
        rows = self._exec_queue.pop(0) if self._exec_queue else []
        return _Result(rows)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1


def _single_ban_session(ban=None) -> _Session:
    return _Session(exec_queue=[[ban] if ban else []])


def _expiring_session(rows: list) -> _Session:
    return _Session(exec_queue=[rows])


def _ban(ip="1.2.3.4", **kw):
    base = dict(ip=ip, failures=5, expires_at=None, lifted_at=None)
    base.update(kw)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------- _bump_stat
@pytest.mark.asyncio
async def test_bump_stat_truncates_hour_to_top_of_hour_in_lookup_key():
    # `exec_queue` bo'sh -> mavjud qator topilmadi -> YANGI qator qo'shiladi;
    # uning `hour`si SOAT BOSHIGA kesilgan bo'lishi SHART (soat ichidagi
    # BARCHA hodisalar BIR qatorga agregatsiya qilinishi uchun).
    session = _Session(exec_queue=[[]])
    await mod._bump_stat(session, TENANT, "1.2.3.4", failure=True, blocked=False)
    row = session.added[0]
    assert row.hour.minute == 0 and row.hour.second == 0 and row.hour.microsecond == 0


@pytest.mark.asyncio
async def test_bump_stat_increments_existing_row_without_recreating_it():
    existing = SimpleNamespace(failures=2, blocked=1, last_at=None)
    session = _Session(exec_queue=[[existing]])
    await mod._bump_stat(session, TENANT, "1.2.3.4", failure=True, blocked=True)
    assert session.added == []  # mavjud qator -- yangisi QO'SHILMAYDI
    assert existing.failures == 3 and existing.blocked == 2


# ---------------------------------------------------------------- _trim_window
def test_trim_window_drops_entries_outside_window():
    from collections import deque
    times = deque([0.0, 1.0, 50.0, 59.9])
    mod._trim_window(times, window_s=10, now=60.0)
    assert list(times) == [50.0, 59.9]


# ---------------------------------------------------------------- _handle_event
@pytest.mark.asyncio
async def test_handle_event_trusted_ip_is_ignored():
    cfg = SipGuardConfig(trusted_nets=("127.0.0.0/8",))
    session = _Session()
    state = mod.SipGuardState()
    await mod._handle_event(session, TENANT, state, SecurityLogEvent("ChallengeResponseFailed", "127.0.0.1"),
                            cfg, now=0.0)
    assert session.added == []
    assert "127.0.0.1" not in state.recent_failures


@pytest.mark.asyncio
async def test_handle_event_already_banned_ip_counts_as_blocked_not_failure():
    cfg = SipGuardConfig()
    session = _single_ban_session(_ban("9.9.9.9"))
    state = mod.SipGuardState()
    await mod._handle_event(session, TENANT, state, SecurityLogEvent("ChallengeResponseFailed", "9.9.9.9"),
                            cfg, now=0.0)
    stat = session.added[0]
    assert stat.failures == 0 and stat.blocked == 1
    assert "9.9.9.9" not in state.recent_failures  # oyna cho'zilmagan


@pytest.mark.asyncio
async def test_handle_event_disabled_guard_bumps_stat_but_never_bans():
    cfg = SipGuardConfig(enabled=False, max_failures=1)
    session = _Session()
    state = mod.SipGuardState()
    await mod._handle_event(session, TENANT, state, SecurityLogEvent("ChallengeResponseFailed", "5.5.5.5"),
                            cfg, now=0.0)
    kinds = [type(o).__name__ for o in session.added]
    assert "IpBan" not in kinds


@pytest.mark.asyncio
async def test_handle_event_reaches_threshold_triggers_ban(monkeypatch):
    cfg = SipGuardConfig(max_failures=3, window_s=60, ban_s=3600)
    session = _Session()
    state = mod.SipGuardState()
    raised = []
    monkeypatch.setattr(mod, "raise_alert", lambda *a, **kw: raised.append(a) or _ok())
    monkeypatch.setattr(mod, "tenant_language", lambda *a, **kw: _lang())

    ev = SecurityLogEvent("ChallengeResponseFailed", "8.8.8.8")
    for t in (0.0, 1.0, 2.0):
        await mod._handle_event(session, TENANT, state, ev, cfg, now=t)

    bans = [o for o in session.added if type(o).__name__ == "IpBan"]
    events = [o for o in session.added if type(o).__name__ == "SecurityEvent"]
    assert len(bans) == 1 and bans[0].ip == "8.8.8.8" and bans[0].failures == 3
    assert any(e.kind == "ip_banned" for e in events)
    assert state.recent_failures["8.8.8.8"] == pytest.approx(state.recent_failures["8.8.8.8"])  # cleared
    assert len(state.recent_failures["8.8.8.8"]) == 0


async def _ok():
    return SimpleNamespace()


async def _lang():
    return "uz"


# ---------------------------------------------------------------- _auto_ban race
@pytest.mark.asyncio
async def test_auto_ban_skips_if_already_banned_race(monkeypatch):
    session = _single_ban_session(_ban("1.1.1.1"))
    cfg = SipGuardConfig()
    await mod._auto_ban(session, TENANT, "1.1.1.1", failures=10, cfg=cfg)
    assert session.added == []  # poyga: boshqa joy allaqachon bloklagan


@pytest.mark.asyncio
async def test_auto_ban_ban_s_zero_means_no_expiry(monkeypatch):
    session = _Session()
    monkeypatch.setattr(mod, "raise_alert", lambda *a, **kw: _ok())
    monkeypatch.setattr(mod, "tenant_language", lambda *a, **kw: _lang())
    cfg = SipGuardConfig(ban_s=0)
    await mod._auto_ban(session, TENANT, "2.2.2.2", failures=5, cfg=cfg)
    ban = next(o for o in session.added if type(o).__name__ == "IpBan")
    assert ban.expires_at is None


@pytest.mark.asyncio
async def test_auto_ban_nonzero_ban_s_sets_expiry_seconds_ahead(monkeypatch):
    session = _Session()
    monkeypatch.setattr(mod, "raise_alert", lambda *a, **kw: _ok())
    monkeypatch.setattr(mod, "tenant_language", lambda *a, **kw: _lang())
    cfg = SipGuardConfig(ban_s=100)
    before = datetime.now(timezone.utc)
    await mod._auto_ban(session, TENANT, "2.2.2.3", failures=5, cfg=cfg)
    ban = next(o for o in session.added if type(o).__name__ == "IpBan")
    delta = (ban.expires_at - before).total_seconds()
    assert 99.0 <= delta <= 101.0  # aniq 100s -- +/- emas


# ---------------------------------------------------------------- _expire_bans
@pytest.mark.asyncio
async def test_expire_bans_lifts_only_due_ones():
    now = datetime.now(timezone.utc)
    due = _ban("3.3.3.3", expires_at=now - timedelta(seconds=1))
    session = _expiring_session([due])
    changed = await mod._expire_bans(session, TENANT)
    assert changed is True
    assert due.lifted_at is not None and due.lift_reason == "expired"
    assert any(type(o).__name__ == "SecurityEvent" and o.kind == "ban_expired" for o in session.added)


@pytest.mark.asyncio
async def test_expire_bans_no_rows_returns_false():
    session = _expiring_session([])
    assert await mod._expire_bans(session, TENANT) is False


# ---------------------------------------------------------------- _reconcile_acl
@pytest.mark.asyncio
async def test_reconcile_acl_skips_when_hash_unchanged_and_last_ok(monkeypatch):
    calls = []
    monkeypatch.setattr(mod, "active_banned_ips", lambda _s: _ips(["1.1.1.1"]))
    monkeypatch.setattr(mod, "apply_acl_ips", lambda *a: calls.append(a) or _apply_ok())
    state = mod.SipGuardState(last_applied_hash=mod.hash_ips(["1.1.1.1"]), last_apply_ok=True)
    await mod._reconcile_acl(session=None, ami=None, state=state)
    assert calls == []


@pytest.mark.asyncio
async def test_reconcile_acl_applies_when_hash_changed(monkeypatch):
    monkeypatch.setattr(mod, "active_banned_ips", lambda _s: _ips(["9.9.9.9"]))
    applied = []

    async def fake_apply(ips, _ami):
        applied.append(ips)
        return AclApplyResult(status="applied", message=None)
    monkeypatch.setattr(mod, "apply_acl_ips", fake_apply)

    state = mod.SipGuardState(last_applied_hash="stale-hash", last_apply_ok=True)
    await mod._reconcile_acl(session=None, ami=None, state=state)
    assert applied == [["9.9.9.9"]]
    assert state.last_applied_hash == mod.hash_ips(["9.9.9.9"])


@pytest.mark.asyncio
async def test_reconcile_acl_retries_after_previous_failure_even_if_hash_same(monkeypatch):
    monkeypatch.setattr(mod, "active_banned_ips", lambda _s: _ips(["1.1.1.1"]))
    calls = []

    async def fake_apply(ips, _ami):
        calls.append(ips)
        return AclApplyResult(status="failed", message="AMI yo'q")
    monkeypatch.setattr(mod, "apply_acl_ips", fake_apply)

    same_hash = mod.hash_ips(["1.1.1.1"])
    state = mod.SipGuardState(last_applied_hash=same_hash, last_apply_ok=False)
    await mod._reconcile_acl(session=None, ami=None, state=state)
    assert calls == [["1.1.1.1"]]  # oldingi urinish muvaffaqiyatsiz -- hash BIR XIL bo'lsa HAM qayta urinadi
    assert state.last_apply_ok is False


async def _ips(lst):
    return lst


async def _apply_ok():
    return AclApplyResult(status="applied", message=None)


# ---------------------------------------------------------------- sip_guard_cycle
class _CycleFactory:
    def __init__(self, session):
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


async def _tenant():
    return TENANT


async def _none():
    return None


async def _false():
    return False


@pytest.mark.asyncio
async def test_sip_guard_cycle_no_tenant_returns_early_without_commit(monkeypatch):
    monkeypatch.setattr(mod, "read_new_lines", lambda *_a: [])
    monkeypatch.setattr(mod, "only_tenant_id", lambda _s: _none())
    session = _Session()
    await mod.sip_guard_cycle(_CycleFactory(session), ami=None, state=mod.SipGuardState())
    assert session.commits == 0  # hali tenant yo'q -- yozadigan joy yo'q


@pytest.mark.asyncio
async def test_sip_guard_cycle_processes_events_then_commits(monkeypatch):
    ev = SecurityLogEvent("ChallengeResponseFailed", "4.4.4.4")
    monkeypatch.setattr(mod, "read_new_lines", lambda *_a: ["line"])
    monkeypatch.setattr(mod, "parse_security_line", lambda _l: ev)
    monkeypatch.setattr(mod, "only_tenant_id", lambda _s: _tenant())
    handled = []

    async def fake_handle(_session, tenant_id, _state, event, _cfg, _now):
        handled.append((tenant_id, event.ip))
    monkeypatch.setattr(mod, "_handle_event", fake_handle)
    monkeypatch.setattr(mod, "_expire_bans", lambda *_a: _false())
    monkeypatch.setattr(mod, "_reconcile_acl", lambda *_a: _none())

    session = _Session()
    await mod.sip_guard_cycle(_CycleFactory(session), ami=None, state=mod.SipGuardState())
    assert handled == [(TENANT, "4.4.4.4")]
    assert session.flushes == 1 and session.commits == 1


# ---------------------------------------------------------------- run_forever
@pytest.mark.asyncio
async def test_run_forever_calls_cycle_each_sleep_tick(monkeypatch):
    calls = []

    async def fake_cycle(*_a):
        calls.append(1)
    monkeypatch.setattr(mod, "sip_guard_cycle", fake_cycle)

    async def fake_sleep(s):
        raise asyncio.CancelledError()
    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await mod.run_forever(session_factory=None, ami=None, interval_s=2)
    assert calls == [1]


@pytest.mark.asyncio
async def test_run_forever_skips_cycle_during_maintenance(monkeypatch):
    from app.services import maintenance

    async def fail_cycle(*_a):
        raise AssertionError("texnik xizmat paytida sip_guard_cycle chaqirilmasin")
    monkeypatch.setattr(mod, "sip_guard_cycle", fail_cycle)

    async def fake_sleep(_s):
        raise asyncio.CancelledError()
    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)

    maintenance.state.enabled = True
    try:
        with pytest.raises(asyncio.CancelledError):
            await mod.run_forever(session_factory=None, ami=None, interval_s=2)
    finally:
        maintenance.state.enabled = False


@pytest.mark.asyncio
async def test_run_forever_survives_cycle_exception_and_keeps_looping(monkeypatch):
    calls = []

    async def fake_cycle(*_a):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
    monkeypatch.setattr(mod, "sip_guard_cycle", fake_cycle)

    sleep_n = {"n": 0}

    async def fake_sleep(_s):
        sleep_n["n"] += 1
        if sleep_n["n"] == 2:
            raise asyncio.CancelledError()
    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await mod.run_forever(session_factory=None, ami=None, interval_s=1)
    assert len(calls) == 2  # birinchi xato -- fon vazifa o'lmadi, ikkinchisi muvaffaqiyatli


@pytest.mark.asyncio
async def test_run_forever_propagates_cancelled_error_raised_by_cycle_itself(monkeypatch):
    async def fake_cycle(*_a):
        raise asyncio.CancelledError()
    monkeypatch.setattr(mod, "sip_guard_cycle", fake_cycle)

    async def fail_if_slept(_s):
        raise AssertionError("bekor qilingandan keyin uxlash kerak emas")
    monkeypatch.setattr(mod.asyncio, "sleep", fail_if_slept)

    with pytest.raises(asyncio.CancelledError):
        await mod.run_forever(session_factory=None, ami=None, interval_s=1)


# ---------------------------------------------------------------- M3a §0: WS hodisalari sanalmaydi
@pytest.mark.asyncio
async def test_handle_event_ws_failure_is_recorded_but_never_counted_or_banned():
    """WS orqali Asterisk nginx IP'sini ko'radi — bitta foydalanuvchining xatosi barcha softfonlarni
    bloklamasin: oyna/statistika/ban YO'Q, faqat `security_events` (`transport='ws'`)."""
    cfg = SipGuardConfig(max_failures=1)
    session = _Session()
    state = mod.SipGuardState()
    ev = SecurityLogEvent("ChallengeResponseFailed", "172.21.0.9", "ws", "t1-101")
    for t in (0.0, 1.0):
        await mod._handle_event(session, TENANT, state, ev, cfg, now=t)
    assert [type(o).__name__ for o in session.added] == ["SecurityEvent", "SecurityEvent"]
    first = session.added[0]
    assert (first.kind, first.transport, first.ip, first.details) == (
        "ws_auth_failed", "ws", "172.21.0.9", {"account": "t1-101"})
    assert "172.21.0.9" not in state.recent_failures


@pytest.mark.asyncio
async def test_handle_event_udp_failure_from_same_ip_still_counts():
    cfg = SipGuardConfig(max_failures=5, trust_lan=False)
    session = _Session(exec_queue=[[], []])
    state = mod.SipGuardState()
    await mod._handle_event(session, TENANT, state, SecurityLogEvent("ChallengeResponseFailed", "172.21.0.9", "udp"),
                            cfg, now=0.0)
    assert len(state.recent_failures["172.21.0.9"]) == 1
    assert session.added[0].failures == 1


@pytest.mark.asyncio
async def test_handle_event_lan_ip_counted_but_never_banned_when_trust_lan():
    # Telefonga noto'g'ri login yozilsa ofis IP'si bloklanib, to'g'ri parol ham 403 olardi.
    cfg = SipGuardConfig(max_failures=3, window_s=60, ban_s=3600)
    assert cfg.trust_lan is True
    session = _Session()
    state = mod.SipGuardState()
    ev = SecurityLogEvent("ChallengeResponseFailed", "192.168.1.50")
    for t in (0.0, 1.0, 2.0, 3.0):
        await mod._handle_event(session, TENANT, state, ev, cfg, now=t)
    assert not [o for o in session.added if type(o).__name__ == "IpBan"]
    assert "192.168.1.50" not in state.recent_failures


@pytest.mark.asyncio
async def test_handle_event_lan_ip_banned_when_trust_lan_off(monkeypatch):
    monkeypatch.setattr(mod, "raise_alert", lambda *a, **kw: _ok())
    monkeypatch.setattr(mod, "tenant_language", lambda *a, **kw: _lang())
    cfg = SipGuardConfig(max_failures=3, window_s=60, ban_s=3600, trust_lan=False)
    session = _Session()
    state = mod.SipGuardState()
    ev = SecurityLogEvent("ChallengeResponseFailed", "10.0.0.7")
    for t in (0.0, 1.0, 2.0):
        await mod._handle_event(session, TENANT, state, ev, cfg, now=t)
    bans = [o for o in session.added if type(o).__name__ == "IpBan"]
    assert len(bans) == 1 and bans[0].ip == "10.0.0.7"
