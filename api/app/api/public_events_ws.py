"""M10 Bo'lak B3 — `WS /api/public/v1/events/ws`: tashqi integratsiyalar uchun
jonli hodisa oqimi (`api_keys.SCOPES` dagi `events:read`).

Avtorizatsiya: `Authorization: Bearer ipk_...` sarlavhasi YOKI (sarlavha
bo'lmasa) BIRINCHI xabar 5 soniya ichida `{"token": "ipk_..."}`. Muvaffaqiyatli
bo'lsa server `{"type":"ready","seq":<oxirgi ko'rilgan>}` yuboradi, keyin
mijoz `{"type":"subscribe","events":[...]|["*"],"since_seq":N,"include_internal":bool}`
orqali filtr/replay so'raydi (so'ramasa sukut — hammasi, replay yo'q,
`include_internal=false`: ichki hodisalar yetkazilmaydi — webhook outbox
bilan bir xil qoida, `app/services/events_ws.py::wants_ws_event`). Har
25 soniyada `{"type":"ping"}` (mijoz javob bermasa ham ulanish ochiq qoladi —
faqat tirik ekanini bildirish, pong talab qilinmaydi).

Yopish kodlari (`app/services/events_ws.py`): 4401 avtorizatsiya yo'q/yaroqsiz,
4403 `events:read` yo'q, 4429 ulanish chegarasi (5/kalit, 50/tenant)."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.api.public import authenticate, bearer_key
from app.core.config import settings
from app.core.errors import ApiError
from app.db.models import IntegrationEvent
from app.services.events_ws import (
    CLOSE_FORBIDDEN_SCOPE,
    CLOSE_TOO_MANY_CONNECTIONS,
    CLOSE_UNAUTHORIZED,
    clamp_since_seq,
    replay_cutoff,
    validate_subscribe,
    wants_ws_event,
)
from app.services.events_ws_registry import Connection, registry

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public/v1", tags=["public"])

_SCOPE = "events:read"
_FIRST_MESSAGE_TIMEOUT_S = 5.0


async def _authenticate_ws(websocket: WebSocket, session: AsyncSession):
    """`None` qaytaradi — chaqiruvchi ulanishni allaqachon yopgan (yopish kodi
    shu yerda tanlanadi); aks holda `public.KeyContext`."""
    token = bearer_key(websocket)
    if token is None:
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=_FIRST_MESSAGE_TIMEOUT_S)
            token = json.loads(raw).get("token")
        except (TimeoutError, asyncio.TimeoutError, ValueError, json.JSONDecodeError, WebSocketDisconnect):
            token = None
    try:
        return await authenticate(session, token, _SCOPE)
    except ApiError as exc:
        # 429 (`api_key_rate_limit_per_min`) — ulanish chegarasi bilan bir xil
        # yopish kodini ishlatamiz (ataylab soddalashtirish, hisobotda bayon
        # qilinadi): shartnomadagi 4429 asosan `ConnectionLimiter` uchun.
        code = {403: CLOSE_FORBIDDEN_SCOPE, 429: CLOSE_TOO_MANY_CONNECTIONS}.get(
            exc.status_code, CLOSE_UNAUTHORIZED
        )
        await websocket.close(code=code)
        return None


async def _latest_seq(session: AsyncSession) -> int:
    row = (await session.execute(select(IntegrationEvent.seq).order_by(IntegrationEvent.seq.desc()).limit(1))
          ).scalar_one_or_none()
    return row or 0


async def _replay(session: AsyncSession, websocket: WebSocket, tenant_id: str, *, since_seq: int,
                  subscribed: tuple[str, ...], latest_seq: int, include_internal: bool = False) -> None:
    clamped = clamp_since_seq(since_seq, latest_seq)
    if clamped is None:
        return
    cutoff = replay_cutoff(datetime.now(timezone.utc))
    stmt = (select(IntegrationEvent)
            .where(IntegrationEvent.tenant_id == tenant_id, IntegrationEvent.seq > clamped,
                  IntegrationEvent.occurred_at >= cutoff)
            .order_by(IntegrationEvent.seq))
    rows = (await session.execute(stmt)).scalars().all()
    for row in rows:
        if wants_ws_event(subscribed, include_internal, row.type, internal=row.internal):
            await websocket.send_json({"type": "event", "seq": row.seq, "event": row.type, "data": row.payload})


async def _handle_subscribe(session: AsyncSession, websocket: WebSocket, conn: Connection, raw: str,
                            latest_seq: int) -> None:
    try:
        data = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        return
    if data.get("type") != "subscribe":
        return
    subscribed = validate_subscribe(data.get("events"))
    if subscribed is None:
        await websocket.send_json({"type": "error", "error": "invalid_subscribe"})
        return
    include_internal = bool(data.get("include_internal", False))
    registry.update_subscription(conn.conn_id, subscribed, include_internal=include_internal)
    since_seq = data.get("since_seq")
    if isinstance(since_seq, int):
        await _replay(session, websocket, conn.tenant_id, since_seq=since_seq, subscribed=subscribed,
                      latest_seq=latest_seq, include_internal=include_internal)


@router.websocket("/events/ws")
async def events_ws(websocket: WebSocket, session: AsyncSession = Depends(get_session)) -> None:
    await websocket.accept()
    key = await _authenticate_ws(websocket, session)
    if key is None:
        return

    if not registry.can_connect(key.key_id, key.tenant_id):
        await websocket.close(code=CLOSE_TOO_MANY_CONNECTIONS)
        return

    conn = Connection(conn_id=str(uuid.uuid4()), key_id=key.key_id, tenant_id=key.tenant_id, websocket=websocket)
    registry.add(conn)
    try:
        latest_seq = await _latest_seq(session)
        await websocket.send_json({"type": "ready", "seq": latest_seq})
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(),
                                             timeout=settings.events_ws_ping_interval_s)
            except (TimeoutError, asyncio.TimeoutError):
                await websocket.send_json({"type": "ping"})
                continue
            await _handle_subscribe(session, websocket, conn, raw, latest_seq)
    except WebSocketDisconnect:
        pass
    finally:
        registry.remove(conn.conn_id)
