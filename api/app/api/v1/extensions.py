"""Ichki raqamlar — m0-contract.md «Ichki raqamlar (S04)»."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_admin
from app.api.v1.voicemail_boxes import apply_dialplan_and_voicemail, delete_box_and_target
from app.core.errors import ApiError
from app.core.lookups import get_tenant_code, get_tenant_scoped_or_404
from app.core.optimistic import check_not_stale
from app.core.security import generate_sip_secret
from app.db.models import CallTarget, Extension, User, VoicemailBox
from app.schemas import (
    CreateExtensionPayload,
    ExtensionCreated,
    ExtensionMutated,
    ExtensionOut,
    Paged,
    RotateSecretResult,
    SipCredentials,
    UpdateExtensionPayload,
)
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.crypto import encrypt_secret
from app.services.devices import notify_extension_devices
from app.services.dialplan_features import is_park_number
from app.services.ext_media import resolve_codecs
from app.services.live_status import endpoint_states
from app.services.number_normalize import normalize_number
from app.services.numbers import ensure_number_free
from app.services.usages import usages_for_target
from app.services.voicemail import remove_box_dir

router = APIRouter(prefix="/extensions", tags=["extensions"])

_NUMBER_RANGE = range(100, 1000)

# M2a §1: realtime maydonlar (Asterisk `asterisk_ext_state`/`ps_endpoints` view'laridan o'qiydi) —
# faqat ular o'zgarsa apply/reload kerak emas.
# M3a §2: `webrtc`/`codecs` ham — `ps_endpoints` view'i (sorcery realtime, keshsiz) darhol ko'radi.
# M3b §1: `recording` — dialplan `innova-rec` realtime o'qiydi.
_REALTIME_FIELDS = frozenset({"dnd", "forward_always", "forward_busy", "pickup_group", "webrtc", "codecs", "recording"})
_KEEP_IF_NONE = ("name", "enabled", "outbound_allowed", "outbound_callerid", "dnd", "recording")
_CLEARABLE = ("forward_always", "forward_busy", "pickup_group")  # aniq null/"" = tozalash
# Tuzatish (a): dialplan `_X.` patterni "+" bilan mos kelmaydi — kirishda
# `normalize_number()` bilan bir xil qoida (boshidagi "+" ham olib tashlanadi).
_FORWARD_RE = re.compile(r"^[0-9]{2,15}$")
_PICKUP_GROUP_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
_REALTIME_APPLY = {"status": "applied", "revision": None, "message": None}


async def _next_free_number(session: AsyncSession, tenant_id: str) -> str:
    used = set((await session.execute(
        select(Extension.number).where(Extension.tenant_id == tenant_id))).scalars().all())
    for candidate in _NUMBER_RANGE:
        if str(candidate) not in used and not is_park_number(str(candidate)):
            return str(candidate)
    raise ApiError(409, "no_free_number", "Bo'sh ichki raqam qolmadi")


def _ext_out(ext: Extension, state: dict | None = None) -> ExtensionOut:
    """Yagona joy — `ExtensionOut` qurilishi (create/update/list bir xil bo'lsin, CRAP pasaytirish)."""
    state = state or {"status": "unknown", "contact": None, "user_agent": None}
    return ExtensionOut(
        id=str(ext.id), number=ext.number, name=ext.name, enabled=ext.enabled,
        status=state["status"], contact=state["contact"], user_agent=state["user_agent"],
        outbound_allowed=ext.outbound_allowed, outbound_callerid=ext.outbound_callerid,
        dnd=ext.dnd, forward_always=ext.forward_always, forward_busy=ext.forward_busy,
        pickup_group=ext.pickup_group, toll_blocked_at=ext.toll_blocked_at,
        toll_block_reason=ext.toll_block_reason, webrtc=ext.webrtc, codecs=list(ext.codecs or []),
        recording=getattr(ext, "recording", None) or "always", updated_at=ext.updated_at,
    )


async def _bulk_extension_out(session: AsyncSession, ami, items: list[Extension]) -> list[ExtensionOut]:
    if not items:
        return []
    code = await get_tenant_code(session, items[0].tenant_id)
    ids = [f"{code}-{e.number}" for e in items]
    states = await endpoint_states(ami, ids)
    return [_ext_out(ext, states.get(f"{code}-{ext.number}")) for ext in items]


@router.get("", response_model=Paged)
async def list_extensions(
    q: str | None = None, page: int = 1, size: int = 50,
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
    ami=Depends(get_ami),
) -> Paged:
    stmt = select(Extension).where(Extension.tenant_id == user.tenant_id)
    count_stmt = select(func.count()).select_from(Extension).where(Extension.tenant_id == user.tenant_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Extension.number.ilike(like)) | (Extension.name.ilike(like)))
        count_stmt = count_stmt.where((Extension.number.ilike(like)) | (Extension.name.ilike(like)))
    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(Extension.number).offset((page - 1) * size).limit(size)
    items = (await session.execute(stmt)).scalars().all()
    return Paged(items=await _bulk_extension_out(session, ami, items), total=total)


