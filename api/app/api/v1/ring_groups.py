"""Qo'ng'iroq guruhlari — m1a-contract.md «Qo'ng'iroq guruhlari (S21)» +
m1b-contract.md bo'lim 3 (tashqi a'zo). Tashqi a'zo kiruvchi marshrutlar
orqali emas, chiquvchi marshrutlar orqali teriladi (`Local/<raqam>@<code>-
outbound-rg`, m1b-contract.md: "guruh nomidan, ichki raqam ruxsatisiz, lekin
xalqaro qoida amal qiladi") — shuning uchun qo'shishda kamida bitta mos
chiquvchi marshrut borligi tekshiriladi (422 `no_outbound_route`)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_ami, get_session, require_access
from app.core.errors import ApiError
from app.core.ids import parse_uuid
from app.core.lookups import get_tenant_scoped_or_404
from app.core.optimistic import check_not_stale
from app.db.models import AudioFile, Extension, MohClass, RingGroup, RingGroupMember, User
from app.schemas import (
    AudioOut,
    CreateRingGroupPayload,
    ExtensionRef,
    MohClassRef,
    RingGroupMemberIn,
    RingGroupMemberOut,
    RingGroupMutated,
    RingGroupOut,
    UpdateRingGroupPayload,
)
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.numbers import dial_number_for_target, ensure_number_free, set_dial_number
from app.services.outbound_rules import resolve_route
from app.services.route_lookup import load_route_rules
from app.services.target_resolution import create_target, delete_satellite_and_target, rename_target, resolve_target
from app.services.usages import usages_for_target

router = APIRouter(prefix="/ring-groups", tags=["ring-groups"])

_RG_OPTIONS = (selectinload(RingGroup.members).selectinload(RingGroupMember.extension),)


async def _resolve_moh_class(session: AsyncSession, tenant_id: str, moh_class_id: str | None) -> MohClass | None:
    """`queues.py::_resolve_moh_class` bilan BIR XIL naqsh (0038, mustaqil nusxa —
    parallel agentlar bilan faylni bo'lishmaslik uchun)."""
    if moh_class_id is None:
        return None
    return await get_tenant_scoped_or_404(
        session, MohClass, tenant_id, moh_class_id,
        not_found_message="Kutish musiqasi sinfi topilmadi", field="moh_class_id",
    )


async def _resolve_audio(session: AsyncSession, tenant_id: str, audio_id: str | None) -> AudioFile | None:
    """`queues.py::_resolve_audio` bilan BIR XIL naqsh (0038, mustaqil nusxa)."""
    if audio_id is None:
        return None
    return await get_tenant_scoped_or_404(
        session, AudioFile, tenant_id, audio_id,
        not_found_message="Ovoz fayli topilmadi", field="audio_id",
    )


def _audio_ref(audio: AudioFile | None) -> AudioOut | None:
    if audio is None:
        return None
    return AudioOut(id=str(audio.id), name=audio.name, duration_ms=audio.duration_ms, created_at=audio.created_at)


async def _validate_members(session: AsyncSession, tenant_id: str, members: list[RingGroupMemberIn]) -> None:
    """Ichki a'zolar bazada mavjudligini (422 `invalid_target`), tashqi
    a'zolar uchun esa kamida bitta mos chiquvchi marshrut borligini
    (422 `no_outbound_route` + `details.number`) tekshiradi."""
    ext_ids = [m.extension_id for m in members if m.extension_id]
    if ext_ids:
        found = {str(f) for f in (await session.execute(
            select(Extension.id).where(Extension.tenant_id == tenant_id, Extension.id.in_(ext_ids))
        )).scalars().all()}
        missing = [i for i in ext_ids if i not in found]
        if missing:
            raise ApiError(422, "invalid_target", "Noto'g'ri ichki raqam", field="members")

    external_numbers = [m.external_number for m in members if m.external_number]
    if not external_numbers:
        return
    routes = await load_route_rules(session, tenant_id)
    for number in external_numbers:
        outcome = resolve_route(routes, number, extension_id=None)
        if not outcome.allowed:
            raise ApiError(422, "no_outbound_route", "Bu tashqi raqam uchun chiquvchi marshrut yo'q",
                            field="members", details={"number": number})


def _replace_members(group: RingGroup, members: list[RingGroupMemberIn]) -> None:
    """To'g'ridan-to'g'ri ro'yxat biriktirish — `.clear()+.append()` o'rniga (bo'sh/eski
    kolleksiyaga `.clear()` uni "yuklangan" deb belgilamay qoldirishi mumkin, keyingi
    qayta o'qishda `selectinload` buni e'tiborsiz qoldiradi)."""
    group.members = [
        RingGroupMember(position=position, extension_id=m.extension_id, external_number=m.external_number)
        for position, m in enumerate(members, start=1)
    ]


async def _rg_out(session: AsyncSession, tenant_id: str, group: RingGroup) -> RingGroupOut:
    number = await dial_number_for_target(session, tenant_id, str(group.target_id))
    no_answer_target = await resolve_target(session, tenant_id, str(group.no_answer_target_id))
    members = [
        RingGroupMemberOut(
            position=m.position,
            extension=ExtensionRef(id=str(m.extension.id), number=m.extension.number, name=m.extension.name)
            if m.extension is not None else None,
            external_number=m.external_number,
        )
        for m in group.members
    ]
    # 0038: `announcement`/`remote_announce` — relationshipsiz FK (`moh_class`
    # xuddi shu RingGroup'da `lazy="joined"` bilan allaqachon yuklangan).
    announcement = await _resolve_audio(session, tenant_id, group.announcement_audio_id)
    remote_announce = await _resolve_audio(session, tenant_id, group.remote_announce_audio_id)
    moh_class = MohClassRef(id=str(group.moh_class.id), name=group.moh_class.name) if group.moh_class else None
    return RingGroupOut(
        id=str(group.id), name=group.name, number=number, strategy=group.strategy,
        ring_seconds=group.ring_seconds, members=members, no_answer_target=no_answer_target,
        callerid_prefix=group.callerid_prefix, updated_at=group.updated_at,
        announcement=_audio_ref(announcement), ring_strategy_sound=group.ring_strategy_sound,
        moh_class=moh_class, alert_info=group.alert_info, skip_busy_agent=group.skip_busy_agent,
        confirm_calls=group.confirm_calls, remote_announce=_audio_ref(remote_announce),
        recording_policy=group.recording_policy,
    )


async def _get_rg_or_404(session: AsyncSession, tenant_id: str, rg_id: str) -> RingGroup:
    valid_id = parse_uuid(rg_id, not_found_message="Qo'ng'iroq guruhi topilmadi")
    group = (await session.execute(
        select(RingGroup).where(RingGroup.tenant_id == tenant_id, RingGroup.id == valid_id)
        .options(*_RG_OPTIONS)
    )).scalar_one_or_none()
    if group is None:
        raise ApiError(404, "not_found", "Qo'ng'iroq guruhi topilmadi")
    return group


@router.get("")
async def list_ring_groups(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> dict:
    items = (await session.execute(
        select(RingGroup).where(RingGroup.tenant_id == user.tenant_id).order_by(RingGroup.name)
        .options(*_RG_OPTIONS)
    )).scalars().all()
    return {"items": [await _rg_out(session, str(user.tenant_id), g) for g in items]}


async def _validate_create_rg_payload(session: AsyncSession, tenant_id: str, payload: CreateRingGroupPayload) -> None:
    """`create_ring_group`'ning barcha kirish tekshiruvlari — alohida (CRAP pasaytirish)."""
    if await resolve_target(session, tenant_id, payload.no_answer_target_id) is None:
        raise ApiError(422, "invalid_target", "Noto'g'ri manzil", field="no_answer_target_id")
    await _validate_members(session, tenant_id, payload.members)
    if payload.number:
        await ensure_number_free(session, tenant_id, payload.number)


@router.post("", response_model=RingGroupMutated, status_code=201)
async def create_ring_group(
    payload: CreateRingGroupPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> RingGroupMutated:
    tenant_id = str(user.tenant_id)
    await _validate_create_rg_payload(session, tenant_id, payload)
    # 0038: ovoz/MOH FK'lar — mavjud bo'lmasa 422 (`queues.py` naqshi).
    announcement = await _resolve_audio(session, tenant_id, payload.announcement_audio_id)
    moh_class = await _resolve_moh_class(session, tenant_id, payload.moh_class_id)
    remote_announce = await _resolve_audio(session, tenant_id, payload.remote_announce_audio_id)

    target = await create_target(session, tenant_id, "ring_group", payload.name)
    group = RingGroup(
        tenant_id=tenant_id, target_id=target.id, name=payload.name, strategy=payload.strategy,
        ring_seconds=payload.ring_seconds, no_answer_target_id=payload.no_answer_target_id,
        callerid_prefix=payload.callerid_prefix,
        announcement_audio_id=announcement.id if announcement else None,
        ring_strategy_sound=payload.ring_strategy_sound,
        moh_class_id=moh_class.id if moh_class else None,
        alert_info=payload.alert_info, skip_busy_agent=payload.skip_busy_agent,
        confirm_calls=payload.confirm_calls,
        remote_announce_audio_id=remote_announce.id if remote_announce else None,
        recording_policy=payload.recording_policy,
    )
    _replace_members(group, payload.members)
    session.add(group)
    await session.flush()
    if payload.number:
        await set_dial_number(session, tenant_id, str(target.id), payload.number)

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="ring_group.create",
                        entity="ring_group", entity_id=str(group.id), diff={"name": payload.name})
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    group = await _get_rg_or_404(session, tenant_id, str(group.id))
    return RingGroupMutated(item=await _rg_out(session, tenant_id, group), apply=apply_result.to_dict())


async def _apply_rg_name(session: AsyncSession, group: RingGroup, payload: UpdateRingGroupPayload, diff: dict) -> None:
    if payload.name is None:
        return
    group.name = payload.name
    await rename_target(session, str(group.target_id), payload.name)
    diff["name"] = payload.name


def _apply_simple_rg_fields(group: RingGroup, payload: UpdateRingGroupPayload, diff: dict) -> None:
    """Oddiy skalyar maydonlar — alohida validatsiya kerak emas (CRAP pasaytirish,
    queues.py'dagi `_apply_simple_queue_fields` namunasi bo'yicha)."""
    for field in (
        "strategy", "ring_seconds", "callerid_prefix", "ring_strategy_sound",
        "skip_busy_agent", "confirm_calls", "recording_policy",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(group, field, value)
            diff[field] = value


async def _apply_rg_alert_info(group: RingGroup, payload: UpdateRingGroupPayload, diff: dict) -> None:
    if payload.alert_info_clear:
        group.alert_info = None
        diff["alert_info"] = None
    elif payload.alert_info is not None:
        group.alert_info = payload.alert_info
        diff["alert_info"] = payload.alert_info


async def _apply_rg_moh_class(
    session: AsyncSession, tenant_id: str, group: RingGroup, payload: UpdateRingGroupPayload, diff: dict,
) -> None:
    if payload.moh_class_id_clear:
        group.moh_class_id = None
        diff["moh_class_id"] = None
    elif payload.moh_class_id is not None:
        moh_class = await _resolve_moh_class(session, tenant_id, payload.moh_class_id)
        group.moh_class_id = moh_class.id if moh_class else None
        diff["moh_class_id"] = payload.moh_class_id


async def _apply_rg_audio_fk(
    session: AsyncSession, tenant_id: str, group: RingGroup, payload: UpdateRingGroupPayload, diff: dict,
    *, payload_field: str,
) -> None:
    """2 audio FK (e'lon/uzoqdan e'lon) — BITTA yo'l (dryer, `queues.py`
    `_apply_queue_audio_fk` naqshi; bu yerda `payload_field == model_field`)."""
    if getattr(payload, f"{payload_field}_clear"):
        setattr(group, payload_field, None)
        diff[payload_field] = None
        return
    audio_id = getattr(payload, payload_field)
    if audio_id is not None:
        audio = await _resolve_audio(session, tenant_id, audio_id)
        setattr(group, payload_field, audio.id if audio else None)
        diff[payload_field] = audio_id


async def _apply_rg_no_answer_target(
    session: AsyncSession, tenant_id: str, group: RingGroup, payload: UpdateRingGroupPayload, diff: dict,
) -> None:
    if payload.no_answer_target_id is None:
        return
    if await resolve_target(session, tenant_id, payload.no_answer_target_id) is None:
        raise ApiError(422, "invalid_target", "Noto'g'ri manzil", field="no_answer_target_id")
    group.no_answer_target_id = payload.no_answer_target_id
    diff["no_answer_target_id"] = payload.no_answer_target_id


async def _apply_rg_members(
    session: AsyncSession, tenant_id: str, group: RingGroup, payload: UpdateRingGroupPayload, diff: dict,
) -> None:
    if payload.members is None:
        return
    # ESLATMA: bu yerda ilgari mavjud bo'lmagan `_validate_extension_ids` chaqirilardi
    # (hech qanday testda `members`ni PATCH qilish tekshirilmagan edi — shu sabab
    # NameError sezilmay qolgan; to'g'ri nom — pastdagi `_validate_members`, 0038).
    await _validate_members(session, tenant_id, payload.members)
    _replace_members(group, payload.members)
    diff["members"] = len(payload.members)


async def _apply_rg_number(
    session: AsyncSession, tenant_id: str, group: RingGroup, payload: UpdateRingGroupPayload, diff: dict,
) -> None:
    if payload.number is None:
        return
    if payload.number:
        await ensure_number_free(session, tenant_id, payload.number, exclude_target_id=str(group.target_id))
    await set_dial_number(session, tenant_id, str(group.target_id), payload.number)
    diff["number"] = payload.number


@router.patch("/{rg_id}", response_model=RingGroupMutated)
async def update_ring_group(
    rg_id: str, payload: UpdateRingGroupPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> RingGroupMutated:
    tenant_id = str(user.tenant_id)
    group = await _get_rg_or_404(session, tenant_id, rg_id)
    check_not_stale(group.updated_at, payload.updated_at)

    diff: dict = {}
    await _apply_rg_name(session, group, payload, diff)
    _apply_simple_rg_fields(group, payload, diff)
    await _apply_rg_no_answer_target(session, tenant_id, group, payload, diff)
    await _apply_rg_members(session, tenant_id, group, payload, diff)
    await _apply_rg_number(session, tenant_id, group, payload, diff)
    await _apply_rg_alert_info(group, payload, diff)
    await _apply_rg_moh_class(session, tenant_id, group, payload, diff)
    await _apply_rg_audio_fk(session, tenant_id, group, payload, diff, payload_field="announcement_audio_id")
    await _apply_rg_audio_fk(session, tenant_id, group, payload, diff, payload_field="remote_announce_audio_id")

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="ring_group.update",
                        entity="ring_group", entity_id=str(group.id), diff=diff)
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    group = await _get_rg_or_404(session, tenant_id, str(group.id))
    return RingGroupMutated(item=await _rg_out(session, tenant_id, group), apply=apply_result.to_dict())


@router.delete("/{rg_id}", status_code=204, response_model=None)
async def delete_ring_group(
    rg_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
    ami=Depends(get_ami),
) -> None:
    tenant_id = str(user.tenant_id)
    group = await _get_rg_or_404(session, tenant_id, rg_id)
    usages = await usages_for_target(session, tenant_id, str(group.target_id))
    if usages:
        raise ApiError(409, "in_use", "Qo'ng'iroq guruhi ishlatilmoqda", details={"usages": usages})

    await delete_satellite_and_target(session, group, str(group.target_id))
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="ring_group.delete",
                        entity="ring_group", entity_id=str(rg_id))
    await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
