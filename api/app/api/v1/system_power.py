"""`GET/POST /api/v1/system/power` — m12-contract.md B2 (qayta yuklash/o'chirish).
Hostname-tasdiqlash (joriy tizim hostname'i, `network`dagi `GET /network/state`
javobi bilan BIR XIL manba) va faol qo'ng'iroqlar soni shu qatlamda hisoblanadi
(netd'da AMI yo'q, `netd/power.py`dagi izohga qarang). Marshrut xaritasida
YO'Q — fail-closed, faqat `*` (`require_access`)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_netd_client, get_session, require_access
from app.core.errors import ApiError
from app.db.models import User
from app.schemas import PowerActionIn, PowerActionOut, PowerStatusOut
from app.services.audit import record_audit
from app.services.live_status import active_channels_count
from app.services.netd_client import NetdClient
from app.services.netd_errors import call_netd

router = APIRouter(tags=["system-power"])

_ERROR_STATUS = {"readonly": 409, "invalid_config": 422, "bad_request": 400}


async def _call(client: NetdClient, op: str, **kwargs: Any) -> dict[str, Any]:
    return await call_netd(client, op, error_status=_ERROR_STATUS, **kwargs)


async def _current_hostname(client: NetdClient) -> str:
    network_state = await _call(client, "state")
    return str(network_state.get("hostname") or "")


@router.get("/system/power", response_model=PowerStatusOut)
async def get_system_power(
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access), ami=Depends(get_ami),
) -> dict[str, Any]:
    hostname, power_state, active_calls = (
        await _current_hostname(client), await _call(client, "power_state"), await active_channels_count(ami),
    )
    return {"hostname": hostname, "active_calls": active_calls, "readonly_reason": power_state["readonly_reason"]}


@router.post("/system/power", response_model=PowerActionOut, status_code=202)
async def post_system_power(
    payload: PowerActionIn, session: AsyncSession = Depends(get_session),
    client: NetdClient = Depends(get_netd_client), user: User = Depends(require_access), ami=Depends(get_ami),
) -> dict[str, Any]:
    hostname = await _current_hostname(client)
    if payload.confirm != hostname:
        raise ApiError(422, "hostname_mismatch", "Hostname mos kelmadi — qo'lda aniq yozing",
                        details={"fields": [{"field": "confirm", "message": "hostname mos emas"}]})
    active_calls = await active_channels_count(ami)
    result = await _call(client, "power_execute", action=payload.action)
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action=f"system.power.{payload.action}", entity="system_power",
                        diff={"action": payload.action, "active_calls": active_calls})
    await session.commit()
    return {**result, "active_calls": active_calls}
