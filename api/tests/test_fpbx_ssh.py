"""M5a SSH: `app/services/fpbx/ssh_fetch.py`, `app/services/fpbx/intake.py`,
`app/api/v1/migration_ssh.py` — unit (mock), + `live` (haqiqiy `innova-fpbx-app`
test stendi, m5a-contract.md §0/§3, `/tmp/backend-ssh.txt`).

Jonli testlar `M5A_SSH_HOST`/`M5A_SSH_PORT`/`M5A_SSH_USER`/`M5A_SSH_PASSWORD` muhit
o'zgaruvchilaridan o'qiydi (parol kodga YOZILMAGAN) — yo'q bo'lsa `skip` (odatiy
`pytest -q` ularni bosmaydi, faqat `-m live` yoki muhit o'zgaruvchilari bilan)."""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api.v1 import migration_ssh as mg_ssh
from app.core.errors import ApiError
from app.services.fpbx import bundle as bundle_mod
from app.services.fpbx import ssh_fetch as sf

USER = SimpleNamespace(id="u1", tenant_id="t1")


# ------------------------------------------------------------------ sof funksiya
@pytest.mark.parametrize("stdout,expected", [
    ("Tayyor: /tmp/x/fpbx-export-h-20261030.tar.gz (19M)\n", "/tmp/x/fpbx-export-h-20261030.tar.gz"),
    ("ba'zi qatorlar\nTayyor: /tmp/a.tar.gz (1K)\n", "/tmp/a.tar.gz"),
    ("hech narsa yo'q\n", None),
    ("", None),
])
def test_parse_export_output(stdout, expected):
    assert sf._parse_export_output(stdout) == expected


# ------------------------------------------------------------------ test_connection (mock asyncssh)
class _FakeKey:
    def __init__(self, data: bytes) -> None:
        self.public_data = data


class _FakeConn:
    def __init__(self, key_data: bytes = b"fake-host-key") -> None:
        self._key_data = key_data
        self.closed = False
        self.ran: list[str] = []

    def get_server_host_key(self):
        return _FakeKey(self._key_data)

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


@pytest.mark.asyncio
async def test_connect_kwargs_uses_password_or_key(monkeypatch):
    import asyncssh

    captured = {}

    async def fake_connect(**kwargs):
        captured.update(kwargs)
        return _FakeConn()

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    conn, fp = await sf._connect(sf.SshCredentials(host="h", port=22, username="root", password="p"))
    assert captured["known_hosts"] is None
    assert captured["password"] == "p"
    assert fp == sf.host_key_fingerprint(b"fake-host-key")
    conn.close()


@pytest.mark.asyncio
async def test_test_connection_success(monkeypatch):
    import asyncssh

    async def fake_connect(**_kwargs):
        return _FakeConn(b"key-a")

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    ok, fp, error = await sf.test_connection(sf.SshCredentials(host="h", port=22, username="root", password="p"))
    assert ok is True
    assert fp == sf.host_key_fingerprint(b"key-a")
    assert error is None


@pytest.mark.asyncio
async def test_test_connection_auth_failed(monkeypatch):
    import asyncssh

    async def fake_connect(**_kwargs):
        raise asyncssh.PermissionDenied("noto'g'ri parol")

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    ok, fp, error = await sf.test_connection(sf.SshCredentials(host="h", port=22, username="root", password="bad"))
    assert (ok, fp, error) == (False, None, "ssh_auth_failed")


@pytest.mark.asyncio
async def test_test_connection_unreachable(monkeypatch):
    import asyncssh

    async def fake_connect(**_kwargs):
        raise OSError("ulanish rad etildi")

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    ok, fp, error = await sf.test_connection(sf.SshCredentials(host="h", port=22, username="root", password="p"))
    assert (ok, fp, error) == (False, None, "ssh_unreachable")


