"""Ish vaqti shartlari — m1a-contract.md «Ish vaqti (S08)»."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_ami, get_session, require_access
from app.core.errors import ApiError
from app.core.ids import parse_uuid
from app.core.optimistic import check_not_stale
from app.db.models import Tenant, TimeCondition, TimeGroup, User
from app.schemas import (
    CreateTimeConditionPayload,
    OverridePayload,
    TimeConditionMutated,
    TimeConditionOut,
    UpdateTimeConditionPayload,
)
from app.api.v1.feature_codes import feature_code_strings
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.feature_codes import validate_feature_code
from app.services.holidays_calc import holidays_mmdd_set
from app.services.numbers import dial_number_for_target, ensure_number_free, set_dial_number
from app.services.target_resolution import create_target, delete_satellite_and_target, rename_target, resolve_target
from app.services.time_eval import compute_state_now
from app.services.usages import usages_for_target

router = APIRouter(prefix="/time-conditions", tags=["time-conditions"])


async def _tc_out(session: AsyncSession, tenant_id: str, tc: TimeCondition) -> TimeConditionOut:
    ranges = [(r.weekdays, r.start_time.strftime("%H:%M"), r.end_time.strftime("%H:%M"))
              for r in tc.time_group.ranges]
    holidays_mmdd = await holidays_mmdd_set(session, tenant_id)
    tenant = await session.get(Tenant, tenant_id)
    state_now = compute_state_now(
        tz_name=tenant.timezone, override=tc.override, ranges=ranges,
        honor_holidays=tc.honor_holidays, holidays_mmdd=holidays_mmdd,
    )
    open_target = await resolve_target(session, tenant_id, str(tc.open_target_id))
    closed_target = await resolve_target(session, tenant_id, str(tc.closed_target_id))
    number = await dial_number_for_target(session, tenant_id, str(tc.target_id))
    return TimeConditionOut(
        id=str(tc.id), name=tc.name, number=number,
        time_group={"id": str(tc.time_group_id), "name": tc.time_group.name},
        honor_holidays=tc.honor_holidays, open_target=open_target, closed_target=closed_target,
        override=tc.override, toggle_code=tc.toggle_code, state_now=state_now, updated_at=tc.updated_at,
    )


_TC_OPTIONS = (selectinload(TimeCondition.time_group).selectinload(TimeGroup.ranges),)


async def _get_tc_or_404(session: AsyncSession, tenant_id: str, tc_id: str) -> TimeCondition:
    valid_id = parse_uuid(tc_id, not_found_message="Ish vaqti sharti topilmadi")
    tc = (await session.execute(
        select(TimeCondition).where(TimeCondition.tenant_id == tenant_id, TimeCondition.id == valid_id)
        .options(*_TC_OPTIONS)
    )).scalar_one_or_none()
    if tc is None:
        raise ApiError(404, "not_found", "Ish vaqti sharti topilmadi")
    return tc


async def _validate_time_group(session: AsyncSession, tenant_id: str, time_group_id: str) -> str:
    group = (await session.execute(
        select(TimeGroup).where(TimeGroup.tenant_id == tenant_id, TimeGroup.id == time_group_id)
    )).scalar_one_or_none()
    if group is None:
        raise ApiError(422, "invalid_time_group", "Noto'g'ri ish vaqti guruhi", field="time_group_id")
    return time_group_id


async def _validate_route_target(session: AsyncSession, tenant_id: str, target_id: str, field: str) -> str:
    resolved = await resolve_target(session, tenant_id, target_id)
    if resolved is None:
        raise ApiError(422, "invalid_target", "Noto'g'ri manzil", field=field)
    return target_id


async def _validate_toggle_code(
    session: AsyncSession, tenant_id: str, code: str, current: str | None = None,
) -> None:
    """Tuzatish (b): `toggle_code` xususiyat kodlari bilan to'qnashmasin (teng yoki
    prefiks) — `feature_codes.py` dagi feature-kod to'qnashuvi bilan BIR XIL qoida/
    funksiya (`validate_feature_code`). O'z joriy kodi qayta yuborilsa — tekshirilmaydi."""
    if code == current:
        return
    validate_feature_code(code, await feature_code_strings(session, tenant_id))


