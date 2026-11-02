"""Bir vaqtda bitta ish — zaxira YOKI tiklash (m4b-contract.md §0: "Bir vaqtda bitta ish...
pg advisory lock -> 409 job_running").

`pg_advisory_xact_lock` (`app/db/session.py::lock_tenant`) TRANZAKSIYA bilan avtomatik
bo'shaydi — zaxira/tiklash ishi esa daqiqalab davom etadi va bir nechta alohida
tranzaksiya/commit qiladi, shu sabab bu yerda ALOHIDA, ishning BOSHIDAN OXIRIGACHA ochiq
turadigan ulanish ustida sessiya-darajali `pg_try_advisory_lock`/`pg_advisory_unlock`
ishlatiladi. Ulanish uzilsa (jarayon yiqilsa ham) Postgres qulfni avtomatik bo'shatadi —
osilib qolgan qulf xavfi yo'q.

`JOB_LOCK_KEY` tenant qulflari (`tenant_lock_key()` — int4 ishorali diapazonda, taxminan
+-2**31) bilan HECH QACHON to'qnashmaydigan, shu diapazondan tashqaridagi doimiy qiymat."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

JOB_LOCK_KEY = 1 << 40  # tenant_lock_key() diapazonidan (+-2**31) tashqarida


class JobAlreadyRunningError(Exception):
    """Boshqa zaxira/tiklash ishi allaqachon ketayotgan edi (router — 409 `job_running`)."""


@dataclass
class JobLock:
    """`try_acquire_job_lock()` natijasi — ish tugagach `release()` SHART (odatda `finally`da)."""

    _conn: AsyncConnection

    async def release(self) -> None:
        await self._conn.execute(text("select pg_advisory_unlock(:key)"), {"key": JOB_LOCK_KEY})
        await self._conn.close()


async def try_acquire_job_lock(engine: AsyncEngine) -> JobLock:
    """Darhol qaytadi: band bo'lsa `JobAlreadyRunningError` (ulanish yopiladi), aks holda
    qulflangan `JobLock` (chaqiruvchi fon vazifa tugagach `release()` qilishi SHART)."""
    conn = await engine.connect()
    result: Result = await conn.execute(text("select pg_try_advisory_lock(:key)"), {"key": JOB_LOCK_KEY})
    if not result.scalar_one():
        await conn.close()
        raise JobAlreadyRunningError("boshqa zaxira/tiklash ishi ketayotgan edi")
    return JobLock(conn)
