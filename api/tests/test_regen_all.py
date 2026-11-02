"""`app/services/regen_all.py` — har qadam mavjud generatorni TO'G'RI argumentlar
bilan chaqirishini tasdiqlaydi (haqiqiy AMI/DB yo'q, hammasi `monkeypatch`)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import regen_all


class _Scalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _Result:
    def __init__(self, *, scalar=None, items=None):
        self._scalar = scalar
        self._items = items or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return _Scalars(self._items)


class _Session:
    def __init__(self, *, settings_row, revision=None, extensions=None):
        self._settings_row = settings_row
        self._revision = revision
        self._extensions = extensions or []

    async def get(self, model, key):
        return self._settings_row

    async def execute(self, *_args, **_kwargs):
        return _Result(scalar=self._revision, items=self._extensions)


@pytest.mark.asyncio
async def test_regenerate_all_calls_every_generator_in_order(monkeypatch):
    calls: list[str] = []
    row = SimpleNamespace(restart_required=False)
    ext = SimpleNamespace(id="e1")
    session = _Session(settings_row=row, revision=None, extensions=[ext])
    ami = object()

    async def fake_apply_config(_session, *, tenant_id, user_id, ami):
        calls.append("apply_config")
        assert tenant_id == "t1"
        assert user_id is None

    async def fake_restore_revision(*_args, **_kwargs):
        calls.append("restore_revision")

    async def fake_apply_moh(_session, *, tenant_id, tenant_code, ami):
        calls.append("apply_moh")

    async def fake_apply_acl(_session, _ami):
        calls.append("apply_acl")

    async def fake_apply_sip_config(_ami, _cfg, *, reload_rtp):
        calls.append("apply_sip_config")
        assert reload_rtp is True

    def fake_current_sip_config(_row):
        return "cfg"

    async def fake_apply_voicemail(_session, *, tenant_id, tenant_code, ami):
        calls.append("apply_voicemail")

    async def fake_notify(_session, _ami, ext, tenant_code):
        calls.append(f"notify:{ext.id}")

    monkeypatch.setattr(regen_all, "apply_config", fake_apply_config)
    monkeypatch.setattr(regen_all, "restore_revision", fake_restore_revision)
    monkeypatch.setattr(regen_all, "apply_moh", fake_apply_moh)
    monkeypatch.setattr(regen_all, "apply_acl", fake_apply_acl)
    monkeypatch.setattr(regen_all, "apply_sip_config", fake_apply_sip_config)
    monkeypatch.setattr(regen_all, "current_sip_config", fake_current_sip_config)
    monkeypatch.setattr(regen_all, "apply_voicemail", fake_apply_voicemail)
    monkeypatch.setattr(regen_all, "notify_extension_devices", fake_notify)

    await regen_all.regenerate_all(session, tenant_id="t1", tenant_code="pbx1", ami=ami)

    assert calls == [
        "apply_config", "apply_moh", "apply_acl", "apply_sip_config", "apply_voicemail", "notify:e1",
    ]
    assert row.restart_required is True


@pytest.mark.asyncio
async def test_regen_dialplan_uses_restore_revision_when_applied_exists(monkeypatch):
    applied = SimpleNamespace(id=5)
    row = SimpleNamespace(restart_required=False)
    session = _Session(settings_row=row, revision=applied, extensions=[])

    restore_mock = AsyncMock()
    apply_mock = AsyncMock()
    monkeypatch.setattr(regen_all, "restore_revision", restore_mock)
    monkeypatch.setattr(regen_all, "apply_config", apply_mock)

    await regen_all._regen_dialplan(session, tenant_id="t1", tenant_code="pbx1", ami=object())

    restore_mock.assert_awaited_once()
    apply_mock.assert_not_awaited()
    assert restore_mock.await_args.kwargs["target"] is applied


@pytest.mark.asyncio
async def test_regen_dialplan_falls_back_to_apply_config_when_no_applied_revision(monkeypatch):
    row = SimpleNamespace(restart_required=False)
    session = _Session(settings_row=row, revision=None, extensions=[])

    restore_mock = AsyncMock()
    apply_mock = AsyncMock()
    monkeypatch.setattr(regen_all, "restore_revision", restore_mock)
    monkeypatch.setattr(regen_all, "apply_config", apply_mock)

    await regen_all._regen_dialplan(session, tenant_id="t1", tenant_code="pbx1", ami=object())

    apply_mock.assert_awaited_once()
    restore_mock.assert_not_awaited()
