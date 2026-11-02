"""Ish vaqti guruhlari — m1a-contract.md «Ish vaqti (S08)»."""
from __future__ import annotations

from datetime import time as dt_time

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_admin
from app.core.errors import ApiError
from app.core.lookups import get_tenant_scoped_or_404
from app.core.optimistic import check_not_stale
from app.db.models import TimeCondition, TimeGroup, TimeRange, User
from app.schemas import (
    CreateTimeGroupPayload,
    TimeGroupMutated,
    TimeGroupOut,
    TimeRangeIn,
    UpdateTimeGroupPayload,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/time-groups", tags=["time-groups"])


def _validate_ranges(ranges: list[TimeRangeIn]) -> None:
    for r in ranges:
        if r.end <= r.start:
            raise ApiError(422, "range_order", "Tugash vaqti boshlanish vaqtidan keyin bo'lishi kerak",
                            field="ranges")


def _group_out(group: TimeGroup) -> TimeGroupOut:
    return TimeGroupOut(
        id=str(group.id), name=group.name,
        ranges=[TimeRangeIn(weekdays=r.weekdays, start=r.start_time.strftime("%H:%M"),
                             end=r.end_time.strftime("%H:%M")) for r in group.ranges],
        updated_at=group.updated_at,
    )


def _replace_ranges(group: TimeGroup, ranges: list[TimeRangeIn]) -> None:
    """To'g'ridan-to'g'ri ro'yxat biriktirish — `.clear()+.append()` o'rniga. Ayniqsa
    `ranges=[]` holatida: hech qachon to'ldirilmagan (yangi/transient) kolleksiyaga
    faqat `.clear()` chaqirish uni "yuklangan" deb belgilamay qoldiradi — keyinroq shu
    obyektga sinxron kodda murojaat qilinsa (`_group_out`), SQLAlchemy kutilmagan lazy
    load urinib ko'radi va `MissingGreenlet` bilan qulaydi."""
    group.ranges = [
        TimeRange(weekdays=r.weekdays, start_time=_parse_hm(r.start), end_time=_parse_hm(r.end))
        for r in ranges
    ]


def _parse_hm(value: str) -> dt_time:
    hh, mm = value.split(":")
    return dt_time(int(hh), int(mm))


@router.get("")
async def list_time_groups(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> dict:
    groups = (await session.execute(
        select(TimeGroup).where(TimeGroup.tenant_id == user.tenant_id).order_by(TimeGroup.name)
    )).unique().scalars().all()
    return {"items": [_group_out(g) for g in groups]}


@router.post("", response_model=TimeGroupMutated, status_code=201)
async def create_time_group(
    payload: CreateTimeGroupPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> TimeGroupMutated:
    _validate_ranges(payload.ranges)
    group = TimeGroup(tenant_id=user.tenant_id, name=payload.name)
    _replace_ranges(group, payload.ranges)
    session.add(group)
    await session.flush()
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="time_group.create", entity="time_group", entity_id=str(group.id),
                        diff={"name": payload.name})
    await session.commit()
    return TimeGroupMutated(item=_group_out(group))


async def _get_group_or_404(session: AsyncSession, tenant_id: str, group_id: str) -> TimeGroup:
    return await get_tenant_scoped_or_404(
        session, TimeGroup, tenant_id, group_id, not_found_message="Ish vaqti guruhi topilmadi",
    )


@router.patch("/{group_id}", response_model=TimeGroupMutated)
async def update_time_group(
    group_id: str, payload: UpdateTimeGroupPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> TimeGroupMutated:
    group = await _get_group_or_404(session, str(user.tenant_id), group_id)
    check_not_stale(group.updated_at, payload.updated_at)

    diff: dict = {}
    if payload.name is not None:
        group.name = payload.name
        diff["name"] = payload.name
    if payload.ranges is not None:
        _validate_ranges(payload.ranges)
        _replace_ranges(group, payload.ranges)
        diff["ranges"] = len(payload.ranges)

    await session.flush()
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="time_group.update", entity="time_group", entity_id=str(group.id), diff=diff)
    await session.commit()
    return TimeGroupMutated(item=_group_out(group))


@router.delete("/{group_id}", status_code=204, response_model=None)
async def delete_time_group(
    group_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> None:
    group = await _get_group_or_404(session, str(user.tenant_id), group_id)
    usages = (await session.execute(
        select(TimeCondition).where(TimeCondition.time_group_id == group.id)
    )).scalars().all()
    if usages:
        raise ApiError(409, "in_use", "Ish vaqti guruhi ishlatilmoqda", details={
            "usages": [{"kind": "time_condition", "id": str(tc.id), "label": tc.name, "field": "time_group"}
                       for tc in usages],
        })
    await session.delete(group)
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="time_group.delete", entity="time_group", entity_id=str(group_id))
    await session.commit()
