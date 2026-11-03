"""Paging/Intercom guruhlari (M9 A4, m9-freepbx-gaps-contract.md) — `number`
terilganda a'zolarga `Page()` (`dialplan_features.page_group_lines`)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_ami, get_session, require_access
from app.core.errors import ApiError
from app.core.ids import parse_uuid
from app.core.optimistic import check_not_stale
from app.db.models import Extension, PageGroup, PageGroupMember, User
from app.schemas import (
    CreatePageGroupPayload,
    ExtensionRef,
    Paged,
    PageGroupMutated,
    PageGroupOut,
    UpdatePageGroupPayload,
)
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.numbers import ensure_number_free

router = APIRouter(prefix="/page-groups", tags=["page-groups"])

_MEMBERS = (selectinload(PageGroup.members).selectinload(PageGroupMember.extension),)


def _out(pg: PageGroup) -> PageGroupOut:
    members = [ExtensionRef(id=str(m.extension.id), number=m.extension.number, name=m.extension.name)
               for m in pg.members if m.extension]
    return PageGroupOut(id=str(pg.id), name=pg.name, number=pg.number, members=members,
                        duplex=pg.duplex, skip_busy=pg.skip_busy, beep=pg.beep, updated_at=pg.updated_at)


async def _get_or_404(session: AsyncSession, tenant_id: str, item_id: str) -> PageGroup:
    valid_id = parse_uuid(item_id, not_found_message="Guruh topilmadi")
    item = (await session.execute(
        select(PageGroup).where(PageGroup.tenant_id == tenant_id, PageGroup.id == valid_id).options(*_MEMBERS)
    )).scalar_one_or_none()
    if item is None:
        raise ApiError(404, "not_found", "Guruh topilmadi")
    return item


async def _validate_members(session: AsyncSession, tenant_id: str, extension_ids: list[str]) -> None:
    if not extension_ids:
        return
    found = (await session.execute(
        select(Extension.id).where(Extension.tenant_id == tenant_id, Extension.id.in_(extension_ids))
    )).scalars().all()
    missing = set(extension_ids) - {str(f) for f in found}
    if missing:
        raise ApiError(422, "invalid_extension", "Noto'g'ri ichki raqam", field="member_extension_ids",
                       details={"missing": sorted(missing)})


def _set_members(pg: PageGroup, extension_ids: list[str]) -> None:
    pg.members = [PageGroupMember(extension_id=eid) for eid in extension_ids]


@router.get("", response_model=Paged)
async def list_page_groups(
    q: str | None = None, page: int = 1, size: int = 50,
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> Paged:
    tenant_id = str(user.tenant_id)
    stmt = select(PageGroup).where(PageGroup.tenant_id == tenant_id).options(*_MEMBERS)
    count_stmt = select(func.count()).select_from(PageGroup).where(PageGroup.tenant_id == tenant_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(PageGroup.name.ilike(like))
        count_stmt = count_stmt.where(PageGroup.name.ilike(like))
    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(PageGroup.name).offset((page - 1) * size).limit(size)
    items = (await session.execute(stmt)).scalars().unique().all()
    return Paged(items=[_out(pg) for pg in items], total=total)


@router.get("/{item_id}", response_model=PageGroupOut)
async def get_page_group(
    item_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> PageGroupOut:
    item = await _get_or_404(session, str(user.tenant_id), item_id)
    return _out(item)


@router.post("", response_model=PageGroupMutated, status_code=201)
async def create_page_group(
    payload: CreatePageGroupPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> PageGroupMutated:
    tenant_id = str(user.tenant_id)
    await ensure_number_free(session, tenant_id, payload.number)
    await _validate_members(session, tenant_id, payload.member_extension_ids)

    item = PageGroup(tenant_id=tenant_id, name=payload.name, number=payload.number,
                      duplex=payload.duplex, skip_busy=payload.skip_busy, beep=payload.beep)
    _set_members(item, payload.member_extension_ids)
    session.add(item)
    await session.flush()

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="page_group.create",
                        entity="page_group", entity_id=str(item.id), diff={"name": payload.name,
                                                                            "number": payload.number})
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    item = await _get_or_404(session, tenant_id, str(item.id))
    return PageGroupMutated(item=_out(item), apply=apply_result.to_dict())


@router.patch("/{item_id}", response_model=PageGroupMutated)
async def update_page_group(
    item_id: str, payload: UpdatePageGroupPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> PageGroupMutated:
    tenant_id = str(user.tenant_id)
    item = await _get_or_404(session, tenant_id, item_id)
    check_not_stale(item.updated_at, payload.updated_at)

    diff: dict = {}
    if payload.name is not None:
        item.name = payload.name
        diff["name"] = payload.name
    if payload.number is not None:
        await ensure_number_free(session, tenant_id, payload.number, exclude_target_id=None)
        item.number = payload.number
        diff["number"] = payload.number
    if payload.member_extension_ids is not None:
        await _validate_members(session, tenant_id, payload.member_extension_ids)
        _set_members(item, payload.member_extension_ids)
        diff["members"] = len(payload.member_extension_ids)
    for field in ("duplex", "skip_busy", "beep"):
        value = getattr(payload, field)
        if value is not None:
            setattr(item, field, value)
            diff[field] = value

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="page_group.update",
                        entity="page_group", entity_id=str(item.id), diff=diff)
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    item = await _get_or_404(session, tenant_id, str(item.id))
    return PageGroupMutated(item=_out(item), apply=apply_result.to_dict())


@router.delete("/{item_id}", status_code=204, response_model=None)
async def delete_page_group(
    item_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
    ami=Depends(get_ami),
) -> None:
    tenant_id = str(user.tenant_id)
    item = await _get_or_404(session, tenant_id, item_id)
    await session.delete(item)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="page_group.delete",
                        entity="page_group", entity_id=str(item_id))
    await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
