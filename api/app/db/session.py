"""Async SQLAlchemy sessiya + tenant bo'yicha advisory lock.

`pg_advisory_xact_lock` — tranzaksiya davomida qulflanadi, commit/rollback'da
avtomatik bo'shaydi (architecture.md: «qo'llash — tenant bo'yicha
pg_advisory_xact_lock»). Lock kaliti — tenant UUID'ning past 64 biti
(bigint ustuniga sig'adigan hash).
"""
from __future__ import annotations

import zlib
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True, pool_size=10)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def tenant_lock_key(tenant_id: str) -> int:
    """UUID -> bigint (signed int4 chegarasida) — `pg_advisory_xact_lock` bitta argumentli
    `bigint` shaklini kutadi."""
    crc = zlib.crc32(tenant_id.encode("utf-8"))
    return crc - (1 << 31)  # int4 ishorali diapazonga tushirish


async def lock_tenant(session: AsyncSession, tenant_id: str) -> None:
    await session.execute(text("select pg_advisory_xact_lock(:key)"),
                           {"key": tenant_lock_key(tenant_id)})
