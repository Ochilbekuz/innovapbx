"""ring_group, queue, conference, announcement, ivr yozuvchilari (call_target'li
satellitlar — maqsad id `ctx.targets`da oldindan ochilgan)."""
from __future__ import annotations

import re

from app.core.security import hash_password
from app.db.models import Announcement, Conference, Ivr, IvrOption, Queue, QueueMember, RingGroup, RingGroupMember
from app.services.fpbx.mappers import Entry
from app.services.fpbx.writers.context import WriteCtx, clamp, matches, pick, unique_name
from app.services.fpbx.writers.media import moh_id_by_name
from app.services.fpbx.writers.refs import extension_id, fallback_audio, required_target, resolve_entity
from app.services.numbers import set_dial_number

_RG_STRATEGIES = frozenset({"ringall", "hunt", "memoryhunt"})
_Q_STRATEGIES = frozenset({"ringall", "leastrecent", "fewestcalls", "random", "rrmemory", "linear", "wrandom"})
_EXTERNAL = r"\+?[0-9]{3,15}"
_DIGIT = r"[0-9*#]"


def _positive_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and value > 0 else None


async def _finish_target(ctx: WriteCtx, entry: Entry, satellite: object) -> str:
    ctx.session.add(satellite)
    await ctx.session.flush()
    if entry.number:
        await set_dial_number(ctx.session, ctx.tenant_id, ctx.target_for(entry), entry.number)
    return str(satellite.id)


async def _rg_member(ctx: WriteCtx, entry: Entry, member: dict) -> dict | None:
    if member.get("extension_number"):
        ext_id = await extension_id(ctx, member["extension_number"])
        if ext_id is not None:
            return {"extension_id": ext_id}
        ctx.warn(entry.source_ref, "member_missing", f"A'zo topilmadi: {member['extension_number']}")
        return None
    if matches(_EXTERNAL, member.get("external_number")):
        return {"external_number": re.sub(r"\s", "", member["external_number"])}
    ctx.warn(entry.source_ref, "member_invalid", "Tashqi a'zo raqami yaroqsiz — tashlab ketildi")
    return None


async def write_ring_group(ctx: WriteCtx, entry: Entry) -> str:
    p = entry.payload
    group = RingGroup(
        tenant_id=ctx.tenant_id, target_id=ctx.target_for(entry), name=p.get("name") or entry.name,
        strategy=pick(p.get("strategy"), _RG_STRATEGIES, "ringall"),
        ring_seconds=clamp(p.get("ring_seconds"), 5, 300, 20),
        no_answer_target_id=await required_target(ctx, p.get("no_answer_target_id"), source_ref=entry.source_ref),
        callerid_prefix=p.get("callerid_prefix"),
    )
    members = [m for m in [await _rg_member(ctx, entry, raw) for raw in p.get("members") or []] if m]
    group.members = [RingGroupMember(position=i, **m) for i, m in enumerate(members, start=1)]
    return await _finish_target(ctx, entry, group)


async def _queue_members(ctx: WriteCtx, entry: Entry, raw_members: list[dict]) -> list[QueueMember]:
    members: dict[str, QueueMember] = {}
    for raw in raw_members:
        ext_id = await extension_id(ctx, raw.get("extension_number"))
        if ext_id is None:
            ctx.warn(entry.source_ref, "member_missing", f"A'zo topilmadi: {raw.get('extension_number')}")
            continue
        members.setdefault(ext_id, QueueMember(extension_id=ext_id, penalty=clamp(raw.get("penalty"), 0, 10, 0),
                                               dynamic=bool(raw.get("dynamic"))))
    return list(members.values())


