"""`app/api/v1/firewall.py` — m12-contract.md B3 (firewall GUI). DB/socketsiz:
soxta `NetdClient` + soxta sessiya (`test_network_api_unit.py` qolipi)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1 import firewall as fw
from app.core.errors import ApiError
from app.schemas import FirewallConfigIn, FirewallPendingActionIn, FirewallServiceIn
from app.services.netd_client import NetdUnavailableError

USER = SimpleNamespace(id="u1", tenant_id="t1")

STATE_RESULT = {
    "services": [{"name": n, "mode": "all", "allow": []} for n in ("ssh", "web", "sip", "rtp")],
    "blocked_cidrs": [], "readonly_reason": None, "pending": None, "last_result": None,
}


class _Session:
    def __init__(self):
        self.added: list = []
        self.commits = 0

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

    async def firewall_state(self, **kw):
        return await self._dispatch("firewall_state", **kw)

    async def firewall_validate(self, **kw):
        return await self._dispatch("firewall_validate", **kw)

    async def firewall_apply(self, **kw):
        return await self._dispatch("firewall_apply", **kw)

    async def firewall_confirm(self, **kw):
        return await self._dispatch("firewall_confirm", **kw)

    async def firewall_rollback(self, **kw):
        return await self._dispatch("firewall_rollback", **kw)


def _ok(result):
    return {"ok": True, "result": result}


def _err(code, message="xato", fields=None):
    return {"ok": False, "error": {"code": code, "message": message, "fields": fields or []}}


def _request(host="10.0.0.5"):
    return SimpleNamespace(client=SimpleNamespace(host=host) if host else None)


def _config(**overrides):
    base = dict(services=[FirewallServiceIn(name=n, mode="all", allow=[]) for n in ("ssh", "web", "sip", "rtp")],
                blocked_cidrs=[], timeout_s=120)
    base.update(overrides)
    return FirewallConfigIn(**base)


@pytest.mark.asyncio
async def test_get_firewall_state_passthrough():
    client = _FakeClient(firewall_state=_ok(STATE_RESULT))
    result = await fw.get_firewall_state(client=client, user=USER)
    assert len(result["services"]) == 4


@pytest.mark.asyncio
async def test_get_firewall_state_helper_unreachable_raises_503():
    client = _FakeClient(firewall_state=NetdUnavailableError("yo'q"))
    with pytest.raises(ApiError) as exc:
        await fw.get_firewall_state(client=client, user=USER)
    assert exc.value.status_code == 503
    assert exc.value.code == "helper_unavailable"


@pytest.mark.asyncio
async def test_validate_firewall_forwards_request_host():
    seen = {}

    def _capture(**kw):
        seen.update(kw)
        return {"ok": True, "errors": [], "warnings": [], "diff": []}

    client = _FakeClient(firewall_validate=lambda **kw: _ok(_capture(**kw)))
    await fw.validate_firewall(_config(), _request("10.0.0.5"), client=client, user=USER)
    assert seen["request_host"] == "10.0.0.5"


@pytest.mark.asyncio
async def test_apply_firewall_records_audit_and_commits():
    session = _Session()
    pending_result = {**STATE_RESULT, "pending": {"id": "fw1", "applied_at": "x", "expires_at": "y", "summary": []}}
    client = _FakeClient(firewall_apply=_ok(pending_result))
    result = await fw.apply_firewall(_config(), _request(), session=session, client=client, user=USER)
    assert result["pending"]["id"] == "fw1"
    assert session.commits == 1
    assert session.added[0].entity_id == "fw1"
    assert session.added[0].action == "update"  # "firewall.apply" -> normalize_action -> update


@pytest.mark.asyncio
async def test_apply_firewall_self_lockout_raises_422_with_fields():
    client = _FakeClient(firewall_apply=_err(
        "invalid_config", "O'zini qulflash", [{"field": "services.ssh.allow", "message": "x"}]))
    with pytest.raises(ApiError) as exc:
        await fw.apply_firewall(_config(), _request(), session=_Session(), client=client, user=USER)
    assert exc.value.status_code == 422
    assert exc.value.details["fields"][0]["field"] == "services.ssh.allow"


@pytest.mark.asyncio
async def test_apply_firewall_readonly_raises_409():
    client = _FakeClient(firewall_apply=_err("readonly", "Faqat ko'rish"))
    with pytest.raises(ApiError) as exc:
        await fw.apply_firewall(_config(), _request(), session=_Session(), client=client, user=USER)
    assert exc.value.status_code == 409
    assert exc.value.code == "readonly"


@pytest.mark.asyncio
async def test_apply_firewall_pending_exists_raises_409():
    client = _FakeClient(firewall_apply=_err("pending_exists"))
    with pytest.raises(ApiError) as exc:
        await fw.apply_firewall(_config(), _request(), session=_Session(), client=client, user=USER)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_confirm_firewall_clears_pending_and_audits():
    session = _Session()
    client = _FakeClient(firewall_confirm=_ok({**STATE_RESULT,
                                                "last_result": {"kind": "confirmed", "at": "x", "message": None}}))
    payload = FirewallPendingActionIn(pending_id="fw1")
    result = await fw.confirm_firewall(payload, session=session, client=client, user=USER)
    assert result["last_result"]["kind"] == "confirmed"
    assert session.added[0].entity_id == "fw1"


@pytest.mark.asyncio
async def test_rollback_firewall_not_found_raises_404():
    client = _FakeClient(firewall_rollback=_err("not_found"))
    payload = FirewallPendingActionIn(pending_id="missing")
    with pytest.raises(ApiError) as exc:
        await fw.rollback_firewall(payload, session=_Session(), client=client, user=USER)
    assert exc.value.status_code == 404


def test_firewall_config_in_rejects_fewer_than_four_services():
    with pytest.raises(ValueError):
        _config(services=[FirewallServiceIn(name="ssh", mode="all", allow=[])])


def test_firewall_service_in_rejects_invalid_cidr():
    with pytest.raises(ValueError):
        FirewallServiceIn(name="ssh", mode="allowlist", allow=["not-a-cidr"])