def new_extension(*, codecs: list[str] | None, **fields) -> Extension:
    """Yangi raqam; `codecs=None` — DB standarti (ustun default) saqlanadi."""
    ext = Extension(**fields)
    if codecs is not None:
        ext.codecs = codecs
    return ext


@router.post("", response_model=ExtensionCreated, status_code=201)
async def create_extension(
    payload: CreateExtensionPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin), ami=Depends(get_ami),
) -> ExtensionCreated:
    codecs = resolve_codecs(webrtc=payload.webrtc, requested=payload.codecs, current=None,
                            switching_on=payload.webrtc)  # 422 — DB'ga tegmasdan oldin
    number = payload.number or await _next_free_number(session, str(user.tenant_id))
    # M2a: dial_numbers (IVR/navbat/guruh raqami) va park raqamlari (700–720) bilan ham to'qnashmasin.
    await ensure_number_free(session, str(user.tenant_id), number)

    secret = generate_sip_secret()
    secret_enc = await encrypt_secret(session, secret)

    target = CallTarget(tenant_id=user.tenant_id, kind="extension", label=f"{number} · {payload.name}")
    session.add(target)
    await session.flush()

    ext = new_extension(tenant_id=user.tenant_id, target_id=target.id, number=number, name=payload.name,
                        sip_password_enc=secret_enc, webrtc=payload.webrtc, codecs=codecs)
    if payload.recording:
        ext.recording = payload.recording
    session.add(ext)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "number_taken", "Bu raqam band", field="number") from exc

    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="extension.create", entity="extension", entity_id=str(ext.id),
                        diff={"number": number, "name": payload.name, "webrtc": payload.webrtc})
    apply_result = await apply_config(session, tenant_id=str(user.tenant_id), user_id=str(user.id), ami=ami)
    await session.commit()

    tenant_code = await get_tenant_code(session, ext.tenant_id)
    sip = SipCredentials(username=f"{tenant_code}-{ext.number}", password=secret,
                          domain=tenant_code, port=5060)
    return ExtensionCreated(item=_ext_out(ext), sip=sip, apply=apply_result.to_dict())


_NORMALIZED = ("forward_always", "forward_busy")  # tuzatish (a): bitta normalizatsiya — number_normalize.py


def _requested_changes(
    payload, *, keep_if_none: tuple[str, ...] = _KEEP_IF_NONE, clearable: tuple[str, ...] = _CLEARABLE,
) -> dict:
    """Berilgan maydonlar: `keep_if_none` — null = o'zgarmaydi; `clearable` — kalit bor bo'lsa, null/"" = tozalash.
    Maydon to'plami parametr qilingan — operator `/me/extension` (§4) FAQAT `dnd`/`forward_always`/
    `forward_busy` to'plamini beradi, admin esa to'liq to'plamni (sukut)."""
    changes = {f: getattr(payload, f, None) for f in keep_if_none if getattr(payload, f, None) is not None}
    changes.update({f: getattr(payload, f) or None for f in clearable if f in payload.model_fields_set})
    for field in _NORMALIZED:
        if changes.get(field) is not None:
            changes[field] = normalize_number(changes[field])
    return changes


def _validate_call_fields(changes: dict, own_number: str) -> None:
    for field in ("forward_always", "forward_busy"):
        value = changes.get(field)
        if value is not None and (not _FORWARD_RE.fullmatch(value) or value == own_number):
            raise ApiError(422, "bad_number", "Yo'naltirish raqami noto'g'ri", field=field)
    group = changes.get("pickup_group")
    if group is not None and not _PICKUP_GROUP_RE.fullmatch(group):
        raise ApiError(422, "bad_pickup_group", "Pickup guruhi: a-z, 0-9, _ yoki -, 1–32 belgi",
                       field="pickup_group")


def _apply_changes(ext: Extension, changes: dict) -> dict:
    diff: dict = {}
    for field, value in changes.items():
        old = getattr(ext, field)
        if value != old:
            diff[field] = {"from": old, "to": value}
            setattr(ext, field, value)
    return diff


def apply_call_field_patch(
    ext: Extension, payload, *, keep_if_none: tuple[str, ...] = _KEEP_IF_NONE,
    clearable: tuple[str, ...] = _CLEARABLE,
) -> dict:
    """Tekshiruv + normalizatsiya + qo'llash — BITTA funksiya (m2b-contract.md §4: "admin PATCH
    bilan BIR XIL tekshiruv va normalizatsiya"). Admin `PATCH /extensions/{id}` VA operator
    `PATCH /me/extension` (`app/api/v1/me.py`) shu funksiyani chaqiradi — ikkinchi mustaqil
    mantiq YO'Q (dryer); farq faqat `keep_if_none`/`clearable` maydon to'plamida."""
    changes = _requested_changes(payload, keep_if_none=keep_if_none, clearable=clearable)
    _validate_call_fields(changes, ext.number)
    return _apply_changes(ext, changes)


