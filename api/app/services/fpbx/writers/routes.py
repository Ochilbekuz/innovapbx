"""inbound_route, outbound_route, blacklist, feature_code yozuvchilari."""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.models import (
    Blacklist,
    FeatureCode,
    InboundRoute,
    OutboundRoute,
    OutboundRoutePattern,
    OutboundRouteTrunk,
)
from app.services.fpbx.mappers import Entry
from app.services.fpbx.writers.context import SkipItem, WriteCtx, matches, unique_name
from app.services.fpbx.writers.refs import required_target, resolve_entity

_RECORD_OVERRIDE = frozenset({"always", "never"})
_PATTERN = r"[0-9XZN.\[\]*#+-]+"
_FEATURE_CODE = r"\*[0-9*#]{1,6}"


async def write_inbound_route(ctx: WriteCtx, entry: Entry) -> str:
    p = entry.payload
    did, cid = p.get("did") or "", p.get("callerid_pattern") or ""
    taken = (await ctx.session.execute(
        select(InboundRoute.id).where(InboundRoute.tenant_id == ctx.tenant_id, InboundRoute.did == did,
                                      InboundRoute.callerid_pattern == cid).limit(1)
    )).first()
    if taken is not None:
        raise SkipItem("did_exists", f"Bu DID uchun kiruvchi yo'nalish allaqachon bor: {did or '(har qanday)'}")
    record = p.get("record_override")
    route = InboundRoute(
        tenant_id=ctx.tenant_id, name=p.get("name") or entry.name, did=did, callerid_pattern=cid,
        target_id=await required_target(ctx, p.get("target_id"), source_ref=entry.source_ref),
        callerid_name_prefix=p.get("callerid_name_prefix"),
        record_override=record if record in _RECORD_OVERRIDE else None, enabled=bool(p.get("enabled", True)),
    )
    ctx.session.add(route)
    await ctx.session.flush()
    return str(route.id)


async def _free_priority(ctx: WriteCtx, wanted: object) -> int:
    """`(tenant_id, priority)` UNIQUE — band bo'lsa ro'yxat oxiriga."""
    if isinstance(wanted, int) and wanted > 0:
        taken = (await ctx.session.execute(
            select(OutboundRoute.id).where(OutboundRoute.tenant_id == ctx.tenant_id,
                                           OutboundRoute.priority == wanted).limit(1)
        )).first()
        if taken is None:
            return wanted
    top = (await ctx.session.execute(
        select(func.max(OutboundRoute.priority)).where(OutboundRoute.tenant_id == ctx.tenant_id)
    )).scalar()
    return (top or 0) + 1


def _patterns(ctx: WriteCtx, entry: Entry) -> list[OutboundRoutePattern]:
    result = []
    for raw in entry.payload.get("patterns") or []:
        if not matches(_PATTERN, raw.get("pattern")):
            ctx.warn(entry.source_ref, "pattern_invalid", f"Naqsh Innova formatiga mos emas: {raw.get('pattern')}")
            continue
        result.append(OutboundRoutePattern(
            strip_prefix=raw.get("strip_prefix") or "", pattern=raw["pattern"],
            add_prefix=raw.get("add_prefix") or "", callerid_match=raw.get("callerid_match") or "",
        ))
    return result


async def _route_trunks(ctx: WriteCtx, entry: Entry) -> list[OutboundRouteTrunk]:
    trunk_ids: list[str] = []
    for ref_value in entry.payload.get("trunks") or []:
        trunk_id = await resolve_entity(ctx, ref_value)
        if trunk_id is None:
            ctx.warn(entry.source_ref, "trunk_missing", f"Trunk topilmadi: {(ref_value or {}).get('$ref')}")
        elif trunk_id not in trunk_ids:
            trunk_ids.append(trunk_id)
    return [OutboundRouteTrunk(position=i, trunk_id=t) for i, t in enumerate(trunk_ids, start=1)]


async def write_outbound_route(ctx: WriteCtx, entry: Entry) -> str:
    p = entry.payload
    pin = p.get("pin_plain")
    route = OutboundRoute(
        tenant_id=ctx.tenant_id, name=await unique_name(ctx, OutboundRoute, p.get("name") or entry.name),
        priority=await _free_priority(ctx, p.get("priority")), callerid=p.get("callerid"),
        override_extension_callerid=bool(p.get("override_extension_callerid")),
        pin_hash=hash_password(pin) if pin else None, international=bool(p.get("international")),
        enabled=bool(p.get("enabled", True)),
    )
    route.patterns = _patterns(ctx, entry)
    route.route_trunks = await _route_trunks(ctx, entry)
    ctx.session.add(route)
    await ctx.session.flush()
    return str(route.id)


async def write_blacklist(ctx: WriteCtx, entry: Entry) -> None:
    p = entry.payload
    number = p.get("number") or entry.number
    if await ctx.session.get(Blacklist, (ctx.tenant_id, number)) is not None:
        raise SkipItem("exists", f"Qora ro'yxatda allaqachon bor: {number}")
    ctx.session.add(Blacklist(tenant_id=ctx.tenant_id, number=number, reason=p.get("reason")))
    await ctx.session.flush()


async def write_feature_code(ctx: WriteCtx, entry: Entry) -> None:
    """Innova'da funksiya kodi doim bor (seed) — yangi qator EMAS, kodi yangilanadi."""
    p = entry.payload
    if not matches(_FEATURE_CODE, p.get("code")):
        raise SkipItem("code_invalid", f"Funksiya kodi Innova formatiga mos emas: {p.get('code')}")
    row = await ctx.session.get(FeatureCode, (ctx.tenant_id, p["feature"]))
    if row is None:
        ctx.session.add(FeatureCode(tenant_id=ctx.tenant_id, feature=p["feature"], code=p["code"],
                                    enabled=bool(p.get("enabled", True))))
    else:
        row.code, row.enabled = p["code"], bool(p.get("enabled", True))
    await ctx.session.flush()
