"""time_group, holiday, time_condition yozuvchilari."""
from __future__ import annotations

from datetime import date, time

from sqlalchemy import select

from app.db.models import Holiday, TimeCondition, TimeGroup, TimeRange
from app.services.fpbx.mappers import Entry
from app.services.fpbx.writers.context import SkipItem, WriteCtx, WriteError, pick, unique_name
from app.services.fpbx.writers.refs import required_target, resolve_entity
from app.services.numbers import set_dial_number

_DAY_END = time(23, 59, 59)
_DAY_START = time(0, 0)
_OVERRIDES = frozenset({"auto", "force_open", "force_closed"})


def split_range(start: time, end: time) -> list[tuple[time, time]]:
    """CHECK `end_time > start_time` — tun bo'yi oraliq (22:00-06:00) ikkiga bo'linadi."""
    if end > start:
        return [(start, end)]
    parts = [(start, _DAY_END)] if start < _DAY_END else []
    if end > _DAY_START:
        parts.append((_DAY_START, end))
    return parts


async def write_time_group(ctx: WriteCtx, entry: Entry) -> str:
    p = entry.payload
    group = TimeGroup(tenant_id=ctx.tenant_id, name=await unique_name(ctx, TimeGroup, p.get("name") or entry.name))
    ctx.session.add(group)
    await ctx.session.flush()
    for rng in p.get("ranges") or []:
        weekdays = sorted({d for d in rng.get("weekdays") or [] if 1 <= d <= 7})
        if not weekdays:
            continue
        for start, end in split_range(time.fromisoformat(rng["start_time"]), time.fromisoformat(rng["end_time"])):
            ctx.session.add(TimeRange(time_group_id=group.id, weekdays=weekdays, start_time=start, end_time=end))
    return str(group.id)


async def write_holiday(ctx: WriteCtx, entry: Entry) -> str:
    p = entry.payload
    day = date.fromisoformat(p["day"])
    taken = (await ctx.session.execute(
        select(Holiday.id).where(Holiday.tenant_id == ctx.tenant_id, Holiday.day == day).limit(1)
    )).first()
    if taken is not None:
        raise SkipItem("holiday_exists", f"{day.isoformat()} sanasi uchun bayram allaqachon bor")
    holiday = Holiday(tenant_id=ctx.tenant_id, name=p.get("name") or entry.name, day=day,
                      recurring_yearly=bool(p.get("recurring_yearly")))
    ctx.session.add(holiday)
    await ctx.session.flush()
    return str(holiday.id)


async def write_time_condition(ctx: WriteCtx, entry: Entry) -> str:
    p = entry.payload
    group_id = await resolve_entity(ctx, p.get("time_group_id"))
    if group_id is None:
        raise WriteError("ref_unresolved", f"{entry.source_ref}: vaqt guruhi topilmadi")
    target_id = ctx.target_for(entry)
    tc = TimeCondition(
        tenant_id=ctx.tenant_id, target_id=target_id,
        name=await unique_name(ctx, TimeCondition, p.get("name") or entry.name),
        time_group_id=group_id, honor_holidays=bool(p.get("honor_holidays", True)),
        open_target_id=await required_target(ctx, p.get("open_target_id"), source_ref=entry.source_ref),
        closed_target_id=await required_target(ctx, p.get("closed_target_id"), source_ref=entry.source_ref),
        override=pick(p.get("override"), _OVERRIDES, "auto"), toggle_code=p.get("toggle_code"),
    )
    ctx.session.add(tc)
    await ctx.session.flush()
    if entry.number:
        await set_dial_number(ctx.session, ctx.tenant_id, target_id, entry.number)
    return str(tc.id)
