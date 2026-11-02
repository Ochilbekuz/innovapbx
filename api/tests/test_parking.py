"""M2a §3: park lot fayli (idempotent) va `GET /parking` javobi (AMI `ParkedCalls`)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services import parking


class _FakeAmi:
    def __init__(self, *, reload_ok=True, show_output="t1-park  700  701-720", events=None):
        self.calls: list[tuple[str, dict]] = []
        self.reload_ok = reload_ok
        self.show_output = show_output
        self.events = events or []
        self.connected = 0

    async def ensure_connected(self) -> None:
        self.connected += 1

    async def action(self, action: str, **fields):
        self.calls.append((action, fields))
        if fields.get("Command", "").startswith("module reload"):
            return {"Response": "Success" if self.reload_ok else "Error", "Message": "boom"}
        return {"Response": "Success", "Output": self.show_output}

    async def action_list(self, action: str, **fields):
        self.calls.append((action, fields))
        return self.events


@pytest.fixture
def park_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(parking.settings, "dialplan_dir", str(tmp_path))
    monkeypatch.setattr(parking.settings, "parking_filename", "res_parking_innova.conf")
    return tmp_path


@pytest.mark.asyncio
async def test_ensure_parking_lot_writes_and_reloads_once(park_dir):
    ami = _FakeAmi()
    assert await parking.ensure_parking_lot(ami, "t1") is True
    text = (park_dir / "res_parking_innova.conf").read_text()
    assert "[t1-park]" in text
    assert ("Command", {"Command": "module reload res_parking.so"}) in ami.calls
    assert ("Command", {"Command": "parking show"}) in ami.calls
    ami2 = _FakeAmi()
    assert await parking.ensure_parking_lot(ami2, "t1") is False
    assert ami2.calls == [] and ami2.connected == 0


@pytest.mark.asyncio
async def test_ensure_parking_lot_rejected_reload_raises(park_dir):
    with pytest.raises(RuntimeError, match="res_parking reload rad etildi: boom"):
        await parking.ensure_parking_lot(_FakeAmi(reload_ok=False), "t1")


@pytest.mark.asyncio
async def test_ensure_parking_lot_missing_lot_raises(park_dir):
    with pytest.raises(RuntimeError, match="park lot"):
        await parking.ensure_parking_lot(_FakeAmi(show_output="Parking Lot: default"), "t1")


@pytest.mark.asyncio
async def test_parking_status_maps_parked_call_events():
    now = datetime(2026, 10, 28, 12, 0, 30, tzinfo=timezone.utc)
    ami = _FakeAmi(events=[
        {"Event": "ParkedCall", "ParkingSpace": "702", "ParkeeCallerIDNum": "998901112233",
         "ParkerDialString": "PJSIP/t1-201", "ParkingDuration": "30"},
        {"Event": "ParkedCall", "ParkingSpace": "701", "ParkeeCallerIDNum": "202",
         "ParkerDialString": "PJSIP/t1-203", "ParkingDuration": "0"},
        {"Event": "Other"},
    ])
    out = await parking.parking_status(ami, "t1", now=now)
    assert out["lot"] == "700" and out["slots"] == "701-720" and out["timeout_s"] == 60
    assert out["parked"] == [
        {"slot": "701", "callerid": "202", "parked_by": "203", "since": "2026-10-28T12:00:30+00:00"},
        {"slot": "702", "callerid": "998901112233", "parked_by": "201", "since": "2026-10-28T12:00:00+00:00"},
    ]
    assert ami.calls == [("ParkedCalls", {"ParkingLot": "t1-park"})]
    assert ami.connected == 1


@pytest.mark.asyncio
async def test_parking_status_empty_and_odd_dial_string():
    ami = _FakeAmi(events=[{"Event": "ParkedCall", "ParkingSpace": "701", "ParkerDialString": "Local"}])
    out = await parking.parking_status(ami, "t1")
    assert out["parked"][0]["parked_by"] == "Local"
    assert out["parked"][0]["callerid"] == ""
