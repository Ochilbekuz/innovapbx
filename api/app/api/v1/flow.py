"""Qo'ng'iroq oqimi grafigi — m1a-contract.md «Qo'ng'iroq oqimi grafigi»."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_session, require_access
from app.core.lookups import get_tenant_scoped_or_404
from app.db.models import InboundRoute, Ivr, Queue, RingGroup, TimeCondition, User
from app.schemas import FlowNode, FlowOut, RouteTarget
from app.services.target_resolution import resolve_target

router = APIRouter(tags=["flow"])

_MAX_DEPTH = 12


async def _edges_for(session: AsyncSession, tenant_id: str, target: RouteTarget) -> list[tuple[str, str]]:
    """`target.kind`ga ko'ra (bola target_id, edge nomi) ro'yxati qaytaradi
    (manba topilmasa — bo'sh, `broken` allaqachon `target.broken`da ko'rsatilgan)."""
    if target.kind == "time_condition":
        tc = (await session.execute(
            select(TimeCondition).where(TimeCondition.tenant_id == tenant_id, TimeCondition.id == target.id)
        )).scalar_one_or_none()
        if tc is None:
            return []
        return [(str(tc.open_target_id), "open"), (str(tc.closed_target_id), "closed")]
    if target.kind == "ivr":
        ivr = (await session.execute(
            select(Ivr).where(Ivr.tenant_id == tenant_id, Ivr.id == target.id)
            .options(selectinload(Ivr.options))
        )).scalar_one_or_none()
        if ivr is None:
            return []
        edges = [(str(o.target_id), f"digit:{o.digit}") for o in ivr.options]
        edges.append((str(ivr.timeout_target_id), "timeout"))
        edges.append((str(ivr.invalid_target_id), "invalid"))
        return edges
    if target.kind == "ring_group":
        rg = (await session.execute(
            select(RingGroup).where(RingGroup.tenant_id == tenant_id, RingGroup.id == target.id)
        )).scalar_one_or_none()
        if rg is None:
            return []
        return [(str(rg.no_answer_target_id), "no_answer")]
    if target.kind == "queue":
        q = (await session.execute(
            select(Queue).where(Queue.tenant_id == tenant_id, Queue.id == target.id)
        )).scalar_one_or_none()
        if q is None:
            return []
        return [(str(q.timeout_target_id), "timeout")]
    return []  # extension/hangup/busy — terminal


async def _build_node(
    session: AsyncSession, tenant_id: str, target: RouteTarget, edge: str | None,
    visited: tuple[str, ...], depth: int,
) -> FlowNode:
    if target.id in visited:
        return FlowNode(target=target, edge=edge, children=[], loop=True, broken=target.broken)
    if depth >= _MAX_DEPTH or target.broken:
        return FlowNode(target=target, edge=edge, children=[], loop=False, broken=target.broken)

    children: list[FlowNode] = []
    for child_id, child_edge in await _edges_for(session, tenant_id, target):
        child_target = await resolve_target(session, tenant_id, child_id)
        if child_target is None:
            continue
        children.append(await _build_node(session, tenant_id, child_target, child_edge,
                                            visited + (target.id,), depth + 1))
    return FlowNode(target=target, edge=edge, children=children, loop=False, broken=target.broken)


@router.get("/flow/{inbound_route_id}", response_model=FlowOut)
async def get_flow(
    inbound_route_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> FlowOut:
    route = await get_tenant_scoped_or_404(
        session, InboundRoute, str(user.tenant_id), inbound_route_id, not_found_message="Marshrut topilmadi",
    )
    root_target = await resolve_target(session, str(user.tenant_id), str(route.target_id))
    if root_target is None:
        root_target = RouteTarget(id=str(route.target_id), kind="extension",
                                   label="(o'chirilgan manzil)", number=None, broken=True)
    root = await _build_node(session, str(user.tenant_id), root_target, "target", (), 1)
    return FlowOut(root=root)
