"""Navbatlar — m1a-contract.md «Navbatlar (S10)». Navbat/a'zolar Asterisk
realtime (`queues`/`queue_members` view) — yozuvdan keyin reload shart emas,
lekin boshqa manzillardan foydalanish uchun dialplan baribir qayta
kompilyatsiya qilinadi (Queue() nomi o'zgarmaydi, shu sabab bu amalda hech
narsani o'zgartirmaydi — faqat izchillik uchun chaqiriladi)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_ami, get_session, require_access
from app.core.errors import ApiError
from app.core.lookups import get_tenant_scoped_or_404
from app.core.optimistic import check_not_stale
from app.db.models import AudioFile, Extension, MohClass, Queue, QueueMember, Tenant, User
from app.schemas import (
    AddQueueMemberPayload,
    AudioOut,
    CreateQueuePayload,
    ExtensionRef,
    MohClassRef,
    QueueLive,
    QueueMemberActionPayload,
    QueueMemberMutated,
    QueueMemberOut,
    QueueMutated,
    QueueOut,
    UpdateQueueMemberPayload,
    UpdateQueuePayload,
)
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.live_status import queue_live_status
from app.services.numbers import dial_number_for_target, ensure_number_free, set_dial_number
from app.services.queue_agents import (
    login_member,
    logout_member,
    nudge_pause_state,
    pause_member,
    unpause_member,
)
from app.services.target_resolution import create_target, delete_satellite_and_target, rename_target, resolve_target
from app.services.usages import usages_for_target

router = APIRouter(prefix="/queues", tags=["queues"])

_Q_OPTIONS = (selectinload(Queue.members).selectinload(QueueMember.extension),)


async def _validate_member_payloads(session: AsyncSession, tenant_id: str, members: list) -> None:
    ext_ids = [m.extension_id for m in members]
    if not ext_ids:
        return
    found = {str(i) for i in (await session.execute(
        select(Extension.id).where(Extension.tenant_id == tenant_id, Extension.id.in_(ext_ids))
    )).scalars().all()}
    missing = [i for i in ext_ids if i not in found]
    if missing:
        raise ApiError(422, "invalid_target", "Noto'g'ri ichki raqam", field="members")


def _replace_members(queue: Queue, members: list) -> None:
    """To'g'ridan-to'g'ri ro'yxat biriktirish — `.clear()+.append()` o'rniga (bo'sh/eski
    kolleksiyaga `.clear()` uni "yuklangan" deb belgilamay qoldirishi mumkin, keyingi
    qayta o'qishda `selectinload` buni e'tiborsiz qoldiradi).

    OCHIQ MASALA (build-log.md'ga qarang): to'liq almashtirish `dynamic`/
    `logged_in`/`paused`/`state_at`ni HAM sukutga qaytaradi — a'zolar ro'yxati
    `members[]` bilan tahrirlangan navbatda agent holati yo'qoladi."""
    queue.members = [
        QueueMember(extension_id=m.extension_id, penalty=m.penalty, dynamic=m.dynamic) for m in members
    ]


def _member_out(m: QueueMember) -> QueueMemberOut:
    return QueueMemberOut(
        extension=ExtensionRef(id=str(m.extension.id), number=m.extension.number, name=m.extension.name),
        penalty=m.penalty, dynamic=m.dynamic, logged_in=m.logged_in, paused=m.paused,
        pause_reason=m.pause_reason, state_at=m.state_at,
    )


async def _get_member_or_404(session: AsyncSession, tenant_id: str, queue_id: str, extension_id: str) -> QueueMember:
    queue = await _get_queue_or_404(session, tenant_id, queue_id)
    member = next((m for m in queue.members if str(m.extension_id) == extension_id), None)
    if member is None:
        raise ApiError(404, "not_found", "Navbat a'zosi topilmadi", field="extension_id")
    return member


async def _resolve_moh_class(session: AsyncSession, tenant_id: str, moh_class_id: str | None) -> MohClass | None:
    """`moh_class_id` berilsa VA topilmasa 404 (`web/src/api/fake.ts`
    `resolveMohClass` bilan BIR XIL — `field: "moh_class_id"`)."""
    if moh_class_id is None:
        return None
    return await get_tenant_scoped_or_404(
        session, MohClass, tenant_id, moh_class_id,
        not_found_message="Kutish musiqasi sinfi topilmadi", field="moh_class_id",
    )


async def _resolve_audio(session: AsyncSession, tenant_id: str, audio_id: str | None) -> AudioFile | None:
    """`audio_id` berilsa VA topilmasa 422 (`_resolve_moh_class` bilan BIR XIL naqsh)."""
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


async def _resolve_breakout_target(session: AsyncSession, tenant_id: str, target_id: str | None) -> str | None:
    """IVR orqali chiqish (`context=`) — 0037: generik `call_targets` FK
    (`breakout_target_id`), xuddi `timeout_target_id` kabi, biroq MAJBURIY EMAS."""
    if target_id is None:
        return None
    if await resolve_target(session, tenant_id, target_id) is None:
        raise ApiError(422, "invalid_target", "Noto'g'ri IVR chiqish manzili", field="breakout_target_id")
    return target_id


async def _queue_out(session: AsyncSession, tenant_id: str, tenant_code: str, queue: Queue, ami) -> QueueOut:
    number = await dial_number_for_target(session, tenant_id, str(queue.target_id))
    timeout_target = await resolve_target(session, tenant_id, str(queue.timeout_target_id))
    breakout_target = (
        await resolve_target(session, tenant_id, str(queue.breakout_target_id))
        if queue.breakout_target_id else None
    )
    members = [_member_out(m) for m in queue.members if m.extension is not None]
    live_raw = await queue_live_status(ami, f"{tenant_code}-q-{queue.id}")
    live = QueueLive(**live_raw) if live_raw is not None else None
    moh_class = MohClassRef(id=str(queue.moh_class.id), name=queue.moh_class.name) if queue.moh_class else None
    return QueueOut(
        id=str(queue.id), name=queue.name, number=number, strategy=queue.strategy,
        agent_ring_seconds=queue.agent_ring_seconds, retry_seconds=queue.retry_seconds,
        wrapup_seconds=queue.wrapup_seconds, max_wait_seconds=queue.max_wait_seconds,
        max_callers=queue.max_callers, announce_position=queue.announce_position,
        announce_frequency_seconds=queue.announce_frequency_seconds, sla_seconds=queue.sla_seconds,
        join_empty=queue.join_empty, record=queue.record, members=members, timeout_target=timeout_target,
        live=live, moh_class=moh_class, updated_at=queue.updated_at,
        skip_busy_agents=queue.skip_busy_agents, weight=queue.weight, autofill=queue.autofill,
        report_hold_time=queue.report_hold_time, member_delay_seconds=queue.member_delay_seconds,
        penalty_members_limit=queue.penalty_members_limit, auto_pause=queue.auto_pause,
        auto_pause_delay_seconds=queue.auto_pause_delay_seconds, auto_pause_busy=queue.auto_pause_busy,
        auto_pause_unavail=queue.auto_pause_unavail, agent_timeout_restart=queue.agent_timeout_restart,
        max_wait_mode=queue.max_wait_mode, leave_when_empty=queue.leave_when_empty,
        announce_position_limit=queue.announce_position_limit, announce_hold_time=queue.announce_hold_time,
        min_announce_frequency_seconds=queue.min_announce_frequency_seconds,
        periodic_announce_frequency_seconds=queue.periodic_announce_frequency_seconds,
        ring_mode=queue.ring_mode, mark_answered_elsewhere=queue.mark_answered_elsewhere,
        cid_name_prefix=queue.cid_name_prefix, alert_info=queue.alert_info,
        periodic_announce_audio=_audio_ref(queue.periodic_announce_audio),
        join_announcement_audio=_audio_ref(queue.join_announcement_audio),
        agent_announcement_audio=_audio_ref(queue.agent_announcement_audio),
        breakout_target=breakout_target,
    )


async def _get_queue_or_404(session: AsyncSession, tenant_id: str, queue_id: str) -> Queue:
    return await get_tenant_scoped_or_404(
        session, Queue, tenant_id, queue_id, not_found_message="Navbat topilmadi", options=_Q_OPTIONS,
    )


async def _tenant_code(session: AsyncSession, tenant_id: str) -> str:
    tenant = await session.get(Tenant, tenant_id)
    return tenant.code


@router.get("")
async def list_queues(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access), ami=Depends(get_ami),
) -> dict:
    tenant_id = str(user.tenant_id)
    code = await _tenant_code(session, tenant_id)
    items = (await session.execute(
        select(Queue).where(Queue.tenant_id == tenant_id).order_by(Queue.name).options(*_Q_OPTIONS)
    )).scalars().all()
    return {"items": [await _queue_out(session, tenant_id, code, q, ami) for q in items]}


