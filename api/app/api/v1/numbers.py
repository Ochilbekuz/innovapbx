"""Raqamlar — m1a-contract.md «Raqamlar»: `GET /numbers/free`."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_admin
from app.db.models import User
from app.schemas import FreeNumbersOut
from app.services.numbers import free_numbers

router = APIRouter(prefix="/numbers", tags=["numbers"])


@router.get("/free", response_model=FreeNumbersOut)
async def list_free_numbers(
    from_: int = Query(default=100, alias="from"), to: int = 999, limit: int = 20,
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> FreeNumbersOut:
    items = await free_numbers(session, str(user.tenant_id), from_n=from_, to_n=to, limit=limit)
    return FreeNumbersOut(items=items)
