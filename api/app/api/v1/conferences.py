"""Konferensiya xonalari — m2a-contract.md §4 (S25). CRUD + Asterisk'ga
yetkazish (`apply_config()` dialplan + `conference.apply_confbridge()`
`confbridge_innova.conf`, voicemail bilan BIR XIL ikki bosqichli qolip).

PIN HECH QACHON ochiq qaytmaydi/saqlanmaydi — faqat `has_pin`/`has_admin_pin`
(xuddi `VoicemailBoxOut.has_pin`/`OutboundRouteSnapshot.has_pin` kabi) va
bcrypt hash. Audit diff'da `pin`/`admin_pin` kalitlari — `audit.py`dagi
`_SECRET_MARKERS` ("pin" so'zini o'z ichiga olgan kalit) avtomatik `***`
bilan maskalaydi, qo'shimcha kod kerak emas."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_access
from app.core.errors import ApiError
from app.core.ids import parse_uuid
from app.core.lookups import get_tenant_code
from app.core.optimistic import check_not_stale
from app.core.security import hash_password
from app.db.models import Conference, User
from app.schemas_conference import (
    ConferenceLive,
    ConferenceMutated,
    ConferenceOut,
    CreateConferencePayload,
    UpdateConferencePayload,
)
from app.services import conference as conf
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.dialplan_features import conf_room
from app.services.numbers import dial_number_for_target, ensure_number_free, set_dial_number
from app.services.target_resolution import create_target, delete_satellite_and_target, rename_target
from app.services.usages import usages_for_target

router = APIRouter(prefix="/conferences", tags=["conferences"])

_NOT_FOUND = "Konferensiya topilmadi"


async def _conf_out(session: AsyncSession, tenant_id: str, tenant_code: str, item: Conference, ami) -> ConferenceOut:
    number = await dial_number_for_target(session, tenant_id, str(item.target_id))
    room = conf_room(tenant_code, str(item.id))
    members = await conf.live_members(ami, room)
    return ConferenceOut(
        id=str(item.id), name=item.name, number=number,
        has_pin=item.pin_hash is not None, has_admin_pin=item.admin_pin_hash is not None,
        record=item.record, max_members=item.max_members, target_id=str(item.target_id),
        updated_at=item.updated_at, live=ConferenceLive(members=members),
    )


async def _get_conf_or_404(session: AsyncSession, tenant_id: str, conference_id: str) -> Conference:
    valid_id = parse_uuid(conference_id, not_found_message=_NOT_FOUND)
    item = (await session.execute(
        select(Conference).where(Conference.tenant_id == tenant_id, Conference.id == valid_id)
    )).scalar_one_or_none()
    if item is None:
        raise ApiError(404, "not_found", _NOT_FOUND)
    return item


async def apply_dialplan_and_confbridge(session: AsyncSession, tenant_id: str, user: User, ami) -> dict:
    """Dialplan + `confbridge_innova.conf` — yozuvchi endpoint'lar uchun bitta
    qolip (`voicemail_boxes.apply_dialplan_and_voicemail` namunasi bo'yicha)."""
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    tenant_code = await get_tenant_code(session, tenant_id)
    try:
        await conf.apply_confbridge(session, tenant_id=tenant_id, tenant_code=tenant_code, ami=ami)
    except Exception as exc:  # noqa: BLE001 — aniq xato xabari bilan 502
        raise ApiError(502, "confbridge_sync_failed",
                       f"Konferensiya Asterisk'ga yetkazilmadi: {exc}"[:500]) from exc
    return apply_result.to_dict()


@router.get("")
async def list_conferences(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access), ami=Depends(get_ami),
) -> dict:
    tenant_id = str(user.tenant_id)
    tenant_code = await get_tenant_code(session, tenant_id)
    items = (await session.execute(
        select(Conference).where(Conference.tenant_id == tenant_id).order_by(Conference.name)
    )).scalars().all()
    return {"items": [await _conf_out(session, tenant_id, tenant_code, c, ami) for c in items]}


