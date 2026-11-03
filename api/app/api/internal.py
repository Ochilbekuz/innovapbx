"""Faqat ICHKI (Asterisk dialplan `CURL()`) chaqiradigan endpoint'lar —
`/api/v1` OSTIDA EMAS (m1b-contract.md bo'lim 2: PIN tekshiruvi). Login/JWT
talab qilinmaydi (dialplan JWT ola olmaydi) — o'rniga `token` query
parametri (`INTERNAL_API_TOKEN`, faqat API konteyneri ↔ Asterisk konteyneri
orasida, tashqariga ochilmaydi — deploy/docker-compose.yml `ports:` yo'q bu
endpoint uchun, faqat ichki tarmoq). Javob doim TEKST (`"1"`/`"0"`) —
Asterisk `CURL()` JSON parse qilmaydi."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.security import check_internal_api_token, verify_password
from app.db.models import OutboundRoute

router = APIRouter(prefix="/internal/outbound-routes", tags=["internal"])

_DENY = Response(content="0", media_type="text/plain")
_ALLOW = Response(content="1", media_type="text/plain")


@router.get("/{route_id}/pin-check")
async def pin_check(
    route_id: str, token: str, pin: str, session: AsyncSession = Depends(get_session),
) -> Response:
    """Doim 200 qaytaradi (tanasi `"0"`/`"1"`) — Asterisk `CURL()` HTTP status
    kodini emas, tana matnini o'qiydi; xato holatlarida ham rad ("0") bilan
    javob beramiz, aks holda chaqiruvchi tomon vaqt tugashi bilan osilib qoladi."""
    if not check_internal_api_token(token):
        return _DENY
    route = (await session.execute(
        select(OutboundRoute).where(OutboundRoute.id == route_id)
    )).scalar_one_or_none()
    if route is None or route.pin_hash is None:
        return _DENY
    return _ALLOW if verify_password(pin, route.pin_hash) else _DENY
