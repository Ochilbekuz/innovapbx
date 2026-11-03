"""Operator portali — `/me` (m2b-contract.md §4, S30).

Ruxsat: faqat `get_current_user` (admin HAM, agar o'z ichki raqami bo'lsa,
shu yo'lni ishlatadi) — alohida ruxsat tekshiruvi SHART emas
(`app/core/permissions.py` `ME_ALL` izohiga qarang, `web/src/api/fake.ts`
bilan bir xil). Ichki raqami yo'q foydalanuvchiga `GET /me/overview`
`extension:null, queues:[]` qaytaradi; QOLGAN barcha `/me/*` 409
`no_extension` ko'taradi.

Dryer — mavjud xizmatlar qayta ishlatiladi, ikkinchi mustaqil mantiq YO'Q:
- `app.api.v1.extensions.apply_call_field_patch` — admin PATCH bilan BITTA funksiya;
- `app.api.v1.queues._member_action(..., source="portal")` — §1 navbat xizmati;
- `app.api.v1.calls._build_calls_query/_filter_own_calls/_paginate` — tarix;
- `app.api.v1.voicemail_boxes.*` — xabarlar (quti faqat o'zinikiga cheklanadi);
- `app.api.v1.users._user_out` — `UserOut` shakli (§3 bilan AYNAN bir xil)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_ami, get_current_user, get_session
from app.api.v1.auth import _is_locked, _register_failed_login
from app.api.v1.calls import _build_calls_query, _filter_own_calls, paginate_with_recordings
from app.api.v1.extensions import apply_call_field_patch
from app.api.v1.qa import _evaluation_out
from app.api.v1.queues import MemberAction, _get_queue_or_404, _member_action
from app.api.v1.users import _user_out as _managed_user_out
from app.api.v1.voicemail_boxes import delete_message, list_box_messages, mark_heard, message_audio
from app.core.errors import ApiError
from app.core.optimistic import check_not_stale
from app.db.models import Cdr, Extension, QaEvaluation, Queue, QueueMember, User, VoicemailBox
from app.schemas import CallDirection, QueueMemberActionPayload
from app.schemas_2fa import (
    TotpDisablePayload,
    TotpEnableOut,
    TotpEnablePayload,
    TotpRecoveryCodesOut,
    TotpSetupOut,
)
from app.schemas_qa import QaEvaluationsOut
from app.schemas_users import (
    MeExtensionMutated,
    MeExtensionOut,
    MeOverviewOut,
    MeQueueActionMutated,
    MeQueueOut,
    MeToday,
    PatchMeExtensionPayload,
)
from app.services.audit import record_audit
from app.services.cdr_grouping import calls_from_rows
from app.services.crypto import decrypt_secret, encrypt_secret
from app.services.dashboard import today_bounds_utc
from app.services.numbers import dial_number_for_target
from app.services.tokens import revoke_refresh_tokens
from app.services.totp import generate_recovery_codes, generate_secret, otpauth_uri, verify as totp_verify
from app.services.totp_auth import hash_recovery_codes, verify_user_code

router = APIRouter(prefix="/me", tags=["me"])

_NOT_ENABLED = ApiError(409, "not_enabled", "2FA yoqilmagan")
_SETUP_REQUIRED = ApiError(409, "setup_required", "Avval /me/2fa/setup chaqiring")
_INVALID_2FA_CODE = ApiError(401, "invalid_code", "Kod noto'g'ri")
_ALREADY_ENABLED = ApiError(409, "already_enabled", "2FA allaqachon yoqilgan — avval o'chiring")
_LOCKED = ApiError(423, "locked", "Hisob vaqtincha bloklangan — keyinroq urining")

_NO_EXTENSION_MSG = "Sizda ichki raqam yo'q"


def _no_extension() -> ApiError:
    return ApiError(409, "no_extension", _NO_EXTENSION_MSG)


def _require_own_extension(user: User) -> Extension:
    """`GET /me/overview`dan BOSHQA barcha `/me/*` shu orqali o'tadi —
    ichki raqam yo'q bo'lsa 409 `no_extension`."""
    if user.extension is None:
        raise _no_extension()
    return user.extension


def _ext_out(ext: Extension, voicemail_box_id: str | None) -> MeExtensionOut:
    return MeExtensionOut(
        id=str(ext.id), number=ext.number, name=ext.name, dnd=ext.dnd,
        forward_always=ext.forward_always, forward_busy=ext.forward_busy,
        outbound_allowed=ext.outbound_allowed, voicemail_box_id=voicemail_box_id,
        updated_at=ext.updated_at,
    )


async def _own_voicemail_box(session: AsyncSession, tenant_id: str, ext_id: str) -> VoicemailBox | None:
    return (await session.execute(
        select(VoicemailBox).where(VoicemailBox.tenant_id == tenant_id, VoicemailBox.extension_id == ext_id)
    )).scalar_one_or_none()


async def _require_own_box(session: AsyncSession, user: User) -> VoicemailBox:
    """Ichki raqam bor-lekin qutisi yo'q holat HAM 409 `no_extension`
    (`web/src/api/fake.ts` `requireOwnVoicemailBox` bilan bir xil — alohida
    kod yo'q)."""
    ext = _require_own_extension(user)
    box = await _own_voicemail_box(session, str(user.tenant_id), str(ext.id))
    if box is None:
        raise _no_extension()
    return box


async def _queue_member_out(session: AsyncSession, tenant_id: str, queue: Queue, member: QueueMember) -> MeQueueOut:
    number = await dial_number_for_target(session, tenant_id, str(queue.target_id))
    return MeQueueOut(id=str(queue.id), name=queue.name, number=number, dynamic=member.dynamic,
                       logged_in=member.logged_in, paused=member.paused, pause_reason=member.pause_reason)


async def _my_queues(session: AsyncSession, tenant_id: str, ext_id: str) -> list[MeQueueOut]:
    """Ichki raqam a'zo bo'lgan navbatlar ro'yxati — §1dagi yuklash
    (`selectinload`) qolipi bilan BIR XIL, faqat shu ext bo'yicha filtr."""
    rows = (await session.execute(
        select(Queue).where(Queue.tenant_id == tenant_id).order_by(Queue.name)
        .options(selectinload(Queue.members).selectinload(QueueMember.extension))
    )).scalars().all()
    out: list[MeQueueOut] = []
    for q in rows:
        member = next((m for m in q.members if str(m.extension_id) == ext_id), None)
        if member is not None:
            out.append(await _queue_member_out(session, tenant_id, q, member))
    return out


async def _today_stats(session: AsyncSession, user: User, number: str) -> MeToday:
    """m2b-contract.md §4: bugungi `{answered, missed, talk_seconds}` — o'z
    ichki raqami bo'yicha. Sana oynasi `/dashboard` bilan BIR XIL funksiya
    (`app.services.dashboard.today_bounds_utc`) — faqat tenant-keng emas,
    bitta ichki raqamga filtrlanadi (dryer: oyna hisoblash takrorlanmaydi)."""
    tenant = user.tenant
    start, end = today_bounds_utc(tenant.timezone, datetime.now(timezone.utc))
    rows = (await session.execute(
        select(Cdr).where(Cdr.accountcode == tenant.code, Cdr.calldate >= start, Cdr.calldate < end)
    )).scalars().all()
    calls = _filter_own_calls(calls_from_rows(list(rows)), number)
    return MeToday(
        answered=sum(1 for c in calls if c.disposition == "answered"),
        missed=sum(1 for c in calls if c.disposition == "no_answer"),
        talk_seconds=sum(c.billsec for c in calls),
    )


@router.get("/overview", response_model=MeOverviewOut)
async def my_overview(
    session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user),
) -> MeOverviewOut:
    ext = user.extension
    if ext is None:
        return MeOverviewOut(user=_managed_user_out(user), extension=None, queues=[],
                              today=MeToday(answered=0, missed=0, talk_seconds=0))

    tenant_id = str(user.tenant_id)
    box = await _own_voicemail_box(session, tenant_id, str(ext.id))
    queues = await _my_queues(session, tenant_id, str(ext.id))
    today = await _today_stats(session, user, ext.number)
    return MeOverviewOut(
        user=_managed_user_out(user), extension=_ext_out(ext, str(box.id) if box else None),
        queues=queues, today=today,
    )


