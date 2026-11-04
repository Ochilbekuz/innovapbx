"""`app/api/v1/system_time.py` — m12-contract.md B1 (sana/vaqt). DB/socketsiz:
soxta `NetdClient` + soxta sessiya (`test_network_api_unit.py` qolipi)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1 import system_time as st
from app.core.errors import ApiError
from app.schemas import TimeConfigIn
from app.services.netd_client import NetdUnavailableError

USER = SimpleNamespace(id="u1", tenant_id="t1")

STATE_RESULT = {"now_utc": "2026-01-01T00:00:00+00:00", "timezone": "UTC", "ntp_enabled": True,
                 "ntp_servers": [], "synced": True, "backend": "timesyncd", "readonly_reason": None}


class _Session:
    def __init__(self, tenant_tz="Asia/Tashkent"):
        self.added: list = []
        self.commits = 0
        self.tenant = SimpleNamespace(id="t1", timezone=tenant_tz)

    async def get(self, _model, _id):
        return self.tenant

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


class _FakeClient:
    def __init__(self, **ops):
        self._ops = ops

    async def _dispatch(self, op, **kwargs):
        behavior = self._ops.get(op)
        if behavior is None:
            raise AssertionError(f"kutilmagan amal: {op}")
        if isinstance(behavior, Exception):
            raise behavior
        return behavior(**kwargs) if callable(behavior) else behavior

    async def time_state(self, **kw):
        return await self._dispatch("time_state", **kw)

    async def time_apply(self, **kw):
        return await self._dispatch("time_apply", **kw)

    async def time_sync(self, **kw):
        return await self._dispatch("time_sync", **kw)


class _ApplySpy:
    def __init__(self):
        self.calls = []

    async def __call__(self, session, *, tenant_id, user_id, ami):
        self.calls.append(tenant_id)
        return SimpleNamespace(to_dict=lambda: {"status": "applied", "revision": 7, "message": None})


@pytest.fixture
def apply_spy(monkeypatch):
    spy = _ApplySpy()
    monkeypatch.setattr(st, "apply_config", spy)
    return spy


def _ok(result):
    return {"ok": True, "result": result}


def _err(code, message="xato", fields=None):
    return {"ok": False, "error": {"code": code, "message": message, "fields": fields or []}}


def _config(**overrides):
    base = dict(timezone="Asia/Tashkent", ntp_servers=[], ntp_enabled=True)
    base.update(overrides)
    return TimeConfigIn(**base)


@pytest.mark.asyncio
async def test_get_system_time_passthrough():
    client = _FakeClient(time_state=_ok(STATE_RESULT))
    result = await st.get_system_time(client=client, user=USER)
    assert result["timezone"] == "UTC"


@pytest.mark.asyncio
async def test_get_system_time_helper_unreachable_raises_503():
    client = _FakeClient(time_state=NetdUnavailableError("yo'q"))
    with pytest.raises(ApiError) as exc:
        await st.get_system_time(client=client, user=USER)
    assert exc.value.status_code == 503
    assert exc.value.code == "helper_unavailable"


@pytest.mark.asyncio
async def test_put_system_time_records_audit_and_commits(apply_spy):
    session = _Session()
    client = _FakeClient(time_apply=_ok({**STATE_RESULT, "timezone": "Asia/Tashkent"}))
    result = await st.put_system_time(_config(), session=session, client=client, user=USER, ami=None)
    assert result["timezone"] == "Asia/Tashkent"
    assert session.commits == 1
    assert session.added[0].action == "update"  # "system.time.apply" -> normalize_action -> update


@pytest.mark.asyncio
async def test_put_system_time_readonly_raises_409():
    client = _FakeClient(time_apply=_err("readonly", "Faqat ko'rish"))
    with pytest.raises(ApiError) as exc:
        await st.put_system_time(_config(), session=_Session(), client=client, user=USER, ami=None)
    assert exc.value.status_code == 409
    assert exc.value.code == "readonly"


@pytest.mark.asyncio
async def test_put_system_time_invalid_config_raises_422_with_fields():
    client = _FakeClient(time_apply=_err("invalid_config", "Yaroqsiz", [{"field": "timezone", "message": "xato"}]))
    with pytest.raises(ApiError) as exc:
        await st.put_system_time(_config(), session=_Session(), client=client, user=USER, ami=None)
    assert exc.value.status_code == 422
    assert exc.value.details["fields"][0]["field"] == "timezone"


def test_time_config_in_rejects_unknown_timezone():
    with pytest.raises(ValueError):
        _config(timezone="Nowhere/Land")


def test_time_config_in_rejects_invalid_ntp_server():
    with pytest.raises(ValueError):
        _config(ntp_servers=["not a host\n"])


# ------------------------------------------------------------------ PBX vaqt zonasi = server vaqt zonasi

@pytest.mark.asyncio
async def test_put_new_timezone_moves_pbx_timezone_and_recompiles_dialplan(apply_spy):
    session = _Session(tenant_tz="Asia/Tashkent")
    client = _FakeClient(time_apply=_ok({**STATE_RESULT, "timezone": "Europe/Moscow"}))
    result = await st.put_system_time(_config(timezone="Europe/Moscow"), session=session, client=client,
                                      user=USER, ami=None)
    assert session.tenant.timezone == "Europe/Moscow"
    assert apply_spy.calls == ["t1"]
    assert result["apply"] == {"status": "applied", "revision": 7, "message": None}


@pytest.mark.asyncio
async def test_put_same_timezone_does_not_recompile(apply_spy):
    session = _Session(tenant_tz="Asia/Tashkent")
    client = _FakeClient(time_apply=_ok({**STATE_RESULT, "timezone": "Asia/Tashkent"}))
    result = await st.put_system_time(_config(), session=session, client=client, user=USER, ami=None)
    assert apply_spy.calls == []
    assert result["apply"] is None


@pytest.mark.asyncio
async def test_put_failed_netd_keeps_pbx_timezone(apply_spy):
    session = _Session(tenant_tz="Asia/Tashkent")
    client = _FakeClient(time_apply=_err("command_failed", "timedatectl xato"))
    with pytest.raises(ApiError) as exc:
        await st.put_system_time(_config(timezone="Europe/Moscow"), session=session, client=client,
                                 user=USER, ami=None)
    assert exc.value.status_code == 502
    assert session.tenant.timezone == "Asia/Tashkent"
    assert apply_spy.calls == []


# ------------------------------------------------------------------ «Hozir sinxronlash»

@pytest.mark.asyncio
async def test_sync_system_time_returns_state_and_audits():
    session = _Session()
    client = _FakeClient(time_sync=_ok({**STATE_RESULT, "sync_server": "0.asia.pool.ntp.org"}))
    result = await st.sync_system_time(session=session, client=client, user=USER)
    assert result["sync_server"] == "0.asia.pool.ntp.org"
    assert session.commits == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("code,status", [("sync_failed", 502), ("ntp_disabled", 409), ("unsupported", 409)])
async def test_sync_system_time_error_statuses(code, status):
    client = _FakeClient(time_sync=_err(code))
    with pytest.raises(ApiError) as exc:
        await st.sync_system_time(session=_Session(), client=client, user=USER)
    assert exc.value.status_code == status
    assert exc.value.code == code
