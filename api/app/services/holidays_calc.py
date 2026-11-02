"""Tenant bayramlari to'plami — `time_conditions.py` (state_now) va
`holidays.py` (CRUD/import) ikkisi ham ishlatadi (DRY, aylanma import yo'q)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Holiday


async def holidays_mmdd_set(session: AsyncSession, tenant_id: str) -> set[tuple[int, int]]:
    days = (await session.execute(
        select(Holiday.day).where(Holiday.tenant_id == tenant_id))).scalars().all()
    return {(d.month, d.day) for d in days}