# ------------------------------------------------------------------ fetch_bundle (mock asyncssh)
class _FakeSftp:
    def __init__(self, store: dict) -> None:
        self._store = store

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return None

    async def makedirs(self, path, exist_ok=True):
        self._store.setdefault("dirs", []).append(path)

    async def put(self, local, remote):
        self._store.setdefault("uploaded", []).append((local, remote))

    async def stat(self, path):
        return SimpleNamespace(size=self._store.get("remote_size", 123))

    async def get(self, remote, local):
        with open(local, "wb") as fh:
            fh.write(self._store.get("remote_bytes", b"archive-bytes"))
        self._store.setdefault("downloaded", []).append((remote, local))

    async def remove(self, path):
        self._store.setdefault("removed", []).append(path)


class _FakeFetchConn(_FakeConn):
    def __init__(self, store: dict, run_results: list[SimpleNamespace]) -> None:
        super().__init__(b"real-host-key")
        self._store = store
        self._run_results = run_results

    def start_sftp_client(self):
        return _FakeSftp(self._store)

    async def run(self, command, *, timeout=None, check=False):
        self.ran.append(command)
        return self._run_results.pop(0)


def _ok_credentials() -> sf.SshCredentials:
    return sf.SshCredentials(host="h", port=22, username="root", password="p")


@pytest.mark.asyncio
async def test_fetch_bundle_host_key_mismatch(monkeypatch):
    import asyncssh

    async def fake_connect(**_kwargs):
        return _FakeConn(b"actual-key")

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    with pytest.raises(sf.SshFetchError) as exc:
        await sf.fetch_bundle(_ok_credentials(), "SHA256:not-the-real-fp", "/tmp/out.tar.gz", max_bytes=10**9)
    assert exc.value.code == "host_key_mismatch"


@pytest.mark.asyncio
async def test_fetch_bundle_export_failed_nonzero_exit(monkeypatch, tmp_path):
    import asyncssh

    store: dict = {}
    conn = _FakeFetchConn(store, [SimpleNamespace(exit_status=1, stdout="", stderr="mysql ulanmadi")])

    async def fake_connect(**_kwargs):
        return conn

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    expected_fp = sf.host_key_fingerprint(b"real-host-key")
    with pytest.raises(sf.SshFetchError) as exc:
        await sf.fetch_bundle(_ok_credentials(), expected_fp, tmp_path / "out.tar.gz", max_bytes=10**9)
    assert exc.value.code == "export_failed"
    assert conn.closed is True


@pytest.mark.asyncio
async def test_fetch_bundle_success_downloads_and_cleans_up(monkeypatch, tmp_path):
    import asyncssh

    store = {"remote_bytes": b"hello-archive"}
    conn = _FakeFetchConn(store, [SimpleNamespace(
        exit_status=0, stdout="Tayyor: /tmp/innova-fpbx-export-x/fpbx-export-h.tar.gz (1K)\n", stderr="",
    )])

    async def fake_connect(**_kwargs):
        return conn

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    expected_fp = sf.host_key_fingerprint(b"real-host-key")
    dest = tmp_path / "out.tar.gz"
    await sf.fetch_bundle(_ok_credentials(), expected_fp, dest, max_bytes=10**9)

    assert dest.read_bytes() == b"hello-archive"
    assert store["downloaded"][0][0] == "/tmp/innova-fpbx-export-x/fpbx-export-h.tar.gz"
    assert any(cmd.startswith("rm -rf") for cmd in conn.ran), "masofadagi papka tozalanishi kerak"
    assert conn.closed is True


