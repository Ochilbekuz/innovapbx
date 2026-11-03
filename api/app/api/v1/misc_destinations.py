"""Boshqa manzillar (M9 A2, m9-freepbx-gaps-contract.md) — `dial`ni ODDIY
ICHKI TERISH kabi yuboradi (toll-fraud/PIN BYPASS qilinmaydi,
`compiler.py::_misc_dest_lines`)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_access
from app.core.errors import ApiError
from app.core.ids import parse_uuid
from app.core.optimistic import check_not_stale
from app.db.models import MiscDestination, User
from app.schemas import (
    CreateMiscDestinationPayload,
    MiscDestinationMutated,
    MiscDestinationOut,
    Paged,
    UpdateMiscDestinationPayload,
)
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.target_resolution import create_target, delete_satellite_and_target, rename_target
from app.services.usages import usages_for_target

router = APIRouter(prefix="/misc-destinations", tags=["misc-destinations"])


def _out(m: MiscDestination) -> MiscDestinationOut:
    return MiscDestinationOut(id=str(m.id), name=m.name, dial=m.dial, updated_at=m.updated_at)


async def _get_or_404(session: AsyncSession, tenant_id: str, item_id: str) -> MiscDestination:
    valid_id = parse_uuid(item_id, not_found_message="Manzil topilmadi")
    item = (await session.execute(
        select(MiscDestination).where(MiscDestination.tenant_id == tenant_id, MiscDestination.id == valid_id)
    )).scalar_one_or_none()
    if item is None:
        raise ApiError(404, "not_found", "Manzil topilmadi")
    return item


@router.get("", response_model=Paged)
async def list_misc_destinations(
    q: str | None = None, page: int = 1, size: int = 50,
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> Paged:
    tenant_id = str(user.tenant_id)
    stmt = select(MiscDestination).where(MiscDestination.tenant_id == tenant_id)
    count_stmt = select(func.count()).select_from(MiscDestination).where(MiscDestination.tenant_id == tenant_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(MiscDestination.name.ilike(like))
        count_stmt = count_stmt.where(MiscDestination.name.ilike(like))
    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(MiscDestination.name).offset((page - 1) * size).limit(size)
    items = (await session.execute(stmt)).scalars().all()
    return Paged(items=[_out(m) for m in items], total=total)


@router.get("/{item_id}", response_model=MiscDestinationOut)
async def get_misc_destination(
    item_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> MiscDestinationOut:
    item = await _get_or_404(session, str(user.tenant_id), item_id)
    return _out(item)


@router.post("", response_model=MiscDestinationMutated, status_code=201)
async def create_misc_destination(
    payload: CreateMiscDestinationPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> MiscDestinationMutated:
    tenant_id = str(user.tenant_id)
    target = await create_target(session, tenant_id, "misc", payload.name)
    item = MiscDestination(tenant_id=tenant_id, target_id=target.id, name=payload.name, dial=payload.dial)
    session.add(item)
    await session.flush()

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="misc_destination.create",
                        entity="misc_destination", entity_id=str(item.id), diff={"name": payload.name})
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    return MiscDestinationMutated(item=_out(item), apply=apply_result.to_dict())


@router.patch("/{item_id}", response_model=MiscDestinationMutated)
async def update_misc_destination(
    item_id: str, payload: UpdateMiscDestinationPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> MiscDestinationMutated:
    tenant_id = str(user.tenant_id)
    item = await _get_or_404(session, tenant_id, item_id)
    check_not_stale(item.updated_at, payload.updated_at)

    diff: dict = {}
    if payload.name is not None:
        item.name = payload.name
        await rename_target(session, str(item.target_id), payload.name)
        diff["name"] = payload.name
    if payload.dial is not None:
        item.dial = payload.dial
        diff["dial"] = payload.dial

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="misc_destination.update",
                        entity="misc_destination", entity_id=str(item.id), diff=diff)
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    return MiscDestinationMutated(item=_out(item), apply=apply_result.to_dict())


@router.delete("/{item_id}", status_code=204, response_model=None)
async def delete_misc_destination(
    item_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
    ami=Depends(get_ami),
) -> None:
    tenant_id = str(user.tenant_id)
    item = await _get_or_404(session, tenant_id, item_id)
    usages = await usages_for_target(session, tenant_id, str(item.target_id))
    if usages:
        raise ApiError(409, "in_use", "Manzil ishlatilmoqda", details={"usages": usages})

    await delete_satellite_and_target(session, item, str(item.target_id))
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="misc_destination.delete",
                        entity="misc_destination", entity_id=str(item_id))
    await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