async def _validate_create_queue_payload(session: AsyncSession, tenant_id: str, payload: CreateQueuePayload) -> None:
    """`create_queue`'ning barcha kirish tekshiruvlari — alohida (CRAP pasaytirish)."""
    if await resolve_target(session, tenant_id, payload.timeout_target_id) is None:
        raise ApiError(422, "invalid_target", "Noto'g'ri manzil", field="timeout_target_id")
    await _validate_member_payloads(session, tenant_id, payload.members)
    if payload.number:
        await ensure_number_free(session, tenant_id, payload.number)


@router.post("", response_model=QueueMutated, status_code=201)
async def create_queue(
    payload: CreateQueuePayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> QueueMutated:
    tenant_id = str(user.tenant_id)
    await _validate_create_queue_payload(session, tenant_id, payload)
    moh_class = await _resolve_moh_class(session, tenant_id, payload.moh_class_id)
    periodic_audio = await _resolve_audio(session, tenant_id, payload.periodic_announce_audio_id)
    join_audio = await _resolve_audio(session, tenant_id, payload.join_announcement_audio_id)
    agent_audio = await _resolve_audio(session, tenant_id, payload.agent_announcement_audio_id)
    breakout_target_id = await _resolve_breakout_target(session, tenant_id, payload.breakout_target_id)

    target = await create_target(session, tenant_id, "queue", payload.name)
    queue = Queue(
        tenant_id=tenant_id, target_id=target.id, name=payload.name, strategy=payload.strategy,
        agent_ring_seconds=payload.agent_ring_seconds, retry_seconds=payload.retry_seconds,
        wrapup_seconds=payload.wrapup_seconds, max_wait_seconds=payload.max_wait_seconds,
        max_callers=payload.max_callers, announce_position=payload.announce_position,
        announce_frequency_seconds=payload.announce_frequency_seconds, sla_seconds=payload.sla_seconds,
        join_empty=payload.join_empty, record=payload.record, timeout_target_id=payload.timeout_target_id,
        moh_class_id=moh_class.id if moh_class else None,
        skip_busy_agents=payload.skip_busy_agents, weight=payload.weight, autofill=payload.autofill,
        report_hold_time=payload.report_hold_time, member_delay_seconds=payload.member_delay_seconds,
        penalty_members_limit=payload.penalty_members_limit, auto_pause=payload.auto_pause,
        auto_pause_delay_seconds=payload.auto_pause_delay_seconds, auto_pause_busy=payload.auto_pause_busy,
        auto_pause_unavail=payload.auto_pause_unavail, agent_timeout_restart=payload.agent_timeout_restart,
        max_wait_mode=payload.max_wait_mode, leave_when_empty=payload.leave_when_empty,
        announce_position_limit=payload.announce_position_limit, announce_hold_time=payload.announce_hold_time,
        min_announce_frequency_seconds=payload.min_announce_frequency_seconds,
        periodic_announce_frequency_seconds=payload.periodic_announce_frequency_seconds,
        ring_mode=payload.ring_mode, mark_answered_elsewhere=payload.mark_answered_elsewhere,
        cid_name_prefix=payload.cid_name_prefix, alert_info=payload.alert_info,
        periodic_announce_audio_file_id=periodic_audio.id if periodic_audio else None,
        join_announcement_audio_file_id=join_audio.id if join_audio else None,
        agent_announcement_audio_file_id=agent_audio.id if agent_audio else None,
        breakout_target_id=breakout_target_id,
    )
    _replace_members(queue, payload.members)
    session.add(queue)
    await session.flush()
    if payload.number:
        await set_dial_number(session, tenant_id, str(target.id), payload.number)

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="queue.create",
                        entity="queue", entity_id=str(queue.id), diff={"name": payload.name})
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    code = await _tenant_code(session, tenant_id)
    queue = await _get_queue_or_404(session, tenant_id, str(queue.id))
    return QueueMutated(item=await _queue_out(session, tenant_id, code, queue, ami), apply=apply_result.to_dict())


