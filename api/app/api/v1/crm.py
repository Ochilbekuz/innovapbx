"""M3b §5 — `/integrations/crm/{bitrix24|amocrm}` (admin): sozlamalar, ulanish testi, foydalanuvchi xaritasi.

Sirlar (`webhook_url`, `application_token`, `token`) javobga HECH QACHON chiqmaydi, auditda `***`;
berilmasa eskisi saqlanadi. URL — format + SSRF tekshiruvi. PUT — optimistik qulf (`updated_at` → 409 `stale`).
"""
from __future__ import annotations

import contextlib
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_access
from app.api.v1.integrations import check_webhook_url
from app.api.v1.settings import get_settings_row
from app.core.errors import ApiError
from app.core.optimistic import check_not_stale
from app.db.models import IntegrationSubscription, User
from app.schemas_crm import (
    BitrixConnectIn,
    BitrixConnectOut,
    BitrixConnectPollOut,
    BitrixDisconnectOut,
    BitrixLicenseOut,
    BitrixSetupOut,
    BitrixSetupResultOut,
    CrmConfigResult,
    CrmProvider,
    CrmTestResult,
    CrmUserItem,
    CrmUsersOut,
    UpdateAmoPayload,
    UpdateBitrixPayload,
    UpdateCrmUserMapPayload,
)
from app.services import bitrix_oauth_flow, crm_settings
from app.services.apply import AmiLike, apply_config
from app.services.audit import record_audit
from app.services.crm_settings import Changes
from app.services.integrations import amocrm, bitrix24, bitrix_broker

router = APIRouter(prefix="/integrations/crm", tags=["integrations"])

# M-CRM §4: shu maydonlar o'zgarsa — kompilyatsiya qilingan dialplan ESKIRADI
# (`_crm_route_lines` ulardan foydalanadi), shu sabab `apply_config` chaqiriladi.
_DIALPLAN_FIELDS = ("route_to_responsible", "set_caller_name", "responsible_ring_s")


async def _audit(session: AsyncSession, user: User, action: str, sub: IntegrationSubscription,
                 diff: dict[str, Any]) -> None:
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id), action=action,
                       entity="crm", entity_id=sub.kind, diff=diff)


async def _subscription(session: AsyncSession, user: User, provider: str) -> IntegrationSubscription:
    return await crm_settings.ensure_subscription(session, str(user.tenant_id), provider)


async def _save(session: AsyncSession, user: User, sub: IntegrationSubscription, changes: Changes,
                ami: AmiLike | None = None) -> CrmConfigResult:
    before_enabled, before_cfg = sub.enabled, dict(sub.config or {})
    await crm_settings.apply_changes(session, sub, changes)
    await session.flush()
    await _audit(session, user, f"crm.{sub.kind}.update", sub, changes.audit_diff())
    newly_enabled = sub.enabled and not before_enabled
    if sub.kind == "bitrix24" and (changes.secrets.get("webhook_url") or newly_enabled):
        # 1 (darhol qayta sinxron): muvaffaqiyatsizlik SAQLASHNI SINDIRMASIN.
        with contextlib.suppress(Exception):
            await crm_settings.test_connection(session, sub)
    if sub.kind == "bitrix24" and ami is not None and (
        before_enabled != sub.enabled or any(sub.config.get(k) != before_cfg.get(k) for k in _DIALPLAN_FIELDS)):
        await apply_config(session, tenant_id=str(user.tenant_id), user_id=str(user.id), ami=ami)
    await session.commit()
    await session.refresh(sub)
    return await crm_settings.crm_view(session, sub)


# ------------------------------------------------------------ o'qish
@router.get("/{provider}", response_model=CrmConfigResult)
async def get_crm(provider: CrmProvider, session: AsyncSession = Depends(get_session),
                  user: User = Depends(require_access)) -> CrmConfigResult:
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
              "default_user_id": payload.default_user_id,
              "route_to_responsible": payload.route_to_responsible,
              "responsible_ring_s": payload.responsible_ring_s, "set_caller_name": payload.set_caller_name,
              "upload_records": payload.upload_records, "auto_sync_users": payload.auto_sync_users}
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
                          user: User = Depends(require_access), ami: AmiLike = Depends(get_ami)) -> CrmConfigResult:
    sub = await _subscription(session, user, "bitrix24")
    check_not_stale(sub.updated_at, payload.updated_at)
    return await _save(session, user, sub, await bitrix_changes(payload), ami)


@router.put("/amocrm", response_model=CrmConfigResult)
async def update_amocrm(payload: UpdateAmoPayload, session: AsyncSession = Depends(get_session),
                        user: User = Depends(require_access)) -> CrmConfigResult:
    sub = await _subscription(session, user, "amocrm")
    check_not_stale(sub.updated_at, payload.updated_at)
    return await _save(session, user, sub, await amo_changes(payload))


# ------------------------------------------------------------ Bitrix OAuth (bitrix-oauth-shartnoma.md §2)
# ESKARTIRISH (shartnoma hujjati `/api/v1/crm/bitrix24/...` deb yozadi — bu REAL mavjud routerning
# haqiqiy yo'li `/api/v1/integrations/crm/bitrix24/...` (web frontend ham shu yo'ldan foydalanadi);
# shartnomadagi yo'l — hujjat qisqartmasi, haqiqiy (mavjud) router shu yerda kengaytiriladi.
def _setup_out(result: bitrix_oauth_flow.SetupResult) -> BitrixSetupOut:
    return BitrixSetupOut(lines=result.lines, default_line=result.default_line, event_bound=result.event_bound,
                          users_synced=result.users_synced, warnings=result.warnings)


