"""M-CRM §3 — CRM yo'naltirish ichki endpoint'i (dialplan `CURL()` chaqiradi,
`app/services/compiler.py::_crm_route_lines`). `internal_cidlookup.py` BILAN
BIR XIL qolip (JWT yo'q, `token` query parametri, javob doim 200/matn).

`{sub_id}` — literal shartnomadagi `?token=&num=`dan OG'ISH: `IntegrationSubscription.id`
tabiiy, oshkor bo'lmagan identifikator (`internal_day_night.py`/`internal_disa.py`
qolipi), ko'p-tenant bir xil `token` bilan chalkashmasin uchun.

Javob: `"<ext>|<ism>"` / `"|<ism>"` / BO'SH SATR (topilmadi/xato/vaqt tugadi —
dialplan hech narsa O'ZGARTIRMAYDI, fail-open)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.security import check_internal_api_token
from app.db.models import IntegrationSubscription
from app.services import crm_route
from app.services.crm_settings import read_secrets

router = APIRouter(prefix="/internal/crm-route", tags=["internal"])

_EMPTY = Response(content="", media_type="text/plain")


@router.get("/{sub_id}")
async def crm_route_lookup(
    sub_id: str, token: str, num: str = "", session: AsyncSession = Depends(get_session),
) -> Response:
    """Doim 200; xato/yo'q/o'chirilgan holatlarda BO'SH SATR (fail-open)."""
    if not check_internal_api_token(token):
        return _EMPTY
    if not num:
        return _EMPTY
    sub = await session.get(IntegrationSubscription, sub_id)
    if sub is None or sub.kind != "bitrix24" or not sub.enabled:
        return _EMPTY
    webhook_url = (await read_secrets(session, sub)).get("webhook_url", "")
    if not webhook_url:
        return _EMPTY
    result = await crm_route.route_for_number(session, sub, webhook_url, num)
    return Response(content=crm_route.format_result(result), media_type="text/plain")
