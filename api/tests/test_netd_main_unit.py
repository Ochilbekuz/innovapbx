"""`app/netd/__main__.py` — jarayon kirish nuqtasi: sozlamalarni yuklaydi,
`NetdService.startup_recover()`ni chaqiradi, soket serverini ko'taradi va
muddat tugashini kuzatuvchi fon vazifasini (`_sweep_expired`) ishga
tushiradi. Haqiqiy tarmoq/fayl tizimisiz — hammasi soxta."""
from __future__ import annotations

import asyncio

import pytest

from app.netd import __main__ as main_mod


@pytest.mark.asyncio
async def test_sweep_expired_calls_maybe_expire_on_each_tick_and_swallows_errors(monkeypatch):
    sleeps: list[float] = []

    async def _fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) >= 3:
            raise asyncio.CancelledError

    monkeypatch.setattr(main_mod.asyncio, "sleep", _fake_sleep)

    class _Service:
        def __init__(self):
            self.calls = 0

        async def _maybe_expire(self):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("birinchi tikda xato")

    service = _Service()
    with pytest.raises(asyncio.CancelledError):
        await main_mod._sweep_expired(service)

    assert sleeps == [main_mod._SWEEP_INTERVAL_S] * 3
    # Birinchi chaqiruv xato bersa ham ikkinchi tikda yana chaqirilgani —
    # xato yutilgani (loop to'xtamagani) isboti.
    assert service.calls == 2


class _FakeServer:
    """`async with server: await server.serve_forever()` shaklini taqlid
    qiladi — testni to'xtatish uchun bitta marotaba chiqariladigan xato."""

    def __init__(self):
        self.closed_via_context = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.closed_via_context = True
        return False

    async def serve_forever(self):
        raise _StopTest


class _StopTest(Exception):
    pass


@pytest.mark.asyncio
async def test_main_wires_settings_executor_service_and_server(monkeypatch):
    calls = {}

    class _Settings:
        exec_mode = "nsenter"
        host_root = "/proc/1/root"
        socket_path = "/run/innova-netd/netd.sock"
        readonly = False

    class _Executor:
        def __init__(self, exec_mode, host_root):
            calls["executor_args"] = (exec_mode, host_root)

    class _Service:
        def __init__(self, executor, settings):
            calls["service_args"] = (executor, settings)
            self.recovered = False

        async def startup_recover(self):
            self.recovered = True
            calls["recovered"] = True

    fake_server = _FakeServer()

    async def _fake_serve(service, socket_path):
        calls["serve_args"] = (service, socket_path)
        return fake_server

    monkeypatch.setattr(main_mod, "load_settings", lambda: _Settings())
    monkeypatch.setattr(main_mod, "Executor", _Executor)
    monkeypatch.setattr(main_mod, "NetdService", _Service)
    monkeypatch.setattr(main_mod, "serve", _fake_serve)

    with pytest.raises(_StopTest):
        await main_mod._main()

    assert calls["executor_args"] == ("nsenter", "/proc/1/root")
    assert calls["recovered"] is True
    assert calls["serve_args"][1] == "/run/innova-netd/netd.sock"
    assert fake_server.closed_via_context is True
