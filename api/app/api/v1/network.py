"""Tarmoq sozlamalari — m8-network-contract.md bo'lim 4 (REST qatlami,
haqiqiy ish privileged `netd` daemonida — `app/services/netd_client.py`
orqali unix-soket). `system.py` bilan BIR XIL qolip: `require_access`
(marshrut xaritasida YO'Q — fail-closed, faqat `*`/admin), `record_audit`
faqat yozuvchi amallarda (`apply`/`confirm`/`rollback`, `validate`da EMAS —
hech narsa o'zgarmaydi)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_netd_client, get_session, require_access
from app.core.errors import ApiError
from app.db.models import User
from app.schemas import (
    NetworkConfigIn,
    NetworkPendingActionIn,
    NetworkPingIn,
    NetworkPingOut,
    NetworkStateOut,
    NetworkValidateOut,
)
from app.services.audit import record_audit
from app.services.netd_client import NetdClient, NetdUnavailableError

router = APIRouter(tags=["network"])

_ERROR_STATUS = {"readonly": 503, "pending_exists": 409, "invalid_config": 422, "not_found": 404, "bad_request": 400}


def _unavailable_state() -> dict[str, Any]:
    """netd bilan umuman aloqa yo'q (soket yo'q/javob bermadi) — qattiq 503
    o'rniga `helper.available=false` qaytariladi, front shu maydonga qarab
    "yordamchi ishlamayapti" banner ko'rsatadi (m8-network-contract.md bo'lim 1)."""
    return {
        "helper": {"available": False, "version": None, "error": "netd bilan aloqa yo'q"},
        "backend": "unknown", "editable": False, "readonly_reason": "netd ishlamayapti",
        "hostname": "", "dns": {"servers": [], "search": [], "editable": False},
        "default_gateway": {"address": None, "interface": None},
        "interfaces": [], "routes": {"static": [], "live": []}, "pending": None, "last_result": None,
    }


def _raise_for_error(error: dict[str, Any]) -> None:
    code = error.get("code", "bad_request")
    fields = error.get("fields") or []
    raise ApiError(_ERROR_STATUS.get(code, 400), code, error.get("message", "Xato"),
                    details={"fields": fields} if fields else None)


async def _call(client: NetdClient, op: str, **kwargs: Any) -> dict[str, Any]:
    try:
        response = await getattr(client, op)(**kwargs)
    except NetdUnavailableError:
        if op == "state":
            return _unavailable_state()
        raise ApiError(503, "helper_unavailable", "netd bilan aloqa yo'q") from None
    if not response.get("ok", False):
        _raise_for_error(response.get("error") or {})
    return response["result"]


def _request_host(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/network/state", response_model=NetworkStateOut)
async def get_network_state(
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access),
) -> dict[str, Any]:
    return await _call(client, "state")


@router.post("/network/validate", response_model=NetworkValidateOut)
async def validate_network(
    payload: NetworkConfigIn, request: Request, client: NetdClient = Depends(get_netd_client),
    user: User = Depends(require_access),
) -> dict[str, Any]:
    return await _call(client, "validate", config=payload.model_dump(), request_host=_request_host(request))


@router.post("/network/apply", response_model=NetworkStateOut)
async def apply_network(
    payload: NetworkConfigIn, request: Request, session: AsyncSession = Depends(get_session),
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access),
) -> dict[str, Any]:
    result = await _call(client, "apply", config=payload.model_dump(), request_host=_request_host(request),
                          meta={"user_id": str(user.id)})
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id), action="network.apply",
                        entity="network", entity_id=(result.get("pending") or {}).get("id"),
                        diff={"hostname": payload.hostname, "interfaces": [i.name for i in payload.interfaces]})
    await session.commit()
    return result


async def _finish_pending_action(
    op: str, action: str, payload: NetworkPendingActionIn,
    session: AsyncSession, client: NetdClient, user: User,
) -> dict[str, Any]:
    """`confirm`/`rollback` — bir xil shakl: netd'ga chaqiruv, audit, commit."""
    result = await _call(client, op, pending_id=payload.pending_id)
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id), action=action,
                        entity="network", entity_id=payload.pending_id, diff={})
    await session.commit()
    return result


@router.post("/network/confirm", response_model=NetworkStateOut)
async def confirm_network(
    payload: NetworkPendingActionIn, session: AsyncSession = Depends(get_session),
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access),
) -> dict[str, Any]:
    return await _finish_pending_action("confirm", "network.confirm", payload, session, client, user)


@router.post("/network/rollback", response_model=NetworkStateOut)
async def rollback_network(
    payload: NetworkPendingActionIn, session: AsyncSession = Depends(get_session),
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access),
) -> dict[str, Any]:
    return await _finish_pending_action("rollback", "network.rollback", payload, session, client, user)


@router.post("/network/ping", response_model=NetworkPingOut)
async def ping_network(
    payload: NetworkPingIn, client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access),
) -> dict[str, Any]:
    """Diagnostika — hech narsa o'zgarmaydi, shu sabab `validate` kabi audit yo'q
    (locked/readonly holatda ham ishlaydi)."""
    return await _call(client, "net_ping", host=payload.host, count=payload.count)
