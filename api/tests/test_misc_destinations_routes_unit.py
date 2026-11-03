"""M9 A2 — `/misc-destinations` CRUD marshrutlari, DB/AMI'siz."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import misc_destinations as md
from app.core.errors import ApiError
from app.schemas import CreateMiscDestinationPayload, UpdateMiscDestinationPayload

USER = SimpleNamespace(id="u1", tenant_id="t1")
NOW = datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)


class _Session:
    def __init__(self):
        self.added: list = []
        self.commits = 0

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


@pytest.fixture
def audit(monkeypatch):
    rows: list = []

    async def fake_audit(session, **kw):
        rows.append(kw)

    monkeypatch.setattr(md, "record_audit", fake_audit)
    return rows


@pytest.fixture
def stub_apply(monkeypatch):
    applied: list = []

    async def fake_apply(session, *, tenant_id, user_id, ami):
        applied.append(tenant_id)
        return SimpleNamespace(to_dict=lambda: {"status": "applied", "revision": 1, "message": None})

    async def no_create_target(session, tenant_id, kind, label):
        return SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(md, "apply_config", fake_apply)
    monkeypatch.setattr(md, "create_target", no_create_target)
    return applied


async def test_create_misc_destination_happy_path(audit, stub_apply):
    s = _Session()
    out = await md.create_misc_destination(
        CreateMiscDestinationPayload(name="Qiz-qiz uchun", dial="9998901112233"), s, USER, ami=None)
    assert s.added[0].dial == "9998901112233" and s.commits == 1
    assert stub_apply == ["t1"] and audit[0]["action"] == "misc_destination.create"
    assert out.item.dial == "9998901112233"


async def test_update_misc_destination_renames_target_and_changes_dial(monkeypatch, audit, stub_apply):
    item = SimpleNamespace(id="m1", target_id="tgt-1", name="Eski", dial="600", updated_at=NOW)
    renamed: list = []

    async def fake_get(session, tenant_id, item_id):
        return item

    async def fake_rename(session, target_id, name):
        renamed.append((target_id, name))

    monkeypatch.setattr(md, "_get_or_404", fake_get)
    monkeypatch.setattr(md, "rename_target", fake_rename)
    payload = UpdateMiscDestinationPayload(name="Yangi", dial="601", updated_at=NOW)
    out = await md.update_misc_destination("m1", payload, _Session(), USER, ami=None)
    assert item.name == "Yangi" and item.dial == "601" and renamed == [("tgt-1", "Yangi")]
    assert audit[0]["diff"] == {"name": "Yangi", "dial": "601"}
    assert out.item.name == "Yangi"


async def test_update_misc_destination_stale_is_409(monkeypatch):
    item = SimpleNamespace(id="m1", target_id="tgt-1", updated_at=NOW)

    async def fake_get(session, tenant_id, item_id):
        return item

    monkeypatch.setattr(md, "_get_or_404", fake_get)
    old = datetime(2020, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ApiError) as e:
        await md.update_misc_destination("m1", UpdateMiscDestinationPayload(updated_at=old), _Session(),
                                          USER, ami=None)
    assert (e.value.status_code, e.value.code) == (409, "stale")


async def test_delete_misc_destination_in_use_is_409(monkeypatch):
    item = SimpleNamespace(id="m1", target_id="tgt-1", name="X")

    async def fake_get(session, tenant_id, item_id):
        return item

    async def usages(session, tenant_id, target_id):
        return [{"kind": "ivr_option", "id": "i1", "label": "IVR", "field": "digit:1"}]

    monkeypatch.setattr(md, "_get_or_404", fake_get)
    monkeypatch.setattr(md, "usages_for_target", usages)
    with pytest.raises(ApiError) as e:
        await md.delete_misc_destination("m1", _Session(), USER, ami=None)
    assert (e.value.status_code, e.value.code) == (409, "in_use")


async def test_delete_misc_destination_ok(monkeypatch, audit, stub_apply):
    item = SimpleNamespace(id="m1", target_id="tgt-1", name="X")

    async def fake_get(session, tenant_id, item_id):
        return item

    async def no_usages(session, tenant_id, target_id):
        return []

    deleted: list = []

    async def fake_delete_satellite(session, obj, target_id):
        deleted.append((obj, target_id))

    monkeypatch.setattr(md, "_get_or_404", fake_get)
    monkeypatch.setattr(md, "usages_for_target", no_usages)
    monkeypatch.setattr(md, "delete_satellite_and_target", fake_delete_satellite)
    s = _Session()
    await md.delete_misc_destination("m1", s, USER, ami=None)
    assert deleted == [(item, "tgt-1")] and s.commits == 1 and audit[0]["action"] == "misc_destination.delete"
