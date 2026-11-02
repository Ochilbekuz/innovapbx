"""`app/services/backup_targets.py` — sof qism to'liq, I/O ingichka qobiq soxta mijozlar bilan."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services import backup_targets as bt
from app.services.backup_retention import RetentionItem

UTC = timezone.utc


# ------------------------------------------------------------------ sof funksiyalar
@pytest.mark.parametrize("name,expected", [
    ("innova-pbx1-20261028-030000-a1b2c3d4.ibk", True),
    ("innova-x.ibk", True),
    ("other-file.ibk", False),
    ("innova-pbx1.tar.gz", False),
    ("INNOVA-PBX1.IBK", False),
])
def test_is_own_backup_file(name, expected):
    assert bt.is_own_backup_file(name) is expected


def test_s3_key_joins_prefix():
    target = bt.S3Target(endpoint="e", region="r", bucket="b", prefix="pbx1/", access_key="a",
                          secret_key="s", path_style=False)
    assert bt.s3_key(target, "innova-x.ibk") == "pbx1/innova-x.ibk"


def test_s3_key_without_prefix():
    target = bt.S3Target(endpoint="e", region="r", bucket="b", prefix="", access_key="a",
                          secret_key="s", path_style=False)
    assert bt.s3_key(target, "innova-x.ibk") == "innova-x.ibk"


def test_sftp_remote_path_strips_trailing_slash():
    target = bt.SftpTarget(host="h", port=22, user="u", folder="/backups/")
    assert bt.sftp_remote_path(target, "innova-x.ibk") == "/backups/innova-x.ibk"


def test_sftp_remote_path_empty_folder_defaults_to_root():
    target = bt.SftpTarget(host="h", port=22, user="u", folder="")
    assert bt.sftp_remote_path(target, "innova-x.ibk") == "/innova-x.ibk"


def test_host_key_fingerprint_is_deterministic_sha256_base64():
    fp1 = bt.host_key_fingerprint(b"some-public-key-bytes")
    fp2 = bt.host_key_fingerprint(b"some-public-key-bytes")
    assert fp1 == fp2
    assert fp1.startswith("SHA256:")
    assert "=" not in fp1


def test_host_key_fingerprint_differs_for_different_keys():
    assert bt.host_key_fingerprint(b"key-a") != bt.host_key_fingerprint(b"key-b")


def test_retention_items_from_names_filters_foreign_files():
    now = datetime(2026, 10, 28, tzinfo=UTC)
    names = {"innova-a.ibk": now, "other.ibk": now, "innova-b.ibk": now}
    items = bt.retention_items_from_names(names)
    assert {i.id for i in items} == {"innova-a.ibk", "innova-b.ibk"}
    assert all(isinstance(i, RetentionItem) for i in items)


# ------------------------------------------------------------------ S3 (soxta mijoz)
class _FakeS3Client:
    def __init__(self, *, fail: Exception | None = None, objects: list[dict] | None = None):
        self.fail = fail
        self.objects = objects or []
        self.calls: list[tuple] = []

    def head_bucket(self, **kwargs):
        self.calls.append(("head_bucket", kwargs))
        if self.fail:
            raise self.fail

    def upload_file(self, *args):
        self.calls.append(("upload_file", args))
        if self.fail:
            raise self.fail

    def download_file(self, *args):
        self.calls.append(("download_file", args))
        if self.fail:
            raise self.fail

    def delete_object(self, **kwargs):
        self.calls.append(("delete_object", kwargs))
        if self.fail:
            raise self.fail

    def list_objects_v2(self, **kwargs):
        self.calls.append(("list_objects_v2", kwargs))
        if self.fail:
            raise self.fail
        return {"Contents": self.objects, "IsTruncated": False}


def _s3target(**overrides):
    base = dict(endpoint="https://s3.example", region="eu", bucket="bk", prefix="pbx1",
                access_key="ak", secret_key="sk", path_style=False)
    base.update(overrides)
    return bt.S3Target(**base)


@pytest.mark.asyncio
async def test_test_s3_ok(monkeypatch):
    client = _FakeS3Client()
    monkeypatch.setattr(bt, "_s3_client", lambda target: client)
    ok, error = await bt.test_s3(_s3target())
    assert (ok, error) == (True, None)


@pytest.mark.asyncio
async def test_test_s3_reports_error(monkeypatch):
    client = _FakeS3Client(fail=RuntimeError("timeout"))
    monkeypatch.setattr(bt, "_s3_client", lambda target: client)
    ok, error = await bt.test_s3(_s3target())
    assert ok is False
    assert "timeout" in error


@pytest.mark.asyncio
async def test_upload_s3_returns_key(monkeypatch):
    client = _FakeS3Client()
    monkeypatch.setattr(bt, "_s3_client", lambda target: client)
    key = await bt.upload_s3(_s3target(), __file__, "innova-x.ibk")
    assert key == "pbx1/innova-x.ibk"
    assert client.calls[0][0] == "upload_file"


@pytest.mark.asyncio
async def test_upload_s3_wraps_errors(monkeypatch):
    client = _FakeS3Client(fail=RuntimeError("boom"))
    monkeypatch.setattr(bt, "_s3_client", lambda target: client)
    with pytest.raises(bt.BackupTargetError, match="boom"):
        await bt.upload_s3(_s3target(), __file__, "innova-x.ibk")


@pytest.mark.asyncio
async def test_fetch_s3_wraps_errors(monkeypatch):
    client = _FakeS3Client(fail=RuntimeError("nope"))
    monkeypatch.setattr(bt, "_s3_client", lambda target: client)
    with pytest.raises(bt.BackupTargetError):
        await bt.fetch_s3(_s3target(), "pbx1/x.ibk", __file__)


@pytest.mark.asyncio
async def test_delete_s3_wraps_errors(monkeypatch):
    client = _FakeS3Client(fail=RuntimeError("nope"))
    monkeypatch.setattr(bt, "_s3_client", lambda target: client)
    with pytest.raises(bt.BackupTargetError):
        await bt.delete_s3(_s3target(), "pbx1/x.ibk")


@pytest.mark.asyncio
async def test_list_own_s3_filters_and_resolves_full_keys(monkeypatch):
    objects = [
        {"Key": "pbx1/innova-a.ibk", "LastModified": datetime(2026, 10, 1, tzinfo=UTC)},
        {"Key": "pbx1/other.ibk", "LastModified": datetime(2026, 10, 2, tzinfo=UTC)},
    ]
    client = _FakeS3Client(objects=objects)
    monkeypatch.setattr(bt, "_s3_client", lambda target: client)
    items = await bt.list_own_s3(_s3target())
    assert [i.id for i in items] == ["pbx1/innova-a.ibk"]


@pytest.mark.asyncio
async def test_list_own_s3_wraps_errors(monkeypatch):
    client = _FakeS3Client(fail=RuntimeError("down"))
    monkeypatch.setattr(bt, "_s3_client", lambda target: client)
    with pytest.raises(bt.BackupTargetError):
        await bt.list_own_s3(_s3target())


# ------------------------------------------------------------------ SFTP (soxta ulanish)
def _connect_returning(conn):
    """`_sftp_connect` soxtasi — haqiqiy kod `await _sftp_connect(target)` qiladi,
    shu sabab bu ASYNC funksiya bo'lishi kerak (oddiy lambda emas)."""
    async def _connect(target):
        return conn
    return _connect