async def _public_base_url(session: AsyncSession, tenant_id: str) -> str | None:
    row = await get_settings_row(session, tenant_id)
    return str((row.integrations or {}).get("public_base_url") or "") or None


@router.post("/bitrix24/connect", response_model=BitrixConnectOut)
async def bitrix_connect(payload: BitrixConnectIn, session: AsyncSession = Depends(get_session),
                         user: User = Depends(require_access)) -> BitrixConnectOut:
    sub = await _subscription(session, user, "bitrix24")
    try:
        authorize_url = await bitrix_oauth_flow.connect(session, sub, payload.domain, user_id=str(user.id))
    except bitrix_broker.BrokerError as exc:
        status, code, message = bitrix_oauth_flow.connect_error_detail(exc)
        raise ApiError(status, code, message) from exc
    await session.commit()
    return BitrixConnectOut(authorize_url=authorize_url)


@router.post("/bitrix24/connect/poll", response_model=BitrixConnectPollOut)
async def bitrix_connect_poll(session: AsyncSession = Depends(get_session),
                              user: User = Depends(require_access)) -> BitrixConnectPollOut:
    sub = await _subscription(session, user, "bitrix24")
    public_base_url = await _public_base_url(session, str(user.tenant_id))
    result = await bitrix_oauth_flow.poll(session, sub, user_id=str(user.id), public_base_url=public_base_url)
    await session.commit()
    return BitrixConnectPollOut(status=result.status, code=result.code, message=result.message,
                                setup=_setup_out(result.setup) if result.setup else None)


@router.post("/bitrix24/setup", response_model=BitrixSetupResultOut)
async def bitrix_setup(session: AsyncSession = Depends(get_session),
                       user: User = Depends(require_access)) -> BitrixSetupResultOut:
    sub = await _subscription(session, user, "bitrix24")
    public_base_url = await _public_base_url(session, str(user.tenant_id))
    try:
        result = await bitrix_oauth_flow.run_setup(session, sub, user_id=str(user.id),
                                                   public_base_url=public_base_url)
    except crm_settings.CrmCallError as exc:
        raise ApiError(409, "setup_failed", exc.result.error or "Sozlash muvaffaqiyatsiz") from exc
    await session.commit()
    return BitrixSetupResultOut(setup=_setup_out(result))


@router.post("/bitrix24/disconnect", response_model=BitrixDisconnectOut)
async def bitrix_disconnect(session: AsyncSession = Depends(get_session),
                            user: User = Depends(require_access)) -> BitrixDisconnectOut:
    sub = await _subscription(session, user, "bitrix24")
    public_base_url = await _public_base_url(session, str(user.tenant_id))
    await bitrix_oauth_flow.disconnect(session, sub, user_id=str(user.id), public_base_url=public_base_url)
    await session.commit()
    return BitrixDisconnectOut(ok=True)


@router.get("/bitrix24/license", response_model=BitrixLicenseOut)
async def bitrix_license(session: AsyncSession = Depends(get_session),
                         user: User = Depends(require_access)) -> BitrixLicenseOut:
    sub = await _subscription(session, user, "bitrix24")
    info = await bitrix_oauth_flow.license_info(session, sub)
    await session.commit()  # birinchi o'qishda yaratilgan qator saqlansin (get_crm bilan BIR XIL qolip)
    return BitrixLicenseOut(**info)


# ------------------------------------------------------------ test va xarita
@router.post("/{provider}/test", response_model=CrmTestResult)
async def test_crm(provider: CrmProvider, session: AsyncSession = Depends(get_session),
                   user: User = Depends(require_access)) -> CrmTestResult:
    sub = await _subscription(session, user, provider)
    result = await crm_settings.test_connection(session, sub)
    await _audit(session, user, f"crm.{provider}.test", sub, {"ok": result.ok, "users_loaded": result.users_loaded})
    await session.commit()
    return result


@router.post("/{provider}/sync", response_model=CrmTestResult)
async def sync_crm(provider: CrmProvider, session: AsyncSession = Depends(get_session),
                   user: User = Depends(require_access)) -> CrmTestResult:
    """1f: `/test` bilan BIR XIL yadro (`crm_settings.test_connection`) — alohida sinxron tugmasi uchun."""
    sub = await _subscription(session, user, provider)
    result = await crm_settings.test_connection(session, sub)
    await _audit(session, user, f"crm.{provider}.sync", sub, {"ok": result.ok, "users_loaded": result.users_loaded})
    await session.commit()
    return result


@router.get("/{provider}/users", response_model=CrmUsersOut)
async def crm_users(provider: CrmProvider, session: AsyncSession = Depends(get_session),
                    user: User = Depends(require_access)) -> CrmUsersOut:
    users = await crm_settings.crm_users_from_store(session, str(user.tenant_id), provider)
    return CrmUsersOut(items=[CrmUserItem(id=u.id, name=u.name, inner_phone=u.inner_phone) for u in users])


@router.put("/{provider}/user-map")
async def update_user_map(provider: CrmProvider, payload: UpdateCrmUserMapPayload,
                          session: AsyncSession = Depends(get_session), user: User = Depends(require_access)) -> dict:
    tenant_id = str(user.tenant_id)
    sub = await _subscription(session, user, provider)
    await crm_settings.update_user_map(session, tenant_id, provider, payload.entries)
    await _audit(session, user, f"crm.{provider}.user_map", sub,
                 {"entries": [e.model_dump() for e in payload.entries]})
    await session.commit()
    entries, _ = await crm_settings.user_map(session, tenant_id, provider)
    return {"items": entries}
