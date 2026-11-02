"""M3a §0/§2 — `GET /internal/softphone/ws-auth`: nginx `auth_request` (`/sip-ws` WS ochilishidan
OLDIN). Ticket `X-Original-URI` sarlavhasidagi `t` dan olinadi (so'rov yo'lida/logda ko'rinmaydi).
204 — ruxsat; 401 — ticketsiz/eskirgan/imzo noto'g'ri/foydalanuvchi faolsiz/raqam endi o'ziniki
emas, webrtc emas yoki o'chirilgan. Tana yo'q. nginx tashqaridan `/internal/`ni 404 qiladi."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.api.v1.softphone import softphone_extension
from app.core.errors import ApiError
from app.db.models import User
from app.services.softphone_ticket import TicketClaims, ticket_from_uri, verify_ticket

router = APIRouter(prefix="/internal/softphone", tags=["internal"])


def ws_allowed(user: User | None, claims: TicketClaims) -> bool:
    """`/me/softphone` bilan BIR XIL shartlar (`softphone_extension`) + ticket aynan shu raqamga."""
    if user is None or not user.is_active:
        return False
    try:
        ext = softphone_extension(user)
    except ApiError:
        return False
    return str(ext.id) == claims.ext_id


@router.get("/ws-auth", status_code=204, response_class=Response)
async def ws_auth(request: Request, session: AsyncSession = Depends(get_session)) -> Response:
    claims = verify_ticket(ticket_from_uri(request.headers.get("x-original-uri")) or "")
    user = await session.get(User, claims.uid) if claims else None
    status = 204 if claims and ws_allowed(user, claims) else 401
    return Response(status_code=status)
