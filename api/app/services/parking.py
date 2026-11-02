"""M2a §3: park joyi — lot fayli (`res_parking.conf` #include) va park qilinganlar ro'yxati.

Lot parametrlari doimiy (`dialplan_features.PARK_*`) — fayl faqat tenant kodiga
bog'liq. `apply_config` har safar `ensure_parking_lot` ni chaqiradi: fayl
o'zgarmagan bo'lsa AMI'ga murojaat yo'q (idempotent)."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Protocol

from app.core.config import settings
from app.services.atomic_write import atomic_write
from app.services.dialplan_features import (
    PARK_FIRST_SLOT,
    PARK_LAST_SLOT,
    PARK_LOT_NUMBER,
    PARK_TIMEOUT_S,
    park_lot_name,
    parking_conf_text,
)


class ParkingAmi(Protocol):
    async def ensure_connected(self) -> None: ...
    async def action(self, action: str, **fields: object) -> dict: ...
    async def action_list(self, action: str, **fields: object) -> list[dict]: ...


def _conf_path() -> str:
    return os.path.join(settings.dialplan_dir, settings.parking_filename)


def _current_text() -> str | None:
    try:
        with open(_conf_path(), encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


async def ensure_parking_lot(ami: ParkingAmi, tenant_code: str) -> bool:
    """Lot fayli yangilanadi va `res_parking` qayta yuklanadi (faqat o'zgargan bo'lsa).
    Qaytaradi: yozildimi. Lot ko'rinmasa — RuntimeError (apply rollback qiladi)."""
    text = parking_conf_text(tenant_code)
    if _current_text() == text:
        return False
    atomic_write(settings.dialplan_dir, settings.parking_filename, text, tmp_prefix=".tmp-park-")
    await ami.ensure_connected()
    reload_resp = await ami.action("Command", Command="module reload res_parking.so")
    if str(reload_resp.get("Response", "")).lower() != "success":
        raise RuntimeError(f"res_parking reload rad etildi: {reload_resp.get('Message', '')}")
    show = await ami.action("Command", Command="parking show")
    if park_lot_name(tenant_code) not in (show.get("Output", "") or ""):
        raise RuntimeError("tekshiruv muvaffaqiyatsiz: park lot ko'rinmadi")
    return True


def _parker_number(dial_string: str) -> str:
    """`PJSIP/t1-201` -> `201` (tenant kodida `-` yo'q)."""
    tail = dial_string.split("/", 1)[-1]
    return tail.split("-", 1)[1] if "-" in tail else tail


def _parked_item(event: dict, now: datetime) -> dict:
    duration = int(event.get("ParkingDuration", "0") or 0)
    return {
        "slot": event.get("ParkingSpace", ""),
        "callerid": event.get("ParkeeCallerIDNum", "") or "",
        "parked_by": _parker_number(event.get("ParkerDialString", "") or ""),
        "since": (now - timedelta(seconds=duration)).isoformat(),
    }


async def parking_status(ami: ParkingAmi, tenant_code: str, *, now: datetime | None = None) -> dict:
    await ami.ensure_connected()
    events = await ami.action_list("ParkedCalls", ParkingLot=park_lot_name(tenant_code))
    moment = now or datetime.now(timezone.utc)
    parked = [_parked_item(e, moment) for e in events if e.get("Event") == "ParkedCall"]
    parked.sort(key=lambda p: p["slot"])
    return {
        "lot": PARK_LOT_NUMBER,
        "slots": f"{PARK_FIRST_SLOT}-{PARK_LAST_SLOT}",
        "timeout_s": PARK_TIMEOUT_S,
        "parked": parked,
    }