async def _apply_queue_name_rename(session: AsyncSession, queue: Queue, payload: UpdateQueuePayload) -> None:
    if payload.name is not None:
        await rename_target(session, str(queue.target_id), payload.name)


async def _validate_queue_timeout_target(session: AsyncSession, tenant_id: str, payload: UpdateQueuePayload) -> None:
    if payload.timeout_target_id is None:
        return
    if await resolve_target(session, tenant_id, payload.timeout_target_id) is None:
        raise ApiError(422, "invalid_target", "Noto'g'ri manzil", field="timeout_target_id")


async def _apply_queue_members(
    session: AsyncSession, tenant_id: str, queue: Queue, payload: UpdateQueuePayload, diff: dict,
) -> None:
    if payload.members is None:
        return
    await _validate_member_payloads(session, tenant_id, payload.members)
    _replace_members(queue, payload.members)
    diff["members"] = len(payload.members)


async def _apply_queue_number(
    session: AsyncSession, tenant_id: str, queue: Queue, payload: UpdateQueuePayload, diff: dict,
) -> None:
    if payload.number is None:
        return
    if payload.number:
        await ensure_number_free(session, tenant_id, payload.number, exclude_target_id=str(queue.target_id))
    await set_dial_number(session, tenant_id, str(queue.target_id), payload.number)
    diff["number"] = payload.number


