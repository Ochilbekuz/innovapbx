"""M9 A3 — `GET`/`PUT /parking/settings` marshrutlari (lot/slot, timeout,
MOH), DB/AMI'siz. `_get_row_or_404`/`_settings_out` to'g'ridan-to'g'ri
stublanadi (haqiqiy `session.get`/MOH/`resolve_target` yon-effektlarisiz)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import parking as pk
from app.core.errors import ApiError
from app.schemas import ParkingSettingsOut, UpdateParkingSettingsPayload

USER = SimpleNamespace(id="u1", tenant_id="t1")
NOW = datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)


class _Session:
    def __init__(self):
        self.commits = 0

    async def flush(self):
        pass

    async def commit(self):
        self.commits += 1

    async def execute(self, stmt):
        raise AssertionError("moh_class_id so'rovi sinovda stublanishi kerak edi")


def _new_row(**over) -> SimpleNamespace:
    base = dict(tenant_id="t1", lot_number="700", first_slot=701, slot_count=20, timeout_s=60,
                on_timeout="origin", timeout_target_id=None, moh_class_id=None, updated_at=NOW)
    base.update(over)
    return SimpleNamespace(**base)


def _fake_out(row: SimpleNamespace) -> ParkingSettingsOut:
    return ParkingSettingsOut(lot_number=row.lot_number, first_slot=row.first_slot, slot_count=row.slot_count,
                              timeout_s=row.timeout_s, on_timeout=row.on_timeout, timeout_target=None,
                              moh_class=None, updated_at=row.updated_at)


@pytest.fixture
def audit(monkeypatch):
    rows: list = []

    async def fake_audit(session, **kw):
        rows.append(kw)

    monkeypatch.setattr(pk, "record_audit", fake_audit)
    return rows


@pytest.fixture
def stub_apply(monkeypatch):
    applied: list = []

    async def fake_apply(session, *, tenant_id, user_id, ami):
        applied.append(tenant_id)
        return SimpleNamespace(to_dict=lambda: {"status": "applied", "revision": 1, "message": None})

    async def not_taken(session, tenant_id, number):
        return False

    async def fake_resolve(session, tenant_id, target_id):
        return None if target_id == "bad" else {"kind": "hangup", "id": target_id, "label": "X", "broken": False}

    monkeypatch.setattr(pk, "apply_config", fake_apply)
    monkeypatch.setattr(pk, "number_taken", not_taken)
    monkeypatch.setattr(pk, "resolve_target", fake_resolve)
    monkeypatch.setattr(pk, "_settings_out", _fake_settings_out)
    return applied


async def _fake_settings_out(session, tenant_id, row):
    return _fake_out(row)


class _GetSession:
    """`_settings_out`ning haqiqiy tanasi uchun — `session.get(MohClass, id)`."""

    def __init__(self, moh: SimpleNamespace | None = None):
        self._moh = moh

    async def get(self, model, key):
        return self._moh


# ------------------------------------------------------------------- _settings_out
async def test_settings_out_bare_row_has_no_target_or_moh(monkeypatch):
    row = _new_row()
    out = await pk._settings_out(_GetSession(), "t1", row)
    assert out.timeout_target is None and out.moh_class is None


async def test_settings_out_resolves_timeout_target(monkeypatch):
    row = _new_row(timeout_target_id="tgt-1")

    async def fake_resolve(session, tenant_id, target_id):
        return {"kind": "hangup", "id": target_id, "label": "X", "broken": False}

    monkeypatch.setattr(pk, "resolve_target", fake_resolve)
    out = await pk._settings_out(_GetSession(), "t1", row)
    assert out.timeout_target.id == "tgt-1"


async def test_settings_out_resolves_moh_class_when_present():
    row = _new_row(moh_class_id="moh-1")
    moh = SimpleNamespace(id="moh-1", name="jazz")
    out = await pk._settings_out(_GetSession(moh), "t1", row)
    assert out.moh_class.name == "jazz"


async def test_settings_out_moh_class_deleted_falls_back_to_none():
    row = _new_row(moh_class_id="gone")
    out = await pk._settings_out(_GetSession(None), "t1", row)
    assert out.moh_class is None


# ------------------------------------------------------------------- GET
async def test_get_parking_settings_returns_current_row(monkeypatch):
    row = _new_row()

    async def fake_get_row(session, tenant_id):
        return row

    monkeypatch.setattr(pk, "_get_row_or_404", fake_get_row)
    monkeypatch.setattr(pk, "_settings_out", _fake_settings_out)
    out = await pk.get_parking_settings_endpoint(_Session(), USER)
    assert out.lot_number == "700" and out.slot_count == 20


# ------------------------------------------------------------------- PUT: happy / validation
async def test_update_parking_settings_changes_lot_and_slots(monkeypatch, audit, stub_apply):
    row = _new_row()

    async def fake_get_row(session, tenant_id):
        return row

    monkeypatch.setattr(pk, "_get_row_or_404", fake_get_row)
    payload = UpdateParkingSettingsPayload(lot_number="800", first_slot=801, slot_count=5, updated_at=NOW)
    out = await pk.update_parking_settings(payload, _Session(), USER, ami=None)
    assert row.lot_number == "800" and row.first_slot == 801 and row.slot_count == 5
    assert audit[0]["diff"] == {"lot_number": "800", "first_slot": 801, "slot_count": 5}
    assert stub_apply == ["t1"] and out.item.lot_number == "800"


async def test_update_parking_settings_number_taken_is_409(monkeypatch, audit):
    row = _new_row()

    async def fake_get_row(session, tenant_id):
        return row

    async def taken(session, tenant_id, number):
        return number == "801"

    monkeypatch.setattr(pk, "_get_row_or_404", fake_get_row)
    monkeypatch.setattr(pk, "number_taken", taken)
    payload = UpdateParkingSettingsPayload(first_slot=801, slot_count=2, updated_at=NOW)
    with pytest.raises(ApiError) as e:
        await pk.update_parking_settings(payload, _Session(), USER, ami=None)
    assert (e.value.status_code, e.value.code, e.value.field) == (409, "number_taken", "first_slot")


async def test_update_parking_settings_target_timeout_without_target_id_is_422(monkeypatch):
    row = _new_row()

    async def fake_get_row(session, tenant_id):
        return row

    monkeypatch.setattr(pk, "_get_row_or_404", fake_get_row)
    payload = UpdateParkingSettingsPayload(on_timeout="target", updated_at=NOW)
    with pytest.raises(ApiError) as e:
        await pk.update_parking_settings(payload, _Session(), USER, ami=None)
    assert (e.value.status_code, e.value.code, e.value.field) == (422, "invalid_target", "timeout_target_id")


async def test_update_parking_settings_invalid_timeout_target_is_422(monkeypatch, audit, stub_apply):
    row = _new_row()

    async def fake_get_row(session, tenant_id):
        return row

    monkeypatch.setattr(pk, "_get_row_or_404", fake_get_row)
    payload = UpdateParkingSettingsPayload(on_timeout="target", timeout_target_id="bad", updated_at=NOW)
    with pytest.raises(ApiError) as e:
        await pk.update_parking_settings(payload, _Session(), USER, ami=None)
    assert (e.value.status_code, e.value.code, e.value.field) == (422, "invalid_target", "timeout_target_id")


async def test_update_parking_settings_invalid_moh_class_is_422(monkeypatch, audit, stub_apply):
    row = _new_row()

    async def fake_get_row(session, tenant_id):
        return row

    class _MohMissSession(_Session):
        async def execute(self, stmt):
            return SimpleNamespace(scalar_one_or_none=lambda: None)

    monkeypatch.setattr(pk, "_get_row_or_404", fake_get_row)
    payload = UpdateParkingSettingsPayload(moh_class_id="bad-moh", updated_at=NOW)
    with pytest.raises(ApiError) as e:
        await pk.update_parking_settings(payload, _MohMissSession(), USER, ami=None)
    assert (e.value.status_code, e.value.code, e.value.field) == (422, "invalid_moh_class", "moh_class_id")


async def test_update_parking_settings_stale_is_409(monkeypatch):
    row = _new_row()

    async def fake_get_row(session, tenant_id):
        return row

    monkeypatch.setattr(pk, "_get_row_or_404", fake_get_row)
    old = datetime(2020, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ApiError) as e:
        await pk.update_parking_settings(UpdateParkingSettingsPayload(updated_at=old), _Session(), USER, ami=None)
    assert (e.value.status_code, e.value.code) == (409, "stale")
