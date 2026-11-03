"""`WS /api/public/v1/events/ws` — autentifikatsiya/yopish kodi tanlovi,
obuna va replay. DB'siz: `authenticate()`/DB so'rovlari soxtalashtiriladi
(sof mantiq — "aniq fayl" talabi: `app/api/public_events_ws.py`)."""
from __future__ import annotations

import asyncio

import pytest

from app.api import public_events_ws as mod
from app.core.errors import ApiError
from app.services.events_ws_registry import Connection, EventsWsRegistry


class _FakeWebSocket:
    def __init__(self, headers: dict | None = None, messages: list[str] | None = None) -> None:
        self.headers = headers or {}
        self._messages = list(messages or [])
        self.sent: list[dict] = []
        self.closed_code: int | None = None

    async def receive_text(self) -> str:
        if not self._messages:
            from fastapi import WebSocketDisconnect
            raise WebSocketDisconnect()
        return self._messages.pop(0)

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)

    async def close(self, code: int = 1000) -> None:
        self.closed_code = code


class _FakeKey:
    key_id = "k1"
    tenant_id = "t1"


def _ok_authenticate(expected_token: str = "ipk_abc"):
    async def _fake(session, token, scope):
        assert token == expected_token
        assert scope == "events:read"
        return _FakeKey()
    return _fake


def _failing_authenticate(status_code: int):
    async def _fake(session, token, scope):
        raise ApiError(status_code, "x", "x")
    return _fake


@pytest.mark.asyncio
async def test_auth_via_header(monkeypatch):
    monkeypatch.setattr(mod, "authenticate", _ok_authenticate())
    ws = _FakeWebSocket(headers={"authorization": "Bearer ipk_abc"})
    key = await mod._authenticate_ws(ws, session=object())
    assert key.key_id == "k1"
    assert ws.closed_code is None


@pytest.mark.asyncio
async def test_auth_via_first_message(monkeypatch):
    monkeypatch.setattr(mod, "authenticate", _ok_authenticate())
    ws = _FakeWebSocket(messages=['{"token": "ipk_abc"}'])
    key = await mod._authenticate_ws(ws, session=object())
    assert key.key_id == "k1"


@pytest.mark.asyncio
async def test_auth_no_token_closes_4401(monkeypatch):
    monkeypatch.setattr(mod, "authenticate", _failing_authenticate(401))
    ws = _FakeWebSocket()
    key = await mod._authenticate_ws(ws, session=object())
    assert key is None
    assert ws.closed_code == mod.CLOSE_UNAUTHORIZED


@pytest.mark.asyncio
async def test_auth_missing_scope_closes_4403(monkeypatch):
    monkeypatch.setattr(mod, "authenticate", _failing_authenticate(403))
    ws = _FakeWebSocket(headers={"authorization": "Bearer ipk_abc"})
    key = await mod._authenticate_ws(ws, session=object())
    assert key is None
    assert ws.closed_code == mod.CLOSE_FORBIDDEN_SCOPE


@pytest.mark.asyncio
async def test_auth_rate_limited_closes_4429(monkeypatch):
    monkeypatch.setattr(mod, "authenticate", _failing_authenticate(429))
    ws = _FakeWebSocket(headers={"authorization": "Bearer ipk_abc"})
    key = await mod._authenticate_ws(ws, session=object())
    assert key is None
    assert ws.closed_code == mod.CLOSE_TOO_MANY_CONNECTIONS


@pytest.mark.asyncio
async def test_handle_subscribe_updates_registry(monkeypatch):
    reg = EventsWsRegistry()
    ws = _FakeWebSocket()
    conn = Connection(conn_id="c1", key_id="k1", tenant_id="t1", websocket=ws)
    reg.add(conn)
    monkeypatch.setattr(mod, "registry", reg)
    await mod._handle_subscribe(session=object(), websocket=ws, conn=conn,
                                raw='{"type": "subscribe", "events": ["call.ended"]}', latest_seq=0)
    assert conn.subscribed == ("call.ended",)


@pytest.mark.asyncio
async def test_handle_subscribe_ignores_invalid_json():
    ws = _FakeWebSocket()
    conn = Connection(conn_id="c1", key_id="k1", tenant_id="t1", websocket=ws)
    await mod._handle_subscribe(session=object(), websocket=ws, conn=conn, raw="not-json", latest_seq=0)
    assert ws.sent == []


@pytest.mark.asyncio
async def test_handle_subscribe_rejects_blank_event_name():
    ws = _FakeWebSocket()
    conn = Connection(conn_id="c1", key_id="k1", tenant_id="t1", websocket=ws)
    await mod._handle_subscribe(session=object(), websocket=ws, conn=conn,
                                raw='{"type": "subscribe", "events": [""]}', latest_seq=0)
    assert ws.sent == [{"type": "error", "error": "invalid_subscribe"}]


class _FakeRow:
    def __init__(self, seq: int, type_: str, payload: dict, *, internal: bool = False) -> None:
        self.seq = seq
        self.type = type_
        self.payload = payload
        self.internal = internal


class _FakeScalars:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def all(self) -> list:
        return self._rows


class _FakeResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class _FakeSession:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    async def execute(self, _stmt):
        return _FakeResult(self._rows)


@pytest.mark.asyncio
async def test_replay_sends_only_matching_subscribed_events():
    rows = [_FakeRow(1, "call.ended", {"foo": "bar"}), _FakeRow(2, "call.ringing", {"foo": "baz"})]
    session = _FakeSession(rows)
    ws = _FakeWebSocket()
    await mod._replay(session, ws, "t1", since_seq=0, subscribed=("call.ended",), latest_seq=2)
    assert ws.sent == [{"type": "event", "seq": 1, "event": "call.ended", "data": {"foo": "bar"}}]


@pytest.mark.asyncio
async def test_replay_wildcard_sends_all():
    rows = [_FakeRow(1, "call.ended", {}), _FakeRow(2, "call.ringing", {})]
    session = _FakeSession(rows)
    ws = _FakeWebSocket()
    await mod._replay(session, ws, "t1", since_seq=0, subscribed=("*",), latest_seq=2)
    assert [e["seq"] for e in ws.sent] == [1, 2]


@pytest.mark.asyncio
async def test_replay_withholds_internal_event_by_default():
    rows = [_FakeRow(1, "internal.diag", {}, internal=True)]
    session = _FakeSession(rows)
    ws = _FakeWebSocket()
    await mod._replay(session, ws, "t1", since_seq=0, subscribed=("*",), latest_seq=1)
    assert ws.sent == []


@pytest.mark.asyncio
async def test_replay_delivers_internal_event_when_opted_in():
    rows = [_FakeRow(1, "internal.diag", {}, internal=True)]
    session = _FakeSession(rows)
    ws = _FakeWebSocket()
    await mod._replay(session, ws, "t1", since_seq=0, subscribed=("*",), latest_seq=1, include_internal=True)
    assert ws.sent == [{"type": "event", "seq": 1, "event": "internal.diag", "data": {}}]


@pytest.mark.asyncio
async def test_handle_subscribe_passes_include_internal_through(monkeypatch):
    reg = EventsWsRegistry()
    ws = _FakeWebSocket()
    conn = Connection(conn_id="c1", key_id="k1", tenant_id="t1", websocket=ws)
    reg.add(conn)
    monkeypatch.setattr(mod, "registry", reg)
    await mod._handle_subscribe(session=object(), websocket=ws, conn=conn,
                                raw='{"type": "subscribe", "events": ["*"], "include_internal": true}',
                                latest_seq=0)
    assert conn.include_internal is True
