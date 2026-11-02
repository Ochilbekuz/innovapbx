"""`apply_config` oqimi (DB/AMI'siz): kompilyatsiya xatosi, unchanged, applied (park lot dialplan'dan
OLDIN — M2a §3), xatoda rollback (oxirgi yaxshi yoki bo'sh dialplan). `free_numbers`/`create_extension`
(M2a: park raqamlari va dial_numbers bilan to'qnashuv)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import Request

from app.api.v1 import extensions as ex
from app.core.errors import ApiError
from app.schemas import CreateExtensionPayload
from app.services import apply as ap
from app.services import numbers
from app.services.compiler import CompileError


class _Session:
    def __init__(self):
        self.added: list = []
        self.flushes = 0

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushes += 1
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = 41


@pytest.fixture
def env(monkeypatch):
    st = {"calls": [], "text": "[t1-from-internal]\n", "last": None, "fail": set()}

    async def lock(session, tenant_id):
        st["calls"].append("lock")

    async def snapshot(session, tenant_id):
        return SimpleNamespace(tenant_code="t1")

    def compile_(snap):
        if "compile" in st["fail"]:
            raise CompileError("halqa", code="loop", details={"path": ["a", "b"]})
        return st["text"]

    async def last(session, tenant_id, status):
        return st["last"]

    async def park(ami, code):
        st["calls"].append(f"park:{code}")
        if "park" in st["fail"]:
            raise RuntimeError("park lot ko'rinmadi")

    def write(text):
        st["calls"].append(f"write:{text[:6]}")
        if "fallback_write" in st["fail"] and "bo'sh" in text:
            raise OSError("disk")

    async def reload(ami, code):
        st["calls"].append("reload")

    monkeypatch.setattr(ap, "lock_tenant", lock)
    monkeypatch.setattr(ap, "build_snapshot", snapshot)
    monkeypatch.setattr(ap, "compile_dialplan", compile_)
    monkeypatch.setattr(ap, "_last_revision", last)
    monkeypatch.setattr(ap, "ensure_parking_lot", park)
    monkeypatch.setattr(ap, "write_dialplan_file", write)
    monkeypatch.setattr(ap, "_reload_and_verify", reload)
    return st


async def _apply(session=None):
    return await ap.apply_config(session or _Session(), tenant_id="t1", user_id="u1", ami=None)


@pytest.mark.asyncio
async def test_compile_error_becomes_api_error(env):
    env["fail"].add("compile")
    with pytest.raises(ApiError) as e:
        await _apply()
    assert (e.value.status_code, e.value.code, e.value.details) == (422, "loop", {"path": ["a", "b"]})


@pytest.mark.asyncio
async def test_unchanged_when_sha_matches_last_good(env):
    env["last"] = SimpleNamespace(id=7, dialplan_sha256=ap.dialplan_sha256(env["text"]), dialplan="x")
    result = await _apply()
    assert (result.status, result.revision) == ("unchanged", 7)
    assert env["calls"] == ["lock"]


@pytest.mark.asyncio
async def test_applied_parks_before_dialplan(env):
    session = _Session()
    result = await _apply(session)
    assert (result.status, result.revision, result.message) == ("applied", 41, None)
    assert env["calls"] == ["lock", "park:t1", "write:[t1-fr", "reload"]
    rev = session.added[0]
    assert rev.status == "applied" and rev.dialplan == env["text"] and rev.user_id == "u1"


@pytest.mark.asyncio
async def test_failure_rolls_back_to_last_good(env):
    env["last"] = SimpleNamespace(id=5, dialplan_sha256="old", dialplan="; old plan")
    env["fail"].add("park")
    session = _Session()
    result = await _apply(session)
    assert (result.status, result.revision) == ("rolled_back", 5)
    assert "park lot" in result.message and result.message.startswith("Qo'llashda xato")
    assert env["calls"][-2:] == ["write:; old ", "reload"]
    assert session.added[0].status == "rolled_back" and "park lot" in session.added[0].error


@pytest.mark.asyncio
async def test_failure_without_last_good_and_broken_fallback(env):
    env["fail"].update({"park", "fallback_write"})
    result = await _apply()
    assert (result.status, result.revision) == ("rolled_back", None)
    assert env["calls"][-1] == "write:; Inno"


# ------------------------------------------------------------------ free_numbers
class _ListSession:
    def __init__(self, *lists):
        self.lists = list(lists)

    async def execute(self, stmt):
        rows = self.lists.pop(0)
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: rows))


@pytest.mark.asyncio
async def test_free_numbers_skips_taken_and_park():
    out = await numbers.free_numbers(_ListSession(["698"], ["721"], []), "t1", from_n=698, to_n=730, limit=3)
    assert out == ["699", "722", "723"]


@pytest.mark.asyncio
async def test_free_numbers_respects_range_end():
    assert await numbers.free_numbers(_ListSession([], [], []), "t1", from_n=719, to_n=721, limit=5) == ["721"]


# ------------------------------------------------------------------ create_extension
@pytest.mark.asyncio
async def test_create_extension_checks_number_with_dial_numbers(monkeypatch):
    seen = {}

    async def ensure(session, tenant_id, number, **kw):
        seen["ensure"] = (tenant_id, number)
        raise ApiError(409, "number_taken", "Bu raqam band", field="number")

    monkeypatch.setattr(ex, "ensure_number_free", ensure)
    user = SimpleNamespace(id="u1", tenant_id="t1")
    # `ensure_number_free` 409 bilan ko'taradi — `request` ishlatilishidan OLDIN (qiymati muhim emas).
    request = Request({"type": "http", "method": "POST", "path": "/", "scheme": "http", "query_string": b"",
                       "headers": [], "client": ("10.0.0.1", 1)})
    with pytest.raises(ApiError) as e:
        await ex.create_extension(CreateExtensionPayload(number="610", name="X"), request, session=None,
                                  user=user, ami=None)
    assert e.value.code == "number_taken" and seen["ensure"] == ("t1", "610")
