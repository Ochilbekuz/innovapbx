"""`/internal/toll/check` va `/internal/toll/event` — dialplan `CURL()`
chaqiradigan ichki endpoint'lar (m2c-contract.md §3). `test_internal_pin_check.py`
BILAN BIR XIL qolip: token noto'g'ri -> DB'ga umuman murojaat qilinmaydi."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import internal_toll
from app.api.deps import get_session
from app.main import app

client = TestClient(app)


def test_check_wrong_token_denies_without_touching_db():
    r = client.get("/internal/toll/check", params={"token": "wrong", "tenant": "t1", "ext": "201"})
    assert r.status_code == 200
    assert r.text == "0"
    assert r.headers["content-type"].startswith("text/plain")


def test_event_wrong_token_denies_without_touching_db():
    r = client.get("/internal/toll/event",
                    params={"token": "wrong", "tenant": "t1", "kind": "concurrent_limit"})
    assert r.text == "0"


def test_missing_internal_token_setting_denies_by_default(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "internal_api_token", "")
    r = client.get("/internal/toll/check", params={"token": "anything", "tenant": "t1", "ext": "201"})
    assert r.text == "0"


# ------------------------------------------------------------ soxta sessiya
class _Result:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    """Har bir `execute()` chaqiruvi `queue`dan ketma-ket javob oladi
    (`_tenant_id` -> kerak bo'lsa Extension qidiruvi, aniq shu tartibda,
    `internal_toll.py` manba kodiga qarab)."""
    def __init__(self, *, queue=None, settings_row=None):
        self.queue = list(queue or [])
        self.settings_row = settings_row

    async def execute(self, _stmt):
        return _Result(self.queue.pop(0) if self.queue else None)

    async def get(self, model, _pk):
        if model.__name__ == "SystemSettings":
            return self.settings_row
        return None


def _use(monkeypatch, session):
    async def fake_session():
        yield session
    app.dependency_overrides[get_session] = fake_session
    monkeypatch.setattr(app, "dependency_overrides", app.dependency_overrides)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_session, None)


def test_check_tenant_not_found_denies(monkeypatch):
    _use(monkeypatch, _FakeSession(queue=[None]))
    from app.core.config import settings
    monkeypatch.setattr(settings, "internal_api_token", "tok")
    r = client.get("/internal/toll/check", params={"token": "tok", "tenant": "nope", "ext": "201"})
    assert r.text == "0"


def test_check_toll_fraud_disabled_allows(monkeypatch):
    session = _FakeSession(queue=[("tenant-1",)], settings_row=SimpleNamespace(toll_fraud={"enabled": False}))
    _use(monkeypatch, session)
    from app.core.config import settings
    monkeypatch.setattr(settings, "internal_api_token", "tok")
    r = client.get("/internal/toll/check", params={"token": "tok", "tenant": "t1", "ext": "201"})
    assert r.text == "1"


def test_check_extension_not_found_allows(monkeypatch):
    session = _FakeSession(
        queue=[("tenant-1",), None],  # tenant found, extension not found
        settings_row=SimpleNamespace(toll_fraud={"enabled": True}),
    )
    _use(monkeypatch, session)
    from app.core.config import settings
    monkeypatch.setattr(settings, "internal_api_token", "tok")
    r = client.get("/internal/toll/check", params={"token": "tok", "tenant": "t1", "ext": "999"})
    assert r.text == "1"


@pytest.mark.parametrize("decision,expected", [(True, "1"), (False, "0")])
def test_check_delegates_to_check_outbound(monkeypatch, decision, expected):
    ext_row = SimpleNamespace(id="ext-1", number="201", toll_blocked_at=None)
    session = _FakeSession(
        queue=[("tenant-1",), ext_row],
        settings_row=SimpleNamespace(toll_fraud={"enabled": True}),
    )
    _use(monkeypatch, session)
    from app.core.config import settings
    monkeypatch.setattr(settings, "internal_api_token", "tok")

    captured = {}

    async def fake_check_outbound(_session, *, tenant_id, extension, number, intl, cfg):
        captured.update(tenant_id=tenant_id, extension=extension, number=number, intl=intl, cfg=cfg)
        return decision

    monkeypatch.setattr(internal_toll, "check_outbound", fake_check_outbound)
    r = client.get("/internal/toll/check",
                    params={"token": "tok", "tenant": "t1", "ext": "201", "number": "998901112233", "intl": "1"})
    assert r.text == expected
    assert captured["tenant_id"] == "tenant-1"
    assert captured["extension"] is ext_row
    assert captured["number"] == "998901112233"
    assert captured["intl"] is True


def test_event_tenant_not_found_denies(monkeypatch):
    _use(monkeypatch, _FakeSession(queue=[None]))
    from app.core.config import settings
    monkeypatch.setattr(settings, "internal_api_token", "tok")
    r = client.get("/internal/toll/event",
                    params={"token": "tok", "tenant": "nope", "kind": "concurrent_limit"})
    assert r.text == "0"


def test_event_unknown_kind_denies_without_recording(monkeypatch):
    session = _FakeSession(queue=[("tenant-1",)], settings_row=SimpleNamespace(toll_fraud={}))
    _use(monkeypatch, session)
    from app.core.config import settings
    monkeypatch.setattr(settings, "internal_api_token", "tok")

    called = []
    monkeypatch.setattr(internal_toll, "record_concurrent_limit",
                        lambda *a, **kw: called.append(1))
    r = client.get("/internal/toll/event", params={"token": "tok", "tenant": "t1", "kind": "unknown"})
    assert r.text == "0"
    assert called == []


def test_event_concurrent_limit_records_and_always_returns_zero(monkeypatch):
    session = _FakeSession(queue=[("tenant-1",)], settings_row=SimpleNamespace(toll_fraud={"max_concurrent_outbound": 5}))
    _use(monkeypatch, session)
    from app.core.config import settings
    monkeypatch.setattr(settings, "internal_api_token", "tok")

    captured = {}

    async def fake_record(_session, *, tenant_id, extension_number, max_concurrent):
        captured.update(tenant_id=tenant_id, extension_number=extension_number, max_concurrent=max_concurrent)

    monkeypatch.setattr(internal_toll, "record_concurrent_limit", fake_record)
    r = client.get("/internal/toll/event",
                    params={"token": "tok", "tenant": "t1", "kind": "concurrent_limit", "ext": "201"})
    assert r.text == "0"
    assert captured == {"tenant_id": "tenant-1", "extension_number": "201", "max_concurrent": 5}
