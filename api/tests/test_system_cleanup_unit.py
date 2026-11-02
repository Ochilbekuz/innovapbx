"""`POST /system/cleanup[/preview]` — uchta toifa (yozuvlar/zaxiralar/ko'chirish
bog'lamlari) soxta sessiya bilan (bazasiz, diskka faqat `tmp_path` ichida tegiladi)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.core import config as config_module
from app.core.errors import ApiError
from app.schemas import CleanupIn
from app.services import system_cleanup as sc
from tests._async_helpers import const_async as _const_async

NOW = datetime(2026, 11, 2, tzinfo=timezone.utc)


class _Result:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self.value or []))


class FakeSession:
    """`execute` natijalari navbat bilan beriladi; `delete`/`add` — kuzatuv ro'yxati
    (mavjud `test_m3b_services_unit.py::FakeSession`ga `delete()` qo'shilgan nusxasi)."""

    def __init__(self, *results) -> None:
        self.results = list(results)
        self.deleted: list = []
        self.added: list = []

    async def execute(self, stmt, params=None):
        return _Result(self.results.pop(0) if self.results else None)

    async def delete(self, obj):
        self.deleted.append(obj)

    def add(self, obj):
        self.added.append(obj)

    async def get(self, model, key):
        return None


def _rec(path="a/b.wav", size_bytes=100, started_at=None):
    return SimpleNamespace(path=path, size_bytes=size_bytes, started_at=started_at or (NOW - timedelta(days=400)),
                            deleted_at=None, tenant_id="t")


def _backup(id=None, size_bytes=10, started_at=None, status="done", copies=None):
    return SimpleNamespace(id=id or uuid.uuid4(), size_bytes=size_bytes, started_at=started_at or NOW,
                            status=status, copies=copies or [])


def _job(id=None, status="done"):
    return SimpleNamespace(id=id or uuid.uuid4(), status=status)


# --------------------------------------------------------------- validate_cleanup_payload
def test_validate_cleanup_payload_all_empty_raises():
    with pytest.raises(ApiError) as exc:
        sc.validate_cleanup_payload(CleanupIn())
    assert exc.value.status_code == 422


def test_validate_cleanup_payload_one_set_ok():
    sc.validate_cleanup_payload(CleanupIn(recordings_older_than_days=30))
    sc.validate_cleanup_payload(CleanupIn(backups_keep_last=5))
    sc.validate_cleanup_payload(CleanupIn(migrations=True))


# --------------------------------------------------------------- yozuvlar
@pytest.mark.asyncio
async def test_recordings_preview_sums_candidate_bytes():
    rows = [_rec(size_bytes=100), _rec(size_bytes=50)]
    session = FakeSession(rows)
    out = await sc._recordings_preview(session, "t", 30, NOW)
    assert out == {"files": 2, "bytes": 150}


@pytest.mark.asyncio
async def test_recordings_preview_empty():
    session = FakeSession([])
    out = await sc._recordings_preview(session, "t", 30, NOW)
    assert out == {"files": 0, "bytes": 0}


@pytest.mark.asyncio
async def test_recordings_cleanup_single_batch(monkeypatch):
    rows = [_rec(path="a.wav", size_bytes=100), _rec(path="b.wav", size_bytes=50)]
    session = FakeSession(rows)  # candidates so'rovi uchun
    monkeypatch.setattr(sc.recordings, "purge_tenant", _make_purge_tenant([(2, [])]))
    errors: list[str] = []
    out = await sc._recordings_cleanup(session, "t", 30, NOW, errors)
    assert out == {"files": 2, "bytes": 150} and errors == []


@pytest.mark.asyncio
async def test_recordings_cleanup_partial_failure_excludes_bytes(monkeypatch):
    rows = [_rec(path="ok.wav", size_bytes=100), _rec(path="bad.wav", size_bytes=50)]
    session = FakeSession(rows)
    monkeypatch.setattr(sc.recordings, "purge_tenant", _make_purge_tenant([(1, ["bad.wav: disk xatosi"])]))
    errors: list[str] = []
    out = await sc._recordings_cleanup(session, "t", 30, NOW, errors)
    assert out == {"files": 1, "bytes": 100} and errors == ["bad.wav: disk xatosi"]


@pytest.mark.asyncio
async def test_recordings_cleanup_loops_until_non_full_batch(monkeypatch):
    rows = [_rec(path=f"{i}.wav", size_bytes=1) for i in range(3)]
    session = FakeSession(rows)
    monkeypatch.setattr(sc.recordings, "PURGE_BATCH_LIMIT", 2)
    calls = _make_purge_tenant([(2, []), (1, [])])
    monkeypatch.setattr(sc.recordings, "purge_tenant", calls)
    errors: list[str] = []
    out = await sc._recordings_cleanup(session, "t", 30, NOW, errors)
    assert out == {"files": 3, "bytes": 3}
    assert calls.n_calls == 2


@pytest.mark.asyncio
async def test_recordings_cleanup_stops_when_whole_batch_fails(monkeypatch):
    # Butun to'plam xato (faqat o'qish disk) — o'sha qatorlar qayta tanlanadi; sikl to'xtashi shart.
    rows = [_rec(path=f"{i}.wav", size_bytes=1) for i in range(2)]
    session = FakeSession(rows)
    monkeypatch.setattr(sc.recordings, "PURGE_BATCH_LIMIT", 2)
    calls = _make_purge_tenant([(0, ["0.wav: ro", "1.wav: ro"])] * 5)
    monkeypatch.setattr(sc.recordings, "purge_tenant", calls)
    errors: list[str] = []
    out = await sc._recordings_cleanup(session, "t", 30, NOW, errors)
    assert out == {"files": 0, "bytes": 0}
    assert calls.n_calls == 1


@pytest.mark.asyncio
async def test_recordings_cleanup_no_candidates_skips_purge(monkeypatch):
    session = FakeSession([])
    called = False

    async def _should_not_run(*a, **k):
        nonlocal called
        called = True
        return (0, [])
    monkeypatch.setattr(sc.recordings, "purge_tenant", _should_not_run)
    out = await sc._recordings_cleanup(session, "t", 30, NOW, [])
    assert out == {"files": 0, "bytes": 0} and called is False


def _make_purge_tenant(returns: list[tuple[int, list[str]]]):
    """`purge_tenant`ni soxtalashtiradi — har chaqiruvda navbatdagi natijani
    qaytaradi (oxirgisidan keyin takrorlaydi), chaqiruv sonini `n_calls`da sanaydi."""
    state = {"i": 0}

    async def _fake(session, tenant_id, days, now):
        value = returns[min(state["i"], len(returns) - 1)]
        state["i"] += 1
        _fake.n_calls += 1
        return value
    _fake.n_calls = 0
    return _fake


# --------------------------------------------------------------- zaxiralar
def test_backups_to_delete_keeps_last_n():
    old = _backup(started_at=NOW - timedelta(days=2))
    mid = _backup(started_at=NOW - timedelta(days=1))
    new = _backup(started_at=NOW)
    doomed = sc._backups_to_delete([old, mid, new], keep_last=1)
    assert doomed == [old, mid]


@pytest.mark.asyncio
async def test_backups_preview_sums_doomed_bytes():
    old = _backup(size_bytes=10, started_at=NOW - timedelta(days=2))
    new = _backup(size_bytes=20, started_at=NOW)
    session = FakeSession([old, new])
    out = await sc._backups_preview(session, "t", keep_last=1)
    assert out == {"files": 1, "bytes": 10}


@pytest.mark.asyncio
async def test_backups_cleanup_deletes_copies_and_rows(monkeypatch):
    copy = SimpleNamespace(id=uuid.uuid4())
    old = _backup(size_bytes=10, started_at=NOW - timedelta(days=2), copies=[copy])
    new = _backup(size_bytes=20, started_at=NOW)
    session = FakeSession([old, new])
    deleted_copies: list = []

    async def _fake_delete_one_copy(session, backups_dir, backup_cfg, copy_obj):
        deleted_copies.append(copy_obj)

    monkeypatch.setattr(sc.backup_delete, "delete_one_copy", _fake_delete_one_copy)
    monkeypatch.setattr(sc.backup_delete, "backup_cfg_of", _const_async({}))
    out = await sc._backups_cleanup(session, "t", "/tmp", keep_last=1, errors=[])
    assert out == {"files": 1, "bytes": 10}
    assert deleted_copies == [copy]
    assert session.deleted == [old]


# --------------------------------------------------------------- ko'chirish bog'lamlari
def test_within_migrations_dir_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module.settings, "migrations_dir", str(tmp_path))
    assert sc._within_migrations_dir(tmp_path / "abc") is True
    assert sc._within_migrations_dir(tmp_path / ".." / "etc") is False


