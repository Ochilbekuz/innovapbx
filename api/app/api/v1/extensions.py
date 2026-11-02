"""Ichki raqamlar — m0-contract.md «Ichki raqamlar (S04)»."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_access
from app.api.v1.voicemail_boxes import apply_dialplan_and_voicemail, delete_box_and_target
from app.core.errors import ApiError
from app.core.lookups import get_tenant_code, get_tenant_scoped_or_404
from app.core.optimistic import check_not_stale
from app.core.security import generate_sip_secret
from app.db.models import CallTarget, Extension, SystemSettings, User, VoicemailBox
from app.schemas import (
    CreateExtensionPayload,
    ExtensionCreated,
    ExtensionMutated,
    ExtensionOut,
    Paged,
    RotateSecretResult,
    SetSecretPayload,
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
from app.services.sip_identity import endpoint_id
from app.services.sip_secret_policy import validate_sip_password
from app.services.usages import usages_for_target
from app.services.voicemail import remove_box_dir

router = APIRouter(prefix="/extensions", tags=["extensions"])

_NUMBER_RANGE = range(100, 1000)

# M2a §1: realtime maydonlar (Asterisk `asterisk_ext_state`/`ps_endpoints` view'laridan o'qiydi) —
# faqat ular o'zgarsa apply/reload kerak emas.
# M3a §2: `webrtc`/`codecs` ham — `ps_endpoints` view'i (sorcery realtime, keshsiz) darhol ko'radi.
# M3b/M3c §1: `recording`/`recording_out` — dialplan `innova-rec` realtime o'qiydi.
_REALTIME_FIELDS = frozenset({
    "dnd", "forward_always", "forward_busy", "pickup_group", "webrtc", "codecs", "recording", "recording_out",
})
_KEEP_IF_NONE = ("name", "enabled", "outbound_allowed", "outbound_callerid", "dnd", "recording")
_CLEARABLE = ("forward_always", "forward_busy", "pickup_group")  # aniq null/"" = tozalash
# Tuzatish (a): dialplan `_X.` patterni "+" bilan mos kelmaydi — kirishda
# `normalize_number()` bilan bir xil qoida (boshidagi "+" ham olib tashlanadi).
_FORWARD_RE = re.compile(r"^[0-9]{2,15}$")
_PICKUP_GROUP_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
_REALTIME_APPLY = {"status": "applied", "revision": None, "message": None}


async def _sip_credentials(session: AsyncSession, request: Request, tenant_id: str, number: str,
                           password: str) -> SipCredentials:
    """Yagona joy — `SipCredentials` qurilishi (create/rotate-secret/set-secret BIR XIL, dryer).
    `username` — ichki raqamning o'zi (`sip_identity.endpoint_id`); `domain` — so'rov host'i
    (port'siz); `port` — `SystemSettings.sip_udp_port` (sozlanmagan bo'lsa 5060, `devices.py`
    `server_port()` bilan bir xil qoida)."""
    row = await session.get(SystemSettings, tenant_id)
    port = (row.sip_udp_port if row else None) or 5060
    return SipCredentials(username=endpoint_id(number), password=password,
                          domain=request.url.hostname or "", port=port)


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
        recording=getattr(ext, "recording", None) or "always",
        recording_in=getattr(ext, "recording", None) or "always",
        recording_out=getattr(ext, "recording_out", None) or "always",
        updated_at=ext.updated_at,
    )


async def _bulk_extension_out(ami, items: list[Extension]) -> list[ExtensionOut]:
    # m-sip-login-plain-number: endpoint id endi tenant-kod prefiksisiz (sip_identity.endpoint_id).
    if not items:
        return []
    states = await endpoint_states(ami, [e.number for e in items])
    return [_ext_out(ext, states.get(ext.number)) for ext in items]


@router.get("", response_model=Paged)
async def list_extensions(
    q: str | None = None, page: int = 1, size: int = 50,
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
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
    return Paged(items=await _bulk_extension_out(ami, items), total=total)


def new_extension(*, codecs: list[str] | None, **fields) -> Extension:
    """Yangi raqam; `codecs=None` — DB standarti (ustun default) saqlanadi."""
    ext = Extension(**fields)
    if codecs is not None:
        ext.codecs = codecs
    return ext


@router.post("", response_model=ExtensionCreated, status_code=201)
async def create_extension(
    payload: CreateExtensionPayload, request: Request, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> ExtensionCreated:
    codecs = resolve_codecs(webrtc=payload.webrtc, requested=payload.codecs, current=None,
                            switching_on=payload.webrtc)  # 422 — DB'ga tegmasdan oldin
    number = payload.number or await _next_free_number(session, str(user.tenant_id))
    # M2a: dial_numbers (IVR/navbat/guruh raqami) va park raqamlari (700–720) bilan ham to'qnashmasin.
    await ensure_number_free(session, str(user.tenant_id), number)
    # Admin PATCH bilan BIR XIL tekshiruv (dryer) — yoziluvdan OLDIN (422 hech narsaga tegmaydi).
    changes = _requested_changes(payload)
    _validate_call_fields(changes, number)

    if payload.password:
        validate_sip_password(payload.password, number)  # 422 `weak_password`
        secret = payload.password
    else:
        secret = generate_sip_secret()
    secret_enc = await encrypt_secret(session, secret)

    target = CallTarget(tenant_id=user.tenant_id, kind="extension", label=f"{number} · {payload.name}")
    session.add(target)
    await session.flush()

    ext = new_extension(tenant_id=user.tenant_id, target_id=target.id, number=number, name=payload.name,
                        sip_password_enc=secret_enc, webrtc=payload.webrtc, codecs=codecs)
    settings_diff = _apply_changes(ext, changes)
    session.add(ext)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "number_taken", "Bu raqam band", field="number") from exc

    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="extension.create", entity="extension", entity_id=str(ext.id),
                        diff={"number": number, "name": payload.name, "webrtc": payload.webrtc, **settings_diff})
    apply_result = await apply_config(session, tenant_id=str(user.tenant_id), user_id=str(user.id), ami=ami)
    await session.commit()

    sip = await _sip_credentials(session, request, str(ext.tenant_id), ext.number, secret)
    return ExtensionCreated(item=_ext_out(ext), sip=sip, apply=apply_result.to_dict())


_NORMALIZED = ("forward_always", "forward_busy")  # tuzatish (a): bitta normalizatsiya — number_normalize.py


def _recording_changes(payload) -> dict:
    """M3c §1 — BITTA birlashtirish qoidasi (create VA update shu funksiyani chaqiradi):
    eski `recording` berilsa IKKALASINI ham o'rnatadi (orqaga moslik — FreePBX import,
    public/fake API); aniq `recording_in`/`recording_out` berilsa ular ustun turadi."""
    legacy = getattr(payload, "recording", None)
    rec_in = getattr(payload, "recording_in", None) or legacy
    rec_out = getattr(payload, "recording_out", None) or legacy
    changes: dict = {}
    if rec_in is not None:
        changes["recording"] = rec_in
    if rec_out is not None:
        changes["recording_out"] = rec_out
    return changes


def _requested_changes(
    payload, *, keep_if_none: tuple[str, ...] = _KEEP_IF_NONE, clearable: tuple[str, ...] = _CLEARABLE,
) -> dict:
    """Berilgan maydonlar: `keep_if_none` — null = o'zgarmaydi; `clearable` — kalit bor bo'lsa, null/"" = tozalash.
    Maydon to'plami parametr qilingan — operator `/me/extension` (§4) FAQAT `dnd`/`forward_always`/
    `forward_busy` to'plamini beradi, admin esa to'liq to'plamni (sukut). `recording` — alohida
    (ikki ustunga yoziladi, `_recording_changes`); `keep_if_none`da bo'lmasa operator uni o'zgartira olmaydi."""
    plain_fields = tuple(f for f in keep_if_none if f != "recording")
    changes = {f: getattr(payload, f, None) for f in plain_fields if getattr(payload, f, None) is not None}
    if "recording" in keep_if_none:
        changes.update(_recording_changes(payload))
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


async def _voicemail_box_for_extension(session: AsyncSession, ext_id: str) -> VoicemailBox | None:
    """Ext'ga bog'langan quti (bo'lsa) — `delete_extension` VA `update_extension` BIR XIL
    so'rov (dryer): quti bor bo'lsa dialplan BILAN BIRGA `voicemail.conf` ham yetkaziladi
    (aks holda ext nomi o'zgarsa quti `fullname`i eskirib qoladi)."""
    return (await session.execute(
        select(VoicemailBox).where(VoicemailBox.extension_id == ext_id))).scalar_one_or_none()


async def _apply_extension_config(session: AsyncSession, tenant_id: str, user: User, ami, ext_id: str) -> dict:
    """Ichki raqamning to'liq (realtime bo'lmagan) qayta qo'llanishi: quti bor bo'lsa
    `voicemail.conf` ham (fullname eskirmasin), bo'lmasa oddiy dialplan apply."""
    box = await _voicemail_box_for_extension(session, ext_id)
    if box is not None:
        return (await apply_dialplan_and_voicemail(session, tenant_id, user, ami)).model_dump()
    return (await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)).to_dict()


@router.patch("/{ext_id}", response_model=ExtensionMutated)
async def update_extension(
    ext_id: str, payload: UpdateExtensionPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
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
        apply = await _apply_extension_config(session, str(user.tenant_id), user, ami, ext.id)
    await session.commit()

    return ExtensionMutated(item=_ext_out(ext), apply=apply)


async def _finish_secret_change(
    session: AsyncSession, ami, request: Request, user: User, ext: Extension, secret: str, *, action: str,
) -> RotateSecretResult:
    """`rotate-secret` VA `PUT .../secret` uchun BIR XIL yakunlash qadami (dryer):
    shifrlash, audit, commit, qurilma NOTIFY, `SipCredentials`."""
    ext.sip_password_enc = await encrypt_secret(session, secret)
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action=action, entity="extension", entity_id=str(ext.id))
    await session.commit()

    tenant_code = await get_tenant_code(session, ext.tenant_id)
    # M4a §2: biriktirilgan apparatlarga check-sync NOTIFY (xato jim — parol baribir almashgan)
    await notify_extension_devices(session, ami, ext, tenant_code)
    sip = await _sip_credentials(session, request, str(ext.tenant_id), ext.number, secret)
    return RotateSecretResult(sip=sip, apply={"status": "realtime", "revision": None, "message": None})


@router.post("/{ext_id}/rotate-secret", response_model=RotateSecretResult)
async def rotate_secret(
    ext_id: str, request: Request, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> RotateSecretResult:
    ext = await _get_extension_or_404(session, str(user.tenant_id), ext_id)
    secret = generate_sip_secret()
    return await _finish_secret_change(session, ami, request, user, ext, secret,
                                       action="extension.rotate_secret")


@router.put("/{ext_id}/secret", response_model=RotateSecretResult)
async def set_secret(
    ext_id: str, payload: SetSecretPayload, request: Request, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> RotateSecretResult:
    """Foydalanuvchi o'zi tanlagan SIP paroli (FreePBX-uslubida) — `rotate-secret`dan farqli,
    tasodifiy EMAS, qoida bo'yicha (`sip_secret_policy.validate_sip_password`) tekshiriladi."""
    ext = await _get_extension_or_404(session, str(user.tenant_id), ext_id)
    validate_sip_password(payload.password, ext.number)
    return await _finish_secret_change(session, ami, request, user, ext, payload.password,
                                       action="extension.set_secret")


@router.delete("/{ext_id}", status_code=204, response_model=None)
async def delete_extension(
    ext_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
    ami=Depends(get_ami),
) -> None:
    ext = await _get_extension_or_404(session, str(user.tenant_id), ext_id)
    # Barcha RESTRICT havolalar (marshrut, IVR tugmasi, vaqt sharti, navbat...) — aks holda FK 500.
    usages = await usages_for_target(session, str(user.tenant_id), str(ext.target_id))
    if usages:
        raise ApiError(409, "in_use", "Ichki raqam ishlatilmoqda", details={"usages": usages})

    # M1c: ext'ning ovozli pochta qutisi (FK CASCADE) bilan birga uning
    # `call_targets` yozuvi ham o'chirilsin — aks holda yetim manzil qoladi.
    box = await _voicemail_box_for_extension(session, ext.id)
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
