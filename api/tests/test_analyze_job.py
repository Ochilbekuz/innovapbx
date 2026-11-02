"""`app/services/fpbx/analyze_job.py::run_analyze_job`/`_run_analyze_job` — DB/tarmoqsiz:
soxta sessiya + `plan_mod.analyze` monkeypatch (M4b `backup_job.py` uslubidagi
try/finally qulf-bo'shatish va muvaffaqiyat/xato yo'llarini tekshiradi)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.fpbx import analyze_job as aj
from app.services.fpbx.mappers import Entry


class _Session:
    def __init__(self, job):
        self._job = job
        self.commits = 0

    async def get(self, _model, _pk):
        return self._job

    async def commit(self):
        self.commits += 1


def _job(**kw):
    base = dict(id="j1", bundle_path="/tmp/bundle", plan=None, status="analyzing",
                step="x", progress=0, error=None, finished_at=None)
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_run_analyze_job_success_populates_plan(monkeypatch):
    job = _job()
    session = _Session(job)
    entry = Entry(kind="extension", source_ref="users:101", name="101", number="101", action="create")

    async def fake_analyze(_bundle_dir, _session, _tenant_id):
        return SimpleNamespace(items=[entry], ignored=[{"table": "x", "key": "1", "reason": "r"}],
                                warnings=[{"code": "w", "message": "m"}])

    monkeypatch.setattr(aj.plan_mod, "analyze", fake_analyze)
    await aj._run_analyze_job(session, "j1", "t1")

    assert job.status == "analyzed"
    assert job.step is None
    assert job.progress == 100
    assert job.finished_at is not None
    assert job.plan["items"] == [entry.public_dict()]
    assert job.plan["ignored"] == [{"table": "x", "key": "1", "reason": "r"}]
    assert job.plan["warnings"] == [{"code": "w", "message": "m"}]
    assert session.commits == 1


@pytest.mark.asyncio
async def test_run_analyze_job_failure_marks_job_failed(monkeypatch):
    job = _job()
    session = _Session(job)

    async def fake_analyze(_bundle_dir, _session, _tenant_id):
        raise ValueError("buzilgan to'plam")

    monkeypatch.setattr(aj.plan_mod, "analyze", fake_analyze)
    await aj._run_analyze_job(session, "j1", "t1")

    assert job.status == "failed"
    assert job.error == {"code": "analyze_failed", "message": "buzilgan to'plam"}
    assert job.finished_at is not None
    assert session.commits == 1


@pytest.mark.asyncio
async def test_run_analyze_job_missing_job_is_noop(monkeypatch):
    session = _Session(None)

    async def fake_analyze(*_a, **_kw):
        raise AssertionError("chaqirilmasligi kerak")

    monkeypatch.setattr(aj.plan_mod, "analyze", fake_analyze)
    await aj._run_analyze_job(session, "missing", "t1")
    assert session.commits == 0


@pytest.mark.asyncio
async def test_run_analyze_job_releases_lock_on_success(monkeypatch):
    released = {"n": 0}

    class _Lock:
        async def release(self):
            released["n"] += 1

    job = _job()

    class _SessionFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return _Session(job)

        async def __aexit__(self, *_exc):
            return False

    async def fake_run(_session, _job_id, _tenant_id):
        return None

    monkeypatch.setattr(aj, "_run_analyze_job", fake_run)
    await aj.run_analyze_job(_SessionFactory(), object(), _Lock(), "j1", "t1")
    assert released["n"] == 1


@pytest.mark.asyncio
async def test_run_analyze_job_releases_lock_even_on_exception(monkeypatch):
    released = {"n": 0}

    class _Lock:
        async def release(self):
            released["n"] += 1

    class _SessionFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return _Session(_job())

        async def __aexit__(self, *_exc):
            return False

    async def fake_run(_session, _job_id, _tenant_id):
        raise RuntimeError("kutilmagan")

    monkeypatch.setattr(aj, "_run_analyze_job", fake_run)
    with pytest.raises(RuntimeError):
        await aj.run_analyze_job(_SessionFactory(), object(), _Lock(), "j1", "t1")
    assert released["n"] == 1