async def _apply_queue_moh_class(
    session: AsyncSession, tenant_id: str, queue: Queue, payload: UpdateQueuePayload, diff: dict,
) -> None:
    if payload.moh_class_id is None:
        return
    moh_class = await _resolve_moh_class(session, tenant_id, payload.moh_class_id)
    queue.moh_class_id = moh_class.id if moh_class else None
    diff["moh_class_id"] = payload.moh_class_id


@router.patch("/{queue_id}", response_model=QueueMutated)
async def update_queue(
    queue_id: str, payload: UpdateQueuePayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> QueueMutated:
    tenant_id = str(user.tenant_id)
    queue = await _get_queue_or_404(session, tenant_id, queue_id)
    check_not_stale(queue.updated_at, payload.updated_at)

    diff: dict = {}
    _apply_simple_queue_fields(queue, payload, diff)
    await _apply_queue_name_rename(session, queue, payload)
    await _validate_queue_timeout_target(session, tenant_id, payload)
    await _apply_queue_members(session, tenant_id, queue, payload, diff)
    await _apply_queue_number(session, tenant_id, queue, payload, diff)
    await _apply_queue_moh_class(session, tenant_id, queue, payload, diff)
    await _apply_queue_cid_name_prefix(queue, payload, diff)
    await _apply_queue_alert_info(queue, payload, diff)
    await _apply_queue_audio_fk(
        session, tenant_id, queue, payload, diff,
        payload_field="periodic_announce_audio_id", model_field="periodic_announce_audio_file_id",
    )
    await _apply_queue_audio_fk(
        session, tenant_id, queue, payload, diff,
        payload_field="join_announcement_audio_id", model_field="join_announcement_audio_file_id",
    )
    await _apply_queue_audio_fk(
        session, tenant_id, queue, payload, diff,
        payload_field="agent_announcement_audio_id", model_field="agent_announcement_audio_file_id",
    )
    await _apply_queue_breakout_target(session, tenant_id, queue, payload, diff)

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="queue.update",
                        entity="queue", entity_id=str(queue.id), diff=diff)
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    code = await _tenant_code(session, tenant_id)
    queue = await _get_queue_or_404(session, tenant_id, str(queue.id))
    return QueueMutated(item=await _queue_out(session, tenant_id, code, queue, ami), apply=apply_result.to_dict())


def _apply_simple_queue_fields(queue: Queue, payload: UpdateQueuePayload, diff: dict) -> None:
    """Oddiy skalyar maydonlar — alohida validatsiya kerak emas (CRAP pasaytirish)."""
    simple_fields = (
        "name", "strategy", "agent_ring_seconds", "retry_seconds", "wrapup_seconds", "max_wait_seconds",
        "max_callers", "announce_position", "announce_frequency_seconds", "sla_seconds", "join_empty",
        "record", "timeout_target_id",
        # 0037 (Queues FreePBX parity).
        "skip_busy_agents", "weight", "autofill", "report_hold_time", "member_delay_seconds",
        "penalty_members_limit", "auto_pause", "auto_pause_delay_seconds", "auto_pause_busy",
        "auto_pause_unavail", "agent_timeout_restart", "max_wait_mode", "leave_when_empty",
        "announce_position_limit", "announce_hold_time", "min_announce_frequency_seconds",
        "periodic_announce_frequency_seconds", "ring_mode", "mark_answered_elsewhere",
    )
    for field in simple_fields:
        value = getattr(payload, field)
        if value is not None:
            setattr(queue, field, value)
            diff[field] = value