@router.get("")
async def list_time_conditions(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> dict:
    items = (await session.execute(
        select(TimeCondition).where(TimeCondition.tenant_id == user.tenant_id).order_by(TimeCondition.name)
        .options(*_TC_OPTIONS)
    )).scalars().all()
    return {"items": [await _tc_out(session, str(user.tenant_id), tc) for tc in items]}


@router.post("", response_model=TimeConditionMutated, status_code=201)
async def create_time_condition(
    payload: CreateTimeConditionPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> TimeConditionMutated:
    tenant_id = str(user.tenant_id)
    await _validate_time_group(session, tenant_id, payload.time_group_id)
    await _validate_route_target(session, tenant_id, payload.open_target_id, "open_target_id")
    await _validate_route_target(session, tenant_id, payload.closed_target_id, "closed_target_id")
    if payload.number:
        await ensure_number_free(session, tenant_id, payload.number)
    if payload.toggle_code:
        await _validate_toggle_code(session, tenant_id, payload.toggle_code)

    target = await create_target(session, tenant_id, "time_condition", payload.name)
    tc = TimeCondition(
        tenant_id=tenant_id, target_id=target.id, name=payload.name, time_group_id=payload.time_group_id,
        honor_holidays=payload.honor_holidays, open_target_id=payload.open_target_id,
        closed_target_id=payload.closed_target_id, override=payload.override, toggle_code=payload.toggle_code,
    )
    session.add(tc)
    await session.flush()
    if payload.number:
        await set_dial_number(session, tenant_id, str(target.id), payload.number)

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="time_condition.create",
                        entity="time_condition", entity_id=str(tc.id), diff={"name": payload.name})
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    tc = await _get_tc_or_404(session, tenant_id, str(tc.id))
    return TimeConditionMutated(item=await _tc_out(session, tenant_id, tc), apply=apply_result.to_dict())


@router.patch("/{tc_id}", response_model=TimeConditionMutated)
async def update_time_condition(
    tc_id: str, payload: UpdateTimeConditionPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> TimeConditionMutated:
    tenant_id = str(user.tenant_id)
    tc = await _get_tc_or_404(session, tenant_id, tc_id)
    check_not_stale(tc.updated_at, payload.updated_at)

    diff: dict = {}
    if payload.name is not None:
        tc.name = payload.name
        await rename_target(session, str(tc.target_id), payload.name)
        diff["name"] = payload.name
    if payload.time_group_id is not None:
        await _validate_time_group(session, tenant_id, payload.time_group_id)
        tc.time_group_id = payload.time_group_id
        diff["time_group_id"] = payload.time_group_id
    if payload.honor_holidays is not None:
        tc.honor_holidays = payload.honor_holidays
        diff["honor_holidays"] = payload.honor_holidays
    if payload.open_target_id is not None:
        await _validate_route_target(session, tenant_id, payload.open_target_id, "open_target_id")
        tc.open_target_id = payload.open_target_id
        diff["open_target_id"] = payload.open_target_id
    if payload.closed_target_id is not None:
        await _validate_route_target(session, tenant_id, payload.closed_target_id, "closed_target_id")
        tc.closed_target_id = payload.closed_target_id
        diff["closed_target_id"] = payload.closed_target_id
    if payload.toggle_code is not None:
        await _validate_toggle_code(session, tenant_id, payload.toggle_code, current=tc.toggle_code)
        tc.toggle_code = payload.toggle_code
        diff["toggle_code"] = payload.toggle_code
    if payload.number is not None:
        if payload.number:
            await ensure_number_free(session, tenant_id, payload.number, exclude_target_id=str(tc.target_id))
        await set_dial_number(session, tenant_id, str(tc.target_id), payload.number)
        diff["number"] = payload.number

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="time_condition.update",
                        entity="time_condition", entity_id=str(tc.id), diff=diff)
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    tc = await _get_tc_or_404(session, tenant_id, str(tc.id))
    return TimeConditionMutated(item=await _tc_out(session, tenant_id, tc), apply=apply_result.to_dict())


@router.post("/{tc_id}/override", response_model=TimeConditionMutated)
async def override_time_condition(
    tc_id: str, payload: OverridePayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> TimeConditionMutated:
    tenant_id = str(user.tenant_id)
    tc = await _get_tc_or_404(session, tenant_id, tc_id)
    tc.override = payload.override
    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="time_condition.override",
                        entity="time_condition", entity_id=str(tc.id), diff={"override": payload.override})
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    return TimeConditionMutated(item=await _tc_out(session, tenant_id, tc), apply=apply_result.to_dict())


@router.delete("/{tc_id}", status_code=204, response_model=None)
async def delete_time_condition(
    tc_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
    ami=Depends(get_ami),
) -> None:
    tenant_id = str(user.tenant_id)
    tc = await _get_tc_or_404(session, tenant_id, tc_id)
    usages = await usages_for_target(session, tenant_id, str(tc.target_id))
    if usages:
        raise ApiError(409, "in_use", "Ish vaqti sharti ishlatilmoqda", details={"usages": usages})

    await delete_satellite_and_target(session, tc, str(tc.target_id))
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="time_condition.delete",
                        entity="time_condition", entity_id=str(tc_id))
    await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
