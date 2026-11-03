"""Kiruvchi marshrutlar — m0-contract.md «Kiruvchi marshrutlar (S07)».
M0: manzil faqat ichki raqam (call_targets.kind == 'extension')."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_ami, get_session, require_access
from app.core.errors import ApiError
from app.core.ids import parse_uuid
from app.core.lookups import get_tenant_scoped_or_404
from app.core.optimistic import check_not_stale
from app.db.models import CallTarget, CidLookupSource, InboundRoute, User
from app.schemas import (
    CidLookupSourceRef,
    CreateInboundRoutePayload,
    InboundRouteMutated,
    InboundRouteOut,
    RouteTarget,
    UpdateInboundRoutePayload,
)
from app.services.apply import apply_config
from app.services.audit import record_audit
from app.services.target_resolution import resolve_target

router = APIRouter(tags=["inbound-routes"])

# M1a: kiruvchi marshrut ANY manzil turiga yo'naltirilishi mumkin
# (m1a-contract.md) — faqat UI'da ko'rsatilmaydigan turlar istisno.
# M9 A1/A2 (m9-freepbx-gaps-contract.md): e'lon/boshqa manzil ham `call_targets`
# satelliti (compiler.py::_SATELLITE_BUILDERS) — kiruvchi marshrut ularga ham
# Goto() qila olishi SHART (aks holda yangi yaratilgan e'lon/boshqa manzilga
# hech qanday kiruvchi marshrutdan erishib bo'lmaydi).
_ALLOWED_ROUTE_TARGET_KINDS = {
    "extension", "ring_group", "queue", "ivr", "time_condition", "hangup", "busy", "voicemail",
    "announcement", "misc",
}

_ROUTE_OPTIONS = (selectinload(InboundRoute.cid_lookup_source),)


async def _route_target(session: AsyncSession, tenant_id: str, target_id) -> RouteTarget:
    resolved = await resolve_target(session, tenant_id, str(target_id))
    if resolved is None:
        return RouteTarget(id=str(target_id), kind="extension", label="(o'chirilgan manzil)", number=None,
                            broken=True)
    return resolved


async def _route_out(session: AsyncSession, tenant_id: str, route: InboundRoute) -> InboundRouteOut:
    source = route.cid_lookup_source
    return InboundRouteOut(
        id=str(route.id), name=route.name, did=route.did or None, cid=route.callerid_pattern or None,
        target=await _route_target(session, tenant_id, route.target_id), enabled=route.enabled,
        updated_at=route.updated_at,
        cid_name_prefix=route.callerid_name_prefix or None, alert_info=route.alert_info or None,
        cid_lookup_source=CidLookupSourceRef(id=str(source.id), name=source.name) if source else None,
    )


@router.get("/inbound-routes")
async def list_inbound_routes(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> dict:
    items = (await session.execute(
        select(InboundRoute).where(InboundRoute.tenant_id == user.tenant_id).order_by(InboundRoute.name)
        .options(*_ROUTE_OPTIONS)
    )).scalars().all()
    return {"items": [await _route_out(session, str(user.tenant_id), r) for r in items]}


async def _validate_target(session: AsyncSession, tenant_id: str, target_id: str) -> str:
    valid_id = parse_uuid(target_id, not_found_message="Manzil topilmadi")
    target = (await session.execute(
        select(CallTarget).where(CallTarget.tenant_id == tenant_id, CallTarget.id == valid_id)
    )).scalar_one_or_none()
    if target is None or target.kind not in _ALLOWED_ROUTE_TARGET_KINDS:
        raise ApiError(422, "invalid_target", "Noto'g'ri manzil", field="target_id")
    return valid_id


async def _did_conflict_exists(session: AsyncSession, tenant_id: str, did: str, cid: str,
                                exclude_id: str | None = None) -> bool:
    stmt = select(InboundRoute.id).where(
        InboundRoute.tenant_id == tenant_id, InboundRoute.did == did, InboundRoute.callerid_pattern == cid,
    )
    if exclude_id is not None:
        stmt = stmt.where(InboundRoute.id != exclude_id)
    return (await session.execute(stmt)).first() is not None


@router.post("/inbound-routes", response_model=InboundRouteMutated, status_code=201)
async def create_inbound_route(
    payload: CreateInboundRoutePayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> InboundRouteMutated:
    did = payload.did or ""
    cid = payload.cid or ""
    target_id = await _validate_target(session, str(user.tenant_id), payload.target_id)
    if await _did_conflict_exists(session, str(user.tenant_id), did, cid):
        raise ApiError(409, "did_conflict", "Shu DID/CallerID uchun marshrut allaqachon mavjud", field="did")
    if payload.cid_lookup_source_id is not None:
        await _validate_cid_lookup_source_id(session, str(user.tenant_id), payload.cid_lookup_source_id)

    route = InboundRoute(
        tenant_id=user.tenant_id, name=payload.name, did=did, callerid_pattern=cid,
        target_id=target_id, enabled=payload.enabled,
        callerid_name_prefix=payload.cid_name_prefix, alert_info=payload.alert_info,
        cid_lookup_source_id=payload.cid_lookup_source_id,
    )
    session.add(route)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "did_conflict", "Shu DID/CallerID uchun marshrut allaqachon mavjud",
                        field="did") from exc

    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="inbound_route.create", entity="inbound_route", entity_id=str(route.id),
                        diff={"name": payload.name, "did": did})
    apply_result = await apply_config(session, tenant_id=str(user.tenant_id), user_id=str(user.id), ami=ami)
    await session.commit()
    route = await _get_route_or_404(session, str(user.tenant_id), str(route.id))
    item = await _route_out(session, str(user.tenant_id), route)
    return InboundRouteMutated(item=item, apply=apply_result.to_dict())


async def _get_route_or_404(session: AsyncSession, tenant_id: str, route_id: str) -> InboundRoute:
    return await get_tenant_scoped_or_404(
        session, InboundRoute, tenant_id, route_id, not_found_message="Marshrut topilmadi",
        options=_ROUTE_OPTIONS,
    )


async def _validate_cid_lookup_source_id(session: AsyncSession, tenant_id: str, source_id: str) -> None:
    found = (await session.execute(
        select(CidLookupSource.id).where(CidLookupSource.tenant_id == tenant_id, CidLookupSource.id == source_id)
    )).first()
    if found is None:
        raise ApiError(422, "invalid_target", "Noto'g'ri CID Lookup manbai", field="cid_lookup_source_id")


async def _apply_did_cid_change(
    session: AsyncSession, tenant_id: str, route: InboundRoute, payload: UpdateInboundRoutePayload,
) -> dict:
    """DID/CallerID ziddiyatini tekshiradi, `route`ga yozadi, diff bo'lagini
    qaytaradi — asosiy funksiyadan ajratilgan (CRAP/CC pasaytirish uchun)."""
    new_did = (payload.did if payload.did is not None else route.did) or ""
    new_cid = (payload.cid if payload.cid is not None else route.callerid_pattern) or ""
    if (new_did, new_cid) != (route.did, route.callerid_pattern):
        if await _did_conflict_exists(session, tenant_id, new_did, new_cid, exclude_id=str(route.id)):
            raise ApiError(409, "did_conflict", "Shu DID/CallerID uchun marshrut allaqachon mavjud", field="did")
    route.did = new_did
    route.callerid_pattern = new_cid
    return {"did": new_did, "cid": new_cid}


async def _apply_route_optional_fields(
    session: AsyncSession, tenant_id: str, route: InboundRoute, payload: UpdateInboundRoutePayload, diff: dict,
) -> None:
    """`name`/`target_id`/`enabled` — berilgan bo'lsa yozadi va `diff`ga qo'shadi."""
    if payload.name is not None:
        route.name = payload.name
        diff["name"] = payload.name
    if payload.target_id is not None:
        route.target_id = await _validate_target(session, tenant_id, payload.target_id)
        diff["target_id"] = payload.target_id
    if payload.enabled is not None:
        route.enabled = payload.enabled
        diff["enabled"] = payload.enabled
    await _apply_cid_name_prefix(route, payload, diff)
    await _apply_alert_info(route, payload, diff)
    await _apply_cid_lookup_source(session, tenant_id, route, payload, diff)


async def _apply_cid_name_prefix(
    route: InboundRoute, payload: UpdateInboundRoutePayload, diff: dict,
) -> None:
    if payload.cid_name_prefix_clear:
        route.callerid_name_prefix = None
        diff["cid_name_prefix"] = None
    elif payload.cid_name_prefix is not None:
        route.callerid_name_prefix = payload.cid_name_prefix
        diff["cid_name_prefix"] = payload.cid_name_prefix


async def _apply_alert_info(
    route: InboundRoute, payload: UpdateInboundRoutePayload, diff: dict,
) -> None:
    if payload.alert_info_clear:
        route.alert_info = None
        diff["alert_info"] = None
    elif payload.alert_info is not None:
        route.alert_info = payload.alert_info
        diff["alert_info"] = payload.alert_info


async def _apply_cid_lookup_source(
    session: AsyncSession, tenant_id: str, route: InboundRoute, payload: UpdateInboundRoutePayload, diff: dict,
) -> None:
    if payload.cid_lookup_source_clear:
        route.cid_lookup_source_id = None
        diff["cid_lookup_source_id"] = None
    elif payload.cid_lookup_source_id is not None:
        await _validate_cid_lookup_source_id(session, tenant_id, payload.cid_lookup_source_id)
        route.cid_lookup_source_id = payload.cid_lookup_source_id
        diff["cid_lookup_source_id"] = payload.cid_lookup_source_id


@router.patch("/inbound-routes/{route_id}", response_model=InboundRouteMutated)
async def update_inbound_route(
    route_id: str, payload: UpdateInboundRoutePayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> InboundRouteMutated:
    route = await _get_route_or_404(session, str(user.tenant_id), route_id)
    check_not_stale(route.updated_at, payload.updated_at)

    diff = await _apply_did_cid_change(session, str(user.tenant_id), route, payload)
    await _apply_route_optional_fields(session, str(user.tenant_id), route, payload, diff)

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "did_conflict", "Shu DID/CallerID uchun marshrut allaqachon mavjud",
                        field="did") from exc

    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="inbound_route.update", entity="inbound_route", entity_id=str(route.id), diff=diff)
    apply_result = await apply_config(session, tenant_id=str(user.tenant_id), user_id=str(user.id), ami=ami)
    await session.commit()
    route = await _get_route_or_404(session, str(user.tenant_id), route_id)
    item = await _route_out(session, str(user.tenant_id), route)
    return InboundRouteMutated(item=item, apply=apply_result.to_dict())


@router.delete("/inbound-routes/{route_id}", status_code=204, response_model=None)
async def delete_inbound_route(
    route_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
    ami=Depends(get_ami),
) -> None:
    route = await _get_route_or_404(session, str(user.tenant_id), route_id)
    await session.delete(route)
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="inbound_route.delete", entity="inbound_route", entity_id=str(route_id))
    await apply_config(session, tenant_id=str(user.tenant_id), user_id=str(user.id), ami=ami)
    await session.commit()
