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
from app.api.v1.calls import _build_calls_query, _filter_own_calls, paginate_with_recordings
from app.api.v1.extensions import apply_call_field_patch
from app.api.v1.queues import MemberAction, _get_queue_or_404, _member_action
from app.api.v1.users import _user_out as _managed_user_out
from app.api.v1.voicemail_boxes import delete_message, list_box_messages, mark_heard, message_audio
from app.core.errors import ApiError
from app.core.optimistic import check_not_stale
from app.db.models import Cdr, Extension, Queue, QueueMember, User, VoicemailBox
from app.schemas import CallDirection, QueueMemberActionPayload
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
from app.services.dashboard import today_bounds_utc
from app.services.numbers import dial_number_for_target

router = APIRouter(prefix="/me", tags=["me"])

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