@router.patch("/extension", response_model=MeExtensionMutated)
async def patch_my_extension(
    payload: PatchMeExtensionPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> MeExtensionMutated:
    ext = _require_own_extension(user)
    check_not_stale(ext.updated_at, payload.updated_at)

    # Tekshiruv + normalizatsiya — admin `PATCH /extensions/{id}` bilan
    # BITTA funksiya (dryer, `app/api/v1/extensions.py`), faqat 3 maydon.
    diff = apply_call_field_patch(ext, payload, keep_if_none=("dnd",), clearable=("forward_always", "forward_busy"))

    await session.flush()
    await session.refresh(ext)  # updated_at — DB trigeri yangilaydi
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="extension.update", entity="extension", entity_id=str(ext.id), diff=diff)
    await session.commit()
    # Barcha maydonlar (`dnd`/`forward_*`) realtime — m2b-contract.md §4
    # "realtime (apply yo'q)": `apply_config()` chaqirilmaydi, javobda `apply` yo'q.
    box = await _own_voicemail_box(session, str(user.tenant_id), str(ext.id))
    return MeExtensionMutated(item=_ext_out(ext, str(box.id) if box else None))


@router.post("/queues/{queue_id}/{action}", response_model=MeQueueActionMutated)
async def act_on_my_queue(
    queue_id: str, action: MemberAction, payload: QueueMemberActionPayload = QueueMemberActionPayload(),
    session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user), ami=Depends(get_ami),
) -> MeQueueActionMutated:
    """Operator o'zini navbatga kiritadi/chiqaradi/pauza qiladi — §1 xizmatini
    (`app.services.queue_agents`) `source="portal"` bilan chaqiradi: admin
    bilan BIR XIL yo'l (`app.api.v1.queues._member_action`), ikkinchisi yo'q."""
    ext = _require_own_extension(user)
    tenant_id = str(user.tenant_id)
    await _member_action(session, user, queue_id, str(ext.id), action, payload, ami, source="portal")

    queue = await _get_queue_or_404(session, tenant_id, queue_id)
    member = next((m for m in queue.members if str(m.extension_id) == str(ext.id)), None)
    if member is None:
        raise ApiError(404, "not_found", "Navbat a'zosi topilmadi", field="extension_id")
    return MeQueueActionMutated(item=await _queue_member_out(session, tenant_id, queue, member))


