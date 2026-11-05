"""`app/api/v1/network.py` — m8-network-contract.md bo'lim 4 (REST qatlami).
DB/socketsiz: soxta `NetdClient` (duck-typed, javobni `protocol.py` konvertida
qaytaradi) + soxta sessiya (`test_backups_v1_unit.py` qolipi)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1 import network as net
from app.core.errors import ApiError
from app.schemas import NetworkConfigIn, NetworkDnsIn, NetworkPendingActionIn, NetworkPingIn
from app.services.netd_client import NetdUnavailableError

USER = SimpleNamespace(id="u1", tenant_id="t1")


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

    async def state(self, **kw):
        return await self._dispatch("state", **kw)

    async def validate(self, **kw):
        return await self._dispatch("validate", **kw)

    async def apply(self, **kw):
        return await self._dispatch("apply", **kw)

    async def confirm(self, **kw):
        return await self._dispatch("confirm", **kw)

    async def rollback(self, **kw):
        return await self._dispatch("rollback", **kw)

    async def net_ping(self, **kw):
        return await self._dispatch("net_ping", **kw)


def _ok(result):
    return {"ok": True, "result": result}


def _err(code, message="xato", fields=None):
    return {"ok": False, "error": {"code": code, "message": message, "fields": fields or []}}


def _request(host="10.0.0.5"):
    return SimpleNamespace(client=SimpleNamespace(host=host) if host else None)


def _config(**overrides):
    base = dict(hostname="host1", interfaces=[], routes=[], dns=NetworkDnsIn(), timeout_s=120)
    base.update(overrides)
    return NetworkConfigIn(**base)


STATE_RESULT = {
    "helper": {"available": True, "version": "1.0", "error": None}, "backend": "ifupdown", "editable": True,
    "readonly_reason": None, "hostname": "host1", "dns": {"servers": [], "search": [], "editable": True},
    "default_gateway": {"address": None, "interface": None}, "interfaces": [],
    "routes": {"static": [], "live": []}, "pending": None, "last_result": None,
}


@pytest.mark.asyncio
async def test_get_network_state_passthrough():
    client = _FakeClient(state=_ok(STATE_RESULT))
    result = await net.get_network_state(client=client, user=USER)
    assert result["backend"] == "ifupdown"


@pytest.mark.asyncio
async def test_get_network_state_degrades_when_netd_unreachable():
    client = _FakeClient(state=NetdUnavailableError("yo'q"))
    result = await net.get_network_state(client=client, user=USER)
    assert result["helper"]["available"] is False
    assert result["editable"] is False


@pytest.mark.asyncio
async def test_validate_network_forwards_request_host():
    seen = {}

    def _capture(**kw):
        seen.update(kw)
        return {"ok": True, "errors": [], "warnings": [], "diff": []}

    client = _FakeClient(validate=lambda **kw: _ok(_capture(**kw)))
    await net.validate_network(_config(), _request("10.0.0.5"), client=client, user=USER)
    assert seen["request_host"] == "10.0.0.5"
    assert seen["config"]["hostname"] == "host1"


@pytest.mark.asyncio
async def test_apply_network_records_audit_and_commits():
    session = _Session()
    client = _FakeClient(apply=_ok({**STATE_RESULT, "pending": {"id": "p1", "applied_at": "x",
                                                                 "expires_at": "y", "summary": []}}))
    result = await net.apply_network(_config(), _request(), session=session, client=client, user=USER)
    assert result["pending"]["id"] == "p1"
    assert session.commits == 1
    assert len(session.added) == 1
    assert session.added[0].action == "update"  # "network.apply" -> normalize_action -> update
    assert session.added[0].entity_id == "p1"


@pytest.mark.asyncio
async def test_apply_network_readonly_raises_503():
    client = _FakeClient(apply=_err("readonly", "Faqat ko'rish"))
    with pytest.raises(ApiError) as exc:
        await net.apply_network(_config(), _request(), session=_Session(), client=client, user=USER)
    assert exc.value.status_code == 503
    assert exc.value.code == "readonly"


@pytest.mark.asyncio
async def test_apply_network_invalid_config_raises_422_with_fields():
    client = _FakeClient(apply=_err("invalid_config", "Yaroqsiz", [{"field": "hostname", "message": "xato"}]))
    with pytest.raises(ApiError) as exc:
        await net.apply_network(_config(), _request(), session=_Session(), client=client, user=USER)
    assert exc.value.status_code == 422
    assert exc.value.details["fields"][0]["field"] == "hostname"


@pytest.mark.asyncio
async def test_apply_network_pending_exists_raises_409():
    client = _FakeClient(apply=_err("pending_exists"))
    with pytest.raises(ApiError) as exc:
        await net.apply_network(_config(), _request(), session=_Session(), client=client, user=USER)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_apply_network_helper_unreachable_raises_503():
    client = _FakeClient(apply=NetdUnavailableError("yo'q"))
    with pytest.raises(ApiError) as exc:
        await net.apply_network(_config(), _request(), session=_Session(), client=client, user=USER)
    assert exc.value.status_code == 503
    assert exc.value.code == "helper_unavailable"


@pytest.mark.asyncio
async def test_confirm_network_clears_pending_and_audits():
    session = _Session()
    client = _FakeClient(confirm=_ok({**STATE_RESULT, "last_result": {"kind": "confirmed", "at": "x",
                                                                        "message": None}}))
    payload = NetworkPendingActionIn(pending_id="p1")
    result = await net.confirm_network(payload, session=session, client=client, user=USER)
    assert result["last_result"]["kind"] == "confirmed"
    assert session.commits == 1
    assert session.added[0].entity_id == "p1"


@pytest.mark.asyncio
async def test_rollback_network_not_found_raises_404():
    client = _FakeClient(rollback=_err("not_found"))
    payload = NetworkPendingActionIn(pending_id="missing")
    with pytest.raises(ApiError) as exc:
        await net.rollback_network(payload, session=_Session(), client=client, user=USER)
    assert exc.value.status_code == 404


# --------------------------------------------------------------------- «Ping» tabi

PING_RESULT = {"host": "1.1.1.1", "ok": True, "transmitted": 4, "received": 4, "loss_pct": 0.0,
               "rtt_min_ms": 1.0, "rtt_avg_ms": 1.5, "rtt_max_ms": 2.0, "output": "4 packets transmitted"}


@pytest.mark.asyncio
async def test_ping_network_forwards_host_and_count_without_audit():
    seen = {}

    def behavior(**kw):
        seen.update(kw)
        return _ok(PING_RESULT)

    result = await net.ping_network(NetworkPingIn(host="1.1.1.1", count=4), client=_FakeClient(net_ping=behavior),
                                    user=USER)
    assert seen == {"host": "1.1.1.1", "count": 4}
    assert result == PING_RESULT


@pytest.mark.asyncio
async def test_ping_network_helper_unreachable_raises_503():
    client = _FakeClient(net_ping=NetdUnavailableError("yo'q"))
    with pytest.raises(ApiError) as exc:
        await net.ping_network(NetworkPingIn(host="google.com"), client=client, user=USER)
    assert exc.value.status_code == 503 and exc.value.code == "helper_unavailable"


@pytest.mark.asyncio
async def test_ping_network_invalid_host_from_netd_raises_422():
    client = _FakeClient(net_ping=_err("invalid_config", "Yaroqsiz host", [{"field": "host", "message": "x"}]))
    with pytest.raises(ApiError) as exc:
        await net.ping_network(NetworkPingIn(host="google.com"), client=client, user=USER)
    assert exc.value.status_code == 422


def test_ping_route_is_registered_as_post():
    paths = {(m, r.path) for r in net.router.routes for m in r.methods}
    assert ("POST", "/network/ping") in paths
