"""M3b §5 — `/integrations/crm/{bitrix24|amocrm}` (admin): sozlamalar, ulanish testi, foydalanuvchi xaritasi.

Sirlar (`webhook_url`, `application_token`, `token`) javobga HECH QACHON chiqmaydi, auditda `***`;
berilmasa eskisi saqlanadi. URL — format + SSRF tekshiruvi. PUT — optimistik qulf (`updated_at` → 409 `stale`).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_admin
from app.api.v1.integrations import check_webhook_url
from app.core.errors import ApiError
from app.core.optimistic import check_not_stale
from app.db.models import IntegrationSubscription, User
from app.schemas_crm import (
    CrmConfigResult,
    CrmProvider,
    CrmTestResult,
    UpdateAmoPayload,
    UpdateBitrixPayload,
    UpdateCrmUserMapPayload,
)
from app.services import crm_settings
from app.services.audit import record_audit
from app.services.crm_settings import Changes
from app.services.integrations import amocrm, bitrix24

router = APIRouter(prefix="/integrations/crm", tags=["integrations"])


async def _audit(session: AsyncSession, user: User, action: str, sub: IntegrationSubscription,
                 diff: dict[str, Any]) -> None:
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id), action=action,
                       entity="crm", entity_id=sub.kind, diff=diff)


async def _subscription(session: AsyncSession, user: User, provider: str) -> IntegrationSubscription:
    return await crm_settings.ensure_subscription(session, str(user.tenant_id), provider)


async def _save(session: AsyncSession, user: User, sub: IntegrationSubscription, changes: Changes) -> CrmConfigResult:
    await crm_settings.apply_changes(session, sub, changes)
    await session.flush()
    await _audit(session, user, f"crm.{sub.kind}.update", sub, changes.audit_diff())
    await session.commit()
    await session.refresh(sub)
    return await crm_settings.crm_view(session, sub)


# ------------------------------------------------------------ o'qish
@router.get("/{provider}", response_model=CrmConfigResult)
async def get_crm(provider: CrmProvider, session: AsyncSession = Depends(get_session),
                  user: User = Depends(require_admin)) -> CrmConfigResult:
    sub = await _subscription(session, user, provider)
    await session.commit()  # birinchi o'qishda yaratilgan qator saqlansin (hook_token barqaror)
    return await crm_settings.crm_view(session, sub)


# ------------------------------------------------------------ yozish
async def bitrix_changes(payload: UpdateBitrixPayload) -> Changes:
    secrets: dict[str, str] = {}
    if payload.webhook_url and payload.webhook_url.strip():
        try:
            url = bitrix24.normalize_webhook_url(payload.webhook_url)
        except bitrix24.InvalidWebhookUrl as exc:
            raise ApiError(422, "bad_webhook_url", "Webhook URL formati: https://<portal>/rest/<id>/<kod>/",
                           field="webhook_url") from exc
        secrets["webhook_url"] = await check_webhook_url(url, field="webhook_url")
    if payload.application_token and payload.application_token.strip():
        secrets["application_token"] = payload.application_token.strip()
    config = {"create_lead": payload.create_lead, "popup_max_delay_s": payload.popup_max_delay_s,
              "default_user_id": payload.default_user_id}
    return Changes(enabled=payload.enabled, config=config, secrets=secrets)


async def amo_changes(payload: UpdateAmoPayload) -> Changes:
    base_url = ""
    if payload.base_url.strip():
        try:
            base_url = amocrm.normalize_base_url(payload.base_url)
        except amocrm.InvalidBaseUrl as exc:
            raise ApiError(422, "bad_base_url", "Manzil formati: https://<subdomen>.amocrm.ru",
                           field="base_url") from exc
        base_url = await check_webhook_url(base_url, field="base_url")
    secrets = {"token": payload.token.strip()} if payload.token and payload.token.strip() else {}
    config = {"base_url": base_url, "unsorted_for_unknown": payload.unsorted_for_unknown,
              "default_user_id": payload.default_user_id}
    return Changes(enabled=payload.enabled, config=config, secrets=secrets)


@router.put("/bitrix24", response_model=CrmConfigResult)
async def update_bitrix24(payload: UpdateBitrixPayload, session: AsyncSession = Depends(get_session),
                          user: User = Depends(require_admin)) -> CrmConfigResult:
    sub = await _subscription(session, user, "bitrix24")
    check_not_stale(sub.updated_at, payload.updated_at)
    return await _save(session, user, sub, await bitrix_changes(payload))


@router.put("/amocrm", response_model=CrmConfigResult)
async def update_amocrm(payload: UpdateAmoPayload, session: AsyncSession = Depends(get_session),
                        user: User = Depends(require_admin)) -> CrmConfigResult:
    sub = await _subscription(session, user, "amocrm")
    check_not_stale(sub.updated_at, payload.updated_at)
    return await _save(session, user, sub, await amo_changes(payload))


# ------------------------------------------------------------ test va xarita
@router.post("/{provider}/test", response_model=CrmTestResult)
async def test_crm(provider: CrmProvider, session: AsyncSession = Depends(get_session),
                   user: User = Depends(require_admin)) -> CrmTestResult:
    sub = await _subscription(session, user, provider)
    result = await crm_settings.test_connection(session, sub)
    await _audit(session, user, f"crm.{provider}.test", sub, {"ok": result.ok, "users_loaded": result.users_loaded})
    await session.commit()
    return result


@router.put("/{provider}/user-map")
async def update_user_map(provider: CrmProvider, payload: UpdateCrmUserMapPayload,
                          session: AsyncSession = Depends(get_session), user: User = Depends(require_admin)) -> dict:
    tenant_id = str(user.tenant_id)
    sub = await _subscription(session, user, provider)
    await crm_settings.update_user_map(session, tenant_id, provider, payload.entries)
    await _audit(session, user, f"crm.{provider}.user_map", sub,
                 {"entries": [e.model_dump() for e in payload.entries]})
    await session.commit()
    entries, _ = await crm_settings.user_map(session, tenant_id, provider)
    return {"items": entries}
