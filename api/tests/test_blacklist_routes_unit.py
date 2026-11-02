"""`/blacklist` marshrut funksiyalari — DB'siz (soxta sessiya), realtime
(apply/reload yo'q — m2a-contract.md §5). CDR `userfield=blacklisted`
belgilanishi dialplan tomonida (`test_compiler_call_features.py`da sinaladi)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import blacklist as bl
from app.core.errors import ApiError
from app.schemas_blacklist import CreateBlacklistPayload

USER = SimpleNamespace(id="u1", tenant_id="t1")
NOW = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)


class _Session:
    def __init__(self):
        self.added: list = []
        self.deleted: list = []
        self.commits = 0

    def add(self, obj):
        # Haqiqiy asyncpg seansida `INSERT ... RETURNING` bilan server_default
        # (`created_at`) flush vaqtida to'ldiriladi (`expire_on_commit=False`,
        # `app/db/session.py`) — soxta seansda shu holatni simulyatsiya qilamiz.
        obj.created_at = NOW
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commits += 1


@pytest.fixture
def audit(monkeypatch):
    rows: list = []

    async def fake_audit(session, **kw):
        rows.append(kw)

    monkeypatch.setattr(bl, "record_audit", fake_audit)
    return rows


async def test_add_normalizes_number_and_commits(monkeypatch, audit):
    async def no_entry(session, tenant_id, number):
        return None

    monkeypatch.setattr(bl, "get_entry", no_entry)
    s = _Session()
    out = await bl.add_blacklist_entry(CreateBlacklistPayload(number="+998 (90) 111-22-33", reason="spam"),
                                       s, USER)
    entry = s.added[0]
    assert entry.number == "998901112233" and entry.reason == "spam"
    assert out.item.number == "998901112233"
    assert audit[0]["action"] == "blacklist.create" and audit[0]["diff"]["number"] == "998901112233"
    assert s.commits == 1


async def test_add_duplicate_is_409(monkeypatch, audit):
    async def existing(session, tenant_id, number):
        return SimpleNamespace(number=number)

    monkeypatch.setattr(bl, "get_entry", existing)
    with pytest.raises(ApiError) as exc:
        await bl.add_blacklist_entry(CreateBlacklistPayload(number="90123"), _Session(), USER)
    assert (exc.value.status_code, exc.value.code, exc.value.field) == (409, "exists", "number")


async def test_add_bad_number_is_422():
    with pytest.raises(ApiError) as exc:
        await bl.add_blacklist_entry(CreateBlacklistPayload(number="1"), _Session(), USER)
    assert exc.value.status_code == 422 and exc.value.code == "bad_number"


async def test_add_anonymous_keyword_accepted(monkeypatch, audit):
    async def no_entry(session, tenant_id, number):
        return None

    monkeypatch.setattr(bl, "get_entry", no_entry)
    out = await bl.add_blacklist_entry(CreateBlacklistPayload(number="anonymous"), _Session(), USER)
    assert out.item.number == "anonymous"


async def test_remove_ok(monkeypatch, audit):
    entry = SimpleNamespace(number="998901112233")

    async def found(session, tenant_id, number):
        return entry

    monkeypatch.setattr(bl, "get_entry", found)
    s = _Session()
    await bl.remove_blacklist_entry("998-90-111-22-33", s, USER)
    assert s.deleted == [entry] and audit[0]["action"] == "blacklist.delete" and s.commits == 1


async def test_remove_not_found_is_404(monkeypatch):
    async def none(session, tenant_id, number):
        return None

    monkeypatch.setattr(bl, "get_entry", none)
    with pytest.raises(ApiError) as exc:
        await bl.remove_blacklist_entry("998901112233", _Session(), USER)
    assert exc.value.status_code == 404 and exc.value.code == "not_found"


async def test_remove_unparseable_number_is_404_not_422():
    with pytest.raises(ApiError) as exc:
        await bl.remove_blacklist_entry("1", _Session(), USER)
    assert exc.value.status_code == 404 and exc.value.code == "not_found"
