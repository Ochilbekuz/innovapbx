"""`app/api/v1/system_update.py` — m11-update-contract.md bo'lim 4. DBsiz:
`settings.update_dir` ni `tmp_path`ga ko'rsatamiz (`test_network_api_unit.py`
qolipi — to'g'ridan-to'g'ri async chaqiruv, soxta sessiya/foydalanuvchi)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1 import system_update as route
from app.core.config import settings
from app.core.errors import ApiError
from app.core.permissions import check_access
from app.schemas_update import SystemUpdateStartIn

USER = SimpleNamespace(id="u1", tenant_id="t1")


class _Session:
    def __init__(self):
        self.added: list = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


@pytest.fixture
def update_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "update_dir", str(tmp_path))
    monkeypatch.setattr(settings, "innova_version", "1.0.12")
    return tmp_path


def _status(path, **kv):
    text = "".join(f"{k}={v}\n" for k, v in kv.items())
    (path / "status").write_text(text)


# --- Fail-closed: marshrut xaritasida yo'q, faqat `*` ruxsatli ---

def test_system_update_routes_denied_without_all_permission():
    for path in ("/system/update", "/system/update/check", "/system/update/start", "/system/update/log"):
        assert check_access(["extensions:edit"], "GET", path) is False
        assert check_access(["extensions:edit"], "POST", path) is False


def test_system_update_routes_allowed_with_all_permission():
    assert check_access(["*"], "GET", "/system/update") is True


# --- GET /system/update ---

@pytest.mark.asyncio
async def test_get_system_update_agent_missing_returns_agent_false(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "update_dir", str(tmp_path / "no-such-dir"))
    monkeypatch.setattr(settings, "innova_version", "1.0.12")
    out = await route.get_system_update(user=USER)
    assert out.agent is False
    assert out.changelog == []
    assert out.current == "1.0.12"


@pytest.mark.asyncio
async def test_get_system_update_reads_status_and_changelog(update_dir):
    _status(update_dir, state="idle", current="1.0.12", latest="1.0.13", available="1")
    (update_dir / "changelog.md").write_text("## 1.0.13 — 2026-11-04\nYangilik\n")
    out = await route.get_system_update(user=USER)
    assert out.agent is True
    assert out.available is True
    assert out.latest == "1.0.13"
    assert [c.version for c in out.changelog] == ["1.0.13"]


# --- POST /system/update/check ---

@pytest.mark.asyncio
async def test_check_agent_missing_raises_503(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "update_dir", str(tmp_path / "missing"))
    monkeypatch.setattr(settings, "innova_version", None)
    with pytest.raises(ApiError) as exc:
        await route.start_system_update_check(user=USER)
    assert exc.value.status_code == 503
    assert exc.value.code == "update_agent_missing"


@pytest.mark.asyncio
async def test_check_writes_request_file_and_returns_pending(update_dir):
    out = await route.start_system_update_check(user=USER)
    assert out.pending == "check"
    assert (update_dir / "request").read_text() == "check\n"


@pytest.mark.asyncio
async def test_check_busy_when_request_already_exists(update_dir):
    (update_dir / "request").write_text("check\n")
    with pytest.raises(ApiError) as exc:
        await route.start_system_update_check(user=USER)
    assert exc.value.status_code == 409
    assert exc.value.code == "update_busy"


@pytest.mark.asyncio
async def test_check_busy_on_write_race_condition(update_dir, monkeypatch):
    """`_guard_can_request` fayl yo'qligini ko'rdi, lekin boshqa so'rov orada
    yozib ulgurdi — `write_request`ning `O_EXCL`'i ushlaydi, 409 bo'lishi kerak."""
    def _raise(*_a, **_kw):
        raise FileExistsError

    monkeypatch.setattr(route.system_update, "write_request", _raise)
    with pytest.raises(ApiError) as exc:
        await route.start_system_update_check(user=USER)
    assert exc.value.status_code == 409
    assert exc.value.code == "update_busy"


@pytest.mark.asyncio
async def test_check_busy_when_state_updating(update_dir):
    _status(update_dir, state="updating")
    with pytest.raises(ApiError) as exc:
        await route.start_system_update_check(user=USER)
    assert exc.value.code == "update_busy"


# --- POST /system/update/start ---

@pytest.mark.asyncio
async def test_start_not_available_raises_409(update_dir):
    _status(update_dir, state="idle", available="0", latest="1.0.13")
    session = _Session()
    with pytest.raises(ApiError) as exc:
        await route.start_system_update(SystemUpdateStartIn(version="1.0.13"), session=session, user=USER)
    assert exc.value.status_code == 409
    assert exc.value.code == "update_not_available"


@pytest.mark.asyncio
async def test_start_version_mismatch_raises_409(update_dir):
    _status(update_dir, state="idle", available="1", latest="1.0.13")
    session = _Session()
    with pytest.raises(ApiError) as exc:
        await route.start_system_update(SystemUpdateStartIn(version="1.0.9"), session=session, user=USER)
    assert exc.value.code == "update_version_mismatch"


@pytest.mark.asyncio
async def test_start_success_writes_request_audits_and_commits(update_dir):
    _status(update_dir, state="idle", available="1", latest="1.0.13", current="1.0.12")
    session = _Session()
    out = await route.start_system_update(SystemUpdateStartIn(version="1.0.13"), session=session, user=USER)
    assert out.pending == "update"
    assert (update_dir / "request").read_text() == "update\n"
    assert session.commits == 1
    assert len(session.added) == 1
    audit = session.added[0]
    assert audit.action == "update"  # "system.update.start" -> normalize_action -> update
    assert audit.diff == {"from": "1.0.12", "to": "1.0.13"}


@pytest.mark.asyncio
async def test_start_bad_version_format_rejected_by_schema():
    with pytest.raises(Exception):
        SystemUpdateStartIn(version="not a version!")


# --- GET /system/update/log ---

@pytest.mark.asyncio
async def test_log_missing_file_returns_zeros(update_dir):
    out = await route.get_system_update_log(offset=0, user=USER)
    assert (out.offset, out.size, out.text) == (0, 0, "")


@pytest.mark.asyncio
async def test_log_reads_and_strips_ansi(update_dir):
    (update_dir / "update.log").write_text("\x1b[31mxato\x1b[0m\n")
    out = await route.get_system_update_log(offset=0, user=USER)
    assert out.text == "xato\n"
    assert out.size == out.offset


@pytest.mark.asyncio
async def test_log_offset_beyond_size_resets_to_zero(update_dir):
    (update_dir / "update.log").write_text("qayta yaratildi\n")
    out = await route.get_system_update_log(offset=9999, user=USER)
    assert out.offset == len("qayta yaratildi\n")
    assert out.text == "qayta yaratildi\n"