async def _apply_queue_cid_name_prefix(queue: Queue, payload: UpdateQueuePayload, diff: dict) -> None:
    if payload.cid_name_prefix_clear:
        queue.cid_name_prefix = None
        diff["cid_name_prefix"] = None
    elif payload.cid_name_prefix is not None:
        queue.cid_name_prefix = payload.cid_name_prefix
        diff["cid_name_prefix"] = payload.cid_name_prefix


async def _apply_queue_alert_info(queue: Queue, payload: UpdateQueuePayload, diff: dict) -> None:
    if payload.alert_info_clear:
        queue.alert_info = None
        diff["alert_info"] = None
    elif payload.alert_info is not None:
        queue.alert_info = payload.alert_info
        diff["alert_info"] = payload.alert_info


async def _apply_queue_audio_fk(
    session: AsyncSession, tenant_id: str, queue: Queue, payload: UpdateQueuePayload, diff: dict,
    *, payload_field: str, model_field: str,
) -> None:
    """3 audio FK (davriy/qo'shilish/agent e'loni) — BITTA yo'l (dryer): farqi
    faqat maydon nomi (`_clear` bayrog'i AYNAN SHU NAQSH — `inbound_routes.py`
    `_apply_cid_lookup_source` bilan bir xil)."""
    if getattr(payload, f"{payload_field}_clear"):
        setattr(queue, model_field, None)
        diff[model_field] = None
        return
    audio_id = getattr(payload, payload_field)
    if audio_id is not None:
        audio = await _resolve_audio(session, tenant_id, audio_id)
        setattr(queue, model_field, audio.id if audio else None)
        diff[model_field] = audio_id


async def _apply_queue_breakout_target(
    session: AsyncSession, tenant_id: str, queue: Queue, payload: UpdateQueuePayload, diff: dict,
) -> None:
    if payload.breakout_target_id_clear:
        queue.breakout_target_id = None
        diff["breakout_target_id"] = None
    elif payload.breakout_target_id is not None:
        queue.breakout_target_id = await _resolve_breakout_target(session, tenant_id, payload.breakout_target_id)
        diff["breakout_target_id"] = payload.breakout_target_id


@router.post("/{queue_id}/members", response_model=QueueMutated, status_code=201)
async def add_queue_member(
    queue_id: str, payload: AddQueueMemberPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> QueueMutated:
    """A'zo qo'shish — `queue_members` realtime, reload SHART EMAS (m1a-contract.md S10),
    shu sabab `apply_config` chaqirilmaydi — tanlagan diapplan ravon qoladi."""
    tenant_id = str(user.tenant_id)
    queue = await _get_queue_or_404(session, tenant_id, queue_id)
    await _validate_member_payloads(session, tenant_id, [payload])
    existing = {str(m.extension_id) for m in queue.members}
    if payload.extension_id not in existing:
        queue.members.append(QueueMember(
            extension_id=payload.extension_id, penalty=payload.penalty, dynamic=payload.dynamic))
        await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="queue.add_member",
                        entity="queue", entity_id=str(queue.id), diff={"extension_id": payload.extension_id})
    await session.commit()
    code = await _tenant_code(session, tenant_id)
    queue = await _get_queue_or_404(session, tenant_id, queue_id)
    return QueueMutated(item=await _queue_out(session, tenant_id, code, queue, ami),
                         apply={"status": "realtime", "revision": None, "message": None})


