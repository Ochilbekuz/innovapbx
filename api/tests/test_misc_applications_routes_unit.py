"""M9 A2 — `/misc-applications` CRUD va `code` to'qnashuv tekshiruvi
(`_validate_code`: boshqa `misc_applications`/feature kodlari/raqamlar bilan),
DB/AMI'siz."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import misc_applications as ma
from app.core.errors import ApiError
from app.db.models import FeatureCode, MiscApplication
from app.schemas import CreateMiscApplicationPayload, UpdateMiscApplicationPayload

USER = SimpleNamespace(id="u1", tenant_id="t1")
NOW = datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)


class _Result:
    def __init__(self, rows: list):
        self._rows = rows

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._rows))


class _Session:
    """`rows[Model]` — `_validate_code`ning ikki so'rovi uchun (siblings/feature kodlari);
    `added`/`commits` — yozish oqimini kuzatish."""

    def __init__(self, rows: dict | None = None):
        self._rows = {MiscApplication: [], FeatureCode: [], **(rows or {})}
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

    monkeypatch.setattr(ma, "record_audit", fake_audit)
    return rows


@pytest.fixture
def stub_apply(monkeypatch):
    applied: list = []

    async def fake_apply(session, *, tenant_id, user_id, ami):
        applied.append(tenant_id)
        return SimpleNamespace(to_dict=lambda: {"status": "applied", "revision": 1, "message": None})

    async def fake_resolve(session, tenant_id, target_id):
        return None if target_id == "bad" else {"kind": "hangup", "id": target_id, "label": "X", "broken": False}

    monkeypatch.setattr(ma, "apply_config", fake_apply)
    monkeypatch.setattr(ma, "resolve_target", fake_resolve)
    return applied


# ------------------------------------------------------------------- _validate_code
async def test_validate_code_rejects_sibling_prefix_clash():
    session = _Session({MiscApplication: ["*45"]})
    with pytest.raises(ApiError) as e:
        await ma._validate_code(session, "t1", "*4")
    assert (e.value.status_code, e.value.code) == (409, "code_taken")
    assert e.value.details == {"conflict": "*45"}


async def test_validate_code_rejects_feature_code_clash():
    session = _Session({FeatureCode: ["*76"]})
    with pytest.raises(ApiError) as e:
        await ma._validate_code(session, "t1", "*76")
    assert e.value.code == "code_taken"


async def test_validate_code_numeric_rejects_extension_number_clash(monkeypatch):
    async def taken(session, tenant_id, number):
        return number == "650"

    monkeypatch.setattr(ma, "number_taken", taken)
    session = _Session()
    with pytest.raises(ApiError) as e:
        await ma._validate_code(session, "t1", "650")
    assert e.value.code == "code_taken" and e.value.field == "code"


async def test_validate_code_ok_when_nothing_clashes(monkeypatch):
    async def not_taken(session, tenant_id, number):
        return False

    monkeypatch.setattr(ma, "number_taken", not_taken)
    await ma._validate_code(_Session(), "t1", "*55")  # ko'tarmaydi


# ------------------------------------------------------------------- create
async def test_create_misc_application_happy_path(monkeypatch, audit, stub_apply):
    monkeypatch.setattr(ma, "_validate_code", lambda *a, **kw: _ok())
    s = _Session()
    out = await ma.create_misc_application(
        CreateMiscApplicationPayload(name="Sayt", code="*55", target_id="tgt-1"), s, USER, ami=None)
    assert s.added[0].code == "*55" and s.commits == 1
    assert stub_apply == ["t1"] and audit[0]["action"] == "misc_application.create"
    assert out.item.code == "*55"


async def test_create_misc_application_invalid_target_is_422(stub_apply):
    with pytest.raises(ApiError) as e:
        await ma.create_misc_application(
            CreateMiscApplicationPayload(name="X", code="*55", target_id="bad"), _Session(), USER, ami=None)
    assert (e.value.status_code, e.value.code, e.value.field) == (422, "invalid_target", "target_id")


async def _ok():
    return None


# ------------------------------------------------------------------- update
async def test_update_misc_application_changes_code_with_exclude_id(monkeypatch, audit, stub_apply):
    item = SimpleNamespace(id="m1", name="Eski", code="*55", target_id="tgt-1", enabled=True, updated_at=NOW)
    seen = {}

    async def fake_get(session, tenant_id, item_id):
        return item

    async def fake_validate(session, tenant_id, code, exclude_id=None):
        seen["args"] = (tenant_id, code, exclude_id)

    monkeypatch.setattr(ma, "_get_or_404", fake_get)
    monkeypatch.setattr(ma, "_validate_code", fake_validate)
    payload = UpdateMiscApplicationPayload(code="*56", updated_at=NOW)
    await ma.update_misc_application("m1", payload, _Session(), USER, ami=None)
    assert item.code == "*56" and seen["args"] == ("t1", "*56", "m1")
    assert audit[0]["diff"] == {"code": "*56"}


async def test_update_misc_application_stale_is_409(monkeypatch):
    item = SimpleNamespace(id="m1", updated_at=NOW)

    async def fake_get(session, tenant_id, item_id):
        return item

    monkeypatch.setattr(ma, "_get_or_404", fake_get)
    old = datetime(2020, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ApiError) as e:
        await ma.update_misc_application("m1", UpdateMiscApplicationPayload(updated_at=old), _Session(),
                                          USER, ami=None)
    assert (e.value.status_code, e.value.code) == (409, "stale")


# ------------------------------------------------------------------- delete
async def test_delete_misc_application_removes_row_no_usages_check(monkeypatch, audit, stub_apply):
    """Kontrakt: `MiscApplication` o'zi `call_targets` SATELLITI EMAS (sof
    `code -> target_id` xaritasi) — `usages_for_target` chaqirilmaydi, shunchaki o'chiriladi."""
    item = SimpleNamespace(id="m1", name="X")

    async def fake_get(session, tenant_id, item_id):
        return item

    monkeypatch.setattr(ma, "_get_or_404", fake_get)
    s = _Session()
    await ma.delete_misc_application("m1", s, USER, ami=None)
    assert s.deleted == [item] and s.commits == 1 and audit[0]["action"] == "misc_application.delete"
