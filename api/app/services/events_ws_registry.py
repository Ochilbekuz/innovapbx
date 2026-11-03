"""M10 Bo'lak B3 — tashqi WS hodisalar: JONLI ulanishlar registri (bitta
jarayon ichida xotirada, Dockerfile bitta Uvicorn worker ekanligi tasdiqlangan
— ko'p worker bo'lsa bu yondashuv ishlamaydi).

Sof qoidalar (`event_matches`/`ConnectionLimiter`/...) `app/services/events_ws.py`da,
unit testlangan. Bu modul FAQAT jarayon holatini (ulanishlar) ushlab turadi —
`app/api/public_events_ws.py` (endpoint) va `app/services/events_ws_broadcast.py`
(fon tarqatuvchi) ishlatadi."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.services.events_ws import ConnectionLimiter, wants_ws_event


class _Sendable(Protocol):
    async def send_json(self, data: dict) -> None: ...


@dataclass
class Connection:
    conn_id: str
    key_id: str
    tenant_id: str
    websocket: _Sendable
    subscribed: tuple[str, ...] = ("*",)
    include_internal: bool = False


@dataclass
class EventsWsRegistry:
    limiter: ConnectionLimiter = field(default_factory=ConnectionLimiter)
    _connections: dict[str, Connection] = field(default_factory=dict)

    def can_connect(self, key_id: str, tenant_id: str) -> bool:
        return self.limiter.can_connect(key_id=key_id, tenant_id=tenant_id)

    def add(self, conn: Connection) -> None:
        self.limiter.register(key_id=conn.key_id, tenant_id=conn.tenant_id)
        self._connections[conn.conn_id] = conn

    def remove(self, conn_id: str) -> None:
        conn = self._connections.pop(conn_id, None)
        if conn is not None:
            self.limiter.release(key_id=conn.key_id, tenant_id=conn.tenant_id)

    def update_subscription(self, conn_id: str, subscribed: tuple[str, ...], *,
                            include_internal: bool = False) -> None:
        conn = self._connections.get(conn_id)
        if conn is not None:
            conn.subscribed = subscribed
            conn.include_internal = include_internal

    def for_tenant(self, tenant_id: str) -> list[Connection]:
        return [c for c in self._connections.values() if c.tenant_id == tenant_id]

    async def broadcast(self, tenant_id: str, event_type: str, message: dict, *, internal: bool = False) -> None:
        for conn in self.for_tenant(tenant_id):
            if wants_ws_event(conn.subscribed, conn.include_internal, event_type, internal=internal):
                await conn.websocket.send_json(message)


registry = EventsWsRegistry()
