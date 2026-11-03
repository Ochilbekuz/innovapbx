"""M10 A2 — o'tkazib yuborilgan qo'ng'iroq bildirishnomasi qoidalari.
Faqat baza yozuvi — dialplan'ga TA'SIR QILMAYDI (shu sabab `apply_config`
chaqirilmaydi, `ring_groups.py`dagidan farqli). Yetkazish — fon vazifa
(`services/missed_call_notify.py`, `main.py` lifespan)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_access
from app.core.errors import ApiError
from app.core.ids import parse_uuid
from app.core.optimistic import check_not_stale
from app.db.models import MissedCallNotice, MissedCallRule, Queue, RingGroup, User
from app.schemas import (
    CreateMissedCallRulePayload,
    MissedCallNoticeOut,
    MissedCallRuleMutated,
    MissedCallRuleOut,
    MissedCallRuleTestResult,
    Paged,
    UpdateMissedCallRulePayload,
)
from app.services import vm_notify
from app.services.audit import record_audit
from app.services.missed_call_notify import send_notice

router = APIRouter(tags=["missed-call"])


async def _scope_label(session: AsyncSession, tenant_id: str, scope_kind: str, scope_value: str | None) -> str | None:
    if not scope_value:
        return None
    if scope_kind == "queue":
        row = await session.get(Queue, scope_value)
        return row.name if row and str(row.tenant_id) == tenant_id else None
    if scope_kind == "ring_group":
        row = await session.get(RingGroup, scope_value)
        return row.name if row and str(row.tenant_id) == tenant_id else None
    return scope_value


async def _out(session: AsyncSession, tenant_id: str, item: MissedCallRule) -> MissedCallRuleOut:
    return MissedCallRuleOut(
        id=str(item.id), name=item.name, scope_kind=item.scope_kind, scope_value=item.scope_value,
        scope_label=await _scope_label(session, tenant_id, item.scope_kind, item.scope_value),
        telegram_chat_ids=list(item.telegram_chat_ids), emails=list(item.emails),
        include_internal=item.include_internal, enabled=item.enabled, updated_at=item.updated_at,
    )


async def _get_or_404(session: AsyncSession, tenant_id: str, rule_id: str) -> MissedCallRule:
    valid_id = parse_uuid(rule_id, not_found_message="Qoida topilmadi")
    row = (await session.execute(select(MissedCallRule).where(
        MissedCallRule.tenant_id == tenant_id, MissedCallRule.id == valid_id))).scalar_one_or_none()
    if row is None:
        raise ApiError(404, "not_found", "Qoida topilmadi")
    return row


@router.get("/missed-call-rules")
async def list_missed_call_rules(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> dict:
    items = (await session.execute(select(MissedCallRule).where(MissedCallRule.tenant_id == user.tenant_id)
                                   .order_by(MissedCallRule.name))).scalars().all()
    return {"items": [await _out(session, str(user.tenant_id), r) for r in items]}


@router.post("/missed-call-rules", response_model=MissedCallRuleMutated, status_code=201)
async def create_missed_call_rule(
    payload: CreateMissedCallRulePayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> MissedCallRuleMutated:
    tenant_id = str(user.tenant_id)
    if payload.scope_kind != "any" and not payload.scope_value:
        raise ApiError(422, "scope_value_required", "Ushbu doira uchun qiymat kerak", field="scope_value")
    item = MissedCallRule(tenant_id=tenant_id, **payload.model_dump())
    session.add(item)
    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="missed_call_rule.create",
                       entity="missed_call_rule", entity_id=str(item.id), diff={"name": item.name})
    await session.commit()
    await session.refresh(item)
    return MissedCallRuleMutated(item=await _out(session, tenant_id, item))


@router.patch("/missed-call-rules/{rule_id}", response_model=MissedCallRuleMutated)
async def update_missed_call_rule(
    rule_id: str, payload: UpdateMissedCallRulePayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> MissedCallRuleMutated:
    tenant_id = str(user.tenant_id)
    item = await _get_or_404(session, tenant_id, rule_id)
    check_not_stale(item.updated_at, payload.updated_at)

    changes = payload.model_dump(exclude_unset=True, exclude={"updated_at"})
    scope_kind = changes.get("scope_kind", item.scope_kind)
    scope_value = changes.get("scope_value", item.scope_value)
    if scope_kind != "any" and not scope_value:
        raise ApiError(422, "scope_value_required", "Ushbu doira uchun qiymat kerak", field="scope_value")
    for name, value in changes.items():
        setattr(item, name, value)

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="missed_call_rule.update",
                       entity="missed_call_rule", entity_id=str(item.id), diff={"fields": sorted(changes)})
    await session.commit()
    await session.refresh(item)
    return MissedCallRuleMutated(item=await _out(session, tenant_id, item))


@router.delete("/missed-call-rules/{rule_id}", status_code=204, response_model=None)
async def delete_missed_call_rule(
    rule_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> None:
    tenant_id = str(user.tenant_id)
    item = await _get_or_404(session, tenant_id, rule_id)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="missed_call_rule.delete",
                       entity="missed_call_rule", entity_id=str(item.id))
    await session.delete(item)
    await session.commit()


@router.post("/missed-call-rules/{rule_id}/test", response_model=MissedCallRuleTestResult)
async def test_missed_call_rule(
    rule_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> MissedCallRuleTestResult:
    tenant_id = str(user.tenant_id)
    item = await _get_or_404(session, tenant_id, rule_id)
    sample = {"from": "+998901234567", "to": "100", "did": None, "extension": "100", "queue": None,
             "status": "missed", "direction": "inbound", "started_at": "2026-01-01T10:00:00Z"}
    cfg = await vm_notify.load_config(session, tenant_id)
    error = await send_notice(cfg, item, sample, "uz")
    if error:
        return MissedCallRuleTestResult(ok=False, message=error)
    return MissedCallRuleTestResult(ok=True, message="Yuborildi")


@router.get("/missed-call-notices", response_model=Paged)
async def list_missed_call_notices(
    rule_id: str | None = None, page: int = 1, page_size: int = 50,
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> Paged:
    conds = [MissedCallNotice.tenant_id == user.tenant_id]
    if rule_id:
        conds.append(MissedCallNotice.rule_id == rule_id)
    total = (await session.execute(select(func.count()).select_from(MissedCallNotice).where(*conds))).scalar_one()
    rows = (await session.execute(select(MissedCallNotice).where(*conds).order_by(MissedCallNotice.id.desc())
                                  .offset((page - 1) * page_size).limit(page_size))).scalars().all()
    rule_names = {str(r.id): r.name for r in (await session.execute(
        select(MissedCallRule).where(MissedCallRule.tenant_id == user.tenant_id))).scalars().all()}
    items = [MissedCallNoticeOut(id=n.id, rule_id=str(n.rule_id), rule_name=rule_names.get(str(n.rule_id), "-"),
                                 call_id=n.call_id, status=n.status, last_error=n.last_error, attempts=n.attempts,
                                 created_at=n.created_at, sent_at=n.sent_at) for n in rows]
    return Paged(items=items, total=total)
