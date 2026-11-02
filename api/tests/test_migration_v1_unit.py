"""`app/api/v1/migration.py` — M5a 1-bosqich: `/migration/freepbx` DB/tarmoqsiz.
`tests/test_backups_v1_unit.py` bilan BIR XIL qolip: soxta sessiya, `record_audit`/
`usernames_by_id`/`get_tenant_scoped_or_404`/`try_acquire_job_lock`/`asyncio.create_task`
monkeypatch."""
from __future__ import annotations

import io
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api.v1 import migration as mg
from app.core.errors import ApiError
from app.schemas_migration import PatchPlanPayload

FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "freepbx-fixture" / "bundle" / "fpbx-export-fixture.tar.gz"

USER = SimpleNamespace(id="u1", tenant_id="t1")
NOW = datetime(2026, 10, 30, 10, 0, tzinfo=timezone.utc)


class _ScalarsResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _Session:
    def __init__(self, *, rows=None, get_map=None):
        self.rows = rows or []
        self.get_map = get_map or {}
        self.added: list = []
        self.deleted: list = []
        self.flushes = self.commits = 0

    async def execute(self, _query):
        return _ScalarsResult(self.rows)

    async def get(self, model, pk):
        return self.get_map.get((model.__name__, pk))

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def flush(self):
        self.flushes += 1
        # Haqiqiy Postgres `server_default`larini simulyatsiya qiladi (`backups.py`
        # uchun `test_backups_v1_unit.py`dagi BIR XIL qolip).
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = "new-job-id"
            if getattr(obj, "created_at", None) is None:
                obj.created_at = NOW

    async def commit(self):
        self.commits += 1


def _job(**kw):
    base = dict(id="j1", tenant_id="t1", source="upload", status="uploaded", step=None,
                progress=None, bundle_path="/tmp/bundle-root", source_meta=None, plan=None,
                options={"rotate_weak_secrets": False}, result=None, error=None,
                pre_import_backup_id=None, created_by=None, created_at=NOW, finished_at=None)
    base.update(kw)
    return SimpleNamespace(**base)


def _plan_item(**kw):
    base = dict(kind="extension", source_ref="users:101", name="101", number="101",
                action="create", reason=None, warnings=[], depends_on=[], replaceable=True,
                has_secret=False, weak_secret=False)
    base.update(kw)
    return base


@pytest.fixture
def env(monkeypatch):
    state: dict = {"audit": []}

    async def fake_audit(session, **kw):
        state["audit"].append(kw)

    monkeypatch.setattr(mg, "record_audit", fake_audit)
    return state


class _UploadFile:
    """`fastapi.UploadFile`ning kerakli qismi — `async .read(n)` qism-qism beradi."""

    def __init__(self, data: bytes, filename: str = "bundle.tar.gz"):
        self.filename = filename
        self._buf = io.BytesIO(data)

    async def read(self, n: int) -> bytes:
        return self._buf.read(n)


def _garbage_tar_gz() -> bytes:
    return b"not-a-real-gzip-tar-archive" * 10


def _traversal_tar_gz() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="fpbx-export-x/../../../tmp/m5a-pwned-unit")
        data = b"pwned"
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


# ------------------------------------------------------------------ GET /export-script
@pytest.mark.asyncio
async def test_download_export_script_returns_file_response():
    resp = await mg.download_export_script(user=USER)
    assert resp.media_type == "text/x-shellscript"
    assert resp.filename == "innova-fpbx-export.sh"
    assert Path(resp.path).is_file()


# ------------------------------------------------------------------ POST /upload
@pytest.mark.asyncio
async def test_upload_bundle_success_creates_job(monkeypatch, env, tmp_path):
    monkeypatch.setattr(mg.settings, "migrations_dir", str(tmp_path))
    file = _UploadFile(FIXTURE.read_bytes())
    session = _Session()
    out = await mg.upload_bundle(file=file, session=session, user=USER)
    assert out.item.source == "upload"
    assert out.item.status == "uploaded"
    assert out.item.source_meta.freepbx_version is not None
    assert session.commits == 1
    job = session.added[0]
    assert Path(job.bundle_path).exists()
    assert (Path(job.bundle_path) / "meta.json").exists()


