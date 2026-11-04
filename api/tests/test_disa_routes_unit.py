"""`/disa` marshrut funksiyalari — DB/AMI'siz (soxta sessiya, tashqi
qadamlar monkeypatch), `test_conference_routes_unit.py` namunasi bo'yicha.
Asosiy talab: PIN hech qachon javobda ochiq saqlanmaydi; PIN bo'sh FAQAT
`allow_no_pin=true` bilan ruxsat etiladi (ham yaratishda Pydantic, ham
yangilashda qayta tekshiriladi — m12-contract.md A2)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import disa as ds
from app.core.config import settings
from app.core.errors import ApiError
from app.schemas import CreateDisaPayload, UpdateDisaPayload

USER = SimpleNamespace(id="u1", tenant_id="t1")
NOW = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _secret_key(monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "test-secret-key")


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

    async def get(self, model, key):
        return None


@pytest.fixture
def audit(monkeypatch):
    rows: list = []

    async def fake_audit(session, **kw):
        rows.append(kw)

    monkeypatch.setattr(ds, "record_audit", fake_audit)
    return rows


@pytest.fixture
def stub_apply(monkeypatch):
    applied: list = []

    async def fake_apply(session, tenant_id, user_id, ami):
        applied.append(tenant_id)
        return SimpleNamespace(to_dict=lambda: {"status": "applied", "revision": 1, "message": None})

    monkeypatch.setattr(ds, "apply_config", fake_apply)
    return applied


async def _no_usages(session, tenant_id, target_id):
    return []


def _item(**over):
    base = dict(id="d1", target_id="tgt-1", name="Tashqi", pin_hmac=None, allow_no_pin=False,
                cid_override=None, digit_timeout=5, response_timeout=10, max_attempts=3,
                enabled=True, updated_at=NOW)
    base.update(over)
    return SimpleNamespace(**base)


# ------------------------------------------------------------------- create
async def test_create_hashes_pin_and_masks_it_in_audit(monkeypatch, audit, stub_apply):
    async def no_create_target(session, tenant_id, kind, label):
        return SimpleNamespace(id=uuid.uuid4())

    async def _get_disa(session, tenant_id, row_id):
        return _item()

    monkeypatch.setattr(ds, "create_target", no_create_target)
    monkeypatch.setattr(ds, "_get_or_404", _get_disa)
    s = _Session()
    payload = CreateDisaPayload(name="Tashqi", pin="1234")
    out = await ds.create_disa(payload, s, USER, ami=None)

    item = s.added[0]
    assert item.pin_hmac and item.pin_hmac != "1234"
    assert audit[0]["diff"] == {"name": "Tashqi"}
    assert not hasattr(out.item, "pin") and not hasattr(out.item, "pin_hmac")
    assert stub_apply == ["t1"] and s.commits == 1


async def test_create_allows_no_pin_when_allow_no_pin_true(monkeypatch, audit, stub_apply):
    async def no_create_target(session, tenant_id, kind, label):
        return SimpleNamespace(id=uuid.uuid4())

    async def _get_disa(session, tenant_id, row_id):
        return _item(allow_no_pin=True)

    monkeypatch.setattr(ds, "create_target", no_create_target)
    monkeypatch.setattr(ds, "_get_or_404", _get_disa)
    s = _Session()
    payload = CreateDisaPayload(name="Tashqi", allow_no_pin=True)
    await ds.create_disa(payload, s, USER, ami=None)
    assert s.added[0].pin_hmac is None


def test_create_payload_rejects_blank_pin_without_allow_no_pin():
    with pytest.raises(Exception):
        CreateDisaPayload(name="Tashqi")


# ------------------------------------------------------------------- update
async def test_update_sets_and_clears_pin(monkeypatch, audit, stub_apply):
    item = _item(pin_hmac="OLD")

    async def _get_disa(session, tenant_id, row_id):
        return item

    monkeypatch.setattr(ds, "_get_or_404", _get_disa)
    payload = UpdateDisaPayload(pin="4321", updated_at=NOW)
    await ds.update_disa("d1", payload, _Session(), USER, ami=None)
    assert item.pin_hmac != "OLD" and item.pin_hmac != "4321"
    assert audit[0]["diff"] == {"pin": "***"}


async def test_update_pin_clear_without_allow_no_pin_is_422(monkeypatch):
    item = _item(pin_hmac="OLD", allow_no_pin=False)

    async def _get_disa(session, tenant_id, row_id):
        return item

    monkeypatch.setattr(ds, "_get_or_404", _get_disa)
    payload = UpdateDisaPayload(pin_clear=True, updated_at=NOW)
    with pytest.raises(ApiError) as exc:
        await ds.update_disa("d1", payload, _Session(), USER, ami=None)
    assert exc.value.status_code == 422 and exc.value.code == "pin_required"


async def test_update_pin_clear_with_allow_no_pin_ok(monkeypatch, audit, stub_apply):
    item = _item(pin_hmac="OLD", allow_no_pin=False)

    async def _get_disa(session, tenant_id, row_id):
        return item

    monkeypatch.setattr(ds, "_get_or_404", _get_disa)
    payload = UpdateDisaPayload(pin_clear=True, allow_no_pin=True, updated_at=NOW)
    await ds.update_disa("d1", payload, _Session(), USER, ami=None)
    assert item.pin_hmac is None and item.allow_no_pin is True


async def test_update_renames_and_updates_simple_fields(monkeypatch, audit, stub_apply):
    item = _item(allow_no_pin=True)
    renamed: list = []

    async def _get_disa(session, tenant_id, row_id):
        return item

    async def fake_rename(session, target_id, name):
        renamed.append((target_id, name))

    monkeypatch.setattr(ds, "_get_or_404", _get_disa)
    monkeypatch.setattr(ds, "rename_target", fake_rename)
    payload = UpdateDisaPayload(
        name="Yangi nom", cid_override="+998901112233", digit_timeout=7,
        response_timeout=15, max_attempts=5, enabled=False, updated_at=NOW,
    )
    await ds.update_disa("d1", payload, _Session(), USER, ami=None)

    assert item.name == "Yangi nom" and renamed == [("tgt-1", "Yangi nom")]
    assert item.cid_override == "+998901112233"
    assert (item.digit_timeout, item.response_timeout, item.max_attempts, item.enabled) == (7, 15, 5, False)
    assert audit[0]["diff"] == {
        "cid_override": "+998901112233", "digit_timeout": 7, "response_timeout": 15,
        "max_attempts": 5, "enabled": False, "name": "Yangi nom",
    }


async def test_update_blank_cid_override_clears_it(monkeypatch, audit, stub_apply):
    item = _item(allow_no_pin=True, cid_override="+998901112233")

    async def _get_disa(session, tenant_id, row_id):
        return item

    monkeypatch.setattr(ds, "_get_or_404", _get_disa)
    payload = UpdateDisaPayload(cid_override="", updated_at=NOW)
    await ds.update_disa("d1", payload, _Session(), USER, ami=None)
    assert item.cid_override is None


async def test_update_stale_is_409(monkeypatch):
    item = _item()

    async def _get_disa(session, tenant_id, row_id):
        return item

    monkeypatch.setattr(ds, "_get_or_404", _get_disa)
    with pytest.raises(ApiError) as exc:
        await ds.update_disa(
            "d1", UpdateDisaPayload(updated_at=datetime(2020, 1, 1, tzinfo=timezone.utc)),
            _Session(), USER, ami=None,
        )
    assert exc.value.status_code == 409 and exc.value.code == "stale"


# ------------------------------------------------------------------- delete
async def test_delete_in_use_is_409_with_usages(monkeypatch):
    item = _item()

    async def _get_disa(session, tenant_id, row_id):
        return item

    async def usages(session, tenant_id, target_id):
        return [{"kind": "ivr_option", "id": "i1", "label": "IVR", "field": "digit:1"}]

    monkeypatch.setattr(ds, "_get_or_404", _get_disa)
    monkeypatch.setattr(ds, "usages_for_target", usages)
    with pytest.raises(ApiError) as exc:
        await ds.delete_disa("d1", _Session(), USER, ami=None)
    assert exc.value.status_code == 409 and exc.value.code == "in_use"


async def test_delete_ok_removes_entity_and_applies(monkeypatch, audit, stub_apply):
    item = _item()

    async def _get_disa(session, tenant_id, row_id):
        return item

    monkeypatch.setattr(ds, "_get_or_404", _get_disa)
    monkeypatch.setattr(ds, "usages_for_target", _no_usages)
    s = _Session()
    await ds.delete_disa("d1", s, USER, ami=None)
    assert audit[0]["action"] == "disa.delete" and s.commits == 1
