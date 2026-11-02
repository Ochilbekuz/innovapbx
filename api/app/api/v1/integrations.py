"""M3b §3/§4 — `/integrations/webhooks`, `/integrations/deliveries`, `/integrations/api-keys` (admin).

Sirlar: webhook secret — `crypto.encrypt_secret` (bir marta qaytariladi, `rotate-secret` — yangisi);
API kalit — faqat sha256 + prefix (`app/services/api_keys.py`). URL — SSRF tekshiruvi (422 `url_forbidden`).
"""
from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_access
from app.core.errors import ApiError
from app.core.lookups import get_tenant_scoped_or_404
from app.core.optimistic import check_not_stale
from app.db.models import ApiKey, IntegrationDelivery, IntegrationEvent, IntegrationSubscription, User
from app.schemas_integrations import (
    ApiKeyCreated,
    ApiKeyOut,
    CreateApiKeyPayload,
    CreateWebhookPayload,
    DeliveryOut,
    UpdateWebhookPayload,
    WebhookCreated,
    WebhookMutated,
    WebhookOut,
    WebhookSecret,
    WebhookTestResult,
)
from app.services import api_keys
from app.services.audit import record_audit
from app.services.crypto import encrypt_secret
from app.services.integrations import outbox, ssrf

router = APIRouter(prefix="/integrations", tags=["integrations"])
DELIVERY_LIMIT = 200


# ------------------------------------------------------------ yordamchilar
def webhook_out(sub: IntegrationSubscription) -> WebhookOut:
    return WebhookOut(
        id=str(sub.id), name=sub.name, url=str((sub.config or {}).get("url") or ""), events=list(sub.events or []),
        include_internal=sub.include_internal, enabled=sub.enabled, has_secret=bool(sub.secret_enc),
        disabled_reason=sub.disabled_reason, failing_since=sub.failing_since, last_success_at=sub.last_success_at,
        created_at=sub.created_at, updated_at=sub.updated_at,
    )


def delivery_out(row: IntegrationDelivery, event_type: str) -> DeliveryOut:
    pending = row.status == "pending"
    return DeliveryOut(
        id=str(row.id), event_id=str(row.event_id), event_type=event_type, call_id=row.call_id, status=row.status,
        attempts=row.attempts, next_attempt_at=row.next_attempt_at if pending else None,
        last_attempt_at=row.last_attempt_at, last_status_code=row.last_status_code, last_error=row.last_error,
        response_body=row.response_body, delivered_at=row.delivered_at, created_at=row.created_at,
        http_status=row.last_status_code, next_retry_at=row.next_attempt_at if pending else None,
    )


def api_key_out(row: ApiKey) -> ApiKeyOut:
    return ApiKeyOut(id=str(row.id), name=row.name, prefix=row.prefix, scopes=list(row.scopes or []),
                     expires_at=row.expires_at, revoked_at=row.revoked_at, last_used_at=row.last_used_at,
                     created_at=row.created_at)


async def check_webhook_url(url: str, field: str = "url") -> str:
    """DNS so'rovi bloklovchi — alohida oqimda. Taqiqlangan → 422 `url_forbidden` (`field` — forma maydoni)."""
    url = url.strip()
    try:
        await asyncio.to_thread(ssrf.check_url_default, url)
    except ssrf.UrlForbidden as exc:
        raise ApiError(422, "url_forbidden", f"URL ruxsat etilmagan: {exc.reason}", field=field) from exc
    return url


def new_webhook_secret() -> str:
    return f"whsec_{secrets.token_urlsafe(32)}"


async def _get_webhook(session: AsyncSession, tenant_id: str, webhook_id: str) -> IntegrationSubscription:
    sub = await get_tenant_scoped_or_404(session, IntegrationSubscription, tenant_id, webhook_id,
                                         not_found_message="Webhook topilmadi")
    if sub.kind != "webhook":
        raise ApiError(404, "not_found", "Webhook topilmadi")
    return sub


async def _audit(session: AsyncSession, user: User, action: str, entity: str, entity_id: str,
                 diff: dict | None = None) -> None:
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id), action=action,
                       entity=entity, entity_id=entity_id, diff=diff)


