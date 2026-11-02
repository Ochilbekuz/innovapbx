"""`app/netd/protocol.py` — JSON amal dispetcheri (soxta `NetdService` orqali,
haqiqiy soket/fayl tizimisiz)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.netd.protocol import dispatch
from app.netd.service import NetdError


class _FakeService:
    async def state(self):
        return {"backend": "ifupdown"}

    async def validate(self, config, *, request_host=None):
        assert isinstance(config, SimpleNamespace)
        return {"ok": True, "config_host": request_host}

    async def apply(self, config, *, request_host=None, meta=None):
        if config.hostname == "bad":
            raise NetdError("invalid_config", "yaroqsiz", [{"field": "hostname", "message": "x"}])
        return {"applied": True, "meta": meta}

    async def confirm(self, pending_id):
        return {"confirmed": pending_id}

    async def rollback(self, pending_id):
        return {"rolled_back": pending_id}


@pytest.mark.asyncio
async def test_unknown_op_is_bad_request():
    response = await dispatch(_FakeService(), {"op": "nuke"})
    assert response == {"ok": False, "error": {"code": "bad_request", "message": "Noma'lum amal: 'nuke'", "fields": []}}


@pytest.mark.asyncio
async def test_state_dispatch():
    response = await dispatch(_FakeService(), {"op": "state"})
    assert response == {"ok": True, "result": {"backend": "ifupdown"}}


@pytest.mark.asyncio
async def test_validate_converts_config_to_namespace_and_forwards_host():
    response = await dispatch(_FakeService(), {"op": "validate", "config": {"hostname": "h"},
                                                "request_host": "10.0.0.5"})
    assert response == {"ok": True, "result": {"ok": True, "config_host": "10.0.0.5"}}


@pytest.mark.asyncio
async def test_validate_missing_config_is_bad_request():
    response = await dispatch(_FakeService(), {"op": "validate"})
    assert response["ok"] is False
    assert response["error"]["code"] == "bad_request"


@pytest.mark.asyncio
async def test_apply_netd_error_becomes_structured_error():
    response = await dispatch(_FakeService(), {"op": "apply", "config": {"hostname": "bad"}})
    assert response["ok"] is False
    assert response["error"]["code"] == "invalid_config"
    assert response["error"]["fields"] == [{"field": "hostname", "message": "x"}]


@pytest.mark.asyncio
async def test_confirm_requires_pending_id():
    response = await dispatch(_FakeService(), {"op": "confirm"})
    assert response["ok"] is False and response["error"]["code"] == "bad_request"


@pytest.mark.asyncio
async def test_confirm_dispatch():
    response = await dispatch(_FakeService(), {"op": "confirm", "pending_id": "p1"})
    assert response == {"ok": True, "result": {"confirmed": "p1"}}


@pytest.mark.asyncio
async def test_rollback_dispatch():
    response = await dispatch(_FakeService(), {"op": "rollback", "pending_id": "p1"})
    assert response == {"ok": True, "result": {"rolled_back": "p1"}}