def apply_media_patch(ext: Extension, payload: UpdateExtensionPayload) -> dict:
    """M3a §2: `webrtc`/`codecs` — qaror `resolve_codecs`da (yagona joy), bu yerda faqat qo'llash.
    Tekshiruv xatosi (422) hech narsa o'zgarmasdan oldin ko'tariladi."""
    webrtc = ext.webrtc if payload.webrtc is None else payload.webrtc
    codecs = resolve_codecs(webrtc=webrtc, requested=payload.codecs, current=ext.codecs,
                            switching_on=webrtc and not ext.webrtc)
    return _apply_changes(ext, {"webrtc": webrtc, "codecs": codecs})


async def _get_extension_or_404(session: AsyncSession, tenant_id: str, ext_id: str) -> Extension:
    return await get_tenant_scoped_or_404(
        session, Extension, tenant_id, ext_id, not_found_message="Ichki raqam topilmadi",
    )


@router.patch("/{ext_id}", response_model=ExtensionMutated)
async def update_extension(
    ext_id: str, payload: UpdateExtensionPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin), ami=Depends(get_ami),
) -> ExtensionMutated:
    ext = await _get_extension_or_404(session, str(user.tenant_id), ext_id)
    check_not_stale(ext.updated_at, payload.updated_at)

    media_diff = apply_media_patch(ext, payload)
    diff = {**apply_call_field_patch(ext, payload), **media_diff}

    await session.flush()
    await session.refresh(ext)  # updated_at — DB triggeri yangilaydi
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="extension.update", entity="extension", entity_id=str(ext.id), diff=diff)
    if diff and set(diff) <= _REALTIME_FIELDS:
        apply = dict(_REALTIME_APPLY)
    else:
        apply = (await apply_config(session, tenant_id=str(user.tenant_id), user_id=str(user.id), ami=ami)).to_dict()
    await session.commit()

    return ExtensionMutated(item=_ext_out(ext), apply=apply)


@router.post("/{ext_id}/rotate-secret", response_model=RotateSecretResult)
async def rotate_secret(
    ext_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
    ami=Depends(get_ami),
) -> RotateSecretResult:
    ext = await _get_extension_or_404(session, str(user.tenant_id), ext_id)
    secret = generate_sip_secret()
    ext.sip_password_enc = await encrypt_secret(session, secret)
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="extension.rotate_secret", entity="extension", entity_id=str(ext.id))
    await session.commit()

    tenant_code = await get_tenant_code(session, ext.tenant_id)
    # M4a §2: biriktirilgan apparatlarga check-sync NOTIFY (xato jim — parol baribir almashgan)
    await notify_extension_devices(session, ami, ext, tenant_code)
    sip = SipCredentials(username=f"{tenant_code}-{ext.number}", password=secret, domain=tenant_code, port=5060)
    return RotateSecretResult(sip=sip, apply={"status": "realtime", "revision": None, "message": None})


@router.delete("/{ext_id}", status_code=204, response_model=None)
async def delete_extension(
    ext_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
    ami=Depends(get_ami),
) -> None:
    ext = await _get_extension_or_404(session, str(user.tenant_id), ext_id)
    # Barcha RESTRICT havolalar (marshrut, IVR tugmasi, vaqt sharti, navbat...) — aks holda FK 500.
    usages = await usages_for_target(session, str(user.tenant_id), str(ext.target_id))
    if usages:
        raise ApiError(409, "in_use", "Ichki raqam ishlatilmoqda", details={"usages": usages})

    # M1c: ext'ning ovozli pochta qutisi (FK CASCADE) bilan birga uning
    # `call_targets` yozuvi ham o'chirilsin — aks holda yetim manzil qoladi.
    box = (await session.execute(
        select(VoicemailBox).where(VoicemailBox.extension_id == ext.id))).scalar_one_or_none()
    if box is not None:
        await delete_box_and_target(session, str(user.tenant_id), box)

    target_id = ext.target_id
    await session.delete(ext)
    target = await session.get(CallTarget, target_id)
    if target is not None:
        await session.delete(target)
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="extension.delete", entity="extension", entity_id=str(ext_id))
    if box is not None:
        await apply_dialplan_and_voicemail(session, str(user.tenant_id), user, ami)
    else:
        await apply_config(session, tenant_id=str(user.tenant_id), user_id=str(user.id), ami=ami)
    await session.commit()
    if box is not None:
        remove_box_dir(await get_tenant_code(session, str(user.tenant_id)), box.mailbox)
