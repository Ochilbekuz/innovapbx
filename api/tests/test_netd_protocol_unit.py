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

    # ------------------------------------------------------- kirish (access: SSH/Veb)
    async def access_state(self):
        return {"ssh": {}, "web": {}}

    async def access_ssh_apply(self, port, *, timeout_s=None):
        return {"pending_id": "a1", "port": port, "timeout_s": timeout_s}

    async def access_web_apply(self, http_port, https_port, *, timeout_s=None):
        return {"pending_id": "a2", "http_port": http_port, "https_port": https_port, "timeout_s": timeout_s}

    async def access_confirm(self, pending_id, *, kind=None):
        return {"confirmed": pending_id, "kind": kind}

    async def access_rollback(self, pending_id):
        return {"rolled_back": pending_id}

    # ------------------------------------------------------- tarmoq «Ping»
    async def net_ping(self, host, count):
        return {"host": host, "count": count}


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


# --------------------------------------------------------------- kirish (access: SSH/Veb)

@pytest.mark.asyncio
async def test_access_state_dispatch():
    response = await dispatch(_FakeService(), {"op": "access_state"})
    assert response == {"ok": True, "result": {"ssh": {}, "web": {}}}


@pytest.mark.asyncio
async def test_access_ssh_apply_forwards_port_and_timeout():
    response = await dispatch(_FakeService(), {"op": "access_ssh_apply", "port": 2222, "timeout_s": 60})
    assert response == {"ok": True, "result": {"pending_id": "a1", "port": 2222, "timeout_s": 60}}


@pytest.mark.asyncio
async def test_access_ssh_apply_missing_port_is_bad_request():
    response = await dispatch(_FakeService(), {"op": "access_ssh_apply"})
    assert response["ok"] is False and response["error"]["code"] == "bad_request"


@pytest.mark.asyncio
async def test_access_ssh_apply_non_int_port_is_bad_request():
    response = await dispatch(_FakeService(), {"op": "access_ssh_apply", "port": "2222"})
    assert response["ok"] is False and response["error"]["code"] == "bad_request"


@pytest.mark.asyncio
async def test_access_web_apply_forwards_both_ports():
    response = await dispatch(_FakeService(), {"op": "access_web_apply", "http_port": 8080, "https_port": 8443})
    assert response == {"ok": True,
                         "result": {"pending_id": "a2", "http_port": 8080, "https_port": 8443, "timeout_s": None}}


@pytest.mark.asyncio
async def test_access_confirm_forwards_pending_id_and_kind():
    response = await dispatch(_FakeService(), {"op": "access_confirm", "pending_id": "a1", "kind": "web"})
    assert response == {"ok": True, "result": {"confirmed": "a1", "kind": "web"}}


@pytest.mark.asyncio
async def test_access_confirm_missing_pending_id_is_bad_request():
    response = await dispatch(_FakeService(), {"op": "access_confirm"})
    assert response["ok"] is False and response["error"]["code"] == "bad_request"


@pytest.mark.asyncio
async def test_access_rollback_dispatch():
    response = await dispatch(_FakeService(), {"op": "access_rollback", "pending_id": "a1"})
    assert response == {"ok": True, "result": {"rolled_back": "a1"}}


@pytest.mark.asyncio
async def test_net_ping_forwards_host_and_count():
    response = await dispatch(_FakeService(), {"op": "net_ping", "host": "1.1.1.1", "count": 3})
    assert response == {"ok": True, "result": {"host": "1.1.1.1", "count": 3}}


@pytest.mark.asyncio
@pytest.mark.parametrize("request_", [
    {"op": "net_ping", "count": 3}, {"op": "net_ping", "host": "", "count": 3},
    {"op": "net_ping", "host": 5, "count": 3}, {"op": "net_ping", "host": "1.1.1.1"},
    {"op": "net_ping", "host": "1.1.1.1", "count": "3"},
])
async def test_net_ping_missing_or_wrong_typed_fields_are_bad_request(request_):
    response = await dispatch(_FakeService(), request_)
    assert response["ok"] is False and response["error"]["code"] == "bad_request"
