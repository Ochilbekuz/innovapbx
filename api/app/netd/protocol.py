"""JSON amal dispetcheri — unix-soket orqali keladigan so'rovlarni
`NetdService` metodlariga yo'naltiradi (m8-network-contract.md bo'lim 1).
Protokol: bitta qatorli JSON so'rov -> bitta qatorli JSON javob.

So'rov shakli: {"op": "state"|"validate"|"apply"|"confirm"|"rollback",
                "config": {...}?, "pending_id": "..."?, "request_host": "..."?}
Javob shakli (muvaffaqiyat): {"ok": true, "result": {...}}
Javob shakli (xato):         {"ok": false, "error": {"code", "message", "fields"}}
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.netd.service import NetdError, NetdService

_OPS = frozenset({"state", "validate", "apply", "confirm", "rollback"})


class ProtocolError(ValueError):
    pass


async def dispatch(service: NetdService, request: dict[str, Any]) -> dict[str, Any]:
    op = request.get("op")
    if op not in _OPS:
        return _error("bad_request", f"Noma'lum amal: {op!r}")
    try:
        result = await _call(service, op, request)
    except NetdError as exc:
        return _error(exc.code, exc.message, exc.fields)
    except ProtocolError as exc:
        return _error("bad_request", str(exc))
    return {"ok": True, "result": result}


async def _call(service: NetdService, op: str, request: dict[str, Any]) -> Any:
    if op == "state":
        return await service.state()
    if op == "validate":
        return await service.validate(_config_of(request), request_host=request.get("request_host"))
    if op == "apply":
        return await service.apply(_config_of(request), request_host=request.get("request_host"),
                                    meta=request.get("meta"))
    if op == "confirm":
        return await service.confirm(_pending_id_of(request))
    return await service.rollback(_pending_id_of(request))


def _config_of(request: dict[str, Any]) -> Any:
    raw = request.get("config")
    if not isinstance(raw, dict):
        raise ProtocolError("`config` maydoni majburiy")
    return _to_namespace(raw)


def _to_namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(**{k: _to_namespace(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_to_namespace(v) for v in value]
    return value


def _pending_id_of(request: dict[str, Any]) -> str:
    pending_id = request.get("pending_id")
    if not isinstance(pending_id, str) or not pending_id:
        raise ProtocolError("`pending_id` maydoni majburiy")
    return pending_id


def _error(code: str, message: str, fields: list[dict] | None = None) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message, "fields": fields or []}}
