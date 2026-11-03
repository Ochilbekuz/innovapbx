"""`app/api/v1/security.py` — M2c §1/§3: `/security/settings` GET/PATCH,
`/security/toll-blocks` GET, `/security/toll-blocks/{id}/unblock` POST,
`/security/events` GET. DB/AMI'siz: soxta sessiya, `record_audit`/`apply_config`
monkeypatch (`test_extensions_call_fields_unit.py` BILAN BIR XIL qolip)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import security as sec
from app.core.errors import ApiError
from app.schemas_security import UpdateSecuritySettingsPayload, UpdateSipGuardItem, UpdateTollFraudItem

USER = SimpleNamespace(id="u1", tenant_id="t1")
OLD = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return SimpleNamespace(all=lambda: self._rows)

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


class _Session:
    def __init__(self, *, settings_row=None, exec_rows=None):
        self.settings_row = settings_row
        self.exec_rows = exec_rows if exec_rows is not None else []
        self.added: list = []
        self.flushes = self.commits = self.refreshed = 0

    async def get(self, _model, _pk):
        return self.settings_row

    async def execute(self, _stmt):
        return _Result(self.exec_rows)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1

    async def refresh(self, _obj):
        self.refreshed += 1


def _settings_row(**kw):
    base = dict(tenant_id="t1", sip_guard={}, toll_fraud={}, require_2fa="off", updated_at=OLD)
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def env(monkeypatch):
    state = {"audit": [], "applied": 0}

    async def fake_audit(session, **kw):
        state["audit"].append(kw)

    async def fake_apply(session, *, tenant_id, user_id, ami):
        state["applied"] += 1
        return SimpleNamespace(to_dict=lambda: {"status": "applied", "revision": 7, "message": None})

    monkeypatch.setattr(sec, "record_audit", fake_audit)
    monkeypatch.setattr(sec, "apply_config", fake_apply)
    return state


@pytest.mark.asyncio
async def test_get_security_settings_returns_parsed_defaults():
    session = _Session(settings_row=_settings_row())
    out = await sec.get_security_settings(session=session, user=USER)
    assert out.sip_guard.enabled is True and out.sip_guard.max_failures == 5
    assert out.toll_fraud.max_concurrent_outbound == 0


@pytest.mark.asyncio
async def test_get_security_settings_404_when_missing():
    session = _Session(settings_row=None)
    with pytest.raises(ApiError) as e:
        await sec.get_security_settings(session=session, user=USER)
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_patch_toll_fraud_max_concurrent_triggers_recompile(env):
    session = _Session(settings_row=_settings_row())
    payload = UpdateSecuritySettingsPayload(
        toll_fraud=UpdateTollFraudItem(max_concurrent_outbound=5), updated_at=OLD,
    )
    out = await sec.update_security_settings(payload, session=session, user=USER, ami=None)
    assert env["applied"] == 1
    assert out.apply.status == "applied" and out.apply.revision == 7
    assert out.item.toll_fraud.max_concurrent_outbound == 5
    assert env["audit"][0]["diff"] == {"toll_fraud": {"max_concurrent_outbound": 5}}
    # `updated_at` DB triggeri bilan yangilanadi — flush'dan keyin ALBATTA
    # `refresh` qilinishi kerak (keyingi PATCH stale-check'i shunga tayanadi).
    assert session.refreshed == 1


@pytest.mark.asyncio
async def test_patch_toll_fraud_other_field_does_not_recompile(env):
    session = _Session(settings_row=_settings_row())
    payload = UpdateSecuritySettingsPayload(
        toll_fraud=UpdateTollFraudItem(ext_max_per_hour=30), updated_at=OLD,
    )
    out = await sec.update_security_settings(payload, session=session, user=USER, ami=None)
    assert env["applied"] == 0
    assert out.apply.status == "unchanged" and out.apply.revision is None
    assert out.item.toll_fraud.ext_max_per_hour == 30


@pytest.mark.asyncio
async def test_patch_sip_guard_partial_merge_keeps_other_fields(env):
    session = _Session(settings_row=_settings_row(sip_guard={"max_failures": 10, "ban_s": 1800}))
    payload = UpdateSecuritySettingsPayload(sip_guard=UpdateSipGuardItem(max_failures=20), updated_at=OLD)
    out = await sec.update_security_settings(payload, session=session, user=USER, ami=None)
    assert out.item.sip_guard.max_failures == 20
    assert out.item.sip_guard.ban_s == 1800
    assert env["applied"] == 0


@pytest.mark.asyncio
async def test_patch_rejects_out_of_range_int(env):
    session = _Session(settings_row=_settings_row())
    payload = UpdateSecuritySettingsPayload(
        sip_guard=UpdateSipGuardItem(max_failures=2), updated_at=OLD,  # < 3
    )
    with pytest.raises(ApiError) as e:
        await sec.update_security_settings(payload, session=session, user=USER, ami=None)
    assert (e.value.status_code, e.value.field) == (422, "sip_guard.max_failures")
    assert env["applied"] == 0


@pytest.mark.asyncio
async def test_patch_rejects_bad_trusted_net(env):
    session = _Session(settings_row=_settings_row())
    payload = UpdateSecuritySettingsPayload(
        sip_guard=UpdateSipGuardItem(trusted_nets=["not-a-net"]), updated_at=OLD,
    )
    with pytest.raises(ApiError) as e:
        await sec.update_security_settings(payload, session=session, user=USER, ami=None)
    assert e.value.field == "sip_guard.trusted_nets"


@pytest.mark.asyncio
async def test_patch_stale_raises_409(env):
    session = _Session(settings_row=_settings_row(updated_at=NOW))
    payload = UpdateSecuritySettingsPayload(toll_fraud=UpdateTollFraudItem(ext_max_per_hour=1), updated_at=OLD)
    with pytest.raises(ApiError) as e:
        await sec.update_security_settings(payload, session=session, user=USER, ami=None)
    assert e.value.status_code == 409


def _ext(**kw):
    base = dict(id="e1", number="201", name="Ali", toll_blocked_at=NOW, toll_block_reason="per_hour")
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_list_toll_blocks_maps_fields():
    session = _Session(exec_rows=[_ext()])
    out = await sec.list_toll_blocks(session=session, user=USER)
    assert len(out.items) == 1
    item = out.items[0]
    assert (item.extension_id, item.number, item.reason) == ("e1", "201", "per_hour")


@pytest.mark.asyncio
async def test_unblock_404_when_extension_not_found(env):
    session = _Session(exec_rows=[])
    with pytest.raises(ApiError) as e:
        await sec.unblock_toll("missing", session=session, user=USER)
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_unblock_409_when_not_blocked(env):
    session = _Session(exec_rows=[_ext(toll_blocked_at=None, toll_block_reason=None)])
    with pytest.raises(ApiError) as e:
        await sec.unblock_toll("e1", session=session, user=USER)
    assert (e.value.status_code, e.value.code) == (409, "not_blocked")


@pytest.mark.asyncio
async def test_unblock_clears_fields_and_writes_event_and_audit(env):
    ext = _ext()
    session = _Session(exec_rows=[ext])
    out = await sec.unblock_toll("e1", session=session, user=USER)
    assert ext.toll_blocked_at is None and ext.toll_block_reason is None
    assert ext.toll_unblocked_at is not None
    assert session.added[0].kind == "toll_unblocked"
    assert out.item.number == "201"
    assert env["audit"][0]["action"] == "security.toll_unblock"


@pytest.mark.asyncio
async def test_list_security_events_maps_extension_number():
    ev = SimpleNamespace(id=1, at=NOW, kind="toll_blocked", ip=None, details={"number": "201"}, transport=None)
    ws = SimpleNamespace(id=2, at=NOW, kind="ws_auth_failed", ip="172.21.0.9", details={}, transport="ws")
    session = _Session(exec_rows=[(ev, "201"), (ws, None)])
    out = await sec.list_security_events(limit=100, kind=None, session=session, user=USER)
    assert out.items[0].extension == "201"
    assert out.items[0].kind == "toll_blocked" and out.items[0].transport is None
    assert out.items[1].transport == "ws"  # M3a §0