@pytest.mark.asyncio
async def test_fetch_bundle_too_large_rejected(monkeypatch, tmp_path):
    import asyncssh

    store = {"remote_size": 10**12}
    conn = _FakeFetchConn(store, [SimpleNamespace(
        exit_status=0, stdout="Tayyor: /tmp/x/fpbx-export-h.tar.gz (999G)\n", stderr="",
    )])

    async def fake_connect(**_kwargs):
        return conn

    monkeypatch.setattr(asyncssh, "connect", fake_connect)
    expected_fp = sf.host_key_fingerprint(b"real-host-key")
    with pytest.raises(sf.SshFetchError) as exc:
        await sf.fetch_bundle(_ok_credentials(), expected_fp, tmp_path / "out.tar.gz", max_bytes=10)
    assert exc.value.code == "export_failed"
    assert any(cmd.startswith("rm -rf") for cmd in conn.ran), "hajm katta bo'lsa ham tozalanishi kerak"


# ------------------------------------------------------------------ fon vazifa (_run_ssh_fetch_job)
class _JobSession:
    def __init__(self, job) -> None:
        self._job = job
        self.commits = 0

    async def get(self, _model, _pk):
        return self._job

    async def commit(self) -> None:
        self.commits += 1


def _job(**kw):
    base = dict(id="j1", tenant_id="t1", source="ssh", status="fetching", step="ssh_fetch",
                progress=0, source_meta={"host": "1.2.3.4"}, bundle_path=None, error=None, finished_at=None)
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_run_ssh_fetch_job_success(monkeypatch, tmp_path):
    monkeypatch.setattr(sf.settings, "migrations_dir", str(tmp_path))
    job = _job()
    session = _JobSession(job)

    async def fake_fetch_bundle(_creds, _fp, dest_path, *, max_bytes):
        from pathlib import Path

        Path(dest_path).write_bytes(b"irrelevant")

    def fake_extract_and_read_meta(_archive_path, work_dir):
        bundle_root = work_dir / "extracted" / "fpbx-export-h-1"
        bundle_root.mkdir(parents=True)
        (bundle_root / "meta.json").write_text("{}")
        return bundle_root, {"host": "1.2.3.4", "freepbx_version": "17.0", "created_at": "2026-10-30T00:00:00Z"}

    monkeypatch.setattr(sf, "fetch_bundle", fake_fetch_bundle)
    monkeypatch.setattr(sf.intake, "extract_and_read_meta", fake_extract_and_read_meta)

    await sf._run_ssh_fetch_job(session, "j1", sf.SshCredentials(host="1.2.3.4", port=22, username="root"), "fp")

    assert job.status == "uploaded"
    assert job.step is None
    assert job.progress == 100
    assert job.finished_at is not None
    assert job.source_meta["freepbx_version"] == "17.0"
    assert Path(job.bundle_path).exists()
    assert session.commits == 1


@pytest.mark.asyncio
async def test_run_ssh_fetch_job_ssh_error_marks_failed(monkeypatch, tmp_path):
    monkeypatch.setattr(sf.settings, "migrations_dir", str(tmp_path))
    job = _job()
    session = _JobSession(job)

    async def fake_fetch_bundle(*_a, **_kw):
        raise sf.SshFetchError("ssh_auth_failed", "noto'g'ri parol")

    monkeypatch.setattr(sf, "fetch_bundle", fake_fetch_bundle)
    await sf._run_ssh_fetch_job(session, "j1", sf.SshCredentials(host="h", port=22, username="root"), "fp")

    assert job.status == "failed"
    assert job.step is None
    assert job.error == {"code": "ssh_auth_failed", "message": "noto'g'ri parol"}
    assert list(tmp_path.iterdir()) == []  # work_dir tozalangan


@pytest.mark.asyncio
async def test_run_ssh_fetch_job_bundle_invalid_marks_failed(monkeypatch, tmp_path):
    monkeypatch.setattr(sf.settings, "migrations_dir", str(tmp_path))
    job = _job()
    session = _JobSession(job)

    async def fake_fetch_bundle(_creds, _fp, dest_path, *, max_bytes):
        Path(dest_path).write_bytes(b"garbage")

    def fake_extract_and_read_meta(_archive_path, _work_dir):
        raise bundle_mod.BundleInvalidError("buzilgan arxiv")

    monkeypatch.setattr(sf, "fetch_bundle", fake_fetch_bundle)
    monkeypatch.setattr(sf.intake, "extract_and_read_meta", fake_extract_and_read_meta)
    await sf._run_ssh_fetch_job(session, "j1", sf.SshCredentials(host="h", port=22, username="root"), "fp")

    assert job.status == "failed"
    assert job.error["code"] == "bundle_invalid"


