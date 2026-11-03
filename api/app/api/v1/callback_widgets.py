"""M10 A1 — qayta chaqirish vidjeti (admin, `apps:edit`). Dialplan'ga ta'sir qiladi
(`<code>-dest-<target_id>` operator manzili majburan yoziladi — `services/snapshot.py`
`callback_widget_target_ids`), shu sabab `ring_groups.py` qolipi: `apply_config()`
flush+audit'dan keyin, commit, so'ng qayta o'qish."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_access
from app.core.config import settings
from app.core.errors import ApiError
from app.core.ids import parse_uuid
from app.core.optimistic import check_not_stale
from app.db.models import CallbackWidget, TimeGroup, User
from app.schemas import (
    CallbackWidgetMutated,
    CallbackWidgetOut,
    CreateCallbackWidgetPayload,
    RotateWidgetKeyResult,
    UpdateCallbackWidgetPayload,
)
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.target_resolution import resolve_target

router = APIRouter(prefix="/callback-widgets", tags=["callback-widgets"])


def _new_public_key() -> str:
    return secrets.token_urlsafe(24)  # >= 24 bayt tasodifiylik — URL'da ochiq, lekin taxmin qilib bo'lmas


def _embed_snippet(public_key: str) -> str | None:
    if not settings.public_base_url:
        return None
    return (f'<script src="{settings.public_base_url}/widget/{public_key}.js" async></script>')


async def _validate_time_group(session: AsyncSession, tenant_id: str, time_group_id: str | None) -> None:
    if time_group_id is None:
        return
    row = (await session.execute(
        select(TimeGroup).where(TimeGroup.tenant_id == tenant_id, TimeGroup.id == time_group_id)
    )).scalar_one_or_none()
    if row is None:
        raise ApiError(422, "invalid_time_group", "Noto'g'ri ish vaqti guruhi", field="time_group_id")


async def _validate_target(session: AsyncSession, tenant_id: str, target_id: str) -> None:
    if await resolve_target(session, tenant_id, target_id) is None:
        raise ApiError(422, "invalid_target", "Noto'g'ri manzil (operator)", field="target_id")


async def _time_group_name(session: AsyncSession, time_group_id: str | None) -> str | None:
    if time_group_id is None:
        return None
    row = await session.get(TimeGroup, time_group_id)
    return row.name if row else None


async def _out(session: AsyncSession, tenant_id: str, item: CallbackWidget) -> CallbackWidgetOut:
    target = await resolve_target(session, tenant_id, str(item.target_id))
    return CallbackWidgetOut(
        id=str(item.id), name=item.name, public_key=item.public_key, target=target,
        allowed_origins=list(item.allowed_origins), time_group_id=str(item.time_group_id)
        if item.time_group_id else None, time_group_name=await _time_group_name(session, item.time_group_id),
        offhours_mode=item.offhours_mode, max_attempts=item.max_attempts, retry_interval_s=item.retry_interval_s,
        callerid_prefix=item.callerid_prefix, allow_international=item.allow_international,
        appearance=item.appearance, enabled=item.enabled, embed_snippet=_embed_snippet(item.public_key),
        updated_at=item.updated_at,
    )


async def _get_or_404(session: AsyncSession, tenant_id: str, widget_id: str) -> CallbackWidget:
    valid_id = parse_uuid(widget_id, not_found_message="Vidjet topilmadi")
    row = (await session.execute(select(CallbackWidget).where(
        CallbackWidget.tenant_id == tenant_id, CallbackWidget.id == valid_id))).scalar_one_or_none()
    if row is None:
        raise ApiError(404, "not_found", "Vidjet topilmadi")
    return row


@router.get("")
async def list_callback_widgets(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> dict:
    items = (await session.execute(select(CallbackWidget).where(CallbackWidget.tenant_id == user.tenant_id)
                                   .order_by(CallbackWidget.name))).scalars().all()
    return {"items": [await _out(session, str(user.tenant_id), w) for w in items]}


@router.post("", response_model=CallbackWidgetMutated, status_code=201)
async def create_callback_widget(
    payload: CreateCallbackWidgetPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> CallbackWidgetMutated:
    tenant_id = str(user.tenant_id)
    await _validate_target(session, tenant_id, payload.target_id)
    await _validate_time_group(session, tenant_id, payload.time_group_id)

    item = CallbackWidget(tenant_id=tenant_id, public_key=_new_public_key(), **payload.model_dump())
    session.add(item)
    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="callback_widget.create",
                       entity="callback_widget", entity_id=str(item.id), diff={"name": item.name})
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    item = await _get_or_404(session, tenant_id, str(item.id))
    return CallbackWidgetMutated(item=await _out(session, tenant_id, item), apply=apply_result.to_dict())


async def _apply_widget_fields(
    session: AsyncSession, tenant_id: str, item: CallbackWidget, payload: UpdateCallbackWidgetPayload, diff: dict,
) -> None:
    if payload.target_id is not None:
        await _validate_target(session, tenant_id, payload.target_id)
        item.target_id, diff["target_id"] = payload.target_id, payload.target_id
    if "time_group_id" in payload.model_fields_set:
        await _validate_time_group(session, tenant_id, payload.time_group_id)
        item.time_group_id, diff["time_group_id"] = payload.time_group_id, payload.time_group_id
    for name in ("name", "allowed_origins", "offhours_mode", "max_attempts", "retry_interval_s",
                 "callerid_prefix", "allow_international", "appearance", "enabled"):
        value = getattr(payload, name)
        if value is not None:
            setattr(item, name, value)
            diff[name] = value


@router.patch("/{widget_id}", response_model=CallbackWidgetMutated)
async def update_callback_widget(
    widget_id: str, payload: UpdateCallbackWidgetPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> CallbackWidgetMutated:
    tenant_id = str(user.tenant_id)
    item = await _get_or_404(session, tenant_id, widget_id)
    check_not_stale(item.updated_at, payload.updated_at)

    diff: dict = {}
    await _apply_widget_fields(session, tenant_id, item, payload, diff)

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="callback_widget.update",
                       entity="callback_widget", entity_id=str(item.id), diff={"fields": sorted(diff)})
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    item = await _get_or_404(session, tenant_id, str(item.id))
    return CallbackWidgetMutated(item=await _out(session, tenant_id, item), apply=apply_result.to_dict())


@router.post("/{widget_id}/rotate-key", response_model=RotateWidgetKeyResult)
async def rotate_widget_key(
    widget_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
    ami=Depends(get_ami),
) -> RotateWidgetKeyResult:
    """Eski `public_key` bilan ulangan saytlar darhol 404 oladi — ataylab (kalit sizgan taqdirda yopish usuli)."""
    tenant_id = str(user.tenant_id)
    item = await _get_or_404(session, tenant_id, widget_id)
    item.public_key = _new_public_key()
    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="callback_widget.rotate_key",
                       entity="callback_widget", entity_id=str(item.id))
    # Dialplan'ga ta'sir qilmaydi (`public_key` faqat ommaviy API'da) — baribir
    # boshqa barcha admin router'lar BILAN BIR XIL javob shakli uchun apply chaqiriladi.
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    item = await _get_or_404(session, tenant_id, str(item.id))
    return RotateWidgetKeyResult(item=await _out(session, tenant_id, item), apply=apply_result.to_dict())


@router.delete("/{widget_id}", status_code=204, response_model=None)
async def delete_callback_widget(
    widget_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
    ami=Depends(get_ami),
) -> None:
    tenant_id = str(user.tenant_id)
    item = await _get_or_404(session, tenant_id, widget_id)
    await session.delete(item)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="callback_widget.delete",
                       entity="callback_widget", entity_id=str(widget_id))
    await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