@pytest.mark.asyncio
async def test_migrations_preview_scans_eligible_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module.settings, "migrations_dir", str(tmp_path))
    job = _job(status="done")
    (tmp_path / str(job.id)).mkdir()
    (tmp_path / str(job.id) / "f.sql").write_bytes(b"12345")
    session = FakeSession([job])
    out = await sc._migrations_preview(session, "t")
    assert out == {"files": 1, "bytes": 5}


@pytest.mark.asyncio
async def test_migrations_cleanup_removes_dir_and_row(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module.settings, "migrations_dir", str(tmp_path))
    job = _job(status="done")
    job_dir = tmp_path / str(job.id)
    job_dir.mkdir()
    (job_dir / "f.sql").write_bytes(b"123")
    session = FakeSession([job])
    errors: list[str] = []
    out = await sc._migrations_cleanup(session, "t", errors)
    assert out == {"files": 1, "bytes": 3} and errors == []
    assert not job_dir.exists()
    assert session.deleted == [job]


@pytest.mark.asyncio
async def test_migrations_cleanup_skips_outside_base_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module.settings, "migrations_dir", str(tmp_path))
    job = _job(status="done")
    session = FakeSession([job])
    errors: list[str] = []
    monkeypatch.setattr(sc, "_within_migrations_dir", lambda p: False)
    out = await sc._migrations_cleanup(session, "t", errors)
    assert out == {"files": 0, "bytes": 0}
    assert len(errors) == 1 and session.deleted == []


