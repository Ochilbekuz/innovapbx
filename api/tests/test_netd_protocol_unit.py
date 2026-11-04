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

    # ------------------------------------------------------- M12 B1/B2/B3
    async def time_state(self):
        return {"timezone": "UTC"}

    async def time_apply(self, config):
        return {"timezone": config.timezone}

    async def time_sync(self):
        return {"sync_server": "0.asia.pool.ntp.org"}

    async def power_state(self):
        return {"readonly_reason": None}

    async def power_execute(self, action):
        if action == "bad":
            raise NetdError("invalid_config", "noma'lum amal", [{"field": "action", "message": "x"}])
        return {"action": action, "scheduled": True}

    async def firewall_state(self):
        return {"services": []}

    async def firewall_validate(self, config, *, request_host=None):
        return {"ok": True, "host": request_host}

    async def firewall_apply(self, config, *, request_host=None):
        return {"applied": True, "host": request_host}

    async def firewall_confirm(self, pending_id):
        return {"confirmed": pending_id}

    async def firewall_rollback(self, pending_id):
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


# --------------------------------------------------------------- M12 B1 (sana/vaqt)

@pytest.mark.asyncio
async def test_time_state_dispatch():
    response = await dispatch(_FakeService(), {"op": "time_state"})
    assert response == {"ok": True, "result": {"timezone": "UTC"}}


class _HangingService:
    async def time_apply(self, config):
        raise TimeoutError


@pytest.mark.asyncio
async def test_command_timeout_becomes_structured_error():
    """Ilgari TimeoutError dispetcherdan chiqib ketardi → netd ulanishni javobsiz yopardi → API «aloqa yo'q» 503."""
    response = await dispatch(_HangingService(), {"op": "time_apply", "config": {"timezone": "UTC"}})
    assert response["ok"] is False
    assert response["error"]["code"] == "command_timeout"


@pytest.mark.asyncio
async def test_time_sync_dispatch():
    response = await dispatch(_FakeService(), {"op": "time_sync"})
    assert response == {"ok": True, "result": {"sync_server": "0.asia.pool.ntp.org"}}


@pytest.mark.asyncio
async def test_time_apply_converts_config_to_namespace():
    response = await dispatch(_FakeService(), {"op": "time_apply", "config": {"timezone": "Asia/Tashkent"}})
    assert response == {"ok": True, "result": {"timezone": "Asia/Tashkent"}}


@pytest.mark.asyncio
async def test_time_apply_missing_config_is_bad_request():
    response = await dispatch(_FakeService(), {"op": "time_apply"})
    assert response["ok"] is False and response["error"]["code"] == "bad_request"


# --------------------------------------------------------------- M12 B2 (quvvat)

@pytest.mark.asyncio
async def test_power_state_dispatch():
    response = await dispatch(_FakeService(), {"op": "power_state"})
    assert response == {"ok": True, "result": {"readonly_reason": None}}


@pytest.mark.asyncio
async def test_power_execute_forwards_action():
    response = await dispatch(_FakeService(), {"op": "power_execute", "action": "reboot"})
    assert response == {"ok": True, "result": {"action": "reboot", "scheduled": True}}


@pytest.mark.asyncio
async def test_power_execute_missing_action_is_bad_request():
    response = await dispatch(_FakeService(), {"op": "power_execute"})
    assert response["ok"] is False and response["error"]["code"] == "bad_request"


@pytest.mark.asyncio
async def test_power_execute_netd_error_becomes_structured_error():
    response = await dispatch(_FakeService(), {"op": "power_execute", "action": "bad"})
    assert response["ok"] is False
    assert response["error"]["code"] == "invalid_config"


# --------------------------------------------------------------- M12 B3 (firewall)

@pytest.mark.asyncio
async def test_firewall_state_dispatch():
    response = await dispatch(_FakeService(), {"op": "firewall_state"})
    assert response == {"ok": True, "result": {"services": []}}


@pytest.mark.asyncio
async def test_firewall_validate_forwards_config_and_host():
    response = await dispatch(_FakeService(), {"op": "firewall_validate", "config": {"services": []},
                                                "request_host": "10.0.0.5"})
    assert response == {"ok": True, "result": {"ok": True, "host": "10.0.0.5"}}


@pytest.mark.asyncio
async def test_firewall_apply_forwards_config_and_host():
    response = await dispatch(_FakeService(), {"op": "firewall_apply", "config": {"services": []},
                                                "request_host": "10.0.0.5"})
    assert response == {"ok": True, "result": {"applied": True, "host": "10.0.0.5"}}


@pytest.mark.asyncio
async def test_firewall_confirm_dispatch():
    response = await dispatch(_FakeService(), {"op": "firewall_confirm", "pending_id": "p1"})
    assert response == {"ok": True, "result": {"confirmed": "p1"}}


@pytest.mark.asyncio
async def test_firewall_rollback_dispatch():
    response = await dispatch(_FakeService(), {"op": "firewall_rollback", "pending_id": "p1"})
    assert response == {"ok": True, "result": {"rolled_back": "p1"}}
