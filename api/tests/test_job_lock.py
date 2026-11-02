"""`app/services/job_lock.py` — tarmoqsiz, soxta ulanish bilan sinaladi (haqiqiy Postgres
`pg_try_advisory_lock` chaqiruvi `test_job_lock_live.py` da, `live` belgisi bilan)."""
from __future__ import annotations

import pytest

from app.services import job_lock as jl


class _FakeResult:
    def __init__(self, value: bool) -> None:
        self._value = value

    def scalar_one(self) -> bool:
        return self._value


class _FakeConn:
    def __init__(self, *, got_lock: bool) -> None:
        self.got_lock = got_lock
        self.executed: list[tuple[str, dict]] = []
        self.closed = False

    async def execute(self, stmt, params=None):  # noqa: ANN001 — SQLAlchemy `text()` obyekti
        sql = str(stmt)
        self.executed.append((sql, params or {}))
        if "pg_try_advisory_lock" in sql:
            return _FakeResult(self.got_lock)
        return _FakeResult(True)

    async def close(self) -> None:
        self.closed = True


class _FakeEngine:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def connect(self) -> _FakeConn:
        return self._conn


@pytest.mark.asyncio
async def test_try_acquire_job_lock_success_returns_lock_holding_connection_open():
    conn = _FakeConn(got_lock=True)
    lock = await jl.try_acquire_job_lock(_FakeEngine(conn))
    assert conn.closed is False
    assert conn.executed[0][1] == {"key": jl.JOB_LOCK_KEY}


@pytest.mark.asyncio
async def test_try_acquire_job_lock_busy_raises_and_closes_connection():
    conn = _FakeConn(got_lock=False)
    with pytest.raises(jl.JobAlreadyRunningError):
        await jl.try_acquire_job_lock(_FakeEngine(conn))
    assert conn.closed is True


@pytest.mark.asyncio
async def test_release_unlocks_and_closes():
    conn = _FakeConn(got_lock=True)
    lock = await jl.try_acquire_job_lock(_FakeEngine(conn))
    await lock.release()
    assert conn.closed is True
    assert any("pg_advisory_unlock" in sql for sql, _ in conn.executed)


def test_job_lock_key_outside_tenant_lock_key_range():
    """`tenant_lock_key()` crc32 asosida, +-2**31 oralig'ida — `JOB_LOCK_KEY` undan tashqarida
    bo'lishi SHART (to'qnashmasin)."""
    assert jl.JOB_LOCK_KEY > (1 << 31)
