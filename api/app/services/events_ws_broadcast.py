"""M10 Bo'lak B3 — `integration_events`ni so'rovchi fon tarqatuvchi: yangi
qatorlarni (`seq` > oxirgi ko'rilgan) ulangan WS mijozlariga yuboradi.

`vm_notify_enabled`/`call_events_enabled` BILAN BIR XIL `run_forever(session_factory,
interval_s)` qolipi (`app/main.py` lifespan shu funksiyani `asyncio.create_task`
qiladi)."""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.db.models import IntegrationEvent
from app.services.events_ws_registry import registry

log = logging.getLogger(__name__)


async def _latest_seq(session_factory) -> int:
    async with session_factory() as session:
        result = (await session.execute(select(IntegrationEvent.seq).order_by(IntegrationEvent.seq.desc()).limit(1))
                  ).scalar_one_or_none()
        return result or 0


async def _poll_once(session_factory, last_seq: int) -> int:
    async with session_factory() as session:
        rows = (await session.execute(
            select(IntegrationEvent).where(IntegrationEvent.seq > last_seq).order_by(IntegrationEvent.seq)
        )).scalars().all()
        for row in rows:
            message = {"type": "event", "seq": row.seq, "event": row.type, "data": row.payload}
            await registry.broadcast(str(row.tenant_id), row.type, message, internal=row.internal)
            last_seq = row.seq
        return last_seq


async def run_forever(session_factory, interval_s: float) -> None:
    last_seq = await _latest_seq(session_factory)
    while True:
        try:
            last_seq = await _poll_once(session_factory, last_seq)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — fon vazifa hech qachon o'lmasin
            log.exception("events_ws tarqatish davri muvaffaqiyatsiz")
        await asyncio.sleep(interval_s)
