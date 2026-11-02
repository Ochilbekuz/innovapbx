"""`GET /live` / `POST /live/spy` — S29, m2b-contract.md §2. Mantiq
`app/services/live.py`da (sof funksiyalar + orkestratsiya); bu yerda faqat
HTTP qatlami."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_access
from app.core.errors import ApiError
from app.db.models import Extension, User
from app.schemas import LiveSpyOut, LiveSpyPayload, LiveStatusOut
from app.services.audit import record_audit
from app.services.live import active_channels, build_live_status, pick_agent_channel
from app.services.sip_identity import pjsip_interface

router = APIRouter(prefix="/live", tags=["live"])

_SPY_FLAGS = {"listen": "q", "whisper": "qw", "barge": "qB"}


@router.get("", response_model=LiveStatusOut)
async def get_live(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access), ami=Depends(get_ami),
) -> LiveStatusOut:
    tenant = user.tenant
    data = await build_live_status(
        session, ami, tenant_id=str(user.tenant_id), tenant_code=tenant.code, tenant_tz=tenant.timezone,
    )
    return LiveStatusOut(**data)


async def _originate_spy(ami, *, tenant_code: str, number: str, target_channel: str, mode: str) -> None:
    """So'rovchining O'Z ichki raqamiga (`number`) qo'ng'iroq qilinadi
    (Originate) — javob bersa `ChanSpy(<target_channel>,q[w|B])` ishga tushadi.
    `Application`/`Data` bilan Originate — alohida dialplan eksten SHART EMAS.
    `tenant_code` endi kanal nomiga qo'shilmaydi (sip_identity.endpoint_id,
    m-sip-login-plain-number) — imzo chaqiruvchilar uchun o'zgarmay qoldi."""
    try:
        await ami.ensure_connected()
        resp = await ami.action(
            "Originate", Channel=pjsip_interface(number), Application="ChanSpy",
            Data=f"{target_channel},{_SPY_FLAGS[mode]}", Async="true", CallerID="Spy <0000>",
        )
    except Exception as exc:  # noqa: BLE001
        raise ApiError(502, "ami_error", "Asterisk bilan bog'lanib bo'lmadi") from exc
    if str(resp.get("Response", "")).lower() != "success":
        raise ApiError(502, "ami_error", resp.get("Message", "Originate rad etildi"))


@router.post("/spy", response_model=LiveSpyOut)
async def spy(
    payload: LiveSpyPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> LiveSpyOut:
    if not user.extension_id:
        raise ApiError(409, "no_extension", "Sizga ichki raqam biriktirilmagan")
    extension = await session.get(Extension, user.extension_id)
    tenant_code = user.tenant.code

    channels = await active_channels(ami) or []
    target = pick_agent_channel(channels, call_id=payload.call_id, channel=payload.channel)
    if target is None:
        raise ApiError(404, "not_found", "Kanal topilmadi", field="channel")

    await _originate_spy(ami, tenant_code=tenant_code, number=extension.number, target_channel=target,
                          mode=payload.mode)

    await record_audit(
        session, tenant_id=str(user.tenant_id), user_id=str(user.id), action="live.spy", entity="call",
        entity_id=payload.call_id or payload.channel or "",
        diff={"call_id": payload.call_id, "channel": payload.channel, "mode": payload.mode},
    )
    await session.commit()
    return LiveSpyOut(status="calling")