@router.get("/{conference_id}", response_model=ConferenceOut)
async def get_conference(
    conference_id: str, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> ConferenceOut:
    tenant_id = str(user.tenant_id)
    item = await _get_conf_or_404(session, tenant_id, conference_id)
    return await _conf_out(session, tenant_id, await get_tenant_code(session, tenant_id), item, ami)


@router.post("", response_model=ConferenceMutated, status_code=201)
async def create_conference(
    payload: CreateConferencePayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> ConferenceMutated:
    tenant_id = str(user.tenant_id)
    if payload.number:
        await ensure_number_free(session, tenant_id, payload.number)

    target = await create_target(session, tenant_id, "conference", payload.name)
    item = Conference(
        tenant_id=tenant_id, target_id=target.id, name=payload.name,
        pin_hash=hash_password(payload.pin) if payload.pin else None,
        admin_pin_hash=hash_password(payload.admin_pin) if payload.admin_pin else None,
        record=payload.record, max_members=payload.max_members,
    )
    session.add(item)
    await session.flush()
    if payload.number:
        await set_dial_number(session, tenant_id, str(target.id), payload.number)

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="conference.create",
                       entity="conference", entity_id=str(item.id),
                       diff={"name": payload.name, "pin": payload.pin, "admin_pin": payload.admin_pin})
    apply_result = await apply_dialplan_and_confbridge(session, tenant_id, user, ami)
    await session.commit()
    item = await _get_conf_or_404(session, tenant_id, str(item.id))
    tenant_code = await get_tenant_code(session, tenant_id)
    return ConferenceMutated(item=await _conf_out(session, tenant_id, tenant_code, item, ami), apply=apply_result)


def _apply_simple_conference_fields(item: Conference, payload: UpdateConferencePayload, diff: dict) -> None:
    """Oddiy maydonlar — CRAP pasaytirish uchun alohida (`ring_groups.py`
    `_apply_simple_rg_fields` namunasi). `max_members` — `model_fields_set`
    (`None` = aniq "cheksiz", xuddi ovozli pochta `greeting_audio_id` kabi)."""
    if payload.record is not None:
        item.record = payload.record
        diff["record"] = payload.record
    if "max_members" in payload.model_fields_set:
        item.max_members = payload.max_members
        diff["max_members"] = payload.max_members


async def _apply_conference_pins(item: Conference, payload: UpdateConferencePayload, diff: dict) -> None:
    given = payload.model_fields_set
    if "pin" in given:
        item.pin_hash = hash_password(payload.pin) if payload.pin else None
        diff["pin"] = payload.pin
    if "admin_pin" in given:
        item.admin_pin_hash = hash_password(payload.admin_pin) if payload.admin_pin else None
        diff["admin_pin"] = payload.admin_pin


async def _apply_conference_number(
    session: AsyncSession, tenant_id: str, item: Conference, payload: UpdateConferencePayload, diff: dict,
) -> None:
    if payload.number is None:
        return
    await ensure_number_free(session, tenant_id, payload.number, exclude_target_id=str(item.target_id))
    await set_dial_number(session, tenant_id, str(item.target_id), payload.number)
    diff["number"] = payload.number


@router.patch("/{conference_id}", response_model=ConferenceMutated)
async def update_conference(
    conference_id: str, payload: UpdateConferencePayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> ConferenceMutated:
    tenant_id = str(user.tenant_id)
    item = await _get_conf_or_404(session, tenant_id, conference_id)
    check_not_stale(item.updated_at, payload.updated_at)

    diff: dict = {}
    if payload.name is not None:
        item.name = payload.name
        await rename_target(session, str(item.target_id), payload.name)
        diff["name"] = payload.name
    _apply_simple_conference_fields(item, payload, diff)
    await _apply_conference_pins(item, payload, diff)
    await _apply_conference_number(session, tenant_id, item, payload, diff)

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="conference.update",
                       entity="conference", entity_id=str(item.id), diff=diff)
    apply_result = await apply_dialplan_and_confbridge(session, tenant_id, user, ami)
    await session.commit()
    item = await _get_conf_or_404(session, tenant_id, conference_id)
    tenant_code = await get_tenant_code(session, tenant_id)
    return ConferenceMutated(item=await _conf_out(session, tenant_id, tenant_code, item, ami), apply=apply_result)


@router.delete("/{conference_id}", status_code=204, response_model=None)
async def delete_conference(
    conference_id: str, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> None:
    tenant_id = str(user.tenant_id)
    item = await _get_conf_or_404(session, tenant_id, conference_id)
    target_id = str(item.target_id)
    usages = await usages_for_target(session, tenant_id, target_id)
    if usages:
        raise ApiError(409, "in_use", f"«{item.name}» konferensiyasi hali ishlatilmoqda",
                       details={"usages": usages})
    name = item.name
    await delete_satellite_and_target(session, item, target_id)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="conference.delete",
                       entity="conference", entity_id=str(conference_id), diff={"name": name})
    await apply_dialplan_and_confbridge(session, tenant_id, user, ami)
    await session.commit()
