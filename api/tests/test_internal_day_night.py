"""`/internal/day-night/{id}/state` va `/toggle` — `test_internal_conference_pin_check.py`
BILAN BIR XIL qolip. `/state` fail-SAFE ("day" qaytaradi xato bo'lsa ham —
chaqiruv yo'naltirishi hech qachon to'xtamasligi uchun); `/toggle` PIN mos
kelmasa `SecurityEvent` yozib rad etadi."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_state_wrong_token_is_failsafe_day():
    r = client.get("/internal/day-night/x/state", params={"token": "wrong"})
    assert r.status_code == 200
    assert r.text == "day"
    assert r.headers["content-type"].startswith("text/plain")


def test_state_missing_internal_token_setting_is_failsafe_day(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "internal_api_token", "")
    r = client.get("/internal/day-night/x/state", params={"token": "anything"})
    assert r.text == "day"


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
    def __init__(self, mode="day", pin_hmac=None, tenant_id="t1"):
        self.mode = mode
        self.pin_hmac = pin_hmac
        self.tenant_id = tenant_id


def test_state_row_not_found_is_failsafe_day(monkeypatch):
    try:
        c = _client_with_row(monkeypatch, None)
        assert c.get("/internal/day-night/dn1/state", params={"token": "tok"}).text == "day"
    finally:
        from app.api.deps import get_session
        app.dependency_overrides.pop(get_session, None)


def test_state_returns_live_mode(monkeypatch):
    try:
        c = _client_with_row(monkeypatch, _Row(mode="night"))
        assert c.get("/internal/day-night/dn1/state", params={"token": "tok"}).text == "night"
    finally:
        from app.api.deps import get_session
        app.dependency_overrides.pop(get_session, None)


def test_toggle_wrong_token_denies():
    r = client.get("/internal/day-night/x/toggle", params={"token": "wrong"})
    assert r.text == "0"


def test_toggle_row_not_found_denies(monkeypatch):
    try:
        c = _client_with_row(monkeypatch, None)
        assert c.get("/internal/day-night/dn1/toggle", params={"token": "tok"}).text == "0"
    finally:
        from app.api.deps import get_session
        app.dependency_overrides.pop(get_session, None)


def test_toggle_no_pin_required_flips_mode(monkeypatch):
    row = _Row(mode="day", pin_hmac=None)
    try:
        c = _client_with_row(monkeypatch, row)
        r = c.get("/internal/day-night/dn1/toggle", params={"token": "tok"})
        assert r.text == "night"
        assert row.mode == "night"
    finally:
        from app.api.deps import get_session
        app.dependency_overrides.pop(get_session, None)


def test_toggle_with_pin_mismatch_denies_and_does_not_flip(monkeypatch):
    from app.services.pin_hmac import hash_pin
    row = _Row(mode="day", pin_hmac=hash_pin("test-secret-key", "1234"))
    try:
        c = _client_with_row(monkeypatch, row)
        r = c.get("/internal/day-night/dn1/toggle", params={"token": "tok", "pin": "0000"})
        assert r.text == "0"
        assert row.mode == "day"
    finally:
        from app.api.deps import get_session
        app.dependency_overrides.pop(get_session, None)


def test_toggle_with_correct_pin_flips_mode(monkeypatch):
    from app.services.pin_hmac import hash_pin
    row = _Row(mode="day", pin_hmac=hash_pin("test-secret-key", "1234"))
    try:
        c = _client_with_row(monkeypatch, row)
        r = c.get("/internal/day-night/dn1/toggle", params={"token": "tok", "pin": "1234"})
        assert r.text == "night"
        assert row.mode == "night"
    finally:
        from app.api.deps import get_session
        app.dependency_overrides.pop(get_session, None)