@pytest.mark.asyncio
async def test_upload_bundle_garbage_rejected_422(monkeypatch, env, tmp_path):
    monkeypatch.setattr(mg.settings, "migrations_dir", str(tmp_path))
    file = _UploadFile(_garbage_tar_gz())
    session = _Session()
    with pytest.raises(ApiError) as e:
        await mg.upload_bundle(file=file, session=session, user=USER)
    assert (e.value.status_code, e.value.code) == (422, "bundle_invalid")
    assert session.commits == 0
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_upload_bundle_traversal_rejected_422_and_sandboxed(monkeypatch, env, tmp_path):
    monkeypatch.setattr(mg.settings, "migrations_dir", str(tmp_path))
    file = _UploadFile(_traversal_tar_gz())
    session = _Session()
    with pytest.raises(ApiError) as e:
        await mg.upload_bundle(file=file, session=session, user=USER)
    assert (e.value.status_code, e.value.code) == (422, "bundle_invalid")
    assert not Path("/tmp/m5a-pwned-unit").exists()


# ------------------------------------------------------------------ POST /jobs/{id}/analyze
@pytest.mark.asyncio
async def test_analyze_job_endpoint_success_schedules_task(monkeypatch, env):
    job = _job()
    created_tasks = []

    async def fake_scoped(_session, _model, _tenant_id, _job_id, **_kw):
        return job

    async def fake_acquire(_engine):
        return SimpleNamespace(release=lambda: None)

    monkeypatch.setattr(mg, "get_tenant_scoped_or_404", fake_scoped)
    monkeypatch.setattr(mg, "try_acquire_job_lock", fake_acquire)
    monkeypatch.setattr(mg.asyncio, "create_task", lambda coro: (created_tasks.append(coro), coro.close())[0])
    session = _Session(get_map={("SystemSettings", "t1"): None})
    out = await mg.analyze_job_endpoint("j1", session=session, user=USER)
    assert out.item.status == "analyzing"
    assert job.status == "analyzing" and job.progress == 0
    assert session.commits == 1
    assert len(created_tasks) == 1


