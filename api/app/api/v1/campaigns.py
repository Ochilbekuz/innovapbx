"""Kampaniyalar — avtoinformator / avtoterish (S18, m6-contract.md §2). Faqat admin, jurnal `campaign.*`.
Terish — fon `campaign_dialer`; dialplan kontekstlari statik (apply shart emas)."""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_access
from app.core.errors import ApiError
from app.core.optimistic import check_not_stale
from app.db.models import Campaign, CampaignContact, User
from app.schemas_campaigns import (
    CampaignList,
    CampaignMutated,
    CampaignOut,
    ContactList,
    ContactOut,
    ContactStatus,
    CreateCampaignPayload,
    ImportContactsPayload,
    ImportContactsResult,
    UpdateCampaignPayload,
)
from app.services import campaigns as svc
from app.services.audit import record_audit
from app.services.fpbx.apply_plan import csv_cell

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

_EXPORT_COLUMNS = ("number", "name", "status", "result", "attempts", "billsec", "key", "last_attempt_at")


async def _one_out(session: AsyncSession, item: Campaign) -> CampaignOut:
    return (await svc.campaigns_out(session, [item]))[0]


async def _audit(session: AsyncSession, user: User, action: str, item: Campaign, diff: dict | None = None) -> None:
    """`normalize_action` start/pause/stop/import ni `update` ga tushiradi — asl amal `diff.op` da saqlanadi."""
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id), action=f"campaign.{action}",
                       entity="campaign", entity_id=str(item.id), diff={"op": action, **(diff or {"name": item.name})})


async def _commit_out(session: AsyncSession, item: Campaign) -> CampaignMutated:
    await session.commit()
    await session.refresh(item)
    return CampaignMutated(item=await _one_out(session, item))


@router.get("", response_model=CampaignList)
async def list_campaigns(session: AsyncSession = Depends(get_session),
                         user: User = Depends(require_access)) -> CampaignList:
    items = (await session.execute(select(Campaign).where(Campaign.tenant_id == str(user.tenant_id))
                                   .order_by(Campaign.created_at.desc()))).scalars().all()
    return CampaignList(items=await svc.campaigns_out(session, list(items)))


@router.get("/{campaign_id}", response_model=CampaignMutated)
async def get_campaign(campaign_id: str, session: AsyncSession = Depends(get_session),
                       user: User = Depends(require_access)) -> CampaignMutated:
    item = await svc.get_campaign_or_404(session, str(user.tenant_id), campaign_id)
    return CampaignMutated(item=await _one_out(session, item))


@router.post("", response_model=CampaignMutated, status_code=201)
async def create_campaign(payload: CreateCampaignPayload, session: AsyncSession = Depends(get_session),
                          user: User = Depends(require_access)) -> CampaignMutated:
    tenant_id = str(user.tenant_id)
    fields = svc.merge_fields({}, payload.model_dump())
    await svc.validate_campaign(session, tenant_id, fields)
    item = Campaign(tenant_id=tenant_id, **fields.model_dump())
    session.add(item)
    await session.flush()
    await _audit(session, user, "create", item, {"name": item.name, "mode": item.mode})
    return await _commit_out(session, item)


@router.patch("/{campaign_id}", response_model=CampaignMutated)
async def update_campaign(campaign_id: str, payload: UpdateCampaignPayload,
                          session: AsyncSession = Depends(get_session),
                          user: User = Depends(require_access)) -> CampaignMutated:
    tenant_id = str(user.tenant_id)
    item = await svc.get_campaign_or_404(session, tenant_id, campaign_id)
    check_not_stale(item.updated_at, payload.updated_at)
    svc.require_editable(item)
    changes = payload.model_dump(exclude_unset=True, exclude={"updated_at"})
    fields = svc.merge_fields(svc.current_fields(item), changes)
    await svc.validate_campaign(session, tenant_id, fields, exclude_id=str(item.id))
    for name, value in fields.model_dump().items():
        setattr(item, name, value)
    await _audit(session, user, "update", item, {"fields": sorted(changes)})
    return await _commit_out(session, item)


