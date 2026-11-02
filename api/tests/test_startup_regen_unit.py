"""Vazifa A §5 — ishga tushganda dialplan/navbat a'zosi/hint ma'lumotlarini majburan
qayta qo'llash (migratsiyadan keyin eski kompilyatsiya fayli eskirib qolmasin).
DB/AMI'siz: soxta sessiya/`apply_config` monkeypatch."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import startup_regen as sr


class _FakeSession:
    def __init__(self, tenant_ids):
        self._ids = tenant_ids
        self.committed = self.rolled_back = 0

    async def execute(self, _stmt):
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: self._ids))

    async def commit(self):
        self.committed += 1

    async def rollback(self):
        self.rolled_back += 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _factory(session):
    return lambda: session


@pytest.mark.asyncio
async def test_calls_apply_config_once_per_tenant(monkeypatch):
    calls = []

    async def fake_apply(session, *, tenant_id, user_id, ami):
        calls.append(tenant_id)

    monkeypatch.setattr(sr, "apply_config", fake_apply)
    session = _FakeSession(["t1", "t2"])
    await sr.regenerate_dialplan_on_startup(_factory(session), ami=None)
    assert calls == ["t1", "t2"] and session.committed == 2


@pytest.mark.asyncio
async def test_one_tenant_failure_does_not_stop_others(monkeypatch):
    calls = []

    async def fake_apply(session, *, tenant_id, user_id, ami):
        calls.append(tenant_id)
        if tenant_id == "bad":
            raise RuntimeError("boom")

    monkeypatch.setattr(sr, "apply_config", fake_apply)
    session = _FakeSession(["bad", "t2"])
    await sr.regenerate_dialplan_on_startup(_factory(session), ami=None)
    assert calls == ["bad", "t2"] and session.rolled_back == 1 and session.committed == 1
