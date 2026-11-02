"""Chiquvchi marshrutlar — m1b-contract.md bo'lim 2 (S22). Qoida mantiqi
(naqsh/strip/xalqaro/trunk/CallerID) `app/services/outbound_rules.py`da SOF
funksiyalar sifatida — ularni BU router (`/simulate`) VA `compiler.py`
(dialplan generatsiyasi) ikkisi ham ishlatadi. DB->qoida dataclass
o'girish `app/services/route_lookup.py`da umumiy (ring_groups.py ham
ishlatadi — tashqi a'zo tekshiruvi)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_ami, get_session, require_access
from app.core.errors import ApiError
from app.core.ids import parse_uuid
from app.core.optimistic import check_not_stale
from app.core.security import hash_password
from app.db.models import (
    Extension,
    ExtensionOutboundRoute,
    OutboundRoute,
    OutboundRoutePattern,
    OutboundRouteTrunk,
    Trunk,
    User,
)
from app.schemas import (
    CreateOutboundRoutePayload,
    ExtensionAllowRef,
    OutboundPatternOut,
    OutboundRouteMutated,
    OutboundRouteOut,
    OutboundRouteTrunkOut,
    ReorderOutboundRoutesPayload,
    SimulatePayload,
    SimulateResult,
    SimulateRouteRef,
    SimulateStepOut,
    TrunkRef,
    UpdateOutboundRoutePayload,
)
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.outbound_rules import resolve_callerid, resolve_route, validate_pattern
from app.services.route_lookup import load_route_rules

router = APIRouter(prefix="/outbound-routes", tags=["outbound-routes"])

_ROUTE_OPTIONS = (
    selectinload(OutboundRoute.patterns),
    selectinload(OutboundRoute.route_trunks).selectinload(OutboundRouteTrunk.trunk),
    selectinload(OutboundRoute.extension_links).selectinload(ExtensionOutboundRoute.extension),
)


async def _route_out(route: OutboundRoute) -> OutboundRouteOut:
    trunks = [
        OutboundRouteTrunkOut(position=rt.position, trunk=TrunkRef(id=str(rt.trunk_id), name=rt.trunk.name))
        for rt in sorted(route.route_trunks, key=lambda r: r.position)
    ]
    extensions: str | list[ExtensionAllowRef] = "all"
    if route.extension_links:
        extensions = [
            ExtensionAllowRef(id=str(link.extension_id), number=link.extension.number, name=link.extension.name)
            for link in sorted(route.extension_links, key=lambda l: l.extension.number)
        ]
    return OutboundRouteOut(
        id=str(route.id), name=route.name, priority=route.priority, enabled=route.enabled,
        patterns=[OutboundPatternOut(strip_prefix=p.strip_prefix, pattern=p.pattern, add_prefix=p.add_prefix,
                                      callerid_match=p.callerid_match) for p in route.patterns],
        trunks=trunks, callerid=route.callerid, override_extension_callerid=route.override_extension_callerid,
        has_pin=route.pin_hash is not None, international=route.international, extensions=extensions,
        updated_at=route.updated_at,
    )


async def _get_route_or_404(session: AsyncSession, tenant_id: str, route_id: str) -> OutboundRoute:
    valid_id = parse_uuid(route_id, not_found_message="Chiquvchi marshrut topilmadi")
    route = (await session.execute(
        select(OutboundRoute).where(OutboundRoute.tenant_id == tenant_id, OutboundRoute.id == valid_id)
        .options(*_ROUTE_OPTIONS)
    )).scalar_one_or_none()
    if route is None:
        raise ApiError(404, "not_found", "Chiquvchi marshrut topilmadi")
    return route


def _validate_patterns(patterns: list) -> None:
    for idx, pat in enumerate(patterns):
        result = validate_pattern(pat.pattern)
        if not result.ok:
            raise ApiError(422, "bad_pattern", "Naqsh noto'g'ri",
                            details={"index": idx, "reason": result.reason})


async def _validate_trunk_ids(session: AsyncSession, tenant_id: str, trunk_ids: list[str]) -> None:
    if not trunk_ids:
        raise ApiError(422, "no_trunk", "Kamida bitta trunk kerak", field="trunk_ids")
    found = {str(t) for t in (await session.execute(
        select(Trunk.id).where(Trunk.tenant_id == tenant_id, Trunk.id.in_(trunk_ids))
    )).scalars().all()}
    missing = [t for t in trunk_ids if t not in found]
    if missing:
        raise ApiError(422, "invalid_target", "Noto'g'ri trunk", field="trunk_ids")


async def _validate_extension_ids(session: AsyncSession, tenant_id: str, extension_ids: list[str]) -> None:
    if not extension_ids:
        return
    found = {str(e) for e in (await session.execute(
        select(Extension.id).where(Extension.tenant_id == tenant_id, Extension.id.in_(extension_ids))
    )).scalars().all()}
    missing = [e for e in extension_ids if e not in found]
    if missing:
        raise ApiError(422, "invalid_target", "Noto'g'ri ichki raqam", field="extension_ids")


def _set_patterns(route: OutboundRoute, patterns: list) -> None:
    route.patterns = [
        OutboundRoutePattern(strip_prefix=p.strip_prefix, pattern=p.pattern, add_prefix=p.add_prefix,
                              callerid_match=p.callerid_match)
        for p in patterns
    ]


def _set_trunks(route: OutboundRoute, trunk_ids: list[str]) -> None:
    route.route_trunks = [
        OutboundRouteTrunk(position=position, trunk_id=trunk_id)
        for position, trunk_id in enumerate(trunk_ids, start=1)
    ]


def _set_extension_links(route: OutboundRoute, extension_ids: str | list[str]) -> None:
    route.extension_links = [
        ExtensionOutboundRoute(extension_id=ext_id)
        for ext_id in (extension_ids if extension_ids != "all" else [])
    ]


@router.get("")
async def list_outbound_routes(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> dict:
    routes = (await session.execute(
        select(OutboundRoute).where(OutboundRoute.tenant_id == user.tenant_id)
        .order_by(OutboundRoute.priority).options(*_ROUTE_OPTIONS)
    )).scalars().unique().all()
    return {"items": [await _route_out(r) for r in routes]}


async def _next_priority(session: AsyncSession, tenant_id: str) -> int:
    current_max = (await session.execute(
        select(OutboundRoute.priority).where(OutboundRoute.tenant_id == tenant_id)
        .order_by(OutboundRoute.priority.desc()).limit(1)
    )).scalar_one_or_none()
    return (current_max or 0) + 1


async def _insert_at_priority(session: AsyncSession, tenant_id: str, priority: int) -> None:
    """Berilgan pozitsiyadan boshlab (va undan keyingi) barcha marshrutlarni
    bitta siljitadi — yangi marshrut aynan shu `priority`da kiritiladi
    (ro'yxatga element qo'shish semantikasi, o'rin band bo'lgani uchun 409
    o'rniga).

    DIQQAT: bitta bulk `UPDATE ... WHERE priority >= X` ishlatilmaydi — jonli
    Postgres'da tasdiqlangan: `(tenant_id, priority)` UNIQUE indeks
    DEFERRABLE emas, shu sabab bitta buyruq ichida bir nechta qatorni
    siljitish vaqtinchalik "duplicate key" xatosini qaytaradi (qatorlar
    qanday tartibda qayta yozilishi kafolatlanmagan). Shu sabab har bir
    qatorni ALOHIDA, ENG YUQORI ustuvorlikdan boshlab (pastga joy bo'shatib)
    suramiz — har safar `flush()` bilan darhol bajariladi."""
    rows = (await session.execute(
        select(OutboundRoute).where(OutboundRoute.tenant_id == tenant_id, OutboundRoute.priority >= priority)
        .order_by(OutboundRoute.priority.desc())
    )).scalars().all()
    for route in rows:
        route.priority += 1
        await session.flush()


@router.post("", response_model=OutboundRouteMutated, status_code=201)
async def create_outbound_route(
    payload: CreateOutboundRoutePayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> OutboundRouteMutated:
    tenant_id = str(user.tenant_id)
    _validate_patterns(payload.patterns)
    await _validate_trunk_ids(session, tenant_id, payload.trunk_ids)
    ext_ids = [] if payload.extension_ids == "all" else payload.extension_ids
    await _validate_extension_ids(session, tenant_id, ext_ids)

    if payload.priority is not None:
        await _insert_at_priority(session, tenant_id, payload.priority)
        priority = payload.priority
    else:
        priority = await _next_priority(session, tenant_id)

    route = OutboundRoute(
        tenant_id=tenant_id, name=payload.name, priority=priority, enabled=payload.enabled,
        callerid=payload.callerid, override_extension_callerid=payload.override_extension_callerid,
        pin_hash=hash_password(payload.pin) if payload.pin else None, international=payload.international,
    )
    _set_patterns(route, payload.patterns)
    _set_trunks(route, payload.trunk_ids)
    _set_extension_links(route, ext_ids if payload.extension_ids != "all" else "all")
    session.add(route)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "name_taken", "Bu nom band", field="name") from exc

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="outbound_route.create",
                        entity="outbound_route", entity_id=str(route.id),
                        diff={"name": payload.name, "priority": priority, "pin": payload.pin})
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    route = await _get_route_or_404(session, tenant_id, str(route.id))
    return OutboundRouteMutated(item=await _route_out(route), apply=apply_result.to_dict())


def _apply_simple_route_fields(route: OutboundRoute, payload: UpdateOutboundRoutePayload, diff: dict) -> None:
    for field in ("name", "enabled", "callerid", "override_extension_callerid", "international"):
        value = getattr(payload, field)
        if value is not None:
            setattr(route, field, value)
            diff[field] = value


def _apply_route_pin(route: OutboundRoute, payload: UpdateOutboundRoutePayload, diff: dict) -> None:
    if payload.pin_clear:
        route.pin_hash = None
        diff["pin"] = None
    elif payload.pin is not None:
        route.pin_hash = hash_password(payload.pin)
        diff["pin"] = payload.pin


async def _apply_route_patterns(
    session: AsyncSession, route: OutboundRoute, payload: UpdateOutboundRoutePayload, diff: dict,
) -> None:
    if payload.patterns is None:
        return
    _validate_patterns(payload.patterns)
    _set_patterns(route, payload.patterns)
    diff["patterns"] = len(payload.patterns)


async def _apply_route_trunks(
    session: AsyncSession, tenant_id: str, route: OutboundRoute, payload: UpdateOutboundRoutePayload, diff: dict,
) -> None:
    if payload.trunk_ids is None:
        return
    await _validate_trunk_ids(session, tenant_id, payload.trunk_ids)
    _set_trunks(route, payload.trunk_ids)
    diff["trunk_ids"] = payload.trunk_ids


async def _apply_route_extensions(
    session: AsyncSession, tenant_id: str, route: OutboundRoute, payload: UpdateOutboundRoutePayload, diff: dict,
) -> None:
    if payload.extension_ids is None:
        return
    ext_ids = [] if payload.extension_ids == "all" else payload.extension_ids
    await _validate_extension_ids(session, tenant_id, ext_ids)
    _set_extension_links(route, ext_ids if payload.extension_ids != "all" else "all")
    diff["extension_ids"] = payload.extension_ids


@router.patch("/{route_id}", response_model=OutboundRouteMutated)
async def update_outbound_route(
    route_id: str, payload: UpdateOutboundRoutePayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> OutboundRouteMutated:
    tenant_id = str(user.tenant_id)
    route = await _get_route_or_404(session, tenant_id, route_id)
    check_not_stale(route.updated_at, payload.updated_at)

    diff: dict = {}
    _apply_simple_route_fields(route, payload, diff)
    _apply_route_pin(route, payload, diff)
    await _apply_route_patterns(session, route, payload, diff)
    await _apply_route_trunks(session, tenant_id, route, payload, diff)
    await _apply_route_extensions(session, tenant_id, route, payload, diff)

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="outbound_route.update",
                        entity="outbound_route", entity_id=str(route.id), diff=diff)
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    route = await _get_route_or_404(session, tenant_id, str(route.id))
    return OutboundRouteMutated(item=await _route_out(route), apply=apply_result.to_dict())


@router.delete("/{route_id}", status_code=204, response_model=None)
async def delete_outbound_route(
    route_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
    ami=Depends(get_ami),
) -> None:
    tenant_id = str(user.tenant_id)
    route = await _get_route_or_404(session, tenant_id, route_id)
    await session.delete(route)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="outbound_route.delete",
                        entity="outbound_route", entity_id=str(route_id))
    await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()


@router.put("/order", response_model=dict)
async def reorder_outbound_routes(
    payload: ReorderOutboundRoutesPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> dict:
    tenant_id = str(user.tenant_id)
    existing = {str(i) for i in (await session.execute(
        select(OutboundRoute.id).where(OutboundRoute.tenant_id == tenant_id)
    )).scalars().all()}
    given = set(payload.ids)
    if given != existing:
        raise ApiError(422, "invalid_target", "`ids` barcha mavjud marshrutlarni, faqat ularni o'z ichiga olishi SHART",
                        field="ids")

    # Avval barcha mavjud raqamlarni band bo'lmagan oraliqqa o'tkazamiz (unique
    # cheklov bilan to'qnashmaslik uchun), so'ngra yakuniy tartibni qo'yamiz.
    routes = {str(r.id): r for r in (await session.execute(
        select(OutboundRoute).where(OutboundRoute.tenant_id == tenant_id)
    )).scalars().all()}
    offset = len(routes) + 1000
    for route in routes.values():
        route.priority += offset
    await session.flush()
    for position, route_id in enumerate(payload.ids, start=1):
        routes[route_id].priority = position
    await session.flush()

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="outbound_route.reorder",
                        entity="outbound_route", entity_id=None, diff={"ids": payload.ids})
    apply_result = await apply_config(session, tenant_id=tenant_id, user_id=str(user.id), ami=ami)
    await session.commit()
    items = (await session.execute(
        select(OutboundRoute).where(OutboundRoute.tenant_id == tenant_id)
        .order_by(OutboundRoute.priority).options(*_ROUTE_OPTIONS)
    )).scalars().unique().all()
    return {"items": [await _route_out(r) for r in items], "apply": apply_result.to_dict()}


async def _simulate_blocked_by_extension_flag(
    session: AsyncSession, tenant_id: str, extension_number: str,
) -> tuple[str | None, str | None, bool]:
    """`(extension_id, extension_outbound_callerid, blocked)` — `outbound_allowed=false`
    bo'lsa dialplan darajasida rad etiladi (m1b-contract.md 34-qator), bu
    marshrut qoidalaridan OLDIN tekshiriladi."""
    ext = (await session.execute(
        select(Extension).where(Extension.tenant_id == tenant_id, Extension.number == extension_number)
    )).scalar_one_or_none()
    if ext is None:
        return None, None, False
    return str(ext.id), ext.outbound_callerid, not ext.outbound_allowed


@router.post("/simulate", response_model=SimulateResult)
async def simulate_outbound_route(
    payload: SimulatePayload, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> SimulateResult:
    """Dialplan bilan BIR XIL qoidalar (`outbound_rules.resolve_route`/
    `resolve_callerid`) — m1b-contract.md bo'lim 2 so'nggi band."""
    tenant_id = str(user.tenant_id)
    ext_id, ext_callerid, blocked = await _simulate_blocked_by_extension_flag(
        session, tenant_id, payload.extension)
    if blocked:
        return SimulateResult(allowed=False, route=None, dialed=None, callerid=None, trunks=[], steps=[],
                               reason="Bu ichki raqamda chiquvchi qo'ng'iroq o'chirilgan (outbound_allowed=false)")

    routes = await load_route_rules(session, tenant_id)
    outcome = resolve_route(routes, payload.number, extension_id=ext_id)
    if not outcome.allowed or outcome.route is None:
        return SimulateResult(
            allowed=False, route=None, dialed=None, callerid=None, trunks=[],
            steps=[SimulateStepOut(route=s.route, result=s.result, detail=s.detail) for s in outcome.steps],
            reason=outcome.reason,
        )

    trunk_cid = None
    if outcome.trunks:
        first_trunk = await session.get(Trunk, outcome.trunks[0].id)
        trunk_cid = first_trunk.outbound_callerid if first_trunk else None
    callerid = resolve_callerid(
        route_callerid=outcome.route.callerid, override_extension_callerid=outcome.route.override_extension_callerid,
        extension_outbound_callerid=ext_callerid, trunk_outbound_callerid=trunk_cid,
    )
    return SimulateResult(
        allowed=True, route=SimulateRouteRef(id=outcome.route.id, name=outcome.route.name), dialed=outcome.dialed,
        callerid=callerid, trunks=[TrunkRef(id=t.id, name=t.name) for t in outcome.trunks],
        steps=[SimulateStepOut(route=s.route, result=s.result, detail=s.detail) for s in outcome.steps],
        reason=None,
    )