@pytest.mark.asyncio
async def test_run_ssh_fetch_job_missing_job_noop(monkeypatch, tmp_path):
    monkeypatch.setattr(sf.settings, "migrations_dir", str(tmp_path))

    class _NoneSession:
        async def get(self, _model, _pk):
            return None

    await sf._run_ssh_fetch_job(_NoneSession(), "missing", sf.SshCredentials(host="h", port=22, username="root"), "fp")
    assert list(tmp_path.iterdir()) == []


# ------------------------------------------------------------------ router (migration_ssh.py)
class _Session:
    def __init__(self, get_map=None) -> None:
        self.added: list = []
        self.commits = 0
        self.get_map = get_map or {}

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = "new-job-id"
            if getattr(obj, "created_at", None) is None:
                from datetime import datetime, timezone

                obj.created_at = datetime(2026, 10, 30, tzinfo=timezone.utc)

    async def commit(self) -> None:
        self.commits += 1

    async def get(self, model, pk):
        return self.get_map.get((model.__name__, pk))


@pytest.fixture
def env(monkeypatch):
    state: dict = {"audit": [], "tasks": []}

    async def fake_audit(_session, **kw):
        state["audit"].append(kw)

    monkeypatch.setattr(mg_ssh, "record_audit", fake_audit)
    monkeypatch.setattr(mg_ssh.asyncio, "create_task", lambda coro: (state["tasks"].append(coro), coro.close())[0])
    return state


@pytest.mark.asyncio
async def test_ssh_test_endpoint_returns_result(monkeypatch):
    async def fake_test_connection(_creds):
        return True, "SHA256:abc", None

    monkeypatch.setattr(mg_ssh, "test_connection", fake_test_connection)
    payload = mg_ssh.SshAuthPayload(host="h", port=22, username="root", password="p")
    out = await mg_ssh.ssh_test(payload, user=USER)
    assert out == mg_ssh.SshTestResult(ok=True, host_key_fp="SHA256:abc", error=None)


@pytest.mark.asyncio
async def test_ssh_fetch_endpoint_creates_job_and_schedules_task(monkeypatch, env):
    async def fake_test_connection(_creds):
        return True, "SHA256:abc", None

    monkeypatch.setattr(mg_ssh, "test_connection", fake_test_connection)
    payload = mg_ssh.SshFetchPayload(host="h", port=22, username="root", password="p", host_key_fp="SHA256:abc")
    session = _Session(get_map={("SystemSettings", "t1"): None})
    out = await mg_ssh.ssh_fetch(payload, session=session, user=USER)

    assert out.item.status == "fetching"
    assert out.item.step == "ssh_fetch"
    assert out.item.source == "ssh"
    assert session.commits == 1
    assert len(env["tasks"]) == 1
    assert env["audit"][0]["action"] == "migration.ssh_fetch"
    assert "password" not in str(env["audit"][0]["diff"])


@pytest.mark.asyncio
async def test_ssh_fetch_endpoint_host_key_mismatch_422(monkeypatch, env):
    async def fake_test_connection(_creds):
        return True, "SHA256:observed", None

    monkeypatch.setattr(mg_ssh, "test_connection", fake_test_connection)
    payload = mg_ssh.SshFetchPayload(host="h", port=22, username="root", password="p",
                                      host_key_fp="SHA256:expected-different")
    session = _Session()
    with pytest.raises(ApiError) as exc:
        await mg_ssh.ssh_fetch(payload, session=session, user=USER)
    assert (exc.value.status_code, exc.value.code) == (422, "host_key_mismatch")
    assert session.commits == 0
    assert len(env["tasks"]) == 0


