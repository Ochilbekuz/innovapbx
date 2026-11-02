"""Ovozli pochta qutilari — m1c-contract.md §2. CRUD + xabarlar.

Quti yaratilganda `call_targets(kind='voicemail')` ham yaratiladi (IVR /
marshrut / ext `no_answer` maqsadi). Ichki raqamga bog'langan quti
yaratilsa va ext'ning `no_answer` maqsadi bo'sh bo'lsa — u shu qutiga
qo'yiladi (ext kartasidagi «Ovozli pochta yoqish»); quti o'chirilsa
tozalanadi. Asterisk'ga yetkazish — `apply_config()` (dialplan) +
`apply_voicemail()` (`voicemail_innova.conf`, MOH bilan bir xil qolip).

Xabarlar spool'dan O'QILADI; «eshitildi»/o'chirish — AMI orqali
(`app/services/voicemail.py` docstringi). Xabar havolasi faqat
`INBOX|Old/msgNNNN` — boshqa har qanday shakl 404 (path traversal yo'q)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_admin
from app.core.errors import ApiError
from app.core.lookups import get_tenant_code, get_tenant_scoped_or_404
from app.core.optimistic import check_not_stale
from app.core.security import hash_password
from app.db.models import AudioFile, CallTarget, Extension, User, VoicemailBox
from app.schemas import ApplyResult
from app.schemas_voicemail import (
    CreateVoicemailBoxPayload,
    UpdateVoicemailBoxPayload,
    VoicemailBoxMutated,
    VoicemailBoxOut,
    VoicemailCounts,
    VoicemailExtensionRef,
    VoicemailGreetingRef,
    VoicemailMessageOut,
)
from app.services import voicemail as vm
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.numbers import ensure_number_free
from app.services.usages import usages_for_target

router = APIRouter(prefix="/voicemail-boxes", tags=["voicemail"])

_NOT_FOUND = "Ovozli pochta qutisi topilmadi"
_MSG_NOT_FOUND = ApiError(404, "not_found", "Xabar topilmadi")
# PATCH'da oddiy (tekshiruvsiz) ko'chiriladigan maydonlar.
_SIMPLE_FIELDS = ("email", "email_notify", "telegram_notify", "telegram_chat_id", "attach_audio")


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _mailbox_taken(field: str) -> ApiError:
    return ApiError(409, "mailbox_taken", "Bu quti raqami band", field=field)


def _box_out(box: VoicemailBox, tenant_code: str) -> VoicemailBoxOut:
    ext = box.extension
    return VoicemailBoxOut(
        id=str(box.id), mailbox=box.mailbox,
        extension=VoicemailExtensionRef(id=str(ext.id), number=ext.number, name=ext.name) if ext else None,
        email=box.email, email_notify=box.email_notify, telegram_notify=box.telegram_notify,
        telegram_chat_id=box.telegram_chat_id, attach_audio=box.attach_audio,
        greeting=VoicemailGreetingRef(id=str(box.greeting.id), name=box.greeting.name) if box.greeting else None,
        has_pin=bool(box.pin_hash),
        counts=VoicemailCounts(**vm.count_messages(vm.box_dir(tenant_code, box.mailbox))),
        updated_at=box.updated_at,
    )


async def _get_box_or_404(session: AsyncSession, tenant_id: str, box_id: str, *, fresh: bool = False) -> VoicemailBox:
    if fresh:
        # `expire_on_commit=False` — trigger yangilagan `updated_at` va
        # o'zgargan bog'lanishlar (greeting/extension) qayta o'qiladi.
        valid = (await get_tenant_scoped_or_404(session, VoicemailBox, tenant_id, box_id,
                                                not_found_message=_NOT_FOUND)).id
        return (await session.execute(
            select(VoicemailBox).where(VoicemailBox.id == valid).execution_options(populate_existing=True)
        )).scalar_one()
    return await get_tenant_scoped_or_404(session, VoicemailBox, tenant_id, box_id, not_found_message=_NOT_FOUND)


async def _check_greeting(session: AsyncSession, tenant_id: str, audio_id: str | None) -> None:
    if audio_id is not None:
        await get_tenant_scoped_or_404(session, AudioFile, tenant_id, audio_id,
                                       not_found_message="Audio topilmadi", field="greeting_audio_id")


async def apply_dialplan_and_voicemail(session: AsyncSession, tenant_id: str, user: User, ami) -> ApplyResult:
    """Dialplan + voicemail.conf — yozuvchi endpoint'lar uchun bitta qolip.
    Voicemail yetkazilmasa 502 (`moh_classes._apply_moh_or_502` bilan bir xil)."""
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    tenant_code = await get_tenant_code(session, tenant_id)
    try:
        await vm.apply_voicemail(session, tenant_id=tenant_id, tenant_code=tenant_code, ami=ami)
    except Exception as exc:  # noqa: BLE001 — aniq xato xabari bilan 502
        raise ApiError(502, "voicemail_sync_failed", f"Ovozli pochta Asterisk'ga yetkazilmadi: {exc}"[:500]) from exc
    return ApplyResult(**apply_result.to_dict())


async def _resolve_owner(session: AsyncSession, tenant_id: str,
                         payload: CreateVoicemailBoxPayload) -> tuple[Extension | None, str]:
    """(ext, mailbox). Umumiy quti raqami mavjud ichki raqam/navbat/guruh/IVR/vaqt sharti/
    konferensiya raqami (`numbers.ensure_number_free` — BIR XIL umumiy yordamchi, dryer) bilan
    bir xil bo'lishi mumkin emas — aks holda o'sha raqam keyin ikki ma'noda ishlatiladi (1.0.4 §2)."""
    if payload.extension_id is not None:
        ext = await get_tenant_scoped_or_404(session, Extension, tenant_id, payload.extension_id,
                                             not_found_message="Ichki raqam topilmadi", field="extension_id")
        return ext, ext.number
    await ensure_number_free(session, tenant_id, payload.mailbox, field="mailbox")
    return None, payload.mailbox