@pytest.mark.asyncio
async def test_analyze_job_endpoint_bundle_missing_409(monkeypatch, env):
    job = _job(bundle_path=None)

    async def fake_scoped(_session, _model, _tenant_id, _job_id, **_kw):
        return job

    monkeypatch.setattr(mg, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session()
    with pytest.raises(ApiError) as e:
        await mg.analyze_job_endpoint("j1", session=session, user=USER)
    assert (e.value.status_code, e.value.code) == (409, "bundle_missing")


@pytest.mark.asyncio
async def test_analyze_job_endpoint_already_running_409(monkeypatch, env):
    job = _job()

    async def fake_scoped(_session, _model, _tenant_id, _job_id, **_kw):
        return job

    async def fake_acquire(_engine):
        raise mg.JobAlreadyRunningError()

    monkeypatch.setattr(mg, "get_tenant_scoped_or_404", fake_scoped)
    monkeypatch.setattr(mg, "try_acquire_job_lock", fake_acquire)
    session = _Session()
    with pytest.raises(ApiError) as e:
        await mg.analyze_job_endpoint("j1", session=session, user=USER)
    assert (e.value.status_code, e.value.code) == (409, "job_running")


# ------------------------------------------------------------------ GET /jobs, GET /jobs/{id}
@pytest.mark.asyncio
async def test_list_jobs_returns_items():
    job = _job(created_at=NOW)
    session = _Session(rows=[job], get_map={("SystemSettings", "t1"): None})
    out = await mg.list_jobs(session=session, user=USER)
    assert len(out.items) == 1 and out.items[0].id == "j1"


@pytest.mark.asyncio
async def test_get_job_returns_item_with_backup_ready(monkeypatch):
    job = _job()

    async def fake_scoped(_session, _model, _tenant_id, _job_id, **_kw):
        return job

    monkeypatch.setattr(mg, "get_tenant_scoped_or_404", fake_scoped)
    settings_row = SimpleNamespace(backup={"passphrase_enc": "x"})
    session = _Session(get_map={("SystemSettings", "t1"): settings_row})
    out = await mg.get_job("j1", session=session, user=USER)
    assert out.item.backup_ready is True


@pytest.mark.asyncio
async def test_get_job_not_found_404(monkeypatch):
    async def fake_scoped(_session, _model, _tenant_id, _job_id, **_kw):
        raise ApiError(404, "not_found", "Ish topilmadi")

    monkeypatch.setattr(mg, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session()
    with pytest.raises(ApiError) as e:
        await mg.get_job("missing", session=session, user=USER)
    assert e.value.status_code == 404


# ------------------------------------------------------------------ GET /jobs/{id}/plan|ignored|warnings
@pytest.mark.asyncio
async def test_get_job_plan_requires_analyzed_409(monkeypatch):
    job = _job(plan=None)

    async def fake_scoped(_session, _model, _tenant_id, _job_id, **_kw):
        return job

    monkeypatch.setattr(mg, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session()
    with pytest.raises(ApiError) as e:
        await mg.get_job_plan("j1", session=session, user=USER)
    assert (e.value.status_code, e.value.code) == (409, "not_analyzed")


@pytest.mark.asyncio
async def test_get_job_plan_filters_and_paginates(monkeypatch):
    items = [_plan_item(kind="extension", source_ref=f"users:{n}", name=str(n), number=str(n))
             for n in (101, 102, 103)]
    items.append(_plan_item(kind="trunk", source_ref="trunks:1", name="sip1", number=None))
    job = _job(plan={"items": items, "ignored": [], "warnings": []})

    async def fake_scoped(_session, _model, _tenant_id, _job_id, **_kw):
        return job

    monkeypatch.setattr(mg, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session()

    out = await mg.get_job_plan("j1", kind="extension", action=None, q=None, page=1, page_size=2,
                                 session=session, user=USER)
    assert out.total == 3
    assert len(out.items) == 2

    out2 = await mg.get_job_plan("j1", kind=None, action=None, q="102", page=1, page_size=50,
                                  session=session, user=USER)
    assert out2.total == 1 and out2.items[0].number == "102"


@pytest.mark.asyncio
async def test_get_job_ignored_and_warnings(monkeypatch):
    job = _job(plan={"items": [], "ignored": [{"table": "t", "key": "k", "reason": "r"}],
                      "warnings": [{"code": "c", "message": "m"}]})

    async def fake_scoped(_session, _model, _tenant_id, _job_id, **_kw):
        return job

    monkeypatch.setattr(mg, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session()
    ignored = await mg.get_job_ignored("j1", session=session, user=USER)
    warnings = await mg.get_job_warnings("j1", session=session, user=USER)
    assert ignored.items[0].table == "t"
    assert warnings.items[0].code == "c"


# ------------------------------------------------------------------ PATCH /jobs/{id}/plan
@pytest.mark.asyncio
async def test_patch_job_plan_conflict_to_skip(monkeypatch, env):
    items = [_plan_item(action="conflict", replaceable=False)]
    job = _job(plan={"items": items, "ignored": [], "warnings": []})

    async def fake_scoped(_session, _model, _tenant_id, _job_id, **_kw):
        return job

    monkeypatch.setattr(mg, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session()
    payload = PatchPlanPayload(items=[{"kind": "extension", "source_ref": "users:101", "action": "skip"}])
    out = await mg.patch_job_plan("j1", payload, session=session, user=USER)
    assert out.item.id == "j1"
    assert job.plan["items"][0]["action"] == "skip"
    assert session.commits == 1


@pytest.mark.asyncio
async def test_patch_job_plan_conflict_to_replace_requires_replaceable(monkeypatch, env):
    items = [_plan_item(action="conflict", replaceable=False)]
    job = _job(plan={"items": items, "ignored": [], "warnings": []})

    async def fake_scoped(_session, _model, _tenant_id, _job_id, **_kw):
        return job

    monkeypatch.setattr(mg, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session()
    payload = PatchPlanPayload(items=[{"kind": "extension", "source_ref": "users:101", "action": "replace"}])
    with pytest.raises(ApiError) as e:
        await mg.patch_job_plan("j1", payload, session=session, user=USER)
    assert (e.value.status_code, e.value.code) == (422, "action_not_allowed")


@pytest.mark.asyncio
async def test_patch_job_plan_conflict_to_replace_ok_when_replaceable(monkeypatch, env):
    items = [_plan_item(action="conflict", replaceable=True)]
    job = _job(plan={"items": items, "ignored": [], "warnings": []})

    async def fake_scoped(_session, _model, _tenant_id, _job_id, **_kw):
        return job

    monkeypatch.setattr(mg, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session()
    payload = PatchPlanPayload(items=[{"kind": "extension", "source_ref": "users:101", "action": "replace"}])
    out = await mg.patch_job_plan("j1", payload, session=session, user=USER)
    assert job.plan["items"][0]["action"] == "replace"
    assert out.item.id == "j1"


@pytest.mark.asyncio
async def test_patch_job_plan_create_to_skip_and_skip_to_create(monkeypatch, env):
    items = [_plan_item(action="create"), _plan_item(kind="trunk", source_ref="trunks:1", action="skip")]
    job = _job(plan={"items": items, "ignored": [], "warnings": []})

    async def fake_scoped(_session, _model, _tenant_id, _job_id, **_kw):
        return job

    monkeypatch.setattr(mg, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session()
    payload = PatchPlanPayload(items=[
        {"kind": "extension", "source_ref": "users:101", "action": "skip"},
        {"kind": "trunk", "source_ref": "trunks:1", "action": "create"},
    ])
    await mg.patch_job_plan("j1", payload, session=session, user=USER)
    by_ref = {(i["kind"], i["source_ref"]): i for i in job.plan["items"]}
    assert by_ref[("extension", "users:101")]["action"] == "skip"
    assert by_ref[("trunk", "trunks:1")]["action"] == "create"


@pytest.mark.asyncio
async def test_patch_job_plan_disallowed_transition_422(monkeypatch, env):
    items = [_plan_item(action="create")]
    job = _job(plan={"items": items, "ignored": [], "warnings": []})

    async def fake_scoped(_session, _model, _tenant_id, _job_id, **_kw):
        return job

    monkeypatch.setattr(mg, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session()
    payload = PatchPlanPayload(items=[{"kind": "extension", "source_ref": "users:101", "action": "replace"}])
    with pytest.raises(ApiError) as e:
        await mg.patch_job_plan("j1", payload, session=session, user=USER)
    assert (e.value.status_code, e.value.code) == (422, "action_not_allowed")


@pytest.mark.asyncio
async def test_patch_job_plan_unknown_source_ref_404(monkeypatch, env):
    job = _job(plan={"items": [], "ignored": [], "warnings": []})

    async def fake_scoped(_session, _model, _tenant_id, _job_id, **_kw):
        return job

    monkeypatch.setattr(mg, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session()
    payload = PatchPlanPayload(items=[{"kind": "extension", "source_ref": "users:999", "action": "skip"}])
    with pytest.raises(ApiError) as e:
        await mg.patch_job_plan("j1", payload, session=session, user=USER)
    assert e.value.status_code == 404


# ------------------------------------------------------------------ DELETE /jobs/{id}
@pytest.mark.asyncio
async def test_delete_job_removes_dir_and_row(monkeypatch, env, tmp_path):
    monkeypatch.setattr(mg.settings, "migrations_dir", str(tmp_path))
    job_dir = tmp_path / "j1"
    job_dir.mkdir()
    (job_dir / "f").write_text("x")
    job = _job()

    async def fake_scoped(_session, _model, _tenant_id, _job_id, **_kw):
        return job

    monkeypatch.setattr(mg, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session()
    resp = await mg.delete_job("j1", session=session, user=USER)
    assert resp.status_code == 204
    assert not job_dir.exists()
    assert session.deleted == [job]
    assert session.commits == 1


@pytest.mark.asyncio
async def test_delete_job_while_analyzing_raises_409(monkeypatch, env):
    job = _job(status="analyzing")

    async def fake_scoped(_session, _model, _tenant_id, _job_id, **_kw):
        return job

    monkeypatch.setattr(mg, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session()
    with pytest.raises(ApiError) as e:
        await mg.delete_job("j1", session=session, user=USER)
    assert (e.value.status_code, e.value.code) == (409, "job_running")
