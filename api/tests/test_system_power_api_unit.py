"""`app/api/v1/system_power.py` — m12-contract.md B2 (qayta yuklash/o'chirish).
DB/socket/AMI'siz: soxta `NetdClient` + soxta `ami` + soxta sessiya."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1 import system_power as sp
from app.core.errors import ApiError
from app.schemas import PowerActionIn

USER = SimpleNamespace(id="u1", tenant_id="t1")
AMI = SimpleNamespace()  # `_FakeClient`/`active_channels_count` soxta, haqiqiy AMI ulanish YO'Q

NETWORK_STATE = {"hostname": "pbx1"}


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

    async def power_state(self, **kw):
        return await self._dispatch("power_state", **kw)

    async def power_execute(self, **kw):
        return await self._dispatch("power_execute", **kw)


def _ok(result):
    return {"ok": True, "result": result}


def _err(code, message="xato", fields=None):
    return {"ok": False, "error": {"code": code, "message": message, "fields": fields or []}}


@pytest.fixture(autouse=True)
def _no_real_ami(monkeypatch):
    async def fake_count(ami):
        return 3

    monkeypatch.setattr(sp, "active_channels_count", fake_count)


@pytest.mark.asyncio
async def test_get_system_power_reports_hostname_and_active_calls():
    client = _FakeClient(state=_ok(NETWORK_STATE), power_state=_ok({"readonly_reason": None}))
    result = await sp.get_system_power(client=client, user=USER, ami=AMI)
    assert result == {"hostname": "pbx1", "active_calls": 3, "readonly_reason": None}


@pytest.mark.asyncio
async def test_post_system_power_hostname_mismatch_raises_422_without_calling_power_execute():
    client = _FakeClient(state=_ok(NETWORK_STATE))
    payload = PowerActionIn(action="reboot", confirm="wrong-host")
    with pytest.raises(ApiError) as exc:
        await sp.post_system_power(payload, session=_Session(), client=client, user=USER, ami=AMI)
    assert exc.value.status_code == 422
    assert exc.value.code == "hostname_mismatch"


@pytest.mark.asyncio
async def test_post_system_power_confirmed_executes_and_records_audit():
    session = _Session()
    client = _FakeClient(state=_ok(NETWORK_STATE),
                          power_execute=_ok({"action": "reboot", "delay_s": 10.0, "scheduled": True}))
    payload = PowerActionIn(action="reboot", confirm="pbx1")
    result = await sp.post_system_power(payload, session=session, client=client, user=USER, ami=AMI)
    assert result == {"action": "reboot", "delay_s": 10.0, "scheduled": True, "active_calls": 3}
    assert session.commits == 1
    assert session.added[0].action == "update"  # "system.power.reboot" -> normalize_action -> update
    assert session.added[0].diff["active_calls"] == 3


@pytest.mark.asyncio
async def test_post_system_power_readonly_raises_409():
    client = _FakeClient(state=_ok(NETWORK_STATE), power_execute=_err("readonly", "Faqat ko'rish"))
    payload = PowerActionIn(action="poweroff", confirm="pbx1")
    with pytest.raises(ApiError) as exc:
        await sp.post_system_power(payload, session=_Session(), client=client, user=USER, ami=AMI)
    assert exc.value.status_code == 409
    assert exc.value.code == "readonly"


def test_power_action_in_rejects_action_outside_reboot_poweroff():
    with pytest.raises(ValueError):
        PowerActionIn(action="shutdown -h now", confirm="pbx1")
