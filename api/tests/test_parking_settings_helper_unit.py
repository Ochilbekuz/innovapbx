"""M9 A3 — `app/services/parking_settings.py::get_parking_settings` (DRY
yordamchi: compiler/snapshot.py VA so'rov vaqtidagi tekshiruvlar bir xil
funksiyadan foydalanadi) va `feature_codes.py::prefix_clash`, DB'siz."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.feature_codes import prefix_clash
from app.services.parking_settings import get_parking_settings


class _GetSession:
    def __init__(self, rows: dict):
        self._rows = rows

    async def get(self, model, key):
        return self._rows.get((model.__name__, key))


async def test_get_parking_settings_returns_defaults_when_row_missing():
    s = _GetSession({})
    settings = await get_parking_settings(s, "t1")
    assert (settings.lot_number, settings.first_slot, settings.slot_count) == ("700", 701, 20)


async def test_get_parking_settings_maps_row_fields_without_moh():
    row = SimpleNamespace(lot_number="800", first_slot=801, slot_count=5, timeout_s=90,
                          on_timeout="target", timeout_target_id="tgt-1", moh_class_id=None)
    s = _GetSession({("ParkingSettings", "t1"): row})
    settings = await get_parking_settings(s, "t1")
    assert settings.lot_number == "800" and settings.timeout_target_id == "tgt-1"
    assert settings.moh_class_name is None


async def test_get_parking_settings_resolves_moh_class_name():
    row = SimpleNamespace(lot_number="700", first_slot=701, slot_count=20, timeout_s=60,
                          on_timeout="origin", timeout_target_id=None, moh_class_id="moh-1")
    moh = SimpleNamespace(name="jazz")
    s = _GetSession({("ParkingSettings", "t1"): row, ("MohClass", "moh-1"): moh})
    settings = await get_parking_settings(s, "t1")
    assert settings.moh_class_name == "jazz"


async def test_get_parking_settings_moh_class_deleted_falls_back_to_none():
    row = SimpleNamespace(lot_number="700", first_slot=701, slot_count=20, timeout_s=60,
                          on_timeout="origin", timeout_target_id=None, moh_class_id="gone")
    s = _GetSession({("ParkingSettings", "t1"): row})
    settings = await get_parking_settings(s, "t1")
    assert settings.moh_class_name is None


def test_prefix_clash_true_when_either_is_a_prefix_of_the_other():
    assert prefix_clash("*4", "*45") is True
    assert prefix_clash("*45", "*4") is True


def test_prefix_clash_false_for_unrelated_codes():
    assert prefix_clash("*56", "*57") is False