@pytest.mark.asyncio
async def test_ssh_fetch_endpoint_auth_failed_422_no_job(monkeypatch, env):
    async def fake_test_connection(_creds):
        return False, None, "ssh_auth_failed"

    monkeypatch.setattr(mg_ssh, "test_connection", fake_test_connection)
    payload = mg_ssh.SshFetchPayload(host="h", port=22, username="root", password="bad",
                                      host_key_fp="SHA256:whatever")
    session = _Session()
    with pytest.raises(ApiError) as exc:
        await mg_ssh.ssh_fetch(payload, session=session, user=USER)
    assert (exc.value.status_code, exc.value.code) == (422, "ssh_auth_failed")
    assert session.commits == 0


def test_payload_requires_exactly_one_secret():
    with pytest.raises(Exception):
        mg_ssh.SshAuthPayload(host="h", username="root")
    with pytest.raises(Exception):
        mg_ssh.SshAuthPayload(host="h", username="root", password="p", private_key="k")


# ------------------------------------------------------------------ JONLI: innova-fpbx-app test stendi
def _live_env():
    host = os.environ.get("M5A_SSH_HOST")
    password = os.environ.get("M5A_SSH_PASSWORD")
    if not host or not password:
        pytest.skip("M5A_SSH_HOST/M5A_SSH_PASSWORD berilmagan — jonli SSH testi o'tkazib yuborildi")
    return sf.SshCredentials(
        host=host, port=int(os.environ.get("M5A_SSH_PORT", "2222")),
        username=os.environ.get("M5A_SSH_USER", "root"), password=password,
    )


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_ssh_test_connection_returns_fp():
    creds = _live_env()
    ok, fp, error = await sf.test_connection(creds)
    assert ok is True and error is None
    assert fp and fp.startswith("SHA256:")


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_wrong_password_is_auth_failed():
    creds = _live_env()
    bad = sf.SshCredentials(host=creds.host, port=creds.port, username=creds.username,
                             password=creds.password + "-wrong")
    ok, fp, error = await sf.test_connection(bad)
    assert (ok, fp, error) == (False, None, "ssh_auth_failed")


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_wrong_host_key_fp_is_mismatch(tmp_path):
    creds = _live_env()
    with pytest.raises(sf.SshFetchError) as exc:
        await sf.fetch_bundle(creds, "SHA256:" + "A" * 43, tmp_path / "out.tar.gz", max_bytes=10**9)
    assert exc.value.code == "host_key_mismatch"


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_fetch_real_export_script_passes_bundle_check(tmp_path):
    creds = _live_env()
    _ok, fp, _error = await sf.test_connection(creds)
    dest = tmp_path / "bundle.tar.gz"
    await sf.fetch_bundle(creds, fp, dest, max_bytes=20 * 1024 * 1024 * 1024)
    assert dest.is_file() and dest.stat().st_size > 0

    extracted = tmp_path / "extracted"
    bundle_mod.extract_bundle(dest, extracted, max_total_bytes=20 * 1024 * 1024 * 1024)
    bundle_root = bundle_mod.find_bundle_root(extracted)
    meta = bundle_mod.read_meta(bundle_root)
    assert meta["format"] == "INNOVA-FPBX-EXPORT/1"
    assert (bundle_root / "tables").is_dir()

    import asyncssh

    async with await asyncssh.connect(host=creds.host, port=creds.port, username=creds.username,
                                       password=creds.password, known_hosts=None) as conn:
        result = await conn.run("ls /tmp | grep innova-fpbx-export || true", check=False)
    assert result.stdout.strip() == "", f"masofada qoldiq topildi: {result.stdout!r}"