@router.get("")
async def list_boxes(
    extension_id: str | None = None, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> dict:
    tenant_id = str(user.tenant_id)
    stmt = select(VoicemailBox).where(VoicemailBox.tenant_id == tenant_id).order_by(VoicemailBox.mailbox)
    if extension_id is not None:
        if not _is_uuid(extension_id):
            return {"items": []}
        stmt = stmt.where(VoicemailBox.extension_id == extension_id)
    code = await get_tenant_code(session, tenant_id)
    boxes = (await session.execute(stmt)).scalars().all()
    return {"items": [_box_out(b, code) for b in boxes]}


@router.post("", response_model=VoicemailBoxMutated, status_code=201)
async def create_box(
    payload: CreateVoicemailBoxPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin), ami=Depends(get_ami),
) -> VoicemailBoxMutated:
    tenant_id = str(user.tenant_id)
    ext, mailbox = await _resolve_owner(session, tenant_id, payload)
    await _check_greeting(session, tenant_id, payload.greeting_audio_id)

    target = CallTarget(tenant_id=tenant_id, kind="voicemail", label=f"Ovozli pochta · {mailbox}")
    session.add(target)
    await session.flush()
    fields = {f: getattr(payload, f) for f in _SIMPLE_FIELDS if getattr(payload, f) is not None}
    box = VoicemailBox(tenant_id=tenant_id, target_id=target.id, extension_id=ext.id if ext else None,
                       mailbox=mailbox, pin_hash=hash_password(payload.pin),
                       greeting_audio_id=payload.greeting_audio_id, **fields)
    session.add(box)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise _mailbox_taken("extension_id" if ext else "mailbox") from exc
    if ext is not None and ext.no_answer_target_id is None:
        ext.no_answer_target_id = target.id

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="voicemail.create",
                       entity="voicemail_box", entity_id=str(box.id),
                       diff={"mailbox": mailbox, "pin": payload.pin, **fields})
    apply_result = await apply_dialplan_and_voicemail(session, tenant_id, user, ami)
    await session.commit()
    box = await _get_box_or_404(session, tenant_id, str(box.id), fresh=True)
    return VoicemailBoxMutated(item=_box_out(box, await get_tenant_code(session, tenant_id)), apply=apply_result)


@router.patch("/{box_id}", response_model=VoicemailBoxMutated)
async def update_box(
    box_id: str, payload: UpdateVoicemailBoxPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin), ami=Depends(get_ami),
) -> VoicemailBoxMutated:
    tenant_id = str(user.tenant_id)
    box = await _get_box_or_404(session, tenant_id, box_id)
    check_not_stale(box.updated_at, payload.updated_at)

    given = payload.model_fields_set
    diff: dict = {f: getattr(payload, f) for f in _SIMPLE_FIELDS if f in given}
    for field_name, value in diff.items():
        setattr(box, field_name, value)
    if "greeting_audio_id" in given:
        await _check_greeting(session, tenant_id, payload.greeting_audio_id)
        box.greeting_audio_id = payload.greeting_audio_id
        diff["greeting_audio_id"] = payload.greeting_audio_id
    if payload.pin is not None:
        box.pin_hash = hash_password(payload.pin)
        diff["pin"] = payload.pin

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="voicemail.update",
                       entity="voicemail_box", entity_id=str(box.id), diff=diff)
    apply_result = await apply_dialplan_and_voicemail(session, tenant_id, user, ami)
    await session.commit()
    box = await _get_box_or_404(session, tenant_id, box_id, fresh=True)
    return VoicemailBoxMutated(item=_box_out(box, await get_tenant_code(session, tenant_id)), apply=apply_result)