# ------------------------------------------------------------ webhook'lar
@router.get("/webhooks")
async def list_webhooks(session: AsyncSession = Depends(get_session), user: User = Depends(require_access)) -> dict:
    rows = (await session.execute(select(IntegrationSubscription).where(
        IntegrationSubscription.tenant_id == str(user.tenant_id), IntegrationSubscription.kind == "webhook",
    ).order_by(IntegrationSubscription.created_at))).scalars().all()
    return {"items": [webhook_out(r) for r in rows]}


@router.post("/webhooks", response_model=WebhookCreated, status_code=201)
async def create_webhook(payload: CreateWebhookPayload, session: AsyncSession = Depends(get_session),
                         user: User = Depends(require_access)) -> WebhookCreated:
    url = await check_webhook_url(payload.url)
    secret = new_webhook_secret()
    sub = IntegrationSubscription(
        tenant_id=str(user.tenant_id), kind="webhook", name=payload.name, config={"url": url},
        secret_enc=await encrypt_secret(session, secret), events=sorted(set(payload.events)),
        include_internal=payload.include_internal, enabled=payload.enabled,
    )
    session.add(sub)
    await session.flush()
    await _audit(session, user, "webhook.create", "webhook", str(sub.id),
                 {"name": sub.name, "url": url, "events": sub.events})
    await session.commit()
    await session.refresh(sub)
    return WebhookCreated(item=webhook_out(sub), secret=secret)


async def _webhook_changes(sub: IntegrationSubscription, payload: UpdateWebhookPayload) -> dict:
    fields = payload.model_fields_set - {"updated_at"}
    changes = {f: getattr(payload, f) for f in fields if getattr(payload, f) is not None}
    if "url" in changes:
        changes["url"] = await check_webhook_url(changes["url"])
    if "events" in changes:
        changes["events"] = sorted(set(changes["events"]))
    return changes


def _apply_webhook_changes(sub: IntegrationSubscription, changes: dict) -> None:
    for field in ("name", "events", "include_internal", "enabled"):
        if field in changes:
            setattr(sub, field, changes[field])
    if "url" in changes:
        sub.config = {**(sub.config or {}), "url": changes["url"]}
    if changes.get("enabled"):  # qayta yoqish — avto-o'chirish sababi va xato hisobi tozalanadi
        sub.disabled_reason, sub.failing_since = None, None


@router.patch("/webhooks/{webhook_id}", response_model=WebhookMutated)
async def update_webhook(webhook_id: str, payload: UpdateWebhookPayload, session: AsyncSession = Depends(get_session),
                         user: User = Depends(require_access)) -> WebhookMutated:
    sub = await _get_webhook(session, str(user.tenant_id), webhook_id)
    check_not_stale(sub.updated_at, payload.updated_at)
    changes = await _webhook_changes(sub, payload)
    _apply_webhook_changes(sub, changes)
    await session.flush()
    await _audit(session, user, "webhook.update", "webhook", str(sub.id), changes)
    await session.commit()
    await session.refresh(sub)
    return WebhookMutated(item=webhook_out(sub))


@router.delete("/webhooks/{webhook_id}", status_code=204, response_model=None)
async def delete_webhook(webhook_id: str, session: AsyncSession = Depends(get_session),
                         user: User = Depends(require_access)) -> Response:
    sub = await _get_webhook(session, str(user.tenant_id), webhook_id)
    await _audit(session, user, "webhook.delete", "webhook", str(sub.id), {"name": sub.name})
    await session.delete(sub)
    await session.commit()
    return Response(status_code=204)


@router.post("/webhooks/{webhook_id}/rotate-secret", response_model=WebhookSecret)
async def rotate_webhook_secret(webhook_id: str, session: AsyncSession = Depends(get_session),
                                user: User = Depends(require_access)) -> WebhookSecret:
    sub = await _get_webhook(session, str(user.tenant_id), webhook_id)
    secret = new_webhook_secret()
    sub.secret_enc = await encrypt_secret(session, secret)
    await _audit(session, user, "webhook.rotate_secret", "webhook", str(sub.id))
    await session.commit()
    return WebhookSecret(secret=secret)