@router.patch("/{queue_id}/members/{extension_id}", response_model=QueueMemberMutated)
async def update_queue_member(
    queue_id: str, extension_id: str, payload: UpdateQueueMemberPayload,
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> QueueMemberMutated:
    """`{penalty?, dynamic?}` — realtime, `apply` YO'Q (m2b-contract.md §1)."""
    tenant_id = str(user.tenant_id)
    member = await _get_member_or_404(session, tenant_id, queue_id, extension_id)
    diff: dict = {}
    if payload.penalty is not None:
        member.penalty = payload.penalty
        diff["penalty"] = payload.penalty
    if payload.dynamic is not None:
        member.dynamic = payload.dynamic
        diff["dynamic"] = payload.dynamic
    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="queue.update_member",
                        entity="queue", entity_id=queue_id, diff=diff)
    await session.commit()
    member = await _get_member_or_404(session, tenant_id, queue_id, extension_id)
    return QueueMemberMutated(item=_member_out(member))


MemberAction = Literal["login", "logout", "pause", "unpause"]

_MEMBER_ACTION_FUNCS = {
    "login": lambda session, member, payload, source: login_member(session, member, source=source),
    "logout": lambda session, member, payload, source: logout_member(session, member, source=source),
    "pause": lambda session, member, payload, source: pause_member(session, member, source=source, reason=payload.reason),
    "unpause": lambda session, member, payload, source: unpause_member(session, member, source=source),
}


async def _member_action(
    session: AsyncSession, user: User, queue_id: str, extension_id: str, action: MemberAction,
    payload: QueueMemberActionPayload, ami, *, source: str = "admin",
) -> QueueMemberMutated:
    """4 holat (login/logout/pause/unpause) — BITTA yo'l (dryer): farqi faqat
    `queue_agents.py` funksiyasi (jadval, `_MEMBER_ACTION_FUNCS`) va audit nomi.
    `source` — kim chaqirdi (`admin`/`portal`); operator kabineti (`app/api/v1/me.py`,
    §4) shu BITTA funksiyani `source="portal"` bilan qayta ishlatadi (dryer,
    ikkinchi mustaqil yozish yo'li YO'Q)."""
    tenant_id = str(user.tenant_id)
    member = await _get_member_or_404(session, tenant_id, queue_id, extension_id)
    await _MEMBER_ACTION_FUNCS[action](session, member, payload, source)
    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action=f"queue.{action}_member",
                        entity="queue", entity_id=queue_id,
                        diff={"extension_id": extension_id, "reason": payload.reason, "source": source})
    await session.commit()
    if action in ("pause", "unpause"):
        code = await _tenant_code(session, tenant_id)
        await nudge_pause_state(
            ami, tenant_code=code, number=member.extension.number, queue_id=queue_id,
            paused=(action == "pause"), reason=payload.reason,
        )
    member = await _get_member_or_404(session, tenant_id, queue_id, extension_id)
    return QueueMemberMutated(item=_member_out(member))


@router.post("/{queue_id}/members/{extension_id}/{action}", response_model=QueueMemberMutated)
async def act_on_queue_member(
    queue_id: str, extension_id: str, action: MemberAction,
    payload: QueueMemberActionPayload = QueueMemberActionPayload(),
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access), ami=Depends(get_ami),
) -> QueueMemberMutated:
    """m2b-contract.md §1: `POST /queues/{id}/members/{extension_id}/{login|logout|pause|unpause}`
    `{reason?}` -> `{item: QueueMemberOut}`. `action` yo'l segmentida — 4 ta
    bir xil shaklli endpoint O'RNIGA (dryer), lekin TASHQI URL manzillari
    kontrakt bilan AYNAN BIR XIL (`.../login`, `.../logout`, `.../pause`,
    `.../unpause`). Noto'g'ri `action` -> 422 `validation_error` (ILGARI:
    mos yo'l yo'qligi sababli 404 `http_error` bo'lardi — ikkisi ham
    bir xil xato konvertida, faqat kod/status farqli)."""
    return await _member_action(session, user, queue_id, extension_id, action, payload, ami)


@router.delete("/{queue_id}", status_code=204, response_model=None)
async def delete_queue(
    queue_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
    ami=Depends(get_ami),
) -> None:
    tenant_id = str(user.tenant_id)
    queue = await _get_queue_or_404(session, tenant_id, queue_id)
    usages = await usages_for_target(session, tenant_id, str(queue.target_id))
    if usages:
        raise ApiError(409, "in_use", "Navbat ishlatilmoqda", details={"usages": usages})

    await delete_satellite_and_target(session, queue, str(queue.target_id))
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="queue.delete",
                        entity="queue", entity_id=str(queue_id))
    await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
