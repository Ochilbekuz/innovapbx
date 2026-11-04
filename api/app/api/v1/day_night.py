"""M12 A1 — Kun/Tun rejimi (Call Flow Control). `*28<code>` funksiya kodi
+ BLF — `app/services/compiler.py::_day_night_toggle_lines`/`_day_night_dest_lines`
(holat PG'da, dialplan CURL orqali reload'siz o'qiydi/yozadi).

PIN HECH QACHON ochiq qaytmaydi/saqlanmaydi — faqat `has_pin`
(`VoicemailBoxOut.has_pin`/`OutboundRouteOut.has_pin` BILAN BIR XIL qolip),
HMAC-SHA256 (`pin_hmac.py`, `pin_sets` BILAN BIR XIL usul)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_access
from app.api.v1.feature_codes import feature_code_strings
from app.core.config import settings
from app.core.errors import ApiError
from app.core.ids import parse_uuid
from app.core.optimistic import check_not_stale
from app.db.models import DayNight, User
from app.schemas import CreateDayNightPayload, DayNightMutated, DayNightOut, UpdateDayNightPayload
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.feature_codes import validate_feature_code
from app.services.pin_hmac import hash_pin
from app.services.target_resolution import create_target, delete_satellite_and_target, rename_target, resolve_target
from app.services.usages import usages_for_target

router = APIRouter(prefix="/day-night", tags=["day-night"])

_NOT_FOUND = "Kun/tun rejimi topilmadi"


async def _out(session: AsyncSession, tenant_id: str, item: DayNight) -> DayNightOut:
    day_target = await resolve_target(session, tenant_id, str(item.day_target_id))
    night_target = await resolve_target(session, tenant_id, str(item.night_target_id))
    return DayNightOut(
        id=str(item.id), name=item.name, code=item.code, mode=item.mode,
        day_target=day_target, night_target=night_target, has_pin=item.pin_hmac is not None,
        updated_at=item.updated_at,
    )


async def _get_or_404(session: AsyncSession, tenant_id: str, row_id: str) -> DayNight:
    valid_id = parse_uuid(row_id, not_found_message=_NOT_FOUND)
    item = (await session.execute(
        select(DayNight).where(DayNight.tenant_id == tenant_id, DayNight.id == valid_id)
    )).scalar_one_or_none()
    if item is None:
        raise ApiError(404, "not_found", _NOT_FOUND)
    return item


async def _validate_target(session: AsyncSession, tenant_id: str, target_id: str, field: str) -> None:
    if await resolve_target(session, tenant_id, target_id) is None:
        raise ApiError(422, "invalid_target", "Noto'g'ri manzil", field=field)


async def _validate_exten_code(session: AsyncSession, tenant_id: str, code: str) -> None:
    """`*28<code>` boshqa funksiya kodi bilan to'qnashmasin — `time_conditions.py`
    `_validate_toggle_code` BILAN BIR XIL qoida/funksiya (`validate_feature_code`)."""
    exten = f"*28{code}"
    validate_feature_code(exten, await feature_code_strings(session, tenant_id))


async def _flush_unique(session: AsyncSession) -> None:
    """`unique (tenant_id, code)` / `unique (tenant_id, name)` buzilishi 500 emas,
    aniq 409 bo'lsin (parallel so'rov poygasi ham shu yerga tushadi)."""
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        field = "code" if "code" in str(exc.orig) else "name"
        message = "Bu kod band" if field == "code" else "Bu nom band"
        raise ApiError(409, f"{field}_taken", message, field=field) from exc


@router.get("")
async def list_day_night(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> dict:
    items = (await session.execute(
        select(DayNight).where(DayNight.tenant_id == user.tenant_id).order_by(DayNight.code)
    )).scalars().all()
    return {"items": [await _out(session, str(user.tenant_id), item) for item in items]}


@router.post("", response_model=DayNightMutated, status_code=201)
async def create_day_night(
    payload: CreateDayNightPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> DayNightMutated:
    tenant_id = str(user.tenant_id)
    await _validate_target(session, tenant_id, payload.day_target_id, "day_target_id")
    await _validate_target(session, tenant_id, payload.night_target_id, "night_target_id")
    await _validate_exten_code(session, tenant_id, payload.code)

    target = await create_target(session, tenant_id, "day_night", payload.name)
    pin_hmac = hash_pin(settings.require_secret_key(), payload.pin) if payload.pin else None
    row = DayNight(
        tenant_id=tenant_id, target_id=target.id, name=payload.name, code=payload.code,
        day_target_id=payload.day_target_id, night_target_id=payload.night_target_id, pin_hmac=pin_hmac,
    )
    session.add(row)
    await _flush_unique(session)

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="day_night.create",
                        entity="day_night", entity_id=str(row.id), diff={"name": payload.name, "code": payload.code})
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    row = await _get_or_404(session, tenant_id, str(row.id))
    return DayNightMutated(item=await _out(session, tenant_id, row), apply=apply_result.to_dict())


@router.patch("/{row_id}", response_model=DayNightMutated)
async def update_day_night(
    row_id: str, payload: UpdateDayNightPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> DayNightMutated:
    tenant_id = str(user.tenant_id)
    row = await _get_or_404(session, tenant_id, row_id)
    check_not_stale(row.updated_at, payload.updated_at)

    diff: dict = {}
    if payload.name is not None:
        row.name = payload.name
        await rename_target(session, str(row.target_id), payload.name)
        diff["name"] = payload.name
    if payload.code is not None and payload.code != row.code:
        await _validate_exten_code(session, tenant_id, payload.code)
        row.code = payload.code
        diff["code"] = payload.code
    if payload.day_target_id is not None:
        await _validate_target(session, tenant_id, payload.day_target_id, "day_target_id")
        row.day_target_id = payload.day_target_id
        diff["day_target_id"] = payload.day_target_id
    if payload.night_target_id is not None:
        await _validate_target(session, tenant_id, payload.night_target_id, "night_target_id")
        row.night_target_id = payload.night_target_id
        diff["night_target_id"] = payload.night_target_id
    if payload.pin_clear:
        row.pin_hmac = None
        diff["pin"] = "***"
    elif payload.pin is not None:
        row.pin_hmac = hash_pin(settings.require_secret_key(), payload.pin)
        diff["pin"] = "***"

    await _flush_unique(session)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="day_night.update",
                        entity="day_night", entity_id=str(row.id), diff=diff)
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    row = await _get_or_404(session, tenant_id, str(row.id))
    return DayNightMutated(item=await _out(session, tenant_id, row), apply=apply_result.to_dict())


@router.post("/{row_id}/toggle", response_model=DayNightMutated)
async def toggle_day_night(
    row_id: str, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> DayNightMutated:
    """Veb-UI orqali — autentifikatsiya/`routing:edit` ruxsati PIN o'rnini
    bosadi (PIN faqat telefon funksiya kodi `*28<code>` uchun, login talab
    qilinmaydigan yo'l). BLF chirog'i — ma'lum cheklov: ushbu veb-orqali
    almashtirish uchun darhol YANGILANMAYDI (keyingi telefon-orqali
    almashtirish/qayta obuna bo'lishigacha), chaqiruv yo'naltirishiga ta'sir
    qilmaydi (`_day_night_dest_lines` doim jonli CURL o'qiydi)."""
    tenant_id = str(user.tenant_id)
    row = await _get_or_404(session, tenant_id, row_id)
    row.mode = "night" if row.mode == "day" else "day"
    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="day_night.toggle",
                        entity="day_night", entity_id=str(row.id), diff={"mode": row.mode})
    # Dialplan holatni har qo'ng'iroqda CURL bilan O'QIYDI -- reload shart emas,
    # faqat BLF/boshqa dialplan o'zgarishlari (manzil almashtirish) bo'lsa kerak.
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    return DayNightMutated(item=await _out(session, tenant_id, row), apply=apply_result.to_dict())


@router.delete("/{row_id}", status_code=204, response_model=None)
async def delete_day_night(
    row_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
    ami=Depends(get_ami),
) -> None:
    tenant_id = str(user.tenant_id)
    row = await _get_or_404(session, tenant_id, row_id)
    usages = await usages_for_target(session, tenant_id, str(row.target_id))
    if usages:
        raise ApiError(409, "in_use", "Kun/tun rejimi ishlatilmoqda", details={"usages": usages})

    await delete_satellite_and_target(session, row, str(row.target_id))
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="day_night.delete",
                        entity="day_night", entity_id=str(row_id))
    await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