class _FakeHostKey:
    def __init__(self, data: bytes) -> None:
        self.public_data = data


class _FakeSftpClient:
    def __init__(self, *, entries=None, fail: Exception | None = None):
        self.entries = entries or []
        self.fail = fail
        self.calls: list[tuple] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def put(self, *args):
        self.calls.append(("put", args))
        if self.fail:
            raise self.fail

    async def get(self, *args):
        self.calls.append(("get", args))
        if self.fail:
            raise self.fail

    async def remove(self, *args):
        self.calls.append(("remove", args))
        if self.fail:
            raise self.fail

    async def readdir(self, path):
        if self.fail:
            raise self.fail
        return self.entries


class _FakeSshConn:
    def __init__(self, *, host_key: bytes = b"hostkey", sftp: _FakeSftpClient | None = None,
                 fail: Exception | None = None) -> None:
        self._host_key = _FakeHostKey(host_key)
        self._sftp = sftp or _FakeSftpClient()
        self.fail = fail
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def get_server_host_key(self):
        return self._host_key

    def close(self) -> None:
        self.closed = True

    async def run(self, *args, **kwargs):
        if self.fail:
            raise self.fail
        return None

    def start_sftp_client(self):
        return self._sftp


def _sftptarget(**overrides):
    base = dict(host="h", port=22, user="u", folder="/backups")
    base.update(overrides)
    return bt.SftpTarget(**base)


def _awaitable_connect(conn):
    """Haqiqiy `asyncssh.connect` — `await`lanadigan korutin qaytaradi (`_sftp_connect`
    o'zi `await asyncssh.connect(...)` qiladi — `test_sftp()`dan farqli, u `async with`
    ishlatadi, shu sabab o'sha testlarda soxta `connect` sinxron qaytaradi)."""
    async def _connect(*args, **kwargs):
        return conn
    return _connect


