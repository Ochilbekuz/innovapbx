"""`app/api/v1/access.py` — kirish (SSH/Veb portlari) REST qatlami. DB/
socketsiz: soxta `NetdClient` + soxta sessiya (`test_firewall_api_unit.py`
qolipi)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1 import access as acc
from app.core.errors import ApiError
from app.schemas import AccessPendingActionIn, AccessSshApplyIn, AccessWebApplyIn
from app.services.netd_client import NetdUnavailableError

USER = SimpleNamespace(id="u1", tenant_id="t1")

STATE_RESULT = {
    "ssh": {"port": 22, "active": True, "listening_ports": [22], "password_auth": True, "root_login": "no",
            "login_users": ["innova"], "host_firewall": "innova"},
    "web": {"http_port": 80, "https_port": 443},
    "readonly_reason": None, "pending": None, "last_result": None,
}


class _Session:
    def __init__(self, select_result=None):
        self.added: list = []
        self.commits = 0
        self._select_result = select_result

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def execute(self, _stmt):
        return SimpleNamespace(scalar_one_or_none=lambda: self._select_result)


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

    async def access_state(self, **kw):
        return await self._dispatch("access_state", **kw)

    async def access_ssh_apply(self, **kw):
        return await self._dispatch("access_ssh_apply", **kw)

    async def access_web_apply(self, **kw):
        return await self._dispatch("access_web_apply", **kw)

    async def access_confirm(self, **kw):
        return await self._dispatch("access_confirm", **kw)

    async def access_rollback(self, **kw):
        return await self._dispatch("access_rollback", **kw)


def _ok(result):
    return {"ok": True, "result": result}


def _err(code, message="xato", fields=None):
    return {"ok": False, "error": {"code": code, "message": message, "fields": fields or []}}


def _request(host="10.0.0.5"):
    return SimpleNamespace(client=SimpleNamespace(host=host) if host else None)


@pytest.mark.asyncio
async def test_get_access_state_passthrough():
    client = _FakeClient(access_state=_ok(STATE_RESULT))
    result = await acc.get_access_state(client=client, user=USER)
    assert result["ssh"]["port"] == 22


@pytest.mark.asyncio
async def test_get_access_state_helper_unreachable_raises_503():
    client = _FakeClient(access_state=NetdUnavailableError("yo'q"))
    with pytest.raises(ApiError) as exc:
        await acc.get_access_state(client=client, user=USER)
    assert exc.value.status_code == 503
    assert exc.value.code == "helper_unavailable"


@pytest.mark.asyncio
async def test_apply_access_ssh_records_audit_and_commits():
    session = _Session()
    pending = {"pending_id": "a1", "expires_at": "x", "warnings": []}
    client = _FakeClient(access_ssh_apply=_ok(pending))
    result = await acc.apply_access_ssh(AccessSshApplyIn(port=2222), session=session, client=client, user=USER)
    assert result["pending_id"] == "a1"
    assert session.commits == 1
    assert session.added[0].entity_id == "a1"
    assert session.added[0].action == "update"  # "access.ssh.apply" -> normalize_action -> update


@pytest.mark.asyncio
async def test_apply_access_ssh_readonly_raises_409():
    client = _FakeClient(access_ssh_apply=_err("readonly", "Faqat ko'rish"))
    with pytest.raises(ApiError) as exc:
        await acc.apply_access_ssh(AccessSshApplyIn(port=2222), session=_Session(), client=client, user=USER)
    assert exc.value.status_code == 409
    assert exc.value.code == "readonly"


@pytest.mark.asyncio
async def test_apply_access_ssh_invalid_config_raises_422_with_fields():
    client = _FakeClient(access_ssh_apply=_err(
        "invalid_config", "Port band", [{"field": "port", "message": "band"}]))
    with pytest.raises(ApiError) as exc:
        await acc.apply_access_ssh(AccessSshApplyIn(port=5060), session=_Session(), client=client, user=USER)
    assert exc.value.status_code == 422
    assert exc.value.details["fields"][0]["field"] == "port"


@pytest.mark.asyncio
async def test_apply_access_ssh_pending_exists_raises_409():
    client = _FakeClient(access_ssh_apply=_err("pending_exists"))
    with pytest.raises(ApiError) as exc:
        await acc.apply_access_ssh(AccessSshApplyIn(port=2222), session=_Session(), client=client, user=USER)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_apply_access_web_records_audit_with_both_ports():
    session = _Session()
    pending = {"pending_id": "a2", "expires_at": "x", "warnings": []}
    client = _FakeClient(access_web_apply=_ok(pending))
    payload = AccessWebApplyIn(http_port=8080, https_port=8443)
    result = await acc.apply_access_web(payload, session=session, client=client, user=USER)
    assert result["pending_id"] == "a2"
    assert session.added[0].diff == {"http_port": 8080, "https_port": 8443}


@pytest.mark.asyncio
async def test_confirm_access_clears_pending_and_audits():
    session = _Session()
    client = _FakeClient(access_confirm=_ok({**STATE_RESULT,
                                              "last_result": {"status": "confirmed", "at": "x", "message": None}}))
    payload = AccessPendingActionIn(pending_id="a1")
    result = await acc.confirm_access(payload, session=session, client=client, user=USER)
    assert result["last_result"]["status"] == "confirmed"
    assert session.added[0].entity_id == "a1"
    assert session.added[0].action == "update"  # "access.confirm" -> normalize_action -> update


@pytest.mark.asyncio
async def test_rollback_access_not_found_raises_404():
    client = _FakeClient(access_rollback=_err("not_found"))
    payload = AccessPendingActionIn(pending_id="missing")
    with pytest.raises(ApiError) as exc:
        await acc.rollback_access(payload, session=_Session(), client=client, user=USER)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_confirm_access_web_public_confirms_without_user():
    session = _Session(select_result="t1")
    seen = {}

    def _capture(**kw):
        seen.update(kw)
        return STATE_RESULT

    client = _FakeClient(access_confirm=lambda **kw: _ok(_capture(**kw)))
    payload = AccessPendingActionIn(pending_id="a2")
    result = await acc.confirm_access_web_public(payload, _request(), session=session, client=client)
    assert result == {"status": "confirmed"}
    assert seen["kind"] == "web"
    assert session.commits == 1
    assert session.added[0].action == "update"  # "access.web.confirm_public" -> normalize_action -> update
    assert session.added[0].user_id is None


@pytest.mark.asyncio
async def test_confirm_access_web_public_without_tenant_skips_audit():
    session = _Session(select_result=None)
    client = _FakeClient(access_confirm=_ok(STATE_RESULT))
    payload = AccessPendingActionIn(pending_id="a2")
    result = await acc.confirm_access_web_public(payload, _request(), session=session, client=client)
    assert result == {"status": "confirmed"}
    assert session.commits == 0
    assert session.added == []


@pytest.mark.asyncio
async def test_confirm_access_web_public_not_found_raises_404():
    client = _FakeClient(access_confirm=_err("not_found"))
    payload = AccessPendingActionIn(pending_id="missing")
    with pytest.raises(ApiError) as exc:
        await acc.confirm_access_web_public(payload, _request(), session=_Session(), client=client)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_confirm_access_web_public_rate_limited_after_many_attempts():
    client = _FakeClient(access_confirm=_err("not_found"))
    payload = AccessPendingActionIn(pending_id="missing")
    acc._limiter = acc.SlidingWindowLimiter()  # testlar orasida mustaqil holat
    host = "203.0.113.9"
    for _ in range(acc._PUBLIC_CONFIRM_RATE_LIMIT_PER_MIN):
        with pytest.raises(ApiError) as exc:
            await acc.confirm_access_web_public(payload, _request(host), session=_Session(), client=client)
        assert exc.value.status_code == 404
    with pytest.raises(ApiError) as exc:
        await acc.confirm_access_web_public(payload, _request(host), session=_Session(), client=client)
    assert exc.value.status_code == 429
    assert exc.value.code == "rate_limited"
