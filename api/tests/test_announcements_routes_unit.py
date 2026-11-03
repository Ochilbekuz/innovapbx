"""M9 A1 — `/announcements` CRUD marshrutlari, DB/AMI'siz
(`test_conference_routes_unit.py` namunasi bo'yicha)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import announcements as an
from app.core.errors import ApiError
from app.schemas import AudioOut, CreateAnnouncementPayload, UpdateAnnouncementPayload

USER = SimpleNamespace(id="u1", tenant_id="t1")
NOW = datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)


class _Session:
    def __init__(self):
        self.added: list = []
        self.deleted: list = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    async def commit(self):
        self.commits += 1

    async def delete(self, obj):
        self.deleted.append(obj)


@pytest.fixture
def audit(monkeypatch):
    rows: list = []

    async def fake_audit(session, **kw):
        rows.append(kw)

    monkeypatch.setattr(an, "record_audit", fake_audit)
    return rows


@pytest.fixture
def stub_apply(monkeypatch):
    applied: list = []

    async def fake_apply(session, *, tenant_id, user_id, ami):
        applied.append(tenant_id)
        return SimpleNamespace(to_dict=lambda: {"status": "applied", "revision": 1, "message": None})

    async def fake_audio(session, tenant_id, audio_id, field):
        return SimpleNamespace(id=audio_id, name="Salom", duration_ms=1000, created_at=NOW)

    async def fake_resolve(session, tenant_id, target_id):
        return None if target_id == "bad" else {"kind": "hangup", "id": target_id, "label": "X", "broken": False}

    async def fake_ann_out(session, tenant_id, ann):
        return an.AnnouncementOut(
            id=str(ann.id), name=ann.name, audio=AudioOut(id="a1", name="Salom", duration_ms=1000,
                                                           format="wav", created_at=NOW),
            allow_skip=ann.allow_skip, repeat_key=ann.repeat_key, answer=ann.answer,
            next_target={"kind": "hangup", "id": ann.next_target_id, "label": "X", "broken": False},
            updated_at=NOW,
        )

    monkeypatch.setattr(an, "apply_config", fake_apply)
    monkeypatch.setattr(an, "_get_audio_or_422", fake_audio)
    monkeypatch.setattr(an, "resolve_target", fake_resolve)
    monkeypatch.setattr(an, "_ann_out", fake_ann_out)
    return applied


async def _no_create_target(session, tenant_id, kind, label):
    return SimpleNamespace(id=uuid.uuid4())


# ------------------------------------------------------------------- create
async def test_create_announcement_happy_path(monkeypatch, audit, stub_apply):
    monkeypatch.setattr(an, "create_target", _no_create_target)
    s = _Session()
    payload = CreateAnnouncementPayload(name="Dam olish kuni", audio_file_id="a1", next_target_id="hang1")
    out = await an.create_announcement(payload, s, USER, ami=None)
    assert s.added[0].name == "Dam olish kuni" and s.commits == 1
    assert stub_apply == ["t1"] and audit[0]["action"] == "announcement.create"
    assert out.item.name == "Dam olish kuni"


async def test_create_announcement_invalid_next_target_is_422(monkeypatch, audit, stub_apply):
    monkeypatch.setattr(an, "create_target", _no_create_target)
    payload = CreateAnnouncementPayload(name="X", audio_file_id="a1", next_target_id="bad")
    with pytest.raises(ApiError) as e:
        await an.create_announcement(payload, _Session(), USER, ami=None)
    assert (e.value.status_code, e.value.code, e.value.field) == (422, "invalid_target", "next_target_id")


# ------------------------------------------------------------------- update
async def test_update_announcement_renames_target_and_audits_diff(monkeypatch, audit, stub_apply):
    item = SimpleNamespace(id="a1", target_id="tgt-1", name="Eski", audio_file_id="a1",
                           next_target_id="hang1", allow_skip=False, repeat_key=None, answer=True,
                           updated_at=NOW)
    renamed: list = []

    async def fake_get(session, tenant_id, ann_id):
        return item

    async def fake_rename(session, target_id, name):
        renamed.append((target_id, name))

    monkeypatch.setattr(an, "_get_or_404", fake_get)
    monkeypatch.setattr(an, "rename_target", fake_rename)
    payload = UpdateAnnouncementPayload(name="Yangi", updated_at=NOW)
    await an.update_announcement("a1", payload, _Session(), USER, ami=None)
    assert item.name == "Yangi" and renamed == [("tgt-1", "Yangi")]
    assert audit[0]["diff"] == {"name": "Yangi"}


async def test_update_announcement_stale_is_409(monkeypatch):
    item = SimpleNamespace(id="a1", target_id="tgt-1", updated_at=NOW)

    async def fake_get(session, tenant_id, ann_id):
        return item

    monkeypatch.setattr(an, "_get_or_404", fake_get)
    old = datetime(2020, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ApiError) as e:
        await an.update_announcement("a1", UpdateAnnouncementPayload(updated_at=old), _Session(), USER, ami=None)
    assert (e.value.status_code, e.value.code) == (409, "stale")


# ------------------------------------------------------------------- delete
async def test_delete_announcement_in_use_is_409(monkeypatch):
    item = SimpleNamespace(id="a1", target_id="tgt-1", name="X")

    async def fake_get(session, tenant_id, ann_id):
        return item

    async def usages(session, tenant_id, target_id):
        return [{"kind": "ivr_option", "id": "i1", "label": "IVR", "field": "digit:1"}]

    monkeypatch.setattr(an, "_get_or_404", fake_get)
    monkeypatch.setattr(an, "usages_for_target", usages)
    with pytest.raises(ApiError) as e:
        await an.delete_announcement("a1", _Session(), USER, ami=None)
    assert (e.value.status_code, e.value.code) == (409, "in_use")


async def test_delete_announcement_ok_removes_entity_and_applies(monkeypatch, audit, stub_apply):
    item = SimpleNamespace(id="a1", target_id="tgt-1", name="X")

    async def fake_get(session, tenant_id, ann_id):
        return item

    async def no_usages(session, tenant_id, target_id):
        return []

    deleted: list = []

    async def fake_delete_satellite(session, obj, target_id):
        deleted.append((obj, target_id))

    monkeypatch.setattr(an, "_get_or_404", fake_get)
    monkeypatch.setattr(an, "usages_for_target", no_usages)
    monkeypatch.setattr(an, "delete_satellite_and_target", fake_delete_satellite)
    s = _Session()
    await an.delete_announcement("a1", s, USER, ami=None)
    assert deleted == [(item, "tgt-1")] and s.commits == 1 and audit[0]["action"] == "announcement.delete"
