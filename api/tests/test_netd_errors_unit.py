"""`app/services/netd_errors.py` — `system_time.py`/`system_power.py`/`firewall.py`
umumiy netd-javob -> `ApiError` yordamchisi. DB/socketsiz, to'liq soxta client."""
from __future__ import annotations

from typing import Any

import pytest

from app.core.errors import ApiError
from app.services.netd_client import NetdUnavailableError
from app.services.netd_errors import DEFAULT_ERROR_STATUS, call_netd, raise_for_netd_error


class _FakeClient:
    def __init__(self, **ops: Any) -> None:
        self._ops = ops

    async def _dispatch(self, op: str, **kwargs: Any) -> Any:
        behavior = self._ops[op]
        if isinstance(behavior, Exception):
            raise behavior
        return behavior

    async def some_op(self, **kw: Any) -> Any:
        return await self._dispatch("some_op", **kw)


def test_raise_for_netd_error_maps_known_codes_to_status():
    with pytest.raises(ApiError) as exc:
        raise_for_netd_error({"code": "readonly", "message": "x"})
    assert exc.value.status_code == 409


def test_raise_for_netd_error_defaults_unknown_code_to_400():
    with pytest.raises(ApiError) as exc:
        raise_for_netd_error({"code": "something_weird"})
    assert exc.value.status_code == 400


def test_raise_for_netd_error_accepts_custom_status_map():
    with pytest.raises(ApiError) as exc:
        raise_for_netd_error({"code": "custom"}, error_status={"custom": 418})
    assert exc.value.status_code == 418


@pytest.mark.asyncio
async def test_call_netd_returns_result_on_ok_true():
    client = _FakeClient(some_op={"ok": True, "result": {"x": 1}})
    result = await call_netd(client, "some_op")
    assert result == {"x": 1}


@pytest.mark.asyncio
async def test_call_netd_treats_missing_ok_key_as_not_ok():
    # `response.get("ok", False)` — "ok" kaliti UMUMAN yo'q bo'lsa ham xato
    # sifatida ko'rilishi SHART (default `False`, mutator: `False -> True`).
    client = _FakeClient(some_op={"result": {"x": 1}})
    with pytest.raises(ApiError) as exc:
        await call_netd(client, "some_op")
    assert exc.value.code == "bad_request"


@pytest.mark.asyncio
async def test_call_netd_raises_helper_unavailable_on_503():
    client = _FakeClient(some_op=NetdUnavailableError("yo'q"))
    with pytest.raises(ApiError) as exc:
        await call_netd(client, "some_op")
    assert exc.value.status_code == 503
    assert exc.value.code == "helper_unavailable"


@pytest.mark.asyncio
async def test_call_netd_uses_custom_error_status_map():
    client = _FakeClient(some_op={"ok": False, "error": {"code": "custom", "message": "x"}})
    with pytest.raises(ApiError) as exc:
        await call_netd(client, "some_op", error_status={"custom": 418})
    assert exc.value.status_code == 418


def test_default_error_status_covers_all_known_codes():
    assert DEFAULT_ERROR_STATUS["readonly"] == 409
    assert DEFAULT_ERROR_STATUS["pending_exists"] == 409
    assert DEFAULT_ERROR_STATUS["invalid_config"] == 422
    assert DEFAULT_ERROR_STATUS["not_found"] == 404
    assert DEFAULT_ERROR_STATUS["bad_request"] == 400
