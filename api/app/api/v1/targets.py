"""Manzil tanlagich — m1a-contract.md: `GET /targets?kind=a,b&q=`,
`GET /targets/{id}/usages`. Barcha M1a turlari (extension/ring_group/queue/
ivr/time_condition/hangup/busy)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_session, require_admin
from app.core.ids import parse_uuid
from app.db.models import User
from app.schemas import TargetUsage
from app.services.target_resolution import list_targets, resolve_target
from app.services.usages import usages_for_target
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/targets", tags=["targets"])


@router.get("")
async def list_targets_endpoint(
    kind: str | None = None, q: str | None = None,
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> dict:
    kinds = [k.strip() for k in kind.split(",") if k.strip()] if kind else None
    items = await list_targets(session, str(user.tenant_id), kinds=kinds, q=q)
    return {"items": items}


@router.get("/{target_id}/usages")
async def target_usages(
    target_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> dict:
    valid_id = parse_uuid(target_id, not_found_message="Manzil topilmadi")
    resolved = await resolve_target(session, str(user.tenant_id), str(valid_id))
    if resolved is None:
        return {"items": []}
    usages = await usages_for_target(session, str(user.tenant_id), str(valid_id))
    return {"items": [TargetUsage(**u) for u in usages]}
