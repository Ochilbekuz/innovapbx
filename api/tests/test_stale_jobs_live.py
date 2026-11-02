"""Qotib qolgan fon ishlari — HAQIQIY Postgres (`reports_test`): qulf bo'sh → `failed`/«interrupted»,
tugagan ishlar tegilmaydi; qulf band (boshqa jarayon ishlayapti) → hech narsa o'zgarmaydi."""
from __future__ import annotations

import secrets
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Backup, MigrationJob, RestoreJob, Tenant
from app.services.job_lock import try_acquire_job_lock
from app.services.stale_jobs import INTERRUPTED, recover_stale_jobs
from tests.test_reports_live import _DATABASE_URL

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(_DATABASE_URL is None, reason="reports_test Postgres konteyneri topilmadi"),
]


@pytest.fixture()
async def env():
    engine = create_async_engine(_DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    tid = str(uuid.uuid4())
    async with factory() as s:
        s.add(Tenant(id=tid, code=f"sj{secrets.token_hex(3)}", name="Qotgan ishlar", timezone="Asia/Tashkent"))
        await s.flush()
        for status in ("applying", "fetching", "analyzed"):
            s.add(MigrationJob(tenant_id=tid, source="upload", status=status, step="x"))
        s.add_all([Backup(tenant_id=tid, kind="manual", status="running"), Backup(tenant_id=tid, kind="manual", status="ok"),
                   RestoreJob(tenant_id=tid, source="local", status="running")])
        await s.commit()
    yield engine, factory, tid
    async with factory() as s:
        await s.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tid})
        await s.commit()
    await engine.dispose()


async def _statuses(factory, tid):
    async with factory() as s:
        jobs = (await s.execute(select(MigrationJob.status, MigrationJob.step, MigrationJob.error)
                                .where(MigrationJob.tenant_id == tid))).all()
        backups = (await s.execute(select(Backup.status, Backup.error, Backup.finished_at)
                                   .where(Backup.tenant_id == tid))).all()
        restores = (await s.execute(select(RestoreJob.status).where(RestoreJob.tenant_id == tid))).scalars().all()
    return jobs, backups, restores


async def test_recover_marks_running_jobs_failed(env):
    engine, factory, tid = env
    assert await recover_stale_jobs(factory, engine) >= 4
    jobs, backups, restores = await _statuses(factory, tid)
    assert sorted(j.status for j in jobs) == ["analyzed", "failed", "failed"]
    assert all(j.error["code"] == INTERRUPTED and j.step is None for j in jobs if j.status == "failed")
    assert sorted(b.status for b in backups) == ["failed", "ok"]
    assert all(b.error and b.finished_at for b in backups if b.status == "failed")
    assert restores == ["failed"]


async def test_recover_does_nothing_while_lock_is_held(env):
    engine, factory, tid = env
    lock = await try_acquire_job_lock(engine)
    try:
        assert await recover_stale_jobs(factory, engine) == 0
    finally:
        await lock.release()
    jobs, backups, restores = await _statuses(factory, tid)
    assert sorted(j.status for j in jobs) == ["analyzed", "applying", "fetching"]
    assert restores == ["running"]