@router.delete("/{campaign_id}", status_code=204, response_model=None)
async def delete_campaign(campaign_id: str, session: AsyncSession = Depends(get_session),
                          user: User = Depends(require_access)) -> None:
    item = await svc.get_campaign_or_404(session, str(user.tenant_id), campaign_id)
    svc.require_editable(item)
    await _audit(session, user, "delete", item)
    await session.delete(item)
    await session.commit()


@router.post("/{campaign_id}/{action}", response_model=CampaignMutated)
async def campaign_action(campaign_id: str, action: str, session: AsyncSession = Depends(get_session),
                          user: User = Depends(require_access)) -> CampaignMutated:
    if action not in ("start", "pause", "stop"):
        raise ApiError(404, "not_found", "Amal topilmadi")
    item = await svc.get_campaign_or_404(session, str(user.tenant_id), campaign_id)
    await svc.transition(session, item, action)
    await _audit(session, user, action, item)
    return await _commit_out(session, item)


@router.post("/{campaign_id}/contacts/import", response_model=ImportContactsResult)
async def import_contacts(campaign_id: str, payload: ImportContactsPayload,
                          session: AsyncSession = Depends(get_session),
                          user: User = Depends(require_access)) -> ImportContactsResult:
    tenant_id = str(user.tenant_id)
    item = await svc.get_campaign_or_404(session, tenant_id, campaign_id)
    if item.status in ("completed", "stopped"):
        raise ApiError(409, "campaign_bad_state", "Tugagan kampaniyaga kontakt qo'shilmaydi")
    report = await svc.import_contacts(session, tenant_id, item, payload.csv, payload.replace)
    await _audit(session, user, "import", item, {k: report[k] for k in ("added", "duplicates", "skipped")}
                 | {"invalid": report["invalid_count"], "replace": payload.replace})
    await session.commit()
    return ImportContactsResult(**report, item=await _one_out(session, item))


def _contact_filter(campaign_id: str, status: str | None, q: str | None) -> list:
    conds = [CampaignContact.campaign_id == campaign_id]
    if status:
        conds.append(CampaignContact.status == status)
    if q and q.strip():
        like = f"%{q.strip()}%"
        conds.append(CampaignContact.number.ilike(like) | CampaignContact.name.ilike(like))
    return conds


@router.get("/{campaign_id}/contacts", response_model=ContactList)
async def list_contacts(campaign_id: str, status: ContactStatus | None = None, q: str | None = Query(None, max_length=80),
                        page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
                        session: AsyncSession = Depends(get_session),
                        user: User = Depends(require_access)) -> ContactList:
    item = await svc.get_campaign_or_404(session, str(user.tenant_id), campaign_id)
    conds = _contact_filter(str(item.id), status, q)
    total = (await session.execute(select(func.count()).select_from(CampaignContact).where(*conds))).scalar_one()
    rows = (await session.execute(select(CampaignContact).where(*conds).order_by(CampaignContact.id)
                                  .offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return ContactList(items=[ContactOut.model_validate(r, from_attributes=True) for r in rows], total=total)


@router.get("/{campaign_id}/export.csv", response_class=PlainTextResponse)
async def export_contacts(campaign_id: str, session: AsyncSession = Depends(get_session),
                          user: User = Depends(require_access)) -> PlainTextResponse:
    item = await svc.get_campaign_or_404(session, str(user.tenant_id), campaign_id)
    rows = (await session.execute(select(CampaignContact).where(CampaignContact.campaign_id == item.id)
                                  .order_by(CampaignContact.id))).scalars().all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_EXPORT_COLUMNS)
    for row in rows:
        writer.writerow([csv_cell(_export_value(getattr(row, col))) for col in _EXPORT_COLUMNS])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="campaign-{item.id}.csv"'})


def _export_value(value: object) -> object:
    return value.isoformat() if hasattr(value, "isoformat") else value