# ------------------------------------------------------------------ _sftp_connect (host kaliti pin)
@pytest.mark.asyncio
async def test_sftp_connect_rejects_untrusted_host_key(monkeypatch):
    """m4b-contract.md §4.3: «SFTP barmoq izi tasdiqlanmasa zaxira `partial`» — host kaliti
    hali `trust` qilinmagan (`host_key_fp` yo'q) bo'lsa ham jim ulanib qolish MITM eshigi."""
    import asyncssh
    conn = _FakeSshConn(host_key=b"server-key")
    monkeypatch.setattr(asyncssh, "connect", _awaitable_connect(conn))
    with pytest.raises(bt.BackupTargetError, match="host_key_not_trusted"):
        await bt._sftp_connect(_sftptarget())
    assert conn.closed is True


@pytest.mark.asyncio
async def test_sftp_connect_rejects_mismatched_host_key(monkeypatch):
    """m4b-contract.md §0: «mos kelmasa `host_key_mismatch`, jim qabul YO'Q»."""
    import asyncssh
    conn = _FakeSshConn(host_key=b"server-key-changed")
    monkeypatch.setattr(asyncssh, "connect", _awaitable_connect(conn))
    target = _sftptarget(host_key_fp="SHA256:wrong")
    with pytest.raises(bt.BackupTargetError, match="host_key_mismatch"):
        await bt._sftp_connect(target)
    assert conn.closed is True


@pytest.mark.asyncio
async def test_sftp_connect_accepts_trusted_host_key(monkeypatch):
    import asyncssh
    conn = _FakeSshConn(host_key=b"server-key-ok")
    expected = bt.host_key_fingerprint(b"server-key-ok")
    monkeypatch.setattr(asyncssh, "connect", _awaitable_connect(conn))
    target = _sftptarget(host_key_fp=expected)
    result = await bt._sftp_connect(target)
    assert result is conn
    assert conn.closed is False


@pytest.mark.asyncio
async def test_test_sftp_returns_observed_fingerprint_when_unset(monkeypatch):
    import asyncssh
    conn = _FakeSshConn(host_key=b"server-key-1")
    monkeypatch.setattr(asyncssh, "connect", lambda *a, **k: conn)
    ok, error, fp = await bt.test_sftp(_sftptarget())
    assert ok is True
    assert error is None
    assert fp == bt.host_key_fingerprint(b"server-key-1")


@pytest.mark.asyncio
async def test_test_sftp_works_on_shell_restricted_server(monkeypatch):
    """Bug: `test_sftp()` ILGARI `conn.run("true")` (qobiq buyrug'i) ishlatardi -- bu
    `ForceCommand internal-sftp` bilan cheklangan serverlarda (masalan `atmoz/sftp`,
    xavfsizlik amaliyoti, m4b-contract.md §2: "yozib-o'qib-o'chirib sinaydi") HAR DOIM
    `ProcessError` bilan muvaffaqiyatsiz bo'lardi, garchi SFTP o'zi ishlasa ham. `run()`
    endi UMUMAN chaqirilmaydi -- shu sabab qobiq rad etsa ham (fake buni isbotlaydi:
    `run()` chaqirilsa xato chiqaradi) `test_sftp()` put/get/remove orqali muvaffaqiyatli
    bo'lishi SHART."""
    import asyncssh

    sftp = _FakeSftpClient()
    conn = _FakeSshConn(host_key=b"server-key-shell-restricted", sftp=sftp)

    async def _run_rejected(*_a, **_kw):
        raise asyncssh.ProcessError(1, None, 1, None, None, None, None, None)

    conn.run = _run_rejected
    monkeypatch.setattr(asyncssh, "connect", lambda *a, **k: conn)

    ok, error, fp = await bt.test_sftp(_sftptarget())

    assert (ok, error) == (True, None)
    assert fp == bt.host_key_fingerprint(b"server-key-shell-restricted")
    assert [c[0] for c in sftp.calls] == ["put", "get", "remove"]


@pytest.mark.asyncio
async def test_test_sftp_mismatch_when_fp_differs(monkeypatch):
    import asyncssh
    conn = _FakeSshConn(host_key=b"server-key-2")
    monkeypatch.setattr(asyncssh, "connect", lambda *a, **k: conn)
    ok, error, fp = await bt.test_sftp(_sftptarget(host_key_fp="SHA256:wrong"))
    assert ok is False
    assert error == "host_key_mismatch"
    assert fp == bt.host_key_fingerprint(b"server-key-2")


@pytest.mark.asyncio
async def test_test_sftp_matches_trusted_fingerprint(monkeypatch):
    import asyncssh
    conn = _FakeSshConn(host_key=b"server-key-3")
    expected = bt.host_key_fingerprint(b"server-key-3")
    monkeypatch.setattr(asyncssh, "connect", lambda *a, **k: conn)
    ok, error, fp = await bt.test_sftp(_sftptarget(host_key_fp=expected))
    assert (ok, error, fp) == (True, None, expected)


