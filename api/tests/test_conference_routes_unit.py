"""`/conferences` marshrut funksiyalari — DB/AMI'siz (soxta sessiya, tashqi
qadamlar monkeypatch), `test_voicemail_routes_unit.py` namunasi bo'yicha.
Asosiy talab: PIN hech qachon javobda/audit diff'da ochiq saqlanmaydi (hash
bazaga yoziladi, `has_pin`/`has_admin_pin` faqat bool). To'liq oqim jonli
testda (`scripts/m2a-proof.sh`, ssenariy 8)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import conferences as cr
from app.core.errors import ApiError
from app.schemas_conference import CreateConferencePayload, UpdateConferencePayload

USER = SimpleNamespace(id="u1", tenant_id="t1")
NOW = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)


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

    monkeypatch.setattr(cr, "record_audit", fake_audit)
    return rows


@pytest.fixture
def stub_apply(monkeypatch):
    applied: list = []

    async def fake_apply(session, tenant_id, user, ami):
        applied.append(tenant_id)
        return {"status": "applied", "revision": 1, "message": None}

    async def fake_code(session, tenant_id):
        return "t1"

    async def fake_get(session, tenant_id, conference_id):
        return SimpleNamespace(id=conference_id, target_id="tgt-1", name="X", pin_hash=None,
                               admin_pin_hash=None, record=False, max_members=None, updated_at=NOW)

    async def no_number(*a, **kw):
        return None

    async def no_live(ami, room):
        return 0

    monkeypatch.setattr(cr, "apply_dialplan_and_confbridge", fake_apply)
    monkeypatch.setattr(cr, "get_tenant_code", fake_code)
    monkeypatch.setattr(cr, "_get_conf_or_404", fake_get)
    monkeypatch.setattr(cr, "dial_number_for_target", no_number)
    monkeypatch.setattr(cr.conf, "live_members", no_live)
    return applied


async def _no_usages(session, tenant_id, target_id):
    return []


# ------------------------------------------------------------------- create
async def test_create_hashes_pins_and_masks_them_in_audit(monkeypatch, audit, stub_apply):
    async def no_create_target(session, tenant_id, kind, label):
        return SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(cr, "create_target", no_create_target)
    s = _Session()
    payload = CreateConferencePayload(name="Yig'ilish", pin="1234", admin_pin="9999")
    out = await cr.create_conference(payload, s, USER, ami=None)

    item = s.added[0]
    assert item.pin_hash and item.pin_hash != "1234"
    assert item.admin_pin_hash and item.admin_pin_hash != "9999"
    assert audit[0]["diff"] == {"name": "Yig'ilish", "pin": "1234", "admin_pin": "9999"}
    assert not hasattr(out.item, "pin") and not hasattr(out.item, "pin_hash")  # javobda ochiq PIN yo'q
    assert stub_apply == ["t1"] and s.commits == 1


async def test_conf_out_maps_pin_hash_presence_to_bool(monkeypatch):
    item = SimpleNamespace(id="c1", target_id="tgt-1", name="X", pin_hash="H", admin_pin_hash=None,
                           record=False, max_members=None, updated_at=NOW)

    async def no_number(*a, **kw):
        return None

    async def no_live(ami, room):
        return 0

    monkeypatch.setattr(cr, "dial_number_for_target", no_number)
    monkeypatch.setattr(cr.conf, "live_members", no_live)
    out = await cr._conf_out(_Session(), "t1", "t1", item, ami=None)
    assert out.has_pin is True and out.has_admin_pin is False


async def test_create_number_taken_is_409(monkeypatch, audit, stub_apply):
    async def taken(session, tenant_id, number, **kw):
        raise ApiError(409, "number_taken", "Bu raqam band", field="number")

    monkeypatch.setattr(cr, "ensure_number_free", taken)
    with pytest.raises(ApiError) as exc:
        await cr.create_conference(CreateConferencePayload(name="X", number="600"), _Session(), USER, ami=None)
    assert exc.value.code == "number_taken"


# ------------------------------------------------------------------- update
async def test_update_sets_and_clears_pins(monkeypatch, audit, stub_apply):
    item = SimpleNamespace(id="c1", target_id="tgt-1", updated_at=NOW, name="X", pin_hash="OLD",
                           admin_pin_hash="OLDADMIN", record=False, max_members=None)

    async def fake_get(session, tenant_id, conference_id):
        return item

    monkeypatch.setattr(cr, "_get_conf_or_404", fake_get)
    payload = UpdateConferencePayload(pin="4321", admin_pin=None, updated_at=NOW)
    await cr.update_conference("c1", payload, _Session(), USER, ami=None)
    assert item.pin_hash != "OLD" and item.pin_hash != "4321"
    assert item.admin_pin_hash is None
    assert audit[0]["diff"] == {"pin": "4321", "admin_pin": None}


async def test_update_max_members_can_be_cleared_via_model_fields_set(monkeypatch, audit, stub_apply):
    item = SimpleNamespace(id="c1", target_id="tgt-1", updated_at=NOW, name="X", pin_hash=None,
                           admin_pin_hash=None, record=False, max_members=20)

    async def fake_get(session, tenant_id, conference_id):
        return item

    monkeypatch.setattr(cr, "_get_conf_or_404", fake_get)
    await cr.update_conference("c1", UpdateConferencePayload(max_members=None, updated_at=NOW),
                               _Session(), USER, ami=None)
    assert item.max_members is None
    assert audit[0]["diff"] == {"max_members": None}


async def test_update_stale_is_409(monkeypatch, audit, stub_apply):
    item = SimpleNamespace(id="c1", target_id="tgt-1", updated_at=NOW)

    async def fake_get(session, tenant_id, conference_id):
        return item

    monkeypatch.setattr(cr, "_get_conf_or_404", fake_get)
    with pytest.raises(ApiError) as exc:
        await cr.update_conference("c1", UpdateConferencePayload(updated_at=datetime(2020, 1, 1, tzinfo=timezone.utc)),
                                   _Session(), USER, ami=None)
    assert exc.value.status_code == 409 and exc.value.code == "stale"


# ------------------------------------------------------------------- delete
async def test_delete_in_use_is_409_with_usages(monkeypatch):
    item = SimpleNamespace(id="c1", target_id="tgt-1", name="Yig'ilish")

    async def fake_get(session, tenant_id, conference_id):
        return item

    async def usages(session, tenant_id, target_id):
        return [{"kind": "ivr_option", "id": "i1", "label": "IVR", "field": "digit:1"}]

    monkeypatch.setattr(cr, "_get_conf_or_404", fake_get)
    monkeypatch.setattr(cr, "usages_for_target", usages)
    with pytest.raises(ApiError) as exc:
        await cr.delete_conference("c1", _Session(), USER, ami=None)
    assert exc.value.status_code == 409 and exc.value.code == "in_use"


async def test_delete_ok_removes_entity_and_applies(monkeypatch, audit, stub_apply):
    item = SimpleNamespace(id="c1", target_id="tgt-1", name="Yig'ilish")

    async def fake_get(session, tenant_id, conference_id):
        return item

    monkeypatch.setattr(cr, "_get_conf_or_404", fake_get)
    monkeypatch.setattr(cr, "usages_for_target", _no_usages)
    s = _Session()
    await cr.delete_conference("c1", s, USER, ami=None)
    assert s.deleted == [item] and audit[0]["action"] == "conference.delete" and s.commits == 1
