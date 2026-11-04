"""Firewall GUI — m12-contract.md B3 (REST qatlami, haqiqiy ish privileged
`netd` daemonida `nft -c -f`/`nft -f` + commit-confirm — `app/netd/firewall.py`).
`network.py` bilan BIR XIL qolip: marshrut xaritasida YO'Q — fail-closed,
faqat `*` (`require_access`), `record_audit` faqat yozuvchi amallarda."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_netd_client, get_session, require_access
from app.db.models import User
from app.schemas import FirewallConfigIn, FirewallPendingActionIn, FirewallStateOut, FirewallValidateOut
from app.services.audit import record_audit
from app.services.netd_client import NetdClient
from app.services.netd_errors import call_netd

router = APIRouter(tags=["firewall"])


async def _call(client: NetdClient, op: str, **kwargs: Any) -> dict[str, Any]:
    return await call_netd(client, op, **kwargs)


def _request_host(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/firewall/state", response_model=FirewallStateOut)
async def get_firewall_state(
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access),
) -> dict[str, Any]:
    return await _call(client, "firewall_state")


@router.post("/firewall/validate", response_model=FirewallValidateOut)
async def validate_firewall(
    payload: FirewallConfigIn, request: Request, client: NetdClient = Depends(get_netd_client),
    user: User = Depends(require_access),
) -> dict[str, Any]:
    return await _call(client, "firewall_validate", config=payload.model_dump(), request_host=_request_host(request))


@router.post("/firewall/apply", response_model=FirewallStateOut)
async def apply_firewall(
    payload: FirewallConfigIn, request: Request, session: AsyncSession = Depends(get_session),
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access),
) -> dict[str, Any]:
    result = await _call(client, "firewall_apply", config=payload.model_dump(), request_host=_request_host(request))
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id), action="firewall.apply",
                        entity="firewall", entity_id=(result.get("pending") or {}).get("id"),
                        diff=payload.model_dump())
    await session.commit()
    return result


async def _finish_pending_action(
    op: str, action: str, payload: FirewallPendingActionIn,
    session: AsyncSession, client: NetdClient, user: User,
) -> dict[str, Any]:
    result = await _call(client, op, pending_id=payload.pending_id)
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id), action=action,
                        entity="firewall", entity_id=payload.pending_id, diff={})
    await session.commit()
    return result


@router.post("/firewall/confirm", response_model=FirewallStateOut)
async def confirm_firewall(
    payload: FirewallPendingActionIn, session: AsyncSession = Depends(get_session),
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access),
) -> dict[str, Any]:
    return await _finish_pending_action("firewall_confirm", "firewall.confirm", payload, session, client, user)


@router.post("/firewall/rollback", response_model=FirewallStateOut)
async def rollback_firewall(
    payload: FirewallPendingActionIn, session: AsyncSession = Depends(get_session),
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access),
) -> dict[str, Any]:
    return await _finish_pending_action("firewall_rollback", "firewall.rollback", payload, session, client, user)
