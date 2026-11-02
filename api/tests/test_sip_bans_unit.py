"""`app/api/v1/sip_bans.py` — M2c §2: `/security/bans` CRUD, `/security/stats`.
DB/AMI'siz soxta sessiya (`test_security_v1_unit.py` BILAN BIR XIL qolip)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import sip_bans as mod
from app.core.errors import ApiError

USER = SimpleNamespace(id="u1", tenant_id="t1")
NOW = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return SimpleNamespace(all=lambda: self._rows)

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalar_one(self):
        return self._rows[0] if self._rows else 0


class _Session:
    def __init__(self, *, settings_row=None, exec_queue=None):
        self.settings_row = settings_row
        self._exec_queue = list(exec_queue or [])
        self.added: list = []
        self.flushes = self.commits = 0

    async def get(self, _model, _pk):
        return self.settings_row

    async def execute(self, _stmt):
        rows = self._exec_queue.pop(0) if self._exec_queue else []
        return _Result(rows)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        # Haqiqiy DB bo'lmasa `server_default=text("now()")` (masalan `IpBan.created_at`)
        # hech qachon to'lmaydi -- real flush/INSERT...RETURNING'ni taqlid qilamiz.
        for obj in self.added:
            if getattr(obj, "created_at", "missing") is None:
                obj.created_at = NOW
        self.flushes += 1

    async def commit(self):
        self.commits += 1


def _ban(**kw):
    base = dict(id="b1", ip="1.2.3.4", reason="auto", failures=5, note=None,
                created_at=NOW, expires_at=None, created_by=None, lifted_at=None, lift_reason=None)
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def env(monkeypatch):
    state = {"audit": [], "apply_calls": 0}

    async def fake_audit(session, **kw):
        state["audit"].append(kw)

    async def fake_apply(session, ami):
        state["apply_calls"] += 1
        return SimpleNamespace(to_dict=lambda: {"status": "applied", "revision": None, "message": None})

    monkeypatch.setattr(mod, "record_audit", fake_audit)
    monkeypatch.setattr(mod, "apply_acl", fake_apply)
    return state


@pytest.mark.asyncio
async def test_list_ip_bans_maps_fields():
    session = _Session(exec_queue=[[_ban()]])
    out = await mod.list_ip_bans(session=session, user=USER)
    assert len(out.items) == 1
    assert out.items[0].ip == "1.2.3.4" and out.items[0].failures == 5


@pytest.mark.asyncio
async def test_create_ban_bad_ip_422(env):
    session = _Session(settings_row=SimpleNamespace(sip_guard={}))
    with pytest.raises(ApiError) as e:
        await mod.create_ip_ban(mod.CreateIpBanPayload(ip="not-an-ip"), session=session, user=USER, ami=None)
    assert (e.value.status_code, e.value.code, e.value.field) == (422, "bad_ip", "ip")


@pytest.mark.asyncio
async def test_create_ban_trusted_ip_409(env):
    session = _Session(settings_row=SimpleNamespace(sip_guard={"trusted_nets": ["9.9.9.0/24"]}))
    with pytest.raises(ApiError) as e:
        await mod.create_ip_ban(mod.CreateIpBanPayload(ip="9.9.9.5"), session=session, user=USER, ami=None)
    assert (e.value.status_code, e.value.code) == (409, "trusted_ip")


@pytest.mark.asyncio
async def test_create_ban_already_banned_409(env):
    session = _Session(settings_row=SimpleNamespace(sip_guard={}), exec_queue=[[_ban(ip="5.5.5.5")]])
    with pytest.raises(ApiError) as e:
        await mod.create_ip_ban(mod.CreateIpBanPayload(ip="5.5.5.5"), session=session, user=USER, ami=None)
    assert (e.value.status_code, e.value.code) == (409, "already_banned")


@pytest.mark.asyncio
async def test_create_ban_success_uses_payload_ban_s(env):
    session = _Session(settings_row=SimpleNamespace(sip_guard={"ban_s": 3600}), exec_queue=[[]])
    out = await mod.create_ip_ban(mod.CreateIpBanPayload(ip="6.6.6.6", ban_s=10), session=session, user=USER, ami=None)
    assert out.item.ip == "6.6.6.6"
    assert out.apply.status == "applied"
    assert env["apply_calls"] == 1
    ban_row = next(o for o in session.added if type(o).__name__ == "IpBan")
    assert ban_row.expires_at - datetime.now(timezone.utc) < timedelta(seconds=11)
    assert env["audit"][0]["action"] == "security.ban_create"


@pytest.mark.asyncio
async def test_create_ban_default_ban_s_zero_means_no_expiry(env):
    session = _Session(settings_row=SimpleNamespace(sip_guard={"ban_s": 0}), exec_queue=[[]])
    out = await mod.create_ip_ban(mod.CreateIpBanPayload(ip="7.7.7.7"), session=session, user=USER, ami=None)
    assert out.item.expires_at is None


@pytest.mark.asyncio
async def test_delete_ban_not_found_404(env):
    session = _Session(exec_queue=[[]])
    with pytest.raises(ApiError) as e:
        await mod.delete_ip_ban("missing", session=session, user=USER, ami=None)
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_ban_lifts_and_writes_event(env):
    ban = _ban()
    session = _Session(exec_queue=[[ban]])
    out = await mod.delete_ip_ban("b1", session=session, user=USER, ami=None)
    assert ban.lifted_at is not None and ban.lift_reason == "manual"
    assert out.apply.status == "applied"
    assert any(type(o).__name__ == "SecurityEvent" and o.kind == "ip_unbanned" for o in session.added)
    assert env["apply_calls"] == 1


@pytest.mark.asyncio
async def test_stats_fills_empty_hours_with_zero():
    session = _Session(exec_queue=[[], [], [0]])
    out = await mod.get_security_stats(hours=3, session=session, user=USER)
    assert len(out.hours) == 3
    assert all(h.failures == 0 and h.blocked == 0 for h in out.hours)
    assert out.totals.bans_active == 0


@pytest.mark.asyncio
async def test_stats_aggregates_top_ips_and_marks_banned():
    stat1 = SimpleNamespace(hour=NOW.replace(minute=0, second=0, microsecond=0), ip="1.1.1.1",
                            failures=3, blocked=1, last_at=NOW)
    stat2 = SimpleNamespace(hour=NOW.replace(minute=0, second=0, microsecond=0), ip="1.1.1.1",
                            failures=2, blocked=0, last_at=NOW + timedelta(minutes=5))
    session = _Session(exec_queue=[[stat1, stat2], ["1.1.1.1"], [1]])
    out = await mod.get_security_stats(hours=1, session=session, user=USER)
    assert out.top_ips[0].ip == "1.1.1.1"
    assert out.top_ips[0].failures == 5
    assert out.top_ips[0].banned is True
    assert out.totals.failures == 5 and out.totals.blocked == 1
    assert out.totals.bans_active == 1