async def delete_box_and_target(session: AsyncSession, tenant_id: str, box: VoicemailBox) -> None:
    """409 `in_use` tekshiruvi (o'z ext'ining `no_answer` maqsadi bundan
    mustasno — u avtomatik tozalanadi), keyin quti + `call_targets`.
    `extensions.delete_extension` ham shuni chaqiradi (yetim manzil qolmasin)."""
    target_id = str(box.target_id)
    usages = [u for u in await usages_for_target(session, tenant_id, target_id)
              if not (u["kind"] == "extension" and u["id"] == str(box.extension_id))]
    if usages:
        raise ApiError(409, "in_use", f"«{box.mailbox}» qutisi hali ishlatilmoqda", details={"usages": usages})
    ext = box.extension
    if ext is not None and str(ext.no_answer_target_id) == target_id:
        ext.no_answer_target_id = None
    await session.delete(box)
    target = await session.get(CallTarget, target_id)
    if target is not None:
        await session.delete(target)
    await session.flush()


@router.delete("/{box_id}", status_code=204, response_model=None)
async def delete_box(
    box_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
    ami=Depends(get_ami),
) -> None:
    tenant_id = str(user.tenant_id)
    box = await _get_box_or_404(session, tenant_id, box_id)
    mailbox = box.mailbox
    await delete_box_and_target(session, tenant_id, box)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="voicemail.delete",
                       entity="voicemail_box", entity_id=str(box_id), diff={"mailbox": mailbox})
    await apply_dialplan_and_voicemail(session, tenant_id, user, ami)
    await session.commit()
    vm.remove_box_dir(await get_tenant_code(session, tenant_id), mailbox)


# ------------------------------------------------------------ xabarlar
async def _box_spool(session: AsyncSession, user: User, box_id: str) -> tuple[VoicemailBox, str]:
    tenant_id = str(user.tenant_id)
    box = await _get_box_or_404(session, tenant_id, box_id)
    return box, await get_tenant_code(session, tenant_id)


async def _message_or_404(session: AsyncSession, user: User, box_id: str,
                          msg: str) -> tuple[VoicemailBox, str, vm.MessagePaths]:
    box, code = await _box_spool(session, user, box_id)
    paths = vm.message_paths(vm.box_dir(code, box.mailbox), msg)
    if paths is None:
        raise _MSG_NOT_FOUND
    return box, code, paths


@router.get("/{box_id}/messages")
async def list_box_messages(
    box_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> dict:
    box, code = await _box_spool(session, user, box_id)
    items = vm.list_messages(vm.box_dir(code, box.mailbox))
    return {"items": [VoicemailMessageOut(**{k: v for k, v in i.items() if k != "msg_id"}) for i in items]}


@router.get("/{box_id}/messages/{msg:path}/audio")
async def message_audio(
    box_id: str, msg: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> FileResponse:
    box, _, paths = await _message_or_404(session, user, box_id, msg)
    if not paths.wav.is_file():
        raise ApiError(404, "not_found", "Xabar audio fayli topilmadi")
    return FileResponse(paths.wav, media_type="audio/wav", filename=f"{box.mailbox}-{paths.wav.stem}.wav")


async def _ami_or_502(coro) -> None:
    try:
        await coro
    except Exception as exc:  # noqa: BLE001
        raise ApiError(502, "voicemail_action_failed", f"Asterisk amalni bajarmadi: {exc}"[:500]) from exc


@router.post("/{box_id}/messages/{msg:path}/heard", status_code=204, response_model=None)
async def mark_heard(
    box_id: str, msg: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
    ami=Depends(get_ami),
) -> None:
    box, code, paths = await _message_or_404(session, user, box_id, msg)
    if paths.folder == "INBOX":
        await _ami_or_502(vm.ami_mark_heard(ami, code, box.mailbox, paths.folder, paths.msg_id))


@router.delete("/{box_id}/messages/{msg:path}", status_code=204, response_model=None)
async def delete_message(
    box_id: str, msg: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
    ami=Depends(get_ami),
) -> None:
    box, code, paths = await _message_or_404(session, user, box_id, msg)
    await _ami_or_502(vm.ami_remove(ami, code, box.mailbox, paths.folder, paths.msg_id))
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id), action="voicemail.delete",
                       entity="voicemail_message", entity_id=str(box.id), diff={"message": msg})
    await session.commit()
