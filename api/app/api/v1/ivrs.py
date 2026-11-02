"""IVR (ovozli menyu) — m1a-contract.md «IVR (S09)»."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_ami, get_session, require_access
from app.core.errors import ApiError
from app.core.ids import parse_uuid
from app.core.optimistic import check_not_stale
from app.db.models import AudioFile, Ivr, IvrOption, User
from app.schemas import (
    AudioOut,
    CreateIvrPayload,
    IvrMutated,
    IvrOptionOut,
    IvrOut,
    UpdateIvrPayload,
)
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.numbers import dial_number_for_target, ensure_number_free, set_dial_number
from app.services.target_resolution import create_target, delete_satellite_and_target, rename_target, resolve_target
from app.services.usages import usages_for_target

router = APIRouter(prefix="/ivrs", tags=["ivrs"])

_IVR_OPTIONS = (selectinload(Ivr.options),)


def _audio_out(audio: AudioFile) -> AudioOut:
    return AudioOut(id=str(audio.id), name=audio.name, duration_ms=audio.duration_ms,
                     format="wav", created_at=audio.created_at)


async def _get_audio_or_422(session: AsyncSession, tenant_id: str, audio_id: str, field: str) -> AudioFile:
    audio = (await session.execute(
        select(AudioFile).where(AudioFile.tenant_id == tenant_id, AudioFile.id == audio_id)
    )).scalar_one_or_none()
    if audio is None:
        raise ApiError(422, "invalid_audio", "Noto'g'ri audio", field=field)
    return audio


async def _validate_options(session: AsyncSession, tenant_id: str, options: list) -> None:
    digits = [o.digit for o in options]
    if len(digits) != len(set(digits)):
        raise ApiError(422, "duplicate_digit", "Raqam birdan ortiq marta ishlatilgan", field="options")
    for opt in options:
        if await resolve_target(session, tenant_id, opt.target_id) is None:
            raise ApiError(422, "invalid_target", "Noto'g'ri manzil", field=f"options.{opt.digit}")


def _replace_options(ivr: Ivr, options: list) -> None:
    """To'g'ridan-to'g'ri ro'yxat biriktirish — `.clear()+.append()` o'rniga, chunki
    bo'sh/eski to'plamga `.clear()` chaqirish kolleksiyani "yuklangan" deb belgilamay
    qoldirishi mumkin (SQLAlchemy'ning identity map xususiyati) va keyinroq shu so'rov
    doirasida qayta o'qishda `selectinload` allaqachon "yuklangan" kolleksiyani e'tiborsiz
    qoldiradi — natijada javobda/snapshot'da options bo'sh ko'rinadi. To'g'ridan-to'g'ri
    biriktirish har doim kolleksiyani "yuklangan" deb belgilaydi."""
    ivr.options = [IvrOption(digit=opt.digit, target_id=opt.target_id) for opt in options]


async def _ivr_out(session: AsyncSession, tenant_id: str, ivr: Ivr) -> IvrOut:
    greeting = await session.get(AudioFile, ivr.greeting_audio_id)
    invalid_audio = await session.get(AudioFile, ivr.invalid_audio_id) if ivr.invalid_audio_id else None
    timeout_target = await resolve_target(session, tenant_id, str(ivr.timeout_target_id))
    invalid_target = await resolve_target(session, tenant_id, str(ivr.invalid_target_id))
    number = await dial_number_for_target(session, tenant_id, str(ivr.target_id))
    options = []
    for opt in ivr.options:
        target = await resolve_target(session, tenant_id, str(opt.target_id))
        options.append(IvrOptionOut(digit=opt.digit, target=target))
    return IvrOut(
        id=str(ivr.id), name=ivr.name, number=number, greeting=_audio_out(greeting),
        invalid_audio=_audio_out(invalid_audio) if invalid_audio else None,
        timeout_seconds=ivr.timeout_seconds, repeats=ivr.repeats, direct_dial=ivr.direct_dial,
        options=options, timeout_target=timeout_target, invalid_target=invalid_target,
        updated_at=ivr.updated_at,
    )


async def _get_ivr_or_404(session: AsyncSession, tenant_id: str, ivr_id: str) -> Ivr:
    valid_id = parse_uuid(ivr_id, not_found_message="IVR topilmadi")
    ivr = (await session.execute(
        select(Ivr).where(Ivr.tenant_id == tenant_id, Ivr.id == valid_id).options(*_IVR_OPTIONS)
    )).scalar_one_or_none()
    if ivr is None:
        raise ApiError(404, "not_found", "IVR topilmadi")
    return ivr


@router.get("")
async def list_ivrs(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> dict:
    items = (await session.execute(
        select(Ivr).where(Ivr.tenant_id == user.tenant_id).order_by(Ivr.name).options(*_IVR_OPTIONS)
    )).scalars().all()
    return {"items": [await _ivr_out(session, str(user.tenant_id), i) for i in items]}


async def _validate_create_ivr_payload(session: AsyncSession, tenant_id: str, payload: CreateIvrPayload) -> None:
    """`create_ivr`'ning barcha kirish tekshiruvlari — alohida (CRAP pasaytirish,
    har bir tekshiruv mustaqil sinalishi mumkin)."""
    await _get_audio_or_422(session, tenant_id, payload.greeting_audio_id, "greeting_audio_id")
    if payload.invalid_audio_id:
        await _get_audio_or_422(session, tenant_id, payload.invalid_audio_id, "invalid_audio_id")
    for field in ("timeout_target_id", "invalid_target_id"):
        if await resolve_target(session, tenant_id, getattr(payload, field)) is None:
            raise ApiError(422, "invalid_target", "Noto'g'ri manzil", field=field)
    await _validate_options(session, tenant_id, payload.options)
    if payload.number:
        await ensure_number_free(session, tenant_id, payload.number)


@router.post("", response_model=IvrMutated, status_code=201)
async def create_ivr(
    payload: CreateIvrPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> IvrMutated:
    tenant_id = str(user.tenant_id)
    await _validate_create_ivr_payload(session, tenant_id, payload)

    target = await create_target(session, tenant_id, "ivr", payload.name)
    ivr = Ivr(
        tenant_id=tenant_id, target_id=target.id, name=payload.name,
        greeting_audio_id=payload.greeting_audio_id, invalid_audio_id=payload.invalid_audio_id,
        timeout_seconds=payload.timeout_seconds, repeats=payload.repeats, direct_dial=payload.direct_dial,
        timeout_target_id=payload.timeout_target_id, invalid_target_id=payload.invalid_target_id,
    )
    _replace_options(ivr, payload.options)
    session.add(ivr)
    await session.flush()
    if payload.number:
        await set_dial_number(session, tenant_id, str(target.id), payload.number)

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="ivr.create",
                        entity="ivr", entity_id=str(ivr.id), diff={"name": payload.name})
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    ivr = await _get_ivr_or_404(session, tenant_id, str(ivr.id))
    return IvrMutated(item=await _ivr_out(session, tenant_id, ivr), apply=apply_result.to_dict())


async def _apply_ivr_name(session: AsyncSession, ivr: Ivr, payload: UpdateIvrPayload, diff: dict) -> None:
    if payload.name is None:
        return
    ivr.name = payload.name
    await rename_target(session, str(ivr.target_id), payload.name)
    diff["name"] = payload.name


async def _apply_ivr_audio_fields(
    session: AsyncSession, tenant_id: str, ivr: Ivr, payload: UpdateIvrPayload, diff: dict,
) -> None:
    if payload.greeting_audio_id is not None:
        await _get_audio_or_422(session, tenant_id, payload.greeting_audio_id, "greeting_audio_id")
        ivr.greeting_audio_id = payload.greeting_audio_id
        diff["greeting_audio_id"] = payload.greeting_audio_id
    if payload.invalid_audio_id is not None:
        await _get_audio_or_422(session, tenant_id, payload.invalid_audio_id, "invalid_audio_id")
        ivr.invalid_audio_id = payload.invalid_audio_id
        diff["invalid_audio_id"] = payload.invalid_audio_id


def _apply_simple_ivr_fields(ivr: Ivr, payload: UpdateIvrPayload, diff: dict) -> None:
    """Oddiy skalyar maydonlar — alohida validatsiya kerak emas (CRAP pasaytirish,
    queues.py'dagi `_apply_simple_queue_fields` namunasi bo'yicha)."""
    for field in ("timeout_seconds", "repeats", "direct_dial"):
        value = getattr(payload, field)
        if value is not None:
            setattr(ivr, field, value)
            diff[field] = value


async def _apply_ivr_target_fields(
    session: AsyncSession, tenant_id: str, ivr: Ivr, payload: UpdateIvrPayload, diff: dict,
) -> None:
    for field in ("timeout_target_id", "invalid_target_id"):
        value = getattr(payload, field)
        if value is None:
            continue
        if await resolve_target(session, tenant_id, value) is None:
            raise ApiError(422, "invalid_target", "Noto'g'ri manzil", field=field)
        setattr(ivr, field, value)
        diff[field] = value


async def _apply_ivr_options(
    session: AsyncSession, tenant_id: str, ivr: Ivr, payload: UpdateIvrPayload, diff: dict,
) -> None:
    if payload.options is None:
        return
    await _validate_options(session, tenant_id, payload.options)
    _replace_options(ivr, payload.options)
    diff["options"] = len(payload.options)


async def _apply_ivr_number(
    session: AsyncSession, tenant_id: str, ivr: Ivr, payload: UpdateIvrPayload, diff: dict,
) -> None:
    if payload.number is None:
        return
    if payload.number:
        await ensure_number_free(session, tenant_id, payload.number, exclude_target_id=str(ivr.target_id))
    await set_dial_number(session, tenant_id, str(ivr.target_id), payload.number)
    diff["number"] = payload.number


@router.patch("/{ivr_id}", response_model=IvrMutated)
async def update_ivr(
    ivr_id: str, payload: UpdateIvrPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> IvrMutated:
    tenant_id = str(user.tenant_id)
    ivr = await _get_ivr_or_404(session, tenant_id, ivr_id)
    check_not_stale(ivr.updated_at, payload.updated_at)

    diff: dict = {}
    await _apply_ivr_name(session, ivr, payload, diff)
    await _apply_ivr_audio_fields(session, tenant_id, ivr, payload, diff)
    _apply_simple_ivr_fields(ivr, payload, diff)
    await _apply_ivr_target_fields(session, tenant_id, ivr, payload, diff)
    await _apply_ivr_options(session, tenant_id, ivr, payload, diff)
    await _apply_ivr_number(session, tenant_id, ivr, payload, diff)

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="ivr.update",
                        entity="ivr", entity_id=str(ivr.id), diff=diff)
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    ivr = await _get_ivr_or_404(session, tenant_id, str(ivr.id))
    return IvrMutated(item=await _ivr_out(session, tenant_id, ivr), apply=apply_result.to_dict())


@router.delete("/{ivr_id}", status_code=204, response_model=None)
async def delete_ivr(
    ivr_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
    ami=Depends(get_ami),
) -> None:
    tenant_id = str(user.tenant_id)
    ivr = await _get_ivr_or_404(session, tenant_id, ivr_id)
    usages = await usages_for_target(session, tenant_id, str(ivr.target_id))
    if usages:
        raise ApiError(409, "in_use", "IVR ishlatilmoqda", details={"usages": usages})

    await delete_satellite_and_target(session, ivr, str(ivr.target_id))
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="ivr.delete",
                        entity="ivr", entity_id=str(ivr_id))
    await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
