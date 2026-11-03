"""M9 A4 — `/page-groups` CRUD marshrutlari (paging/intercom guruhlari),
DB/AMI'siz. `_out`/`_set_members` to'g'ridan-to'g'ri stublanadi — haqiqiy
`PageGroupMember.extension` munosabati (selectinload) soxta sessiyada
yuklanmaydi (IDOR emas, oddiy ORM lazy-load cheklovi)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import page_groups as pg
from app.core.errors import ApiError
from app.db.models import Extension
from app.schemas import CreatePageGroupPayload, PageGroupOut, UpdatePageGroupPayload

USER = SimpleNamespace(id="u1", tenant_id="t1")
NOW = datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)


class _Result:
    def __init__(self, rows: list):
        self._rows = rows

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._rows))


class _Session:
    def __init__(self, rows: dict | None = None):
        self._rows = {Extension: [], **(rows or {})}
        self.added: list = []
        self.deleted: list = []
        self.commits = 0

    async def execute(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        return _Result(self._rows[entity])

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()
            if getattr(obj, "updated_at", None) is None:
                obj.updated_at = NOW

    async def commit(self):
        self.commits += 1

    async def delete(self, obj):
        self.deleted.append(obj)


@pytest.fixture
def audit(monkeypatch):
    rows: list = []

    async def fake_audit(session, **kw):
        rows.append(kw)

    monkeypatch.setattr(pg, "record_audit", fake_audit)
    return rows


def _fake_out(item: SimpleNamespace) -> PageGroupOut:
    return PageGroupOut(id=str(item.id), name=item.name, number=item.number, members=[],
                        duplex=item.duplex, skip_busy=item.skip_busy, beep=item.beep,
                        updated_at=item.updated_at)


@pytest.fixture
def stub_apply(monkeypatch):
    applied: list = []

    async def fake_apply(session, *, tenant_id, user_id, ami):
        applied.append(tenant_id)
        return SimpleNamespace(to_dict=lambda: {"status": "applied", "revision": 1, "message": None})

    async def fake_ensure_free(session, tenant_id, number, **kw):
        return None

    monkeypatch.setattr(pg, "apply_config", fake_apply)
    monkeypatch.setattr(pg, "ensure_number_free", fake_ensure_free)
    monkeypatch.setattr(pg, "_out", _fake_out)
    return applied


def _new_group(**over) -> SimpleNamespace:
    base = dict(id="pg1", name="Sotuv", number="601", members=[], duplex=False,
                skip_busy=True, beep=True, updated_at=NOW)
    base.update(over)
    return SimpleNamespace(**base)


# ------------------------------------------------------------------- _validate_members
async def test_validate_members_rejects_unknown_extension_ids():
    session = _Session({Extension: ["e1"]})
    with pytest.raises(ApiError) as e:
        await pg._validate_members(session, "t1", ["e1", "e2"])
    assert (e.value.status_code, e.value.code, e.value.field) == (422, "invalid_extension", "member_extension_ids")
    assert e.value.details == {"missing": ["e2"]}


async def test_validate_members_ok_when_empty():
    await pg._validate_members(_Session(), "t1", [])  # ko'tarmaydi — so'rov yo'q


# ------------------------------------------------------------------- create
async def test_create_page_group_happy_path(monkeypatch, audit, stub_apply):
    monkeypatch.setattr(pg, "_validate_members", _no_validate)
    item = _new_group()

    async def fake_get_or_404(session, tenant_id, item_id):
        return item

    monkeypatch.setattr(pg, "_get_or_404", fake_get_or_404)
    s = _Session()
    out = await pg.create_page_group(
        CreatePageGroupPayload(name="Sotuv", number="601", member_extension_ids=["e1"]), s, USER, ami=None)
    assert s.added[0].number == "601" and s.commits == 1
    assert stub_apply == ["t1"] and audit[0]["action"] == "page_group.create"
    assert out.item.number == "601"


async def _no_validate(session, tenant_id, extension_ids):
    return None


# ------------------------------------------------------------------- update
async def test_update_page_group_changes_number_and_members(monkeypatch, audit, stub_apply):
    item = _new_group()

    async def fake_get_or_404(session, tenant_id, item_id):
        return item

    monkeypatch.setattr(pg, "_get_or_404", fake_get_or_404)
    monkeypatch.setattr(pg, "_validate_members", _no_validate)
    monkeypatch.setattr(pg, "_set_members", lambda item, ids: setattr(item, "members", list(ids)))
    payload = UpdatePageGroupPayload(number="602", member_extension_ids=["e1", "e2"], updated_at=NOW)
    out = await pg.update_page_group("pg1", payload, _Session(), USER, ami=None)
    assert item.number == "602" and len(item.members) == 2
    assert audit[0]["diff"] == {"number": "602", "members": 2}
    assert out.item.number == "602"


async def test_update_page_group_stale_is_409(monkeypatch):
    item = _new_group()

    async def fake_get_or_404(session, tenant_id, item_id):
        return item

    monkeypatch.setattr(pg, "_get_or_404", fake_get_or_404)
    old = datetime(2020, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ApiError) as e:
        await pg.update_page_group("pg1", UpdatePageGroupPayload(updated_at=old), _Session(), USER, ami=None)
    assert (e.value.status_code, e.value.code) == (409, "stale")


async def test_update_page_group_number_taken_is_409(monkeypatch, audit):
    item = _new_group()

    async def fake_get_or_404(session, tenant_id, item_id):
        return item

    async def taken(session, tenant_id, number, **kw):
        raise ApiError(409, "number_taken", "Bu raqam band", field="number")

    monkeypatch.setattr(pg, "_get_or_404", fake_get_or_404)
    monkeypatch.setattr(pg, "ensure_number_free", taken)
    with pytest.raises(ApiError) as e:
        await pg.update_page_group("pg1", UpdatePageGroupPayload(number="602", updated_at=NOW), _Session(),
                                   USER, ami=None)
    assert e.value.code == "number_taken"


# ------------------------------------------------------------------- delete
async def test_delete_page_group_removes_row(monkeypatch, audit, stub_apply):
    item = _new_group()

    async def fake_get_or_404(session, tenant_id, item_id):
        return item

    monkeypatch.setattr(pg, "_get_or_404", fake_get_or_404)
    s = _Session()
    await pg.delete_page_group("pg1", s, USER, ami=None)
    assert s.deleted == [item] and s.commits == 1 and audit[0]["action"] == "page_group.delete"
