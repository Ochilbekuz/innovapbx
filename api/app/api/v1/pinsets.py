"""M9 B1 — PIN to'plamlari (m9-freepbx-gaps-contract.md Bo'lak B1). CRUD +
PIN boshqaruvi; haqiqiy tekshiruv (HMAC solishtirish) dialplan `CURL()` orqali
`app/api/internal_pinset.py`da — bu yerda faqat ochiq matn PIN hech qachon
saqlanmaydi/qaytarilmaydi (faqat `label`)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_session, require_access
from app.core.config import settings
from app.core.errors import ApiError
from app.core.lookups import get_tenant_scoped_or_404
from app.core.optimistic import check_not_stale
from app.db.models import OutboundRoute, PinSet, PinSetPin, User
from app.schemas import (
    AddPinsPayload,
    CreatePinSetPayload,
    PinItemOut,
    PinItemsOut,
    PinSetOut,
    PinSetUsageRef,
    UpdatePinSetPayload,
)
from app.services.audit import record_audit
from app.services.pin_hmac import hash_pin

router = APIRouter(prefix="/pin-sets", tags=["pin-sets"])

_NAME_TAKEN = ApiError(409, "name_taken", "Shu nomli PIN to'plami allaqachon mavjud", field="name")
_PIN_TAKEN = ApiError(409, "pin_taken", "Bu PIN to'plamda allaqachon band", field="pin")


async def _used_by(session: AsyncSession, tenant_id: str, pin_set_id: str) -> list[PinSetUsageRef]:
    rows = (await session.execute(
        select(OutboundRoute.id, OutboundRoute.name).where(
            OutboundRoute.tenant_id == tenant_id, OutboundRoute.pin_set_id == pin_set_id)
    )).all()
    return [PinSetUsageRef(id=str(r.id), name=r.name) for r in rows]


async def _pin_set_out(session: AsyncSession, tenant_id: str, pin_set: PinSet) -> PinSetOut:
    pin_count = len(pin_set.pins)
    return PinSetOut(
        id=str(pin_set.id), name=pin_set.name, record_in_cdr=pin_set.record_in_cdr,
        pin_count=pin_count, used_by=await _used_by(session, tenant_id, str(pin_set.id)),
        updated_at=pin_set.updated_at,
    )


_PIN_SET_OPTIONS = (selectinload(PinSet.pins),)


async def _get_pin_set_or_404(session: AsyncSession, tenant_id: str, pin_set_id: str) -> PinSet:
    return await get_tenant_scoped_or_404(
        session, PinSet, tenant_id, pin_set_id, not_found_message="PIN to'plami topilmadi",
        options=_PIN_SET_OPTIONS,
    )


@router.get("")
async def list_pin_sets(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> dict:
    items = (await session.execute(
        select(PinSet).where(PinSet.tenant_id == user.tenant_id).order_by(PinSet.name)
        .options(*_PIN_SET_OPTIONS)
    )).scalars().all()
    return {"items": [await _pin_set_out(session, str(user.tenant_id), p) for p in items]}


@router.post("", response_model=PinSetOut, status_code=201)
async def create_pin_set(
    payload: CreatePinSetPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> PinSetOut:
    tenant_id = str(user.tenant_id)
    pin_set = PinSet(tenant_id=tenant_id, name=payload.name, record_in_cdr=payload.record_in_cdr)
    session.add(pin_set)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise _NAME_TAKEN from exc

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="pin_set.create",
                        entity="pin_set", entity_id=str(pin_set.id), diff={"name": payload.name})
    await session.commit()
    pin_set = await _get_pin_set_or_404(session, tenant_id, str(pin_set.id))
    return await _pin_set_out(session, tenant_id, pin_set)


@router.patch("/{pin_set_id}", response_model=PinSetOut)
async def update_pin_set(
    pin_set_id: str, payload: UpdatePinSetPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> PinSetOut:
    tenant_id = str(user.tenant_id)
    pin_set = await _get_pin_set_or_404(session, tenant_id, pin_set_id)
    check_not_stale(pin_set.updated_at, payload.updated_at)

    diff: dict = {}
    if payload.name is not None:
        pin_set.name = payload.name
        diff["name"] = payload.name
    if payload.record_in_cdr is not None:
        pin_set.record_in_cdr = payload.record_in_cdr
        diff["record_in_cdr"] = payload.record_in_cdr

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise _NAME_TAKEN from exc

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="pin_set.update",
                        entity="pin_set", entity_id=str(pin_set.id), diff=diff)
    await session.commit()
    pin_set = await _get_pin_set_or_404(session, tenant_id, pin_set_id)
    return await _pin_set_out(session, tenant_id, pin_set)


@router.delete("/{pin_set_id}", status_code=204, response_model=None)
async def delete_pin_set(
    pin_set_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> None:
    tenant_id = str(user.tenant_id)
    pin_set = await _get_pin_set_or_404(session, tenant_id, pin_set_id)
    used_by = await _used_by(session, tenant_id, pin_set_id)
    if used_by:
        raise ApiError(409, "in_use", f"«{pin_set.name}» hali chiquvchi marshrut(lar)da ishlatilmoqda",
                        details={"usages": [u.model_dump() for u in used_by]})

    await session.delete(pin_set)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="pin_set.delete",
                        entity="pin_set", entity_id=str(pin_set_id))
    await session.commit()


@router.get("/{pin_set_id}/pins", response_model=PinItemsOut)
async def list_pins(
    pin_set_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> PinItemsOut:
    pin_set = await _get_pin_set_or_404(session, str(user.tenant_id), pin_set_id)
    return PinItemsOut(items=[PinItemOut(id=str(p.id), label=p.label) for p in sorted(pin_set.pins, key=lambda p: p.label)])


async def _existing_pin_hmacs(session: AsyncSession, pin_set_id: str) -> set[str]:
    rows = (await session.execute(
        select(PinSetPin.pin_hmac).where(PinSetPin.pin_set_id == pin_set_id)
    )).scalars().all()
    return set(rows)


@router.post("/{pin_set_id}/pins", response_model=PinItemsOut, status_code=201)
async def add_pins(
    pin_set_id: str, payload: AddPinsPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> PinItemsOut:
    tenant_id = str(user.tenant_id)
    pin_set = await _get_pin_set_or_404(session, tenant_id, pin_set_id)
    secret = settings.require_secret_key()

    seen = await _existing_pin_hmacs(session, pin_set_id)
    created: list[PinSetPin] = []
    for item in payload.pins:
        digest = hash_pin(secret, item.pin)
        if digest in seen:
            await session.rollback()
            raise _PIN_TAKEN
        seen.add(digest)
        row = PinSetPin(pin_set_id=pin_set.id, pin_hmac=digest, label=item.label)
        session.add(row)
        created.append(row)

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="pin_set.add_pins",
                        entity="pin_set", entity_id=str(pin_set.id), diff={"count": len(created)})
    await session.commit()
    # DIQQAT: faqat SHU so'rovda yaratilgan yangi PIN'lar qaytariladi (to'liq
    # ro'yxat EMAS) -- frontend shu sababli yangi qo'shilgan sonini
    # `res.items.length` dan to'g'ridan-to'g'ri olishi kerak (eski-yangi farqini
    # hisoblash EMAS, chunki bu yerda "eski" ro'yxat umuman qaytarilmaydi).
    return PinItemsOut(items=[PinItemOut(id=str(p.id), label=p.label) for p in created])


@router.delete("/{pin_set_id}/pins/{pin_id}", status_code=204, response_model=None)
async def delete_pin(
    pin_set_id: str, pin_id: str, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> None:
    tenant_id = str(user.tenant_id)
    await _get_pin_set_or_404(session, tenant_id, pin_set_id)
    pin = (await session.execute(
        select(PinSetPin).where(PinSetPin.id == pin_id, PinSetPin.pin_set_id == pin_set_id)
    )).scalar_one_or_none()
    if pin is None:
        raise ApiError(404, "not_found", "PIN topilmadi")

    await session.delete(pin)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="pin_set.delete_pin",
                        entity="pin_set", entity_id=pin_set_id, diff={"pin_id": pin_id})
    await session.commit()
