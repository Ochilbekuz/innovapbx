"""`app/api/v1/backups.py` — M4b §2: `/backups` CRUD + fon ishlar. DB/tarmoqsiz:
soxta sessiya, `get_tenant_scoped_or_404`/`usernames_by_id`/`backup_job`/`rj`
(restore_job)/`try_acquire_job_lock`/`asyncio.create_task` monkeypatch."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import backups as bk
from app.core.errors import ApiError
from app.schemas_backup import CreateBackupPayload, InspectBackupPayload, RestoreBackupPayload
from app.services.backup_format import BackupCorruptError, BadPassphraseError
from app.services.backup_targets import BackupTargetError
from app.services.job_lock import JobAlreadyRunningError
from app.services.restore_job import ActiveCallsError, RestoreNewerError

USER = SimpleNamespace(id="u1", tenant_id="t1")
NOW = datetime(2026, 10, 29, 10, 0, tzinfo=timezone.utc)


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
        self.flushes = self.commits = self.refreshed = 0

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
        # Haqiqiy Postgres `server_default=now()`ni simulyatsiya qiladi (`eager_defaults`
        # — flush'dan keyin RETURNING orqali avtomatik to'ldiriladi); soxta sessiya buni
        # qilmaydi, shu sabab yangi qo'shilgan obyektlar uchun qo'lda qo'yiladi.
        for obj in self.added:
            if getattr(obj, "started_at", "unset") is None:
                obj.started_at = NOW

    async def commit(self):
        self.commits += 1

    async def refresh(self, _obj, attribute_names=None):
        self.refreshed += 1


def _backup(**kw):
    base = dict(id="b1", tenant_id="t1", kind="manual", status="ok", components=["config"],
                step=None, progress=None, file_name="innova-host-20261029-000000-abcd1234.ibk",
                sha256="deadbeef", manifest=None, size_bytes=100, error=None, created_by=None,
                started_at=NOW, finished_at=NOW, copies=[])
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def env(monkeypatch):
    state: dict = {"audit": []}

    async def fake_audit(session, **kw):
        state["audit"].append(kw)

    monkeypatch.setattr(bk, "record_audit", fake_audit)
    monkeypatch.setattr(bk, "usernames_by_id", _fake_usernames_by_id)
    return state


async def _fake_usernames_by_id(_session, _ids):
    return {}


# ------------------------------------------------------------------ GET /backups
@pytest.mark.asyncio
async def test_list_backups_returns_items(env):
    session = _Session(rows=[_backup()])
    out = await bk.list_backups(session=session, user=USER)
    assert len(out.items) == 1 and out.items[0].id == "b1"


# ------------------------------------------------------------------ POST /backups
@pytest.mark.asyncio
async def test_create_backup_success_creates_task_and_returns_202_shape(monkeypatch, env):
    created_tasks = []
    monkeypatch.setattr(bk.asyncio, "create_task", lambda coro: (created_tasks.append(coro), coro.close())[0])

    lock = SimpleNamespace(released=0)

    async def fake_acquire(_engine):
        return lock

    async def fake_create_record(_session, **_kw):
        return _backup(id="new-id")

    monkeypatch.setattr(bk, "try_acquire_job_lock", fake_acquire)
    monkeypatch.setattr(bk.backup_job, "create_backup_record", fake_create_record)
    session = _Session()
    out = await bk.create_backup(CreateBackupPayload(components=["config"]), session=session, user=USER)
    assert out.job.kind == "backup" and out.job.id == "new-id"
    assert session.commits == 1
    assert len(created_tasks) == 1


@pytest.mark.asyncio
async def test_create_backup_job_already_running_raises_409(monkeypatch, env):
    async def fake_acquire(_engine):
        raise JobAlreadyRunningError()

    monkeypatch.setattr(bk, "try_acquire_job_lock", fake_acquire)
    session = _Session()
    with pytest.raises(ApiError) as e:
        await bk.create_backup(CreateBackupPayload(components=["config"]), session=session, user=USER)
    assert (e.value.status_code, e.value.code) == (409, "job_running")


@pytest.mark.asyncio
async def test_create_backup_passphrase_required_releases_lock_409(monkeypatch, env):
    lock = SimpleNamespace(released=0)

    async def fake_acquire(_engine):
        return lock

    async def release():
        lock.released += 1

    lock.release = release

    async def fake_create_record(_session, **_kw):
        raise bk.backup_job.PassphraseRequiredError()

    monkeypatch.setattr(bk, "try_acquire_job_lock", fake_acquire)
    monkeypatch.setattr(bk.backup_job, "create_backup_record", fake_create_record)
    session = _Session()
    with pytest.raises(ApiError) as e:
        await bk.create_backup(CreateBackupPayload(components=["config"]), session=session, user=USER)
    assert (e.value.status_code, e.value.code) == (409, "passphrase_required")
    assert lock.released == 1


# ------------------------------------------------------------------ GET /backups/restores
@pytest.mark.asyncio
async def test_list_restores_returns_items(env):
    job = SimpleNamespace(id="r1", backup_id="b1", source="local", status="ok", step=None,
                           progress=100, error=None, force=False, pre_restore_backup_id=None,
                           started_by=None, started_at=NOW, finished_at=NOW)
    session = _Session(rows=[job])
    out = await bk.list_restores(session=session, user=USER)
    assert len(out.items) == 1 and out.items[0].id == "r1"


# ------------------------------------------------------------------ GET /backups/jobs/{id} (ochiq)
_BACKUP_UUID = "11111111-1111-1111-1111-111111111111"
_RESTORE_UUID = "22222222-2222-2222-2222-222222222222"


@pytest.mark.asyncio
async def test_get_backup_job_state_maps_partial_to_ok():
    backup = _backup(status="partial", step="upload", progress=90)
    session = _Session(get_map={("Backup", _BACKUP_UUID): backup})
    out = await bk.get_backup_job_state(_BACKUP_UUID, session=session)
    assert out.kind == "backup" and out.status == "ok"


@pytest.mark.asyncio
async def test_get_backup_job_state_restore_job():
    job = SimpleNamespace(status="running", step="pg_restore", progress=50, error=None)
    session = _Session(get_map={("RestoreJob", _RESTORE_UUID): job})
    out = await bk.get_backup_job_state(_RESTORE_UUID, session=session)
    assert out.kind == "restore" and out.status == "running"


@pytest.mark.asyncio
async def test_get_backup_job_state_not_found_404():
    session = _Session()
    with pytest.raises(ApiError) as e:
        await bk.get_backup_job_state("00000000-0000-0000-0000-000000000000", session=session)
    assert e.value.status_code == 404


# ------------------------------------------------------------------ GET /backups/{id}
@pytest.mark.asyncio
async def test_get_backup_returns_item(monkeypatch, env):
    backup = _backup()

    async def fake_scoped(_session, _model, _tenant_id, _entity_id, **_kw):
        return backup

    monkeypatch.setattr(bk, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session()
    out = await bk.get_backup("b1", session=session, user=USER)
    assert out.item.id == "b1"


# ------------------------------------------------------------------ DELETE /backups/{id}
@pytest.mark.asyncio
async def test_delete_backup_removes_local_file_and_row(monkeypatch, env, tmp_path):
    monkeypatch.setattr(bk.settings, "backups_dir", str(tmp_path))
    local_file = tmp_path / "f.ibk"
    local_file.write_bytes(b"x")
    copy = SimpleNamespace(target="local", status="ok", remote_path="f.ibk")
    backup = _backup(copies=[copy])

    async def fake_scoped(_session, _model, _tenant_id, _entity_id, **_kw):
        return backup

    monkeypatch.setattr(bk, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session(get_map={("SystemSettings", "t1"): None})
    resp = await bk.delete_backup("b1", session=session, user=USER)
    assert resp.status_code == 204
    assert not local_file.exists()
    assert session.deleted == [backup]
    assert session.commits == 1


@pytest.mark.asyncio
async def test_delete_backup_swallows_remote_target_error(monkeypatch, env):
    copy = SimpleNamespace(target="s3", status="ok", remote_path="r/path")
    backup = _backup(copies=[copy])

    async def fake_scoped(_session, _model, _tenant_id, _entity_id, **_kw):
        return backup

    async def fake_s3_target(_session, _cfg):
        return "target"

    async def fake_delete_s3(_target, _path):
        raise BackupTargetError("bo'lmadi")

    monkeypatch.setattr(bk, "get_tenant_scoped_or_404", fake_scoped)
    monkeypatch.setattr(bk, "s3_target_from_settings", fake_s3_target)
    monkeypatch.setattr(bk, "delete_s3", fake_delete_s3)
    settings_row = SimpleNamespace(backup={"targets": {"s3": {}}})
    session = _Session(get_map={("SystemSettings", "t1"): settings_row})
    resp = await bk.delete_backup("b1", session=session, user=USER)
    assert resp.status_code == 204
    assert session.commits == 1


# ------------------------------------------------------------------ GET /backups/{id}/download
@pytest.mark.asyncio
async def test_download_backup_no_local_copy_raises_409(monkeypatch, env):
    backup = _backup(file_name=None)

    async def fake_scoped(_session, _model, _tenant_id, _entity_id, **_kw):
        return backup

    monkeypatch.setattr(bk, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session()
    with pytest.raises(ApiError) as e:
        await bk.download_backup("b1", session=session, user=USER)
    assert (e.value.status_code, e.value.code) == (409, "no_local_copy")


@pytest.mark.asyncio
async def test_download_backup_streams_existing_file(monkeypatch, env, tmp_path):
    monkeypatch.setattr(bk.settings, "backups_dir", str(tmp_path))
    (tmp_path / "f.ibk").write_bytes(b"x")
    backup = _backup(file_name="f.ibk")

    async def fake_scoped(_session, _model, _tenant_id, _entity_id, **_kw):
        return backup

    monkeypatch.setattr(bk, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session()
    resp = await bk.download_backup("b1", session=session, user=USER)
    assert resp.filename == "f.ibk"


# ------------------------------------------------------------------ POST /backups/{id}/fetch
@pytest.mark.asyncio
async def test_fetch_backup_copy_noop_when_local_exists(monkeypatch, env, tmp_path):
    monkeypatch.setattr(bk.settings, "backups_dir", str(tmp_path))
    (tmp_path / "f.ibk").write_bytes(b"x")
    backup = _backup(file_name="f.ibk")

    async def fake_scoped(_session, _model, _tenant_id, _entity_id, **_kw):
        return backup

    monkeypatch.setattr(bk, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session()
    out = await bk.fetch_backup_copy("b1", session=session, user=USER)
    assert out.item.id == "b1"


@pytest.mark.asyncio
async def test_fetch_backup_copy_no_remote_copy_raises_409(monkeypatch, env, tmp_path):
    monkeypatch.setattr(bk.settings, "backups_dir", str(tmp_path))
    backup = _backup(file_name="f.ibk", copies=[])

    async def fake_scoped(_session, _model, _tenant_id, _entity_id, **_kw):
        return backup

    monkeypatch.setattr(bk, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session(get_map={("SystemSettings", "t1"): None})
    with pytest.raises(ApiError) as e:
        await bk.fetch_backup_copy("b1", session=session, user=USER)
    assert (e.value.status_code, e.value.code) == (409, "no_remote_copy")


@pytest.mark.asyncio
async def test_fetch_backup_copy_fetches_from_s3_and_upserts_local(monkeypatch, env, tmp_path):
    monkeypatch.setattr(bk.settings, "backups_dir", str(tmp_path))
    remote_copy = SimpleNamespace(target="s3", status="ok", remote_path="r/path", size_bytes=1,
                                   error=None, uploaded_at=NOW)
    backup = _backup(file_name="f.ibk", copies=[remote_copy])

    async def fake_scoped(_session, _model, _tenant_id, _entity_id, **_kw):
        return backup

    async def fake_s3_target(_session, _cfg):
        return "target"

    async def fake_fetch_s3(_target, _remote, local_path):
        local_path.write_bytes(b"content")

    monkeypatch.setattr(bk, "get_tenant_scoped_or_404", fake_scoped)
    monkeypatch.setattr(bk, "s3_target_from_settings", fake_s3_target)
    monkeypatch.setattr(bk, "fetch_s3", fake_fetch_s3)
    settings_row = SimpleNamespace(backup={"targets": {"s3": {}}})
    session = _Session(get_map={("SystemSettings", "t1"): settings_row})
    out = await bk.fetch_backup_copy("b1", session=session, user=USER)
    assert out.item.id == "b1"
    assert session.commits == 1
    assert (tmp_path / "f.ibk").exists()


# ------------------------------------------------------------------ POST /backups/{id}/inspect
@pytest.mark.asyncio
async def test_inspect_backup_no_local_copy_raises_409(monkeypatch, env):
    backup = _backup(file_name=None)

    async def fake_scoped(_session, _model, _tenant_id, _entity_id, **_kw):
        return backup

    monkeypatch.setattr(bk, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session()
    with pytest.raises(ApiError) as e:
        await bk.inspect_backup("b1", InspectBackupPayload(), session=session, user=USER)
    assert (e.value.status_code, e.value.code) == (409, "no_local_copy")


@pytest.mark.asyncio
async def test_inspect_backup_bad_passphrase_422(monkeypatch, env, tmp_path):
    monkeypatch.setattr(bk.settings, "backups_dir", str(tmp_path))
    (tmp_path / "f.ibk").write_bytes(b"x")
    backup = _backup(file_name="f.ibk")

    async def fake_scoped(_session, _model, _tenant_id, _entity_id, **_kw):
        return backup

    async def fake_inspect(_session, _path, _passphrase):
        raise BadPassphraseError()

    monkeypatch.setattr(bk, "get_tenant_scoped_or_404", fake_scoped)
    monkeypatch.setattr(bk.rj, "inspect", fake_inspect)
    session = _Session()
    with pytest.raises(ApiError) as e:
        await bk.inspect_backup("b1", InspectBackupPayload(passphrase="pw"), session=session, user=USER)
    assert (e.value.status_code, e.value.code) == (422, "bad_passphrase")


@pytest.mark.asyncio
async def test_inspect_backup_persists_manifest_for_uploaded_kind(monkeypatch, env, tmp_path):
    monkeypatch.setattr(bk.settings, "backups_dir", str(tmp_path))
    (tmp_path / "f.ibk").write_bytes(b"x")
    backup = _backup(file_name="f.ibk", kind="uploaded", manifest=None, components=[])

    class _FakeManifest:
        def to_dict(self):
            return {"format": "INNOVABK1", "product_version": "0.1.0", "alembic_revision": "abc",
                    "created_at": NOW.isoformat(), "source_host": "h", "components": ["config"],
                    "parts": [], "db_key_fp": "fp"}

        components = ("config",)

    async def fake_scoped(_session, _model, _tenant_id, _entity_id, **_kw):
        return backup

    async def fake_inspect(_session, _path, _passphrase):
        return {"manifest": _FakeManifest(), "checks": {"sha256": "ok"}, "compatible": True, "warnings": []}

    monkeypatch.setattr(bk, "get_tenant_scoped_or_404", fake_scoped)
    monkeypatch.setattr(bk.rj, "inspect", fake_inspect)
    session = _Session()
    out = await bk.inspect_backup("b1", InspectBackupPayload(passphrase="pw"), session=session, user=USER)
    assert out.compatible is True
    assert backup.manifest is not None and backup.components == ["config"]
    assert session.commits == 1


# ------------------------------------------------------------------ POST /backups/{id}/restore
@pytest.mark.asyncio
async def test_restore_backup_no_local_copy_raises_409(monkeypatch, env):
    backup = _backup(file_name=None)

    async def fake_scoped(_session, _model, _tenant_id, _entity_id, **_kw):
        return backup

    monkeypatch.setattr(bk, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session()
    with pytest.raises(ApiError) as e:
        await bk.restore_backup(
            "b1", RestoreBackupPayload(confirm="TIKLASH"), session=session, user=USER, ami=None)
    assert (e.value.status_code, e.value.code) == (409, "no_local_copy")


@pytest.mark.asyncio
async def test_restore_backup_active_calls_raises_409_with_count(monkeypatch, env, tmp_path):
    monkeypatch.setattr(bk.settings, "backups_dir", str(tmp_path))
    (tmp_path / "f.ibk").write_bytes(b"x")
    backup = _backup(file_name="f.ibk")

    async def fake_scoped(_session, _model, _tenant_id, _entity_id, **_kw):
        return backup

    async def fake_precheck(*_a, **_kw):
        raise ActiveCallsError(count=3)

    monkeypatch.setattr(bk, "get_tenant_scoped_or_404", fake_scoped)
    monkeypatch.setattr(bk.rj, "precheck_and_create_job", fake_precheck)
    session = _Session()
    with pytest.raises(ApiError) as e:
        await bk.restore_backup(
            "b1", RestoreBackupPayload(confirm="TIKLASH", passphrase="pw"), session=session, user=USER, ami=None)
    assert (e.value.status_code, e.value.code) == (409, "active_calls")
    assert e.value.details == {"count": 3}


@pytest.mark.asyncio
async def test_restore_backup_newer_raises_422(monkeypatch, env, tmp_path):
    monkeypatch.setattr(bk.settings, "backups_dir", str(tmp_path))
    (tmp_path / "f.ibk").write_bytes(b"x")
    backup = _backup(file_name="f.ibk")

    async def fake_scoped(_session, _model, _tenant_id, _entity_id, **_kw):
        return backup

    async def fake_precheck(*_a, **_kw):
        raise RestoreNewerError("yangiroq")

    monkeypatch.setattr(bk, "get_tenant_scoped_or_404", fake_scoped)
    monkeypatch.setattr(bk.rj, "precheck_and_create_job", fake_precheck)
    session = _Session()
    with pytest.raises(ApiError) as e:
        await bk.restore_backup(
            "b1", RestoreBackupPayload(confirm="TIKLASH", passphrase="pw"), session=session, user=USER, ami=None)
    assert (e.value.status_code, e.value.code) == (422, "backup_newer")


@pytest.mark.asyncio
async def test_restore_backup_success_creates_task(monkeypatch, env, tmp_path):
    monkeypatch.setattr(bk.settings, "backups_dir", str(tmp_path))
    (tmp_path / "f.ibk").write_bytes(b"x")
    backup = _backup(file_name="f.ibk", kind="uploaded")
    job = SimpleNamespace(id="job1")
    lock = SimpleNamespace()
    precheck_kwargs = {}

    async def fake_scoped(_session, _model, _tenant_id, _entity_id, **_kw):
        return backup

    async def fake_precheck(*_a, **kw):
        precheck_kwargs.update(kw)
        return job, lock

    async def fake_get_tenant_code(_session, _tenant_id):
        return "demo"

    created_tasks = []
    monkeypatch.setattr(bk.asyncio, "create_task", lambda coro: (created_tasks.append(coro), coro.close())[0])
    monkeypatch.setattr(bk, "get_tenant_scoped_or_404", fake_scoped)
    monkeypatch.setattr(bk.rj, "precheck_and_create_job", fake_precheck)
    monkeypatch.setattr(bk, "get_tenant_code", fake_get_tenant_code)
    session = _Session()
    out = await bk.restore_backup(
        "b1", RestoreBackupPayload(confirm="TIKLASH", passphrase="pw"), session=session, user=USER, ami=None)
    assert out.job.kind == "restore" and out.job.id == "job1"
    assert session.commits == 1
    assert len(created_tasks) == 1
    assert precheck_kwargs["source"] == "upload"


# ------------------------------------------------------------------ _resolve_passphrase
@pytest.mark.asyncio
async def test_resolve_passphrase_uses_explicit_value_without_touching_db():
    session = _Session()  # get_map bo'sh -- chaqirilsa KeyError beradi
    out = await bk._resolve_passphrase(session, "t1", "explicit-pass")
    assert out == "explicit-pass"


@pytest.mark.asyncio
async def test_resolve_passphrase_decrypts_system_settings_when_not_given(monkeypatch):
    settings_row = SimpleNamespace(backup={"passphrase_enc": "enc-pass"})
    session = _Session(get_map={("SystemSettings", "t1"): settings_row})

    async def fake_decrypt(_session, enc):
        return f"plain:{enc}"

    monkeypatch.setattr(bk, "decrypt_secret", fake_decrypt)
    out = await bk._resolve_passphrase(session, "t1", None)
    assert out == "plain:enc-pass"


@pytest.mark.asyncio
async def test_resolve_passphrase_raises_422_when_settings_row_missing():
    session = _Session(get_map={("SystemSettings", "t1"): None})
    with pytest.raises(ApiError) as e:
        await bk._resolve_passphrase(session, "t1", None)
    assert (e.value.status_code, e.value.code) == (422, "passphrase_required")


@pytest.mark.asyncio
async def test_resolve_passphrase_raises_422_when_passphrase_not_set():
    settings_row = SimpleNamespace(backup={"passphrase_enc": None})
    session = _Session(get_map={("SystemSettings", "t1"): settings_row})
    with pytest.raises(ApiError) as e:
        await bk._resolve_passphrase(session, "t1", None)
    assert (e.value.status_code, e.value.code) == (422, "passphrase_required")


# ------------------------------------------------------------------ POST /backups/upload
class _FakeUploadFile:
    def __init__(self, chunks: list[bytes]):
        self._chunks = list(chunks)

    async def read(self, _size: int) -> bytes:
        return self._chunks.pop(0) if self._chunks else b""


@pytest.mark.asyncio
async def test_upload_backup_streams_to_disk_and_creates_record(monkeypatch, env, tmp_path):
    monkeypatch.setattr(bk.settings, "backups_dir", str(tmp_path))
    monkeypatch.setattr(bk.socket, "gethostname", lambda: "host1")
    file = _FakeUploadFile([b"hello ", b"world"])
    session = _Session()
    out = await bk.upload_backup(file=file, session=session, user=USER)
    assert out.item.kind == "uploaded" and out.item.status == "ok"
    assert out.item.size_bytes == len(b"hello world")
    written = list(tmp_path.glob("innova-host1-*.ibk"))
    assert len(written) == 1 and written[0].read_bytes() == b"hello world"
    assert session.commits == 1


# ------------------------------------------------------------------ fetch — qolgan tarmoqlar
@pytest.mark.asyncio
async def test_fetch_backup_copy_fetches_from_sftp_and_upserts_existing_local_copy(monkeypatch, env, tmp_path):
    monkeypatch.setattr(bk.settings, "backups_dir", str(tmp_path))
    remote_copy = SimpleNamespace(target="sftp", status="ok", remote_path="r/path", size_bytes=1,
                                   error="old-error", uploaded_at=None)
    existing_local = SimpleNamespace(target="local", status="failed", remote_path=None, size_bytes=None,
                                      error="stale", uploaded_at=None)
    backup = _backup(file_name="f.ibk", copies=[existing_local, remote_copy])

    async def fake_scoped(_session, _model, _tenant_id, _entity_id, **_kw):
        return backup

    async def fake_sftp_target(_session, _cfg):
        return "target"

    async def fake_fetch_sftp(_target, _remote, local_path):
        local_path.write_bytes(b"content")

    monkeypatch.setattr(bk, "get_tenant_scoped_or_404", fake_scoped)
    monkeypatch.setattr(bk, "sftp_target_from_settings", fake_sftp_target)
    monkeypatch.setattr(bk, "fetch_sftp", fake_fetch_sftp)
    settings_row = SimpleNamespace(backup={"targets": {"sftp": {}}})
    session = _Session(get_map={("SystemSettings", "t1"): settings_row})
    out = await bk.fetch_backup_copy("b1", session=session, user=USER)
    assert out.item.id == "b1"
    assert existing_local.status == "ok" and existing_local.error is None
    assert session.added == []  # mavjud nusxa qayta ishlatildi, yangi qo'shilmadi


@pytest.mark.asyncio
async def test_fetch_backup_copy_raises_502_on_target_error(monkeypatch, env, tmp_path):
    monkeypatch.setattr(bk.settings, "backups_dir", str(tmp_path))
    remote_copy = SimpleNamespace(target="s3", status="ok", remote_path="r/path", size_bytes=1,
                                   error=None, uploaded_at=NOW)
    backup = _backup(file_name="f.ibk", copies=[remote_copy])

    async def fake_scoped(_session, _model, _tenant_id, _entity_id, **_kw):
        return backup

    async def fake_s3_target(_session, _cfg):
        return "target"

    async def fake_fetch_s3(_target, _remote, _local_path):
        raise BackupTargetError("ulanish yo'q")

    monkeypatch.setattr(bk, "get_tenant_scoped_or_404", fake_scoped)
    monkeypatch.setattr(bk, "s3_target_from_settings", fake_s3_target)
    monkeypatch.setattr(bk, "fetch_s3", fake_fetch_s3)
    settings_row = SimpleNamespace(backup={"targets": {"s3": {}}})
    session = _Session(get_map={("SystemSettings", "t1"): settings_row})
    with pytest.raises(ApiError) as e:
        await bk.fetch_backup_copy("b1", session=session, user=USER)
    assert (e.value.status_code, e.value.code) == (502, "fetch_failed")


# ------------------------------------------------------------------ delete — qolgan tarmoqlar
@pytest.mark.asyncio
async def test_delete_backup_deletes_sftp_copy(monkeypatch, env):
    copy = SimpleNamespace(target="sftp", status="ok", remote_path="r/path")
    backup = _backup(copies=[copy])

    async def fake_scoped(_session, _model, _tenant_id, _entity_id, **_kw):
        return backup

    calls = []

    async def fake_sftp_target(_session, _cfg):
        return "target"

    async def fake_delete_sftp(_target, path):
        calls.append(path)

    monkeypatch.setattr(bk, "get_tenant_scoped_or_404", fake_scoped)
    monkeypatch.setattr(bk, "sftp_target_from_settings", fake_sftp_target)
    monkeypatch.setattr(bk, "delete_sftp", fake_delete_sftp)
    settings_row = SimpleNamespace(backup={"targets": {"sftp": {}}})
    session = _Session(get_map={("SystemSettings", "t1"): settings_row})
    resp = await bk.delete_backup("b1", session=session, user=USER)
    assert resp.status_code == 204
    assert calls == ["r/path"]


@pytest.mark.asyncio
async def test_delete_backup_skips_copy_without_remote_path(monkeypatch, env):
    copy = SimpleNamespace(target="local", status="ok", remote_path=None)
    backup = _backup(copies=[copy])

    async def fake_scoped(_session, _model, _tenant_id, _entity_id, **_kw):
        return backup

    monkeypatch.setattr(bk, "get_tenant_scoped_or_404", fake_scoped)
    session = _Session(get_map={("SystemSettings", "t1"): None})
    resp = await bk.delete_backup("b1", session=session, user=USER)
    assert resp.status_code == 204