@pytest.mark.asyncio
async def test_test_sftp_connection_error(monkeypatch):
    import asyncssh

    def _raise(*a, **k):
        raise OSError("refused")

    monkeypatch.setattr(asyncssh, "connect", _raise)
    ok, error, fp = await bt.test_sftp(_sftptarget())
    assert ok is False
    assert "refused" in error
    assert fp is None


@pytest.mark.asyncio
async def test_upload_sftp_puts_file(monkeypatch):
    import asyncssh
    sftp = _FakeSftpClient()
    conn = _FakeSshConn(sftp=sftp)
    monkeypatch.setattr(bt, "_sftp_connect", _connect_returning(conn))
    path = await bt.upload_sftp(_sftptarget(), __file__, "innova-x.ibk")
    assert path == "/backups/innova-x.ibk"
    assert sftp.calls[0][0] == "put"


@pytest.mark.asyncio
async def test_upload_sftp_wraps_errors(monkeypatch):
    import asyncssh
    sftp = _FakeSftpClient(fail=asyncssh.Error(1, "sftp failure"))
    conn = _FakeSshConn(sftp=sftp)
    monkeypatch.setattr(bt, "_sftp_connect", _connect_returning(conn))
    with pytest.raises(bt.BackupTargetError):
        await bt.upload_sftp(_sftptarget(), __file__, "innova-x.ibk")


@pytest.mark.asyncio
async def test_fetch_sftp_gets_file(monkeypatch):
    sftp = _FakeSftpClient()
    conn = _FakeSshConn(sftp=sftp)
    monkeypatch.setattr(bt, "_sftp_connect", _connect_returning(conn))
    await bt.fetch_sftp(_sftptarget(), "/backups/innova-x.ibk", __file__)
    assert sftp.calls[0][0] == "get"


@pytest.mark.asyncio
async def test_delete_sftp_removes_file(monkeypatch):
    sftp = _FakeSftpClient()
    conn = _FakeSshConn(sftp=sftp)
    monkeypatch.setattr(bt, "_sftp_connect", _connect_returning(conn))
    await bt.delete_sftp(_sftptarget(), "/backups/innova-x.ibk")
    assert sftp.calls[0][0] == "remove"


class _Attrs:
    def __init__(self, mtime: int) -> None:
        self.mtime = mtime


class _Entry:
    def __init__(self, filename: str, mtime: int) -> None:
        self.filename = filename
        self.attrs = _Attrs(mtime)


@pytest.mark.asyncio
async def test_list_own_sftp_filters_dot_entries_and_foreign_files(monkeypatch):
    entries = [_Entry(".", 0), _Entry("..", 0), _Entry("innova-a.ibk", 1_700_000_000),
               _Entry("other.ibk", 1_700_000_001)]
    sftp = _FakeSftpClient(entries=entries)
    conn = _FakeSshConn(sftp=sftp)
    monkeypatch.setattr(bt, "_sftp_connect", _connect_returning(conn))
    items = await bt.list_own_sftp(_sftptarget())
    assert [i.id for i in items] == ["/backups/innova-a.ibk"]


@pytest.mark.asyncio
async def test_list_own_sftp_wraps_errors(monkeypatch):
    import asyncssh
    sftp = _FakeSftpClient(fail=asyncssh.Error(1, "down"))
    conn = _FakeSshConn(sftp=sftp)
    monkeypatch.setattr(bt, "_sftp_connect", _connect_returning(conn))
    with pytest.raises(bt.BackupTargetError):
        await bt.list_own_sftp(_sftptarget())


def test_sftp_connect_kwargs_bounded_by_target_timeout(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "backup_target_timeout_s", 7.0)
    target = bt.SftpTarget(host="h", port=2222, user="u", password="p", key=None,
                           folder="/f", host_key_fp="fp")
    kw = bt._sftp_connect_kwargs(target)
    assert kw["connect_timeout"] == 7.0 and kw["login_timeout"] == 7.0
    assert (kw["host"], kw["port"], kw["username"], kw["password"]) == ("h", 2222, "u", "p")
    assert kw["client_keys"] is None and kw["known_hosts"] is None


def test_s3_client_bounded_timeouts_and_retries(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "backup_target_timeout_s", 5.0)
    target = bt.S3Target(endpoint="http://minio:9000", region="us-east-1", bucket="b",
                         prefix="", access_key="a", secret_key="s", path_style=True)
    cfg = bt._s3_client(target).meta.config
    assert cfg.connect_timeout == 5.0 and cfg.read_timeout == 5.0
    assert cfg.retries["total_max_attempts"] == 2
    assert cfg.s3["addressing_style"] == "path"
