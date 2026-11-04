"""`/internal/disa/{id}/pin-check` — `test_internal_conference_pin_check.py`
BILAN BIR XIL qolip, lekin fail-CLOSED (noma'lum holatda HAR DOIM "0" —
toll-fraud xavfi, `internal_day_night.py`dagi fail-SAFE'dan FARQLI)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_wrong_token_denies():
    r = client.get("/internal/disa/x/pin-check", params={"token": "wrong", "pin": "1234"})
    assert r.status_code == 200
    assert r.text == "0"
    assert r.headers["content-type"].startswith("text/plain")


def test_missing_internal_token_setting_denies_by_default(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "internal_api_token", "")
    r = client.get("/internal/disa/x/pin-check", params={"token": "anything", "pin": "1234"})
    assert r.text == "0"


def _client_with_row(monkeypatch, row):
    from app.api.deps import get_session
    from app.core.config import settings
    monkeypatch.setattr(settings, "internal_api_token", "tok")
    monkeypatch.setattr(settings, "secret_key", "test-secret-key")

    class _Session:
        async def get(self, model, key):
            return row

        def add(self, obj):
            pass

        async def commit(self):
            pass

    async def fake_session():
        yield _Session()

    app.dependency_overrides[get_session] = fake_session
    return TestClient(app)


class _Row:
    def __init__(self, pin_hmac=None, allow_no_pin=False, enabled=True, tenant_id="t1"):
        self.pin_hmac = pin_hmac
        self.allow_no_pin = allow_no_pin
        self.enabled = enabled
        self.tenant_id = tenant_id


def test_row_not_found_denies(monkeypatch):
    try:
        c = _client_with_row(monkeypatch, None)
        assert c.get("/internal/disa/d1/pin-check", params={"token": "tok", "pin": "1234"}).text == "0"
    finally:
        from app.api.deps import get_session
        app.dependency_overrides.pop(get_session, None)


def test_disabled_row_denies_even_with_correct_pin(monkeypatch):
    from app.services.pin_hmac import hash_pin
    row = _Row(pin_hmac=hash_pin("test-secret-key", "1234"), enabled=False)
    try:
        c = _client_with_row(monkeypatch, row)
        assert c.get("/internal/disa/d1/pin-check", params={"token": "tok", "pin": "1234"}).text == "0"
    finally:
        from app.api.deps import get_session
        app.dependency_overrides.pop(get_session, None)


def test_no_pin_set_allows_only_when_allow_no_pin(monkeypatch):
    try:
        c = _client_with_row(monkeypatch, _Row(pin_hmac=None, allow_no_pin=True))
        assert c.get("/internal/disa/d1/pin-check", params={"token": "tok", "pin": ""}).text == "1"
    finally:
        from app.api.deps import get_session
        app.dependency_overrides.pop(get_session, None)


def test_no_pin_set_denies_when_allow_no_pin_false(monkeypatch):
    try:
        c = _client_with_row(monkeypatch, _Row(pin_hmac=None, allow_no_pin=False))
        assert c.get("/internal/disa/d1/pin-check", params={"token": "tok", "pin": ""}).text == "0"
    finally:
        from app.api.deps import get_session
        app.dependency_overrides.pop(get_session, None)


def test_correct_pin_allows(monkeypatch):
    from app.services.pin_hmac import hash_pin
    try:
        c = _client_with_row(monkeypatch, _Row(pin_hmac=hash_pin("test-secret-key", "1234")))
        assert c.get("/internal/disa/d1/pin-check", params={"token": "tok", "pin": "1234"}).text == "1"
    finally:
        from app.api.deps import get_session
        app.dependency_overrides.pop(get_session, None)


def test_wrong_pin_denies_and_writes_security_event(monkeypatch):
    from app.services.pin_hmac import hash_pin
    row = _Row(pin_hmac=hash_pin("test-secret-key", "1234"))
    events: list = []

    try:
        from app.api.deps import get_session
        from app.core.config import settings
        monkeypatch.setattr(settings, "internal_api_token", "tok")
        monkeypatch.setattr(settings, "secret_key", "test-secret-key")

        class _Session:
            async def get(self, model, key):
                return row

            def add(self, obj):
                events.append(obj)

            async def commit(self):
                pass

        async def fake_session():
            yield _Session()

        app.dependency_overrides[get_session] = fake_session
        c = TestClient(app)
        r = c.get("/internal/disa/d1/pin-check", params={"token": "tok", "pin": "0000"})
        assert r.text == "0"
        assert len(events) == 1 and events[0].kind == "disa_pin_fail"
    finally:
        from app.api.deps import get_session
        app.dependency_overrides.pop(get_session, None)