@router.get("/calls")
async def my_calls(
    from_: str | None = None, to: str | None = None, q: str | None = None, direction: CallDirection | None = None,
    page: int = 1, size: int = 50,
    session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user),
) -> dict:
    """Tarix — `app.api.v1.calls`dagi so'rov/filtr funksiyalari qayta
    ishlatiladi, FAQAT o'z ichki raqamiga cheklangan (admin kengaytmasi yo'q)."""
    ext = _require_own_extension(user)
    stmt = _build_calls_query(user.tenant.code, from_=from_, to=to, q=q)
    rows = (await session.execute(stmt)).scalars().all()
    calls = _filter_own_calls(calls_from_rows(list(rows)), ext.number)
    if direction:
        calls = [c for c in calls if c.direction == direction]
    return await paginate_with_recordings(session, str(user.tenant_id), calls, page, size)


@router.get("/voicemail")
async def my_voicemail(
    session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user),
) -> dict:
    box = await _require_own_box(session, user)
    return await list_box_messages(str(box.id), session=session, user=user)


@router.get("/voicemail/{msg:path}/audio")
async def my_voicemail_audio(
    msg: str, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user),
) -> FileResponse:
    box = await _require_own_box(session, user)
    return await message_audio(str(box.id), msg, session=session, user=user)


@router.post("/voicemail/{msg:path}/heard", status_code=204, response_model=None)
async def my_voicemail_heard(
    msg: str, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user),
    ami=Depends(get_ami),
) -> None:
    box = await _require_own_box(session, user)
    await mark_heard(str(box.id), msg, session=session, user=user, ami=ami)


@router.delete("/voicemail/{msg:path}", status_code=204, response_model=None)
async def my_voicemail_delete(
    msg: str, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user),
    ami=Depends(get_ami),
) -> None:
    box = await _require_own_box(session, user)
    await delete_message(str(box.id), msg, session=session, user=user, ami=ami)


# --------------------------------------------------------------------- B1: qa
@router.get("/evaluations", response_model=QaEvaluationsOut)
async def my_evaluations(
    page: int = 1, size: int = 50,
    session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user),
) -> QaEvaluationsOut:
    """Operator o'zining baholashlarini ko'radi (`evaluator_name` HAR DOIM
    `None` — kim baholaganini ko'rsatmaymiz, `/calls/{linkedid}/evaluations`
    bilan BIR XIL qoida)."""
    ext = _require_own_extension(user)
    rows = (await session.execute(
        select(QaEvaluation).where(QaEvaluation.tenant_id == user.tenant_id, QaEvaluation.extension_id == ext.id)
        .options(selectinload(QaEvaluation.checklist)).order_by(QaEvaluation.created_at.desc())
    )).scalars().all()
    total = len(rows)
    start = (page - 1) * size
    return QaEvaluationsOut(items=[_evaluation_out(r, None) for r in rows[start:start + size]], total=total)


