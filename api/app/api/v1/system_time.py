"""`GET/PUT /api/v1/system/time` + `POST /system/time/sync` — m12-contract.md B1
(sana/vaqt, haqiqiy ish privileged `netd` daemonida — `timedatectl` +
`timesyncd.conf.d/innova.conf`). `network.py` bilan BIR XIL qolip: marshrut
xaritasida YO'Q (`app/core/permissions.py`) — fail-closed, faqat `*` ruxsatli
foydalanuvchi (`require_access`).

Server vaqt zonasi = PBX vaqt zonasi: PUT tenant `timezone`ini ham shunga
o'tkazadi va dialplan'ni qayta kompilyatsiya qiladi — ish vaqti (`GotoIfTime`),
kampaniya oynalari va hisobotlar shu zonada hisoblanadi."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_netd_client, get_session, require_access
from app.db.models import Tenant, User
from app.schemas import TimeConfigIn, TimeStateOut
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.netd_client import NetdClient
from app.services.netd_errors import call_netd

router = APIRouter(tags=["system-time"])

_ERROR_STATUS = {"readonly": 409, "invalid_config": 422, "bad_request": 400, "ntp_disabled": 409,
                 "unsupported": 409, "command_failed": 502, "sync_failed": 502, "command_timeout": 504}


async def _call(client: NetdClient, op: str, **kwargs: Any) -> dict[str, Any]:
    return await call_netd(client, op, error_status=_ERROR_STATUS, **kwargs)


async def _move_pbx_timezone(session: AsyncSession, user: User, tz: str, ami: Any) -> dict[str, Any] | None:
    """Tenant zonasi o'zgargan bo'lsa — yozib, dialplan'ni qayta qo'llaydi; aks holda None."""
    tenant_id = str(user.tenant_id)
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None or tenant.timezone == tz:
        return None
    tenant.timezone = tz
    result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    return result.to_dict()


@router.get("/system/time", response_model=TimeStateOut)
async def get_system_time(
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access),
) -> dict[str, Any]:
    return await _call(client, "time_state")


@router.put("/system/time", response_model=TimeStateOut)
async def put_system_time(
    payload: TimeConfigIn, session: AsyncSession = Depends(get_session),
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access),
    ami=Depends(get_ami),
) -> dict[str, Any]:
    result = await _call(client, "time_apply", config=payload.model_dump())
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id), action="system.time.apply",
                        entity="system_time", diff=payload.model_dump())
    apply = await _move_pbx_timezone(session, user, payload.timezone, ami)
    await session.commit()
    return {**result, "apply": apply}


@router.post("/system/time/sync", response_model=TimeStateOut)
async def sync_system_time(
    session: AsyncSession = Depends(get_session),
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access),
) -> dict[str, Any]:
    result = await _call(client, "time_sync")
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id), action="system.time.sync",
                        entity="system_time", diff={"sync_server": result.get("sync_server")})
    await session.commit()
    return result