async def write_queue(ctx: WriteCtx, entry: Entry) -> str:
    p = entry.payload
    queue = Queue(
        tenant_id=ctx.tenant_id, target_id=ctx.target_for(entry),
        name=await unique_name(ctx, Queue, p.get("name") or entry.name),
        strategy=pick(p.get("strategy"), _Q_STRATEGIES, "ringall"),
        moh_class_id=await moh_id_by_name(ctx, p.get("moh_class_name")),
        agent_ring_seconds=clamp(p.get("agent_ring_seconds"), 5, 120, 15),
        retry_seconds=clamp(p.get("retry_seconds"), 0, None, 5),
        wrapup_seconds=clamp(p.get("wrapup_seconds"), 0, None, 0),
        max_wait_seconds=_positive_or_none(p.get("max_wait_seconds")) or 300,
        max_callers=_positive_or_none(p.get("max_callers")),
        announce_position=bool(p.get("announce_position")),
        announce_frequency_seconds=clamp(p.get("announce_frequency_seconds"), 0, None, 0),
        sla_seconds=clamp(p.get("sla_seconds"), 0, None, 20), join_empty=bool(p.get("join_empty")),
        record=bool(p.get("record")),
        timeout_target_id=await required_target(ctx, p.get("timeout_target_id"), source_ref=entry.source_ref),
    )
    queue.members = await _queue_members(ctx, entry, p.get("members") or [])
    return await _finish_target(ctx, entry, queue)


async def write_conference(ctx: WriteCtx, entry: Entry) -> str:
    p = entry.payload
    pin, admin_pin = p.get("pin_plain"), p.get("admin_pin_plain")
    conference = Conference(
        tenant_id=ctx.tenant_id, target_id=ctx.target_for(entry), name=p.get("name") or entry.name,
        pin_hash=hash_password(pin) if pin else None, admin_pin_hash=hash_password(admin_pin) if admin_pin else None,
        record=bool(p.get("record")),
        max_members=m if (m := _positive_or_none(p.get("max_members"))) and m > 1 else None,
    )
    return await _finish_target(ctx, entry, conference)


async def write_announcement(ctx: WriteCtx, entry: Entry) -> str:
    p = entry.payload
    audio_id = await resolve_entity(ctx, p.get("audio_file_id")) or await fallback_audio(ctx, entry.source_ref)
    announcement = Announcement(
        tenant_id=ctx.tenant_id, target_id=ctx.target_for(entry), name=p.get("name") or entry.name,
        audio_file_id=audio_id,
        next_target_id=await required_target(ctx, p.get("next_target_id"), source_ref=entry.source_ref),
    )
    return await _finish_target(ctx, entry, announcement)


async def _ivr_options(ctx: WriteCtx, entry: Entry, raw_options: list[dict]) -> list[IvrOption]:
    options: dict[str, IvrOption] = {}
    for raw in raw_options:
        digit = raw.get("digit")
        if not matches(_DIGIT, digit) or digit in options:
            ctx.warn(entry.source_ref, "ivr_option_invalid", f"IVR tugmasi yaroqsiz/takror: {digit}")
            continue
        options[digit] = IvrOption(
            digit=digit, target_id=await required_target(ctx, raw.get("target_id"), source_ref=entry.source_ref))
    return list(options.values())


async def write_ivr(ctx: WriteCtx, entry: Entry) -> str:
    p = entry.payload
    greeting = await resolve_entity(ctx, p.get("greeting_audio_id")) or await fallback_audio(ctx, entry.source_ref)
    ivr = Ivr(
        tenant_id=ctx.tenant_id, target_id=ctx.target_for(entry),
        name=await unique_name(ctx, Ivr, p.get("name") or entry.name),
        greeting_audio_id=greeting, invalid_audio_id=await resolve_entity(ctx, p.get("invalid_audio_id")),
        timeout_seconds=clamp(p.get("timeout_seconds"), 1, 60, 7), repeats=clamp(p.get("repeats"), 0, 5, 2),
        direct_dial=bool(p.get("direct_dial")),
        timeout_target_id=await required_target(ctx, p.get("timeout_target_id"), source_ref=entry.source_ref),
        invalid_target_id=await required_target(ctx, p.get("invalid_target_id"), source_ref=entry.source_ref),
    )
    ivr.options = await _ivr_options(ctx, entry, p.get("options") or [])
    return await _finish_target(ctx, entry, ivr)