# --------------------------------------------------------------------- B2: 2fa
async def _verify_2fa_code_or_raise(session: AsyncSession, user: User, code: str) -> None:
    """`disable`/`recovery-codes` uchun — `/auth/login/totp` bilan BIR XIL himoya
    (`auth.py._is_locked`/`_register_failed_login` qayta ishlatiladi, ikkinchi
    mustaqil hisoblagich YO'Q): qulflangan hisob rad etiladi, noto'g'ri kod HAR
    DOIM muvaffaqiyatsiz login sifatida hisoblanadi — aks holda sessiyasi
    o'g'irlangan (lekin parolni bilmaydigan) hujumchi TOTP/tiklash kodini
    cheksiz tera olardi."""
    if _is_locked(user):
        raise _LOCKED
    if not await verify_user_code(session, user, code):
        await _register_failed_login(session, user)
        await session.commit()
        raise _INVALID_2FA_CODE


@router.post("/2fa/setup", response_model=TotpSetupOut)
async def setup_2fa(
    session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user),
) -> TotpSetupOut:
    """Yangi (hali YOQILMAGAN) sekret — qayta chaqirilsa eskisi bekor bo'ladi
    (faqat `/me/2fa/enable` muvaffaqiyatli bo'lgani kuchda qoladi). 2FA
    ALLAQACHON yoqilgan bo'lsa rad etiladi (409) — aks holda joriy sessiyani
    (access token) o'g'irlagan hujumchi o'ZINING sekretini yozib qo'yib,
    egasi hali bilmay turib hisobni to'liq egallab olardi (`enable`da kod
    tekshiruvi bor, lekin sekret SHU YERDA, kodsiz, almashtirilardi)."""
    if user.totp_enabled_at is not None:
        raise _ALREADY_ENABLED
    secret = generate_secret()
    user.totp_secret_enc = await encrypt_secret(session, secret)
    await session.commit()
    return TotpSetupOut(secret=secret, otpauth_uri=otpauth_uri(secret, account=user.username))


@router.post("/2fa/enable", response_model=TotpEnableOut)
async def enable_2fa(
    payload: TotpEnablePayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> TotpEnableOut:
    if not user.totp_secret_enc:
        raise _SETUP_REQUIRED
    secret = await decrypt_secret(session, user.totp_secret_enc)
    now = int(datetime.now(timezone.utc).timestamp())
    step = totp_verify(secret, payload.code, now, last_step=user.totp_last_step)
    if step is None:
        raise _INVALID_2FA_CODE

    codes = generate_recovery_codes()
    user.totp_last_step = step
    user.totp_enabled_at = datetime.now(timezone.utc)
    user.totp_recovery_hashes = hash_recovery_codes(codes)
    # 2FA endi majburiy — boshqa joydagi (masalan o'g'irlangan) sessiyalar
    # qayta kirishga majburlansin (m2b-contract.md §3 bilan BIR XIL qoida:
    # xavfsizlik holati o'zgarsa — refresh tokenlar bekor).
    await revoke_refresh_tokens(session, str(user.id))
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="user.update", entity="user", entity_id=str(user.id), diff={"totp_enabled": True})
    await session.commit()
    return TotpEnableOut(recovery_codes=codes)


@router.post("/2fa/disable", status_code=204, response_model=None)
async def disable_2fa(
    payload: TotpDisablePayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> None:
    if user.totp_enabled_at is None:
        raise _NOT_ENABLED
    await _verify_2fa_code_or_raise(session, user, payload.code)

    user.totp_secret_enc = None
    user.totp_enabled_at = None
    user.totp_recovery_hashes = []
    user.totp_last_step = None
    await revoke_refresh_tokens(session, str(user.id))
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="user.update", entity="user", entity_id=str(user.id), diff={"totp_enabled": False})
    await session.commit()


@router.post("/2fa/recovery-codes", response_model=TotpRecoveryCodesOut)
async def regenerate_recovery_codes(
    payload: TotpDisablePayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> TotpRecoveryCodesOut:
    """Eski kodlar hammasi BEKOR qilinadi (yangi 10 ta bilan to'liq
    almashtiriladi) — qayta tasdiqlash uchun joriy kod (TOTP yoki eski
    tiklash kodi) talab qilinadi (`disable` bilan BIR XIL tekshiruv)."""
    if user.totp_enabled_at is None:
        raise _NOT_ENABLED
    await _verify_2fa_code_or_raise(session, user, payload.code)

    codes = generate_recovery_codes()
    user.totp_recovery_hashes = hash_recovery_codes(codes)
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="user.update", entity="user", entity_id=str(user.id),
                        diff={"totp_recovery_codes": "regenerated"})
    await session.commit()
    return TotpRecoveryCodesOut(recovery_codes=codes)
