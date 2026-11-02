"""Bayramlar — m1a-contract.md «Ish vaqti (S08)»: CRUD + `/holidays/import-uz`."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_admin
from app.core.lookups import get_tenant_scoped_or_404
from app.db.models import Holiday, User
from app.schemas import (
    CreateHolidayPayload,
    HolidayOut,
    ImportUzHolidaysPayload,
    ImportUzHolidaysResult,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/holidays", tags=["holidays"])

# O'zbekiston rasmiy bayramlari — har yili takrorlanadigan sanalar (recurring_yearly).
_FIXED_UZ_HOLIDAYS = [
    ("Yangi yil", 1, 1),
    ("Xalqaro xotin-qizlar kuni", 3, 8),
    ("Navro'z bayrami", 3, 21),
    ("Xotira va qadrlash kuni", 5, 9),
    ("Mustaqillik kuni", 9, 1),
    ("O'qituvchi va murabbiylar kuni", 10, 1),
    ("O'zbekiston Konstitutsiyasi kuni", 12, 8),
    ("Yil oxiri", 12, 31),
]

# Oy-quyosh taqvimiga bog'liq — yiliga ko'chadi, shu sabab faqat ma'lum
# yillar uchun jadval (m1a-contract.md: bo'lmasa `skipped`ga qo'shiladi).
_RAMAZON_HAYIT = {2024: (4, 10), 2025: (3, 30), 2026: (3, 20), 2027: (3, 9)}
_QURBON_HAYIT = {2024: (6, 16), 2025: (6, 6), 2026: (5, 27), 2027: (5, 16)}


def _holiday_out(h: Holiday) -> HolidayOut:
    return HolidayOut(id=str(h.id), name=h.name, day=h.day.isoformat(), recurring_yearly=h.recurring_yearly)


@router.get("")
async def list_holidays(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> dict:
    items = (await session.execute(
        select(Holiday).where(Holiday.tenant_id == user.tenant_id).order_by(Holiday.day)
    )).scalars().all()
    return {"items": [_holiday_out(h) for h in items]}


@router.post("", response_model=HolidayOut, status_code=201)
async def create_holiday(
    payload: CreateHolidayPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> HolidayOut:
    holiday = Holiday(tenant_id=user.tenant_id, name=payload.name, day=date.fromisoformat(payload.day),
                       recurring_yearly=payload.recurring_yearly)
    session.add(holiday)
    await session.flush()
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="holiday.create", entity="holiday", entity_id=str(holiday.id),
                        diff={"name": payload.name, "day": payload.day})
    await session.commit()
    return _holiday_out(holiday)


@router.delete("/{holiday_id}", status_code=204, response_model=None)
async def delete_holiday(
    holiday_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> None:
    holiday = await get_tenant_scoped_or_404(
        session, Holiday, str(user.tenant_id), holiday_id, not_found_message="Bayram topilmadi",
    )
    await session.delete(holiday)
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="holiday.delete", entity="holiday", entity_id=str(holiday_id))
    await session.commit()


async def _existing_days(session: AsyncSession, tenant_id: str) -> set[date]:
    rows = (await session.execute(
        select(Holiday.day).where(Holiday.tenant_id == tenant_id))).scalars().all()
    return set(rows)


def _lunar_candidates(year: int) -> tuple[list[tuple[str, date]], list[str]]:
    candidates: list[tuple[str, date]] = []
    skipped: list[str] = []
    for key, name, table in (("ramazon_hayit", "Ramazon hayit", _RAMAZON_HAYIT),
                              ("qurbon_hayit", "Qurbon hayit", _QURBON_HAYIT)):
        mmdd = table.get(year)
        if mmdd is None:
            skipped.append(key)
            continue
        candidates.append((name, date(year, *mmdd)))
    return candidates, skipped


@router.post("/import-uz", response_model=ImportUzHolidaysResult)
async def import_uz_holidays(
    payload: ImportUzHolidaysPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> ImportUzHolidaysResult:
    tenant_id = str(user.tenant_id)
    existing_days = await _existing_days(session, tenant_id)

    fixed = [(name, date(payload.year, m, d), True) for name, m, d in _FIXED_UZ_HOLIDAYS]
    lunar, skipped = _lunar_candidates(payload.year)
    fixed += [(name, day, False) for name, day in lunar]

    created = 0
    items: list[HolidayOut] = []
    for name, day, recurring in fixed:
        if day in existing_days:
            continue
        holiday = Holiday(tenant_id=tenant_id, name=name, day=day, recurring_yearly=recurring)
        session.add(holiday)
        await session.flush()
        items.append(_holiday_out(holiday))
        existing_days.add(day)
        created += 1

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id),
                        action="holiday.import_uz", entity="holiday", diff={"year": payload.year,
                                                                              "created": created})
    await session.commit()
    return ImportUzHolidaysResult(items=items, created=created, skipped=skipped)
