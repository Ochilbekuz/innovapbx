"""M3b §5 — Bitrix24 click-to-call: `POST /api/public/v1/crm/bitrix24/{hook_token}/call` (ONEXTERNALCALLSTART).

Bitrix tanasi form-encoded: `event`, `data[USER_ID]`, `data[PHONE_NUMBER]`, `data[CALL_ID]`, `auth[application_token]`.
Tekshiruv: `hook_token` → yoqilgan Bitrix obunasi (yo'q → 404); `application_token` `hmac.compare_digest` bilan
(yo'q/noto'g'ri → 403). USER_ID → ichki raqam (`crm_user_map`), so'ng umumiy originate (`place_originate`).
Bitrix `CALL_ID` `crm_call_links` ga originate'dan OLDIN yoziladi — yetkazuvchi ikkinchi `register` yubormaydi.
"""
from __future__ import annotations

import hmac
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session
from app.api.public import OriginateOrder, _enabled_extension, place_originate
from app.core.errors import ApiError
from app.core.lookups import get_tenant_code
from app.db.models import CrmCallLink, CrmUserMap, IntegrationSubscription
from app.services import originate
from app.services.crm_settings import read_secrets

router = APIRouter(prefix="/api/public/v1/crm", tags=["public"])
PROVIDER = "bitrix24"
START_EVENT = "ONEXTERNALCALLSTART"


@dataclass(frozen=True)
class CallStart:
    user_id: str
    phone: str
    call_id: str

    @classmethod
    def parse(cls, form: Mapping[str, str]) -> CallStart:
        start = cls(user_id=str(form.get("data[USER_ID]") or "").strip(),
                    phone=str(form.get("data[PHONE_NUMBER]") or "").strip(),
                    call_id=str(form.get("data[CALL_ID]") or "").strip())
        if not start.user_id or not start.call_id:
            raise ApiError(422, "invalid_request", "data[USER_ID] va data[CALL_ID] majburiy")
        return start


def token_matches(expected: str | None, given: str | None) -> bool:
    """Doimiy vaqtli taqqoslash; sozlanmagan token — har doim rad (bo'sh = bo'sh emas)."""
    if not expected or not given:
        return False
    return hmac.compare_digest(expected.encode(), given.encode())


def member_matches(expected: str | None, given: str | None) -> bool:
    """OAuth rejimi: `auth[member_id]` saqlangan `config.member_id` bilan ANIQ mos kelishi SHART
    (bo'sh = bo'sh emas — `token_matches` bilan BIR XIL qoida)."""
    return bool(expected) and expected == given


def hook_auth_ok(auth_mode: str | None, config: Mapping[str, object], secrets: Mapping[str, str],
                 form: Mapping[str, str]) -> bool:
    """Vebhuk rejimi (`auth_mode` yo'q/`webhook`) — O'ZGARMAGAN (`application_token` tekshiruvi).
    OAuth rejimida `member_id` MAJBURIY mos kelishi; `application_token` saqlangan bo'lsa — qo'shimcha
    HMAC tekshiruv (bo'lmasa — Bitrix bu maydonni bermasligi mumkin, member_id yetarli)."""
    if auth_mode != "oauth":
        return token_matches(secrets.get("application_token"), form.get("auth[application_token]"))
    if not member_matches(config.get("member_id"), form.get("auth[member_id]")):
        return False
    app_token = secrets.get("application_token")
    if app_token:
        return token_matches(app_token, form.get("auth[application_token]"))
    return True


async def hook_subscription(session: AsyncSession, hook_token: str) -> IntegrationSubscription:
    sub = (await session.execute(select(IntegrationSubscription).where(
        IntegrationSubscription.kind == PROVIDER,
        IntegrationSubscription.config["hook_token"].astext == hook_token,
    ))).scalar_one_or_none()
    if sub is None or not sub.enabled:
        raise ApiError(404, "not_found", "Hook topilmadi")
    return sub


async def extension_for_user(session: AsyncSession, tenant_id: str, user_id: str) -> str:
    number = (await session.execute(select(CrmUserMap.extension).where(
        CrmUserMap.tenant_id == tenant_id, CrmUserMap.provider == PROVIDER, CrmUserMap.crm_user_id == user_id,
    ).order_by(CrmUserMap.extension).limit(1))).scalar_one_or_none()
    if number is None:
        raise ApiError(422, "unknown_user", "Bitrix24 foydalanuvchisi ichki raqamga bog'lanmagan", field="USER_ID")
    return number


def phone_number(raw: str) -> str:
    try:
        return originate.validate_to(raw)
    except originate.InvalidNumber as exc:
        raise ApiError(422, "invalid_number", "PHONE_NUMBER faqat [0-9+*#], ko'pi bilan 32 belgi",
                       field="PHONE_NUMBER") from exc


def external_id(call_id: str) -> str | None:
    try:
        return originate.validate_external_id(call_id)
    except originate.InvalidExternalId:
        return None


@router.post("/bitrix24/{hook_token}/call", status_code=202)
async def bitrix_call_start(hook_token: str, request: Request, session: AsyncSession = Depends(get_session),
                            ami=Depends(get_ami)) -> JSONResponse:
    sub = await hook_subscription(session, hook_token)
    form = {k: str(v) for k, v in (await request.form()).items()}
    secrets = await read_secrets(session, sub)
    if not hook_auth_ok(str((sub.config or {}).get("auth_mode") or ""), sub.config or {}, secrets, form):
        raise ApiError(403, "forbidden", "application_token noto'g'ri")
    if form.get("event", "").upper() != START_EVENT:
        return JSONResponse(status_code=200, content={"ignored": True})
    start = CallStart.parse(form)
    tenant_id = str(sub.tenant_id)
    to = phone_number(start.phone)
    ext = await _enabled_extension(session, tenant_id, await extension_for_user(session, tenant_id, start.user_id))
    request_id = str(uuid.uuid4())
    session.add(CrmCallLink(tenant_id=tenant_id, provider=PROVIDER, linkedid=request_id,
                            external_call_id=start.call_id, origin="crm", user_id=start.user_id,
                            shown_users=[start.user_id]))
    order = OriginateOrder(tenant_id=tenant_id, tenant_code=await get_tenant_code(session, tenant_id),
                           extension=ext.number, to=to, request_id=request_id, external_id=external_id(start.call_id))
    await place_originate(session, ami, order, action="crm.originate", audit={"provider": PROVIDER})
    return JSONResponse(status_code=202, content={"request_id": request_id})
