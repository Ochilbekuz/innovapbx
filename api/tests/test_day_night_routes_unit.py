"""`/day-night` marshrut funksiyalari — DB/AMI'siz (soxta sessiya, tashqi
qadamlar monkeypatch), `test_conference_routes_unit.py` namunasi bo'yicha.
Asosiy talab: PIN hech qachon javobda ochiq saqlanmaydi (hash bazaga
yoziladi, `has_pin` faqat bool), exten kod boshqa funksiya kodi bilan
to'qnashmasligi tekshiriladi, BLF cheklovi hujjatlashtirilgan."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import day_night as dn
from app.core.config import settings
from app.core.errors import ApiError
from app.schemas import CreateDayNightPayload, RouteTarget, UpdateDayNightPayload

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

    monkeypatch.setattr(dn, "record_audit", fake_audit)
    return rows


@pytest.fixture
def stub_apply(monkeypatch):
    applied: list = []

    async def fake_apply(session, tenant_id, user_id, ami):
        applied.append(tenant_id)
        return SimpleNamespace(to_dict=lambda: {"status": "applied", "revision": 1, "message": None})

    async def fake_resolve_target(session, tenant_id, target_id):
        return RouteTarget(id=target_id, kind="extension", label="X", number="100", broken=False)

    monkeypatch.setattr(dn, "apply_config", fake_apply)
    monkeypatch.setattr(dn, "resolve_target", fake_resolve_target)
    return applied


async def _no_usages(session, tenant_id, target_id):
    return []


def _item(**over):
    base = dict(id="dn1", target_id="tgt-1", name="Asosiy", code="0", mode="day", pin_hmac=None,
                day_target_id="tgt-day", night_target_id="tgt-night", updated_at=NOW)
    base.update(over)
    return SimpleNamespace(**base)


# ------------------------------------------------------------------- create
async def test_create_hashes_pin_and_masks_it_in_audit(monkeypatch, audit, stub_apply):
    async def no_create_target(session, tenant_id, kind, label):
        return SimpleNamespace(id=uuid.uuid4())

    async def ok_exten(session, tenant_id, code):
        return None

    async def _get_dn(session, tenant_id, row_id):
        return _item()

    monkeypatch.setattr(dn, "create_target", no_create_target)
    monkeypatch.setattr(dn, "_validate_exten_code", ok_exten)
    monkeypatch.setattr(dn, "_get_or_404", _get_dn)
    s = _Session()
    payload = CreateDayNightPayload(name="Asosiy", code="0", day_target_id="tgt-day",
                                     night_target_id="tgt-night", pin="1234")
    out = await dn.create_day_night(payload, s, USER, ami=None)

    item = s.added[0]
    assert item.pin_hmac and item.pin_hmac != "1234"
    assert audit[0]["diff"] == {"name": "Asosiy", "code": "0"}
    assert not hasattr(out.item, "pin") and not hasattr(out.item, "pin_hmac")
    assert stub_apply == ["t1"] and s.commits == 1


async def test_create_rejects_invalid_target(monkeypatch, audit, stub_apply):
    async def bad_resolve(session, tenant_id, target_id):
        return None

    monkeypatch.setattr(dn, "resolve_target", bad_resolve)
    payload = CreateDayNightPayload(name="X", code="0", day_target_id="bad", night_target_id="tgt-night")
    with pytest.raises(ApiError) as exc:
        await dn.create_day_night(payload, _Session(), USER, ami=None)
    assert exc.value.code == "invalid_target"


async def test_create_rejects_clashing_exten_code(monkeypatch, stub_apply):
    async def clashing(session, tenant_id, code):
        raise ApiError(409, "code_taken", "Kod band")

    monkeypatch.setattr(dn, "_validate_exten_code", clashing)
    payload = CreateDayNightPayload(name="X", code="9", day_target_id="tgt-day", night_target_id="tgt-night")
    with pytest.raises(ApiError) as exc:
        await dn.create_day_night(payload, _Session(), USER, ami=None)
    assert exc.value.code == "code_taken"


# ------------------------------------------------------------------- update
async def test_update_sets_and_clears_pin(monkeypatch, audit, stub_apply):
    item = _item(pin_hmac="OLD")

    async def _get_dn(session, tenant_id, row_id):
        return item

    monkeypatch.setattr(dn, "_get_or_404", _get_dn)
    payload = UpdateDayNightPayload(pin="4321", updated_at=NOW)
    await dn.update_day_night("dn1", payload, _Session(), USER, ami=None)
    assert item.pin_hmac != "OLD" and item.pin_hmac != "4321"
    assert audit[0]["diff"] == {"pin": "***"}  # PIN audit diff'da hech qachon ochiq saqlanmaydi


async def test_update_pin_clear_removes_hash(monkeypatch, audit, stub_apply):
    item = _item(pin_hmac="OLD")

    async def _get_dn(session, tenant_id, row_id):
        return item

    monkeypatch.setattr(dn, "_get_or_404", _get_dn)
    payload = UpdateDayNightPayload(pin_clear=True, updated_at=NOW)
    await dn.update_day_night("dn1", payload, _Session(), USER, ami=None)
    assert item.pin_hmac is None
    assert audit[0]["diff"] == {"pin": "***"}


async def test_update_renames_and_changes_code_and_targets(monkeypatch, audit, stub_apply):
    item = _item()
    renamed: list = []
    validated_codes: list = []
    validated_targets: list = []

    async def _get_dn(session, tenant_id, row_id):
        return item

    async def fake_rename(session, target_id, name):
        renamed.append((target_id, name))

    async def ok_exten(session, tenant_id, code):
        validated_codes.append(code)

    async def ok_target(session, tenant_id, target_id, field):
        validated_targets.append((target_id, field))

    monkeypatch.setattr(dn, "_get_or_404", _get_dn)
    monkeypatch.setattr(dn, "rename_target", fake_rename)
    monkeypatch.setattr(dn, "_validate_exten_code", ok_exten)
    monkeypatch.setattr(dn, "_validate_target", ok_target)
    payload = UpdateDayNightPayload(
        name="Yangi nom", code="5", day_target_id="tgt-day2", night_target_id="tgt-night2", updated_at=NOW,
    )
    await dn.update_day_night("dn1", payload, _Session(), USER, ami=None)

    assert item.name == "Yangi nom" and renamed == [("tgt-1", "Yangi nom")]
    assert item.code == "5" and validated_codes == ["5"]
    assert (item.day_target_id, item.night_target_id) == ("tgt-day2", "tgt-night2")
    assert validated_targets == [("tgt-day2", "day_target_id"), ("tgt-night2", "night_target_id")]
    assert audit[0]["diff"] == {
        "name": "Yangi nom", "code": "5", "day_target_id": "tgt-day2", "night_target_id": "tgt-night2",
    }


async def test_update_same_code_skips_revalidation(monkeypatch, audit, stub_apply):
    item = _item(code="0")
    calls: list = []

    async def _get_dn(session, tenant_id, row_id):
        return item

    async def tracked_exten(session, tenant_id, code):
        calls.append(code)

    monkeypatch.setattr(dn, "_get_or_404", _get_dn)
    monkeypatch.setattr(dn, "_validate_exten_code", tracked_exten)
    payload = UpdateDayNightPayload(code="0", updated_at=NOW)
    await dn.update_day_night("dn1", payload, _Session(), USER, ami=None)
    assert calls == [] and audit[0]["diff"] == {}


async def test_update_stale_is_409(monkeypatch):
    item = _item()

    async def _get_dn(session, tenant_id, row_id):
        return item

    monkeypatch.setattr(dn, "_get_or_404", _get_dn)
    with pytest.raises(ApiError) as exc:
        await dn.update_day_night(
            "dn1", UpdateDayNightPayload(updated_at=datetime(2020, 1, 1, tzinfo=timezone.utc)),
            _Session(), USER, ami=None,
        )
    assert exc.value.status_code == 409 and exc.value.code == "stale"


# ------------------------------------------------------------------- toggle
async def test_toggle_flips_mode_day_to_night_and_back(monkeypatch, audit, stub_apply):
    item = _item(mode="day")

    async def _get_dn(session, tenant_id, row_id):
        return item

    monkeypatch.setattr(dn, "_get_or_404", _get_dn)
    await dn.toggle_day_night("dn1", _Session(), USER, ami=None)
    assert item.mode == "night"
    assert audit[0]["diff"] == {"mode": "night"}

    audit.clear()
    await dn.toggle_day_night("dn1", _Session(), USER, ami=None)
    assert item.mode == "day"
    assert audit[0]["diff"] == {"mode": "day"}


# ------------------------------------------------------------------- delete
async def test_delete_in_use_is_409_with_usages(monkeypatch):
    item = _item()

    async def _get_dn(session, tenant_id, row_id):
        return item

    monkeypatch.setattr(dn, "_get_or_404", _get_dn)

    async def usages(session, tenant_id, target_id):
        return [{"kind": "ivr_option", "id": "i1", "label": "IVR", "field": "digit:1"}]

    monkeypatch.setattr(dn, "usages_for_target", usages)
    with pytest.raises(ApiError) as exc:
        await dn.delete_day_night("dn1", _Session(), USER, ami=None)
    assert exc.value.status_code == 409 and exc.value.code == "in_use"


async def test_delete_ok_removes_entity_and_applies(monkeypatch, audit, stub_apply):
    item = _item()

    async def _get_dn(session, tenant_id, row_id):
        return item

    monkeypatch.setattr(dn, "_get_or_404", _get_dn)
    monkeypatch.setattr(dn, "usages_for_target", _no_usages)
    s = _Session()
    await dn.delete_day_night("dn1", s, USER, ami=None)
    assert audit[0]["action"] == "day_night.delete" and s.commits == 1
