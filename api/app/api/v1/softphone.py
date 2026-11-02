"""M3a §2 — `GET /api/v1/me/softphone`: brauzer softfoni uchun O'Z raqamining SIP hisobi + WS ticket.

Har qanday kirgan foydalanuvchi, FAQAT o'z raqami (`users.extension_id`). Parol faqat egasiga
(FreePBX UCP kabi), `Cache-Control: no-store`; audit `softphone.credentials` (parol/ticketsiz).
Raqam rejimi/holati qarori — `softphone_extension()` (sof, ws-auth bilan bir xil shartlar)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.core.config import settings
from app.core.errors import ApiError
from app.db.models import Extension, User
from app.schemas_softphone import SoftphoneOut, SoftphoneSip
from app.services.audit import record_audit
from app.services.crypto import decrypt_secret
from app.services.rate_limit import SlidingWindowLimiter
from app.services.sip_identity import endpoint_id
from app.services.softphone_ticket import issue_ticket

router = APIRouter(prefix="/me", tags=["me"])

WS_PATH = "/sip-ws"
_SIP_DOMAIN = "innova"
_SIP_REALM = "asterisk"  # ps_auths view (0009) bilan bir xil
_limiter = SlidingWindowLimiter()


def softphone_extension(user: User) -> Extension:
    """404 `no_extension` / 409 `webrtc_disabled` / 409 `extension_disabled` — aks holda raqam."""
    ext = user.extension
    if ext is None:
        raise ApiError(404, "no_extension", "Sizda ichki raqam yo'q")
    if not ext.webrtc:
        raise ApiError(409, "webrtc_disabled", "Raqamda brauzer softfoni yoqilmagan")
    if not ext.enabled:
        raise ApiError(409, "extension_disabled", "Ichki raqam o'chirilgan")
    return ext


@router.get("/softphone", response_model=SoftphoneOut)
async def my_softphone(
    response: Response, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user),
) -> SoftphoneOut:
    if not _limiter.allow(str(user.id), limit=settings.softphone_rate_limit_per_min):
        raise ApiError(429, "rate_limited", "Juda ko'p so'rov — birozdan keyin qayta urining")
    ext = softphone_extension(user)
    endpoint = endpoint_id(ext.number)  # SIP domen/portdan mustaqil — fixed WSS-ichki ID (dizayn qarori)
    password = await decrypt_secret(session, ext.sip_password_enc)
    ticket, expires_at = issue_ticket(uid=str(user.id), ext_id=str(ext.id))
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="softphone.credentials", entity="extension", entity_id=str(ext.id),
                        diff={"number": ext.number})
    await session.commit()
    response.headers["Cache-Control"] = "no-store"
    return SoftphoneOut(
        number=ext.number, display_name=ext.callerid_name or ext.name, ws_path=WS_PATH,
        ticket=ticket, ticket_expires_at=expires_at,
        sip=SoftphoneSip(uri=f"sip:{endpoint}@{_SIP_DOMAIN}", auth_user=endpoint, password=password,
                         realm=_SIP_REALM),
    )


@router.get("/softphone/status", status_code=204)
async def my_softphone_status(response: Response, user: User = Depends(get_current_user)) -> Response:
    """Ochiq softfon ulanishi uchun yengil holat tekshiruvi (parol/ticket bermaydi, audit yozmaydi).
    Brauzer har 30 s so'raydi — admin webrtc'ni o'chirsa chip ≤ 60 s ichida yo'qoladi (§5.8)."""
    softphone_extension(user)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