@router.post("/webhooks/{webhook_id}/test", response_model=WebhookTestResult)
async def test_webhook(webhook_id: str, session: AsyncSession = Depends(get_session),
                       user: User = Depends(require_access)) -> WebhookTestResult:
    sub = await _get_webhook(session, str(user.tenant_id), webhook_id)
    event = await outbox.enqueue_test_ping(session, sub)
    delivery_id = (await session.execute(select(IntegrationDelivery.id).where(
        IntegrationDelivery.event_id == event.id, IntegrationDelivery.subscription_id == sub.id))).scalar()
    await session.commit()
    return WebhookTestResult(queued=delivery_id is not None, delivery_id=str(delivery_id) if delivery_id else None)


@router.get("/webhooks/{webhook_id}/deliveries")
async def list_deliveries(
    webhook_id: str, status: str | None = None, limit: int = Query(default=50, ge=1, le=DELIVERY_LIMIT),
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> dict:
    sub = await _get_webhook(session, str(user.tenant_id), webhook_id)
    stmt = (select(IntegrationDelivery, IntegrationEvent.type)
            .join(IntegrationEvent, IntegrationEvent.id == IntegrationDelivery.event_id)
            .where(IntegrationDelivery.subscription_id == sub.id))
    if status:
        stmt = stmt.where(IntegrationDelivery.status == status)
    rows = (await session.execute(stmt.order_by(IntegrationDelivery.seq.desc()).limit(limit))).all()
    return {"items": [delivery_out(row, event_type) for row, event_type in rows]}


@router.post("/deliveries/{delivery_id}/replay", response_model=DeliveryOut)
async def replay_delivery(delivery_id: str, session: AsyncSession = Depends(get_session),
                          user: User = Depends(require_access)) -> DeliveryOut:
    row = await get_tenant_scoped_or_404(session, IntegrationDelivery, str(user.tenant_id), delivery_id,
                                         not_found_message="Yetkazish topilmadi")
    outbox.reset_for_replay(row, datetime.now(timezone.utc))
    await _audit(session, user, "integration.replay", "integration_delivery", str(row.id))
    event = await session.get(IntegrationEvent, row.event_id)
    await session.commit()
    await session.refresh(row)
    return delivery_out(row, event.type)


# ------------------------------------------------------------ API kalitlar
@router.get("/api-keys")
async def list_api_keys(session: AsyncSession = Depends(get_session), user: User = Depends(require_access)) -> dict:
    rows = (await session.execute(select(ApiKey).where(ApiKey.tenant_id == str(user.tenant_id))
                                  .order_by(ApiKey.created_at.desc()))).scalars().all()
    return {"items": [api_key_out(r) for r in rows]}


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=201)
async def create_api_key(payload: CreateApiKeyPayload, session: AsyncSession = Depends(get_session),
                         user: User = Depends(require_access)) -> ApiKeyCreated:
    try:
        scopes = api_keys.validate_scopes(list(payload.scopes))
    except ValueError as exc:
        raise ApiError(422, "bad_scope", str(exc), field="scopes") from exc
    if payload.expires_at is not None and payload.expires_at <= datetime.now(timezone.utc):
        raise ApiError(422, "bad_value", "Muddat o'tmishda", field="expires_at")
    new = api_keys.generate_key()
    row = ApiKey(tenant_id=str(user.tenant_id), name=payload.name, prefix=new.prefix, key_hash=new.key_hash,
                 scopes=scopes, expires_at=payload.expires_at, created_by=str(user.id))
    session.add(row)
    await session.flush()
    await _audit(session, user, "api_key.create", "api_key", str(row.id),
                 {"name": row.name, "prefix": row.prefix, "scopes": scopes})
    await session.commit()
    await session.refresh(row)
    return ApiKeyCreated(item=api_key_out(row), key=new.plaintext)


@router.delete("/api-keys/{key_id}", status_code=204, response_model=None)
async def revoke_api_key(key_id: str, session: AsyncSession = Depends(get_session),
                         user: User = Depends(require_access)) -> Response:
    row = await get_tenant_scoped_or_404(session, ApiKey, str(user.tenant_id), key_id,
                                         not_found_message="API kalit topilmadi")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        await _audit(session, user, "api_key.revoke", "api_key", str(row.id), {"prefix": row.prefix})
    await session.commit()
    return Response(status_code=204)
