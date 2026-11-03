"""Park qilish (S26 ko'rish — m2a-contract.md §3; M9 A3 sozlamalar —
m9-freepbx-gaps-contract.md): `GET /parking/calls` (jonli, faqat ko'rish) va
`GET`/`PUT /parking/settings` (lot/slotlar, timeout, MOH — avval
`dialplan_features.PARK_*` qattiq yozilgan edi, endi bazada)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_access
from app.core.errors import ApiError
from app.core.lookups import get_tenant_code
from app.core.optimistic import check_not_stale
from app.db.models import MohClass, ParkingSettings, User
from app.schemas import MohClassRef, ParkingSettingsMutated, ParkingSettingsOut, UpdateParkingSettingsPayload
from app.schemas_features import ParkingStatusOut
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.numbers import number_taken
from app.services.parking import parking_status
from app.services.parking_settings import get_parking_settings
from app.services.target_resolution import resolve_target

router = APIRouter(prefix="/parking", tags=["parking"])


async def _get_row_or_404(session: AsyncSession, tenant_id: str) -> ParkingSettings:
    row = await session.get(ParkingSettings, tenant_id)
    if row is None:
        raise ApiError(404, "not_found", "Park sozlamalari topilmadi")
    return row


async def _settings_out(session: AsyncSession, tenant_id: str, row: ParkingSettings) -> ParkingSettingsOut:
    timeout_target = None
    if row.timeout_target_id:
        timeout_target = await resolve_target(session, tenant_id, str(row.timeout_target_id))
    moh_class = None
    if row.moh_class_id:
        moh = await session.get(MohClass, row.moh_class_id)
        if moh is not None:
            moh_class = MohClassRef(id=str(moh.id), name=moh.name)
    return ParkingSettingsOut(
        lot_number=row.lot_number, first_slot=row.first_slot, slot_count=row.slot_count,
        timeout_s=row.timeout_s, on_timeout=row.on_timeout, timeout_target=timeout_target,
        moh_class=moh_class, updated_at=row.updated_at,
    )


async def _validate_park_numbers(session: AsyncSession, tenant_id: str, lot_number: str, first_slot: int,
                                  slot_count: int) -> None:
    """Yangi lot/slot raqamlari ichki raqam/manzil raqami/umumiy quti bilan
    to'qnashmasin (409 `number_taken`). Eski park diapazoni bilan solishtirish
    kerak emas — u shu konfiguratsiya tomonidan almashtirilyapti."""
    candidates = [lot_number, *(str(first_slot + i) for i in range(slot_count))]
    for number in candidates:
        if await number_taken(session, tenant_id, number):
            raise ApiError(409, "number_taken", f"Bu raqam band: {number}", field="first_slot")


@router.get("/calls", response_model=ParkingStatusOut)
async def list_parked_calls(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access), ami=Depends(get_ami),
) -> ParkingStatusOut:
    tenant_id = str(user.tenant_id)
    code = await get_tenant_code(session, tenant_id)
    parking = await get_parking_settings(session, tenant_id)
    return ParkingStatusOut(**await parking_status(ami, code, parking))


@router.get("/settings", response_model=ParkingSettingsOut)
async def get_parking_settings_endpoint(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> ParkingSettingsOut:
    tenant_id = str(user.tenant_id)
    row = await _get_row_or_404(session, tenant_id)
    return await _settings_out(session, tenant_id, row)


async def _validate_slot_change(session: AsyncSession, tenant_id: str, payload: UpdateParkingSettingsPayload,
                                 row: ParkingSettings) -> None:
    """Lot/slot maydonlaridan biri o'zgarganda — yangi (yoki saqlanib qolgan)
    to'liq uchlik bilan to'qnashuvni tekshiradi."""
    if payload.lot_number is None and payload.first_slot is None and payload.slot_count is None:
        return
    new_lot = payload.lot_number if payload.lot_number is not None else row.lot_number
    new_first = payload.first_slot if payload.first_slot is not None else row.first_slot
    new_count = payload.slot_count if payload.slot_count is not None else row.slot_count
    await _validate_park_numbers(session, tenant_id, new_lot, new_first, new_count)


def _ensure_on_timeout_target(payload: UpdateParkingSettingsPayload, row: ParkingSettings) -> None:
    """`on_timeout=target` bo'lsa, (eski yoki yangi) `timeout_target_id` bo'lishi shart."""
    new_on_timeout = payload.on_timeout if payload.on_timeout is not None else row.on_timeout
    new_timeout_target = payload.timeout_target_id if payload.timeout_target_id is not None else row.timeout_target_id
    if new_on_timeout == "target" and not new_timeout_target:
        raise ApiError(422, "invalid_target", "`on_timeout=target` uchun `timeout_target_id` kerak",
                       field="timeout_target_id")


def _apply_scalar_fields(payload: UpdateParkingSettingsPayload, row: ParkingSettings) -> dict:
    diff: dict = {}
    for field in ("lot_number", "first_slot", "slot_count", "timeout_s", "on_timeout"):
        value = getattr(payload, field)
        if value is not None:
            setattr(row, field, value)
            diff[field] = value
    return diff


async def _apply_timeout_target(session: AsyncSession, tenant_id: str, payload: UpdateParkingSettingsPayload,
                                 row: ParkingSettings, diff: dict) -> None:
    if payload.timeout_target_id is None:
        return
    if await resolve_target(session, tenant_id, payload.timeout_target_id) is None:
        raise ApiError(422, "invalid_target", "Noto'g'ri manzil", field="timeout_target_id")
    row.timeout_target_id = payload.timeout_target_id
    diff["timeout_target_id"] = payload.timeout_target_id


async def _apply_moh_class(session: AsyncSession, tenant_id: str, payload: UpdateParkingSettingsPayload,
                            row: ParkingSettings, diff: dict) -> None:
    if payload.moh_class_id is None:
        return
    moh = (await session.execute(
        select(MohClass.id).where(MohClass.tenant_id == tenant_id, MohClass.id == payload.moh_class_id)
    )).scalar_one_or_none()
    if moh is None:
        raise ApiError(422, "invalid_moh_class", "Noto'g'ri MOH klassi", field="moh_class_id")
    row.moh_class_id = payload.moh_class_id
    diff["moh_class_id"] = payload.moh_class_id


@router.put("/settings", response_model=ParkingSettingsMutated)
async def update_parking_settings(
    payload: UpdateParkingSettingsPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> ParkingSettingsMutated:
    tenant_id = str(user.tenant_id)
    row = await _get_row_or_404(session, tenant_id)
    check_not_stale(row.updated_at, payload.updated_at)

    await _validate_slot_change(session, tenant_id, payload, row)
    _ensure_on_timeout_target(payload, row)

    diff = _apply_scalar_fields(payload, row)
    await _apply_timeout_target(session, tenant_id, payload, row, diff)
    await _apply_moh_class(session, tenant_id, payload, row, diff)

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="parking_settings.update",
                        entity="parking_settings", entity_id=tenant_id, diff=diff)
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    return ParkingSettingsMutated(item=await _settings_out(session, tenant_id, row), apply=apply_result.to_dict())