# --------------------------------------------------------------- orkestrator
@pytest.mark.asyncio
async def test_preview_combines_categories_and_never_deletes(monkeypatch):
    monkeypatch.setattr(sc, "_recordings_preview", _const_async({"files": 1, "bytes": 10}))
    monkeypatch.setattr(sc, "_backups_preview", _const_async({"files": 2, "bytes": 20}))
    monkeypatch.setattr(sc, "_migrations_preview", _const_async({"files": 3, "bytes": 30}))
    payload = CleanupIn(recordings_older_than_days=30, backups_keep_last=5, migrations=True)
    out = await sc.preview(FakeSession(), "t", payload, NOW)
    assert out.total_bytes == 60 and out.errors == []
    assert out.recordings.files == 1 and out.backups.files == 2 and out.migrations.files == 3


@pytest.mark.asyncio
async def test_preview_only_requested_categories_run():
    payload = CleanupIn(recordings_older_than_days=30)
    out = await sc.preview(FakeSession([]), "t", payload, NOW)
    assert out.backups.files == 0 and out.migrations.files == 0


@pytest.mark.asyncio
async def test_execute_combines_categories_and_errors(monkeypatch):
    async def _fake_recordings_cleanup(session, tenant_id, days, now, errors):
        errors.append("x: xato")
        return {"files": 1, "bytes": 10}
    monkeypatch.setattr(sc, "_recordings_cleanup", _fake_recordings_cleanup)
    payload = CleanupIn(recordings_older_than_days=30)
    out = await sc.execute(FakeSession(), "t", "/tmp", payload, NOW)
    assert out.total_bytes == 10 and out.errors == ["x: xato"]
