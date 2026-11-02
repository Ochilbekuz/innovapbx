"""`app/netd/server.py` — unix-soket server: `serve()` soket yaratadi va
har bir ulanishni `_handle()` orqali bitta qator so'rov/javob sifatida
qayta ishlaydi (m8-network-contract.md bo'lim 1). Haqiqiy
`asyncio.start_unix_server` ishlatiladi (tmp_path soketi), lekin host
tarmog'iga yoki haqiqiy `NetdService`ga tegilmaydi — soxta servis."""
from __future__ import annotations

import asyncio
import json
import os

import pytest

from app.netd import server as server_mod


class _FakeService:
    async def state(self):
        return {"backend": "netplan"}


async def _roundtrip(socket_path: str, raw: bytes) -> dict:
    reader, writer = await asyncio.open_unix_connection(path=socket_path)
    writer.write(raw)
    await writer.drain()
    writer.write_eof() if writer.can_write_eof() else None
    response = await reader.readline()
    writer.close()
    return json.loads(response)


@pytest.mark.asyncio
async def test_serve_creates_socket_with_restrictive_mode(tmp_path):
    socket_path = str(tmp_path / "sub" / "netd.sock")
    srv = await server_mod.serve(_FakeService(), socket_path)
    try:
        assert os.path.exists(socket_path)
        assert (os.stat(socket_path).st_mode & 0o777) == 0o660
    finally:
        srv.close()
        await srv.wait_closed()


@pytest.mark.asyncio
async def test_serve_unlinks_stale_socket_file(tmp_path):
    socket_path = str(tmp_path / "netd.sock")
    os.makedirs(os.path.dirname(socket_path), exist_ok=True)
    with open(socket_path, "w") as fh:
        fh.write("eski")
    srv = await server_mod.serve(_FakeService(), socket_path)
    try:
        assert os.path.exists(socket_path)
    finally:
        srv.close()
        await srv.wait_closed()


@pytest.mark.asyncio
async def test_handle_dispatches_valid_request(tmp_path):
    socket_path = str(tmp_path / "netd.sock")
    srv = await server_mod.serve(_FakeService(), socket_path)
    try:
        response = await _roundtrip(socket_path, b'{"op": "state"}\n')
        assert response == {"ok": True, "result": {"backend": "netplan"}}
    finally:
        srv.close()
        await srv.wait_closed()


@pytest.mark.asyncio
async def test_handle_returns_bad_request_for_invalid_json(tmp_path):
    socket_path = str(tmp_path / "netd.sock")
    srv = await server_mod.serve(_FakeService(), socket_path)
    try:
        response = await _roundtrip(socket_path, b"{not json\n")
        assert response == {"ok": False, "error": {"code": "bad_request", "message": "Yaroqsiz JSON", "fields": []}}
    finally:
        srv.close()
        await srv.wait_closed()


@pytest.mark.asyncio
async def test_handle_returns_bad_request_for_oversized_line(tmp_path):
    socket_path = str(tmp_path / "netd.sock")
    srv = await server_mod.serve(_FakeService(), socket_path)
    try:
        oversized = b'{"op": "state", "pad": "' + b"x" * (server_mod._MAX_LINE_BYTES + 1) + b'"}\n'
        response = await _roundtrip(socket_path, oversized)
        assert response == {"ok": False, "error": {"code": "bad_request", "message": "So'rov juda katta", "fields": []}}
    finally:
        srv.close()
        await srv.wait_closed()


@pytest.mark.asyncio
async def test_handle_swallows_dispatch_exceptions_without_crashing_server(tmp_path, monkeypatch, caplog):
    async def _boom(service, request):
        raise RuntimeError("kutilmagan xato")

    monkeypatch.setattr(server_mod, "dispatch", _boom)
    socket_path = str(tmp_path / "netd.sock")
    srv = await server_mod.serve(_FakeService(), socket_path)
    try:
        reader, writer = await asyncio.open_unix_connection(path=socket_path)
        writer.write(b'{"op": "state"}\n')
        await writer.drain()
        raw = await reader.readline()
        assert raw == b""  # ulanish xatodan keyin yopiladi, javobsiz
        writer.close()
        # Server tirik qolganini keyingi muvaffaqiyatli so'rov bilan isbotlaymiz
        monkeypatch.undo()
        response = await _roundtrip(socket_path, b'{"op": "state"}\n')
        assert response == {"ok": True, "result": {"backend": "netplan"}}
    finally:
        srv.close()
        await srv.wait_closed()


@pytest.mark.asyncio
async def test_handle_returns_immediately_on_empty_read(tmp_path):
    """Mijoz hech narsa yozmasdan ulanishni yopsa — server osilib qolmasligi kerak."""
    socket_path = str(tmp_path / "netd.sock")
    srv = await server_mod.serve(_FakeService(), socket_path)
    try:
        _reader, writer = await asyncio.open_unix_connection(path=socket_path)
        writer.close()
        await writer.wait_closed()
        await asyncio.sleep(0.05)  # server tomonida `_handle` yakunlanishi uchun
    finally:
        srv.close()
        await srv.wait_closed()
