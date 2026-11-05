"""Kirish (SSH/Veb portlari) — host firewall + sshd + veb konteyner porti,
privileged `netd` daemonida bajariladi (`app/netd/access.py`). `firewall.py`
bilan BIR XIL qolip: marshrut xaritasida YO'Q — fail-closed, faqat `*`
(`require_access`); FAQAT `/access/web/confirm-public` autentifikatsiyasiz —
veb konteyner YANGI portda qayta ochilgandan keyin YANGI origin'dan
tasdiqlash kerak (eski sahifadagi localStorage token yangi origin'da yo'q)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_netd_client, get_session, require_access
from app.core.errors import ApiError
from app.db.models import Tenant, User
from app.schemas import (
    AccessApplyOut,
    AccessPendingActionIn,
    AccessSshApplyIn,
    AccessStateOut,
    AccessWebApplyIn,
    AccessWebConfirmPublicOut,
)
from app.services.audit import record_audit
from app.services.netd_client import NetdClient
from app.services.netd_errors import call_netd
from app.services.rate_limit import SlidingWindowLimiter

router = APIRouter(tags=["access"])

_ERROR_STATUS = {
    "readonly": 409, "pending_exists": 409, "invalid_config": 422, "not_found": 404, "bad_request": 400,
    "unsupported": 422, "sshd_config_conflict": 422, "apply_failed": 502, "command_failed": 502,
    "command_timeout": 504,
}
_PUBLIC_CONFIRM_RATE_LIMIT_PER_MIN = 10
_limiter = SlidingWindowLimiter()


async def _call(client: NetdClient, op: str, **kwargs: Any) -> dict[str, Any]:
    return await call_netd(client, op, error_status=_ERROR_STATUS, **kwargs)


def _request_host(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/access/state", response_model=AccessStateOut)
async def get_access_state(
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access),
) -> dict[str, Any]:
    return await _call(client, "access_state")


@router.post("/access/ssh/apply", response_model=AccessApplyOut)
async def apply_access_ssh(
    payload: AccessSshApplyIn, session: AsyncSession = Depends(get_session),
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access),
) -> dict[str, Any]:
    result = await _call(client, "access_ssh_apply", port=payload.port, timeout_s=payload.timeout_s)
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id), action="access.ssh.apply",
                        entity="access", entity_id=result.get("pending_id"), diff={"port": payload.port})
    await session.commit()
    return result


@router.post("/access/web/apply", response_model=AccessApplyOut)
async def apply_access_web(
    payload: AccessWebApplyIn, session: AsyncSession = Depends(get_session),
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access),
) -> dict[str, Any]:
    result = await _call(client, "access_web_apply", http_port=payload.http_port, https_port=payload.https_port,
                          timeout_s=payload.timeout_s)
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id), action="access.web.apply",
                        entity="access", entity_id=result.get("pending_id"),
                        diff={"http_port": payload.http_port, "https_port": payload.https_port})
    await session.commit()
    return result


async def _finish_pending_action(
    op: str, action: str, payload: AccessPendingActionIn,
    session: AsyncSession, client: NetdClient, user: User,
) -> dict[str, Any]:
    result = await _call(client, op, pending_id=payload.pending_id)
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id), action=action,
                        entity="access", entity_id=payload.pending_id, diff={})
    await session.commit()
    return result


@router.post("/access/confirm", response_model=AccessStateOut)
async def confirm_access(
    payload: AccessPendingActionIn, session: AsyncSession = Depends(get_session),
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access),
) -> dict[str, Any]:
    return await _finish_pending_action("access_confirm", "access.confirm", payload, session, client, user)


@router.post("/access/rollback", response_model=AccessStateOut)
async def rollback_access(
    payload: AccessPendingActionIn, session: AsyncSession = Depends(get_session),
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access),
) -> dict[str, Any]:
    return await _finish_pending_action("access_rollback", "access.rollback", payload, session, client, user)


async def _default_tenant_id(session: AsyncSession) -> str | None:
    """Yagona (appliance) tenant — ochiq `confirm-public`da autentifikatsiya
    yo'q, shu sabab audit uchun `user.tenant_id` o'rniga shu bilan olinadi."""
    row = (await session.execute(select(Tenant.id).limit(1))).scalar_one_or_none()
    return str(row) if row is not None else None


@router.post("/access/web/confirm-public", response_model=AccessWebConfirmPublicOut)
async def confirm_access_web_public(
    payload: AccessPendingActionIn, request: Request, session: AsyncSession = Depends(get_session),
    client: NetdClient = Depends(get_netd_client),
) -> dict[str, Any]:
    host = _request_host(request) or "noma'lum"
    if not _limiter.allow(host, limit=_PUBLIC_CONFIRM_RATE_LIMIT_PER_MIN):
        raise ApiError(429, "rate_limited", "Juda ko'p urinish — birozdan keyin qayta urinib ko'ring")
    await _call(client, "access_confirm", pending_id=payload.pending_id, kind="web")
    tenant_id = await _default_tenant_id(session)
    if tenant_id is not None:
        await record_audit(session, tenant_id=tenant_id, user_id=None, action="access.web.confirm_public",
                            entity="access", entity_id=payload.pending_id, diff={}, ip=host)
        await session.commit()
    return {"status": "confirmed"}
