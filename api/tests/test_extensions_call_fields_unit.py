"""M2a §1: ext PATCH — DND/yo'naltirish/pickup guruhi (realtime, apply'siz) va raqam bandligi.
DB/AMI'siz: soxta sessiya, tashqi qadamlar monkeypatch. Jonli oqim — `scripts/m2a-proof.sh`."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import extensions as ex
from app.core.errors import ApiError
from app.schemas import UpdateExtensionPayload

USER = SimpleNamespace(id="u1", tenant_id="t1")
OLD = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)


class _Session:
    def __init__(self):
        self.commits = self.flushes = self.refreshed = 0

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        self.refreshed += 1
        obj.updated_at = NOW


def _ext(**kw):
    base = dict(id="e1", number="201", name="Ali", enabled=True, outbound_allowed=True,
                outbound_callerid=None, dnd=False, forward_always=None, forward_busy="202",
                pickup_group=None, toll_blocked_at=None, toll_block_reason=None, updated_at=OLD,
                webrtc=False, codecs=["ulaw", "alaw", "g722", "opus"])
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def env(monkeypatch):
    state = {"ext": _ext(), "audit": [], "applied": 0}

    async def fake_get(session, tenant_id, ext_id):
        return state["ext"]

    async def fake_audit(session, **kw):
        state["audit"].append(kw)

    async def fake_apply(session, *, tenant_id, user_id, ami):
        state["applied"] += 1
        return SimpleNamespace(to_dict=lambda: {"status": "applied", "revision": 7, "message": None})

    monkeypatch.setattr(ex, "_get_extension_or_404", fake_get)
    monkeypatch.setattr(ex, "record_audit", fake_audit)
    monkeypatch.setattr(ex, "apply_config", fake_apply)
    return state


async def _patch(body: dict, session=None, stamp=OLD):
    payload = UpdateExtensionPayload(updated_at=stamp, **body)
    return await ex.update_extension("e1", payload, session=session or _Session(), user=USER, ami=None)


@pytest.mark.asyncio
async def test_realtime_fields_change_without_apply(env):
    session = _Session()
    out = await _patch({"dnd": True, "forward_always": "998901112233", "pickup_group": "sales"}, session)
    assert env["applied"] == 0
    assert out.apply.model_dump() == {"status": "applied", "revision": None, "message": None}
    assert out.item.dnd is True and out.item.forward_always == "998901112233"
    assert out.item.pickup_group == "sales" and out.item.forward_busy == "202"
    assert out.item.updated_at == NOW and session.refreshed == 1 and session.commits == 1
    assert env["audit"][0]["diff"] == {
        "dnd": {"from": False, "to": True},
        "forward_always": {"from": None, "to": "998901112233"},
        "pickup_group": {"from": None, "to": "sales"},
    }


@pytest.mark.asyncio
async def test_explicit_null_clears_and_missing_keeps(env):
    out = await _patch({"forward_busy": None})
    assert out.item.forward_busy is None
    assert env["ext"].forward_busy is None and env["applied"] == 0
    out2 = await _patch({"name": "Vali"}, stamp=NOW)
    assert out2.item.forward_busy is None and out2.item.name == "Vali"


@pytest.mark.asyncio
async def test_empty_string_clears(env):
    env["ext"].pickup_group = "sales"
    out = await _patch({"pickup_group": "", "forward_busy": ""})
    assert out.item.pickup_group is None and out.item.forward_busy is None


@pytest.mark.asyncio
async def test_non_realtime_change_applies(env):
    out = await _patch({"name": "Vali", "dnd": True})
    assert env["applied"] == 1 and out.apply.revision == 7


@pytest.mark.asyncio
async def test_no_change_still_applies_as_before(env):
    await _patch({})
    assert env["applied"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [
    ("forward_always", "abc"), ("forward_always", "1"), ("forward_busy", "+1234567890123456"),
    ("forward_always", "201"), ("forward_busy", "+201"),
])
async def test_bad_forward_number(env, field, value):
    with pytest.raises(ApiError) as e:
        await _patch({field: value})
    assert (e.value.status_code, e.value.code, e.value.field) == (422, "bad_number", field)
    assert env["applied"] == 0 and env["audit"] == []


@pytest.mark.asyncio
async def test_forward_number_whitespace_dash_parens_normalized(env):
    """Tuzatish (a): bo'shliq/`-`/`()` ham normalizatsiyada olib tashlanadi (blacklist bilan bir xil)."""
    out = await _patch({"forward_busy": "(998) 90-111-22-33"})
    assert out.item.forward_busy == "998901112233"


@pytest.mark.asyncio
async def test_plus_number_normalized_at_input(env):
    """Tuzatish (a): boshidagi `+` kirishda olib tashlanadi (dialplan `_X.` mos kelishi uchun)."""
    out = await _patch({"forward_always": "+998901112233"})
    assert out.item.forward_always == "998901112233"
    assert env["audit"][0]["diff"]["forward_always"]["to"] == "998901112233"


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["Sales", "a b", "x" * 33, "ñ"])
async def test_bad_pickup_group(env, value):
    with pytest.raises(ApiError) as e:
        await _patch({"pickup_group": value})
    assert (e.value.status_code, e.value.code, e.value.field) == (422, "bad_pickup_group", "pickup_group")


@pytest.mark.asyncio
async def test_pickup_group_edge_lengths(env):
    out = await _patch({"pickup_group": "a" * 32})
    assert out.item.pickup_group == "a" * 32
    out = await _patch({"pickup_group": "a-_9"}, stamp=NOW)
    assert out.item.pickup_group == "a-_9"


def test_ext_out_has_call_fields():
    item = ex._ext_out(_ext(dnd=True, pickup_group="g1"))
    assert (item.dnd, item.forward_always, item.forward_busy, item.pickup_group) == (True, None, "202", "g1")
    assert item.status == "unknown"


class _NumSession:
    def __init__(self, used):
        self.used = used

    async def execute(self, stmt):
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: self.used))


@pytest.mark.asyncio
async def test_next_free_number_skips_park_range(monkeypatch):
    monkeypatch.setattr(ex, "_NUMBER_RANGE", range(699, 723))
    used = ["699"]
    assert await ex._next_free_number(_NumSession(used), "t1") == "721"


@pytest.mark.asyncio
async def test_next_free_number_exhausted(monkeypatch):
    monkeypatch.setattr(ex, "_NUMBER_RANGE", range(700, 721))
    with pytest.raises(ApiError) as e:
        await ex._next_free_number(_NumSession([]), "t1")
    assert e.value.code == "no_free_number"
