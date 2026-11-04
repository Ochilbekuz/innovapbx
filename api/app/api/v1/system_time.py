"""`GET/PUT /api/v1/system/time` — m12-contract.md B1 (sana/vaqt, haqiqiy ish
privileged `netd` daemonida — `timedatectl` + `timesyncd.conf.d/innova.conf`).
`network.py` bilan BIR XIL qolip: marshrut xaritasida YO'Q (`app/core/permissions.py`)
— fail-closed, faqat `*` ruxsatli foydalanuvchi (`require_access`)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_netd_client, get_session, require_access
from app.db.models import User
from app.schemas import TimeConfigIn, TimeStateOut
from app.services.audit import record_audit
from app.services.netd_client import NetdClient
from app.services.netd_errors import call_netd

router = APIRouter(tags=["system-time"])

_ERROR_STATUS = {"readonly": 409, "invalid_config": 422, "bad_request": 400}


async def _call(client: NetdClient, op: str, **kwargs: Any) -> dict[str, Any]:
    return await call_netd(client, op, error_status=_ERROR_STATUS, **kwargs)


@router.get("/system/time", response_model=TimeStateOut)
async def get_system_time(
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access),
) -> dict[str, Any]:
    return await _call(client, "time_state")


@router.put("/system/time", response_model=TimeStateOut)
async def put_system_time(
    payload: TimeConfigIn, session: AsyncSession = Depends(get_session),
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access),
) -> dict[str, Any]:
    result = await _call(client, "time_apply", config=payload.model_dump())
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id), action="system.time.apply",
                        entity="system_time", diff=payload.model_dump())
    await session.commit()
    return result
