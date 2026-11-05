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
from typing import Any, Callable

from app.netd.service import NetdError, NetdService

_OPS = frozenset({
    "state", "validate", "apply", "confirm", "rollback",
    # M12 B1 (sana/vaqt) / B2 (quvvat) / B3 (firewall) — tarmoqdan MUSTAQIL amallar,
    # lekin bitta soket/protokol qatlamidan o'tadi (m12-contract.md B1-B3).
    "time_state", "time_apply", "time_sync", "power_state", "power_execute",
    "firewall_state", "firewall_validate", "firewall_apply", "firewall_confirm", "firewall_rollback",
    # Kirish (SSH/Veb portlari) — m12-contract.mddan tashqari kengaytma,
    # lekin bir xil soket/protokol qatlami.
    "access_state", "access_ssh_apply", "access_web_apply", "access_confirm", "access_rollback",
    # Tarmoq diagnostikasi («Ping» tabi) — faqat o'qish, hech narsa o'zgarmaydi.
    "net_ping",
})


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
    except TimeoutError:
        return _error("command_timeout", "Server tizim buyrug'i belgilangan vaqtda javob bermadi")
    return {"ok": True, "result": result}


_DISPATCH_TABLE: dict[str, Any] = {
    "state": lambda service, request: service.state(),
    "validate": lambda service, request: service.validate(
        _config_of(request), request_host=request.get("request_host")),
    "apply": lambda service, request: service.apply(
        _config_of(request), request_host=request.get("request_host"), meta=request.get("meta")),
    "confirm": lambda service, request: service.confirm(_pending_id_of(request)),
    "rollback": lambda service, request: service.rollback(_pending_id_of(request)),
    "time_state": lambda service, request: service.time_state(),
    "time_apply": lambda service, request: service.time_apply(_config_of(request)),
    "time_sync": lambda service, request: service.time_sync(),
    "power_state": lambda service, request: service.power_state(),
    "power_execute": lambda service, request: service.power_execute(_action_of(request)),
    "firewall_state": lambda service, request: service.firewall_state(),
    "firewall_validate": lambda service, request: service.firewall_validate(
        _config_of(request), request_host=request.get("request_host")),
    "firewall_apply": lambda service, request: service.firewall_apply(
        _config_of(request), request_host=request.get("request_host")),
    "firewall_confirm": lambda service, request: service.firewall_confirm(_pending_id_of(request)),
    "firewall_rollback": lambda service, request: service.firewall_rollback(_pending_id_of(request)),
    "access_state": lambda service, request: service.access_state(),
    "access_ssh_apply": lambda service, request: service.access_ssh_apply(
        _int_field_of(request, "port"), timeout_s=request.get("timeout_s")),
    "access_web_apply": lambda service, request: service.access_web_apply(
        _int_field_of(request, "http_port"), _int_field_of(request, "https_port"),
        timeout_s=request.get("timeout_s")),
    "access_confirm": lambda service, request: service.access_confirm(
        _pending_id_of(request), kind=request.get("kind")),
    "access_rollback": lambda service, request: service.access_rollback(_pending_id_of(request)),
    "net_ping": lambda service, request: service.net_ping(
        _str_field_of(request, "host"), _int_field_of(request, "count")),
}


async def _call(service: NetdService, op: str, request: dict[str, Any]) -> Any:
    return await _DISPATCH_TABLE[op](service, request)


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


def _field_of(request: dict[str, Any], name: str, valid: Callable[[Any], bool], message: str) -> Any:
    value = request.get(name)
    if not valid(value):
        raise ProtocolError(message)
    return value


def _str_field_of(request: dict[str, Any], name: str) -> str:
    return _field_of(request, name, lambda v: isinstance(v, str) and v != "", f"`{name}` maydoni majburiy")


def _pending_id_of(request: dict[str, Any]) -> str:
    return _str_field_of(request, "pending_id")


def _int_field_of(request: dict[str, Any], name: str) -> int:
    return _field_of(request, name, lambda v: isinstance(v, int) and not isinstance(v, bool),
                     f"`{name}` maydoni butun son bo'lishi kerak")


def _action_of(request: dict[str, Any]) -> str:
    return _str_field_of(request, "action")


def _error(code: str, message: str, fields: list[dict] | None = None) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message, "fields": fields or []}}
