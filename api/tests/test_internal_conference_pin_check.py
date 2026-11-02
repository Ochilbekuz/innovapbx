"""`/internal/conferences/{id}/pin-check` — m2a-contract.md §4. `internal.py`
(M1b) bilan bir xil qolip, lekin javob UCH xil: `"admin"`/`"user"`/`"deny"`
(oddiy `"0"`/`"1"` YETARLI EMAS — dialplan qaysi ConfBridge profiliga qo'shish
kerakligini shu bilan hal qiladi)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_wrong_token_denies_without_touching_db():
    r = client.get("/internal/conferences/00000000-0000-0000-0000-000000000000/pin-check",
                    params={"token": "wrong-token", "pin": "1234"})
    assert r.status_code == 200
    assert r.text == "deny"
    assert r.headers["content-type"].startswith("text/plain")


def test_missing_internal_token_setting_denies_by_default(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "internal_api_token", "")
    r = client.get("/internal/conferences/x/pin-check", params={"token": "anything", "pin": "1234"})
    assert r.text == "deny"


def _client_with_hashes(monkeypatch, pin_hash, admin_pin_hash):
    from app.api.deps import get_session
    from app.core.config import settings
    monkeypatch.setattr(settings, "internal_api_token", "tok")

    class _Row:
        def __init__(self):
            self.pin_hash = pin_hash
            self.admin_pin_hash = admin_pin_hash

    class _Res:
        def first(self):
            return _Row()

    class _Session:
        async def execute(self, stmt):
            return _Res()

    async def fake_session():
        yield _Session()

    app.dependency_overrides[get_session] = fake_session
    return TestClient(app)


def _check(c, pin):
    return c.get("/internal/conferences/c1/pin-check", params={"token": "tok", "pin": pin}).text


def test_pin_check_returns_user_or_admin_or_deny(monkeypatch):
    from app.api.deps import get_session
    from app.core.security import hash_password
    try:
        c = _client_with_hashes(monkeypatch, hash_password("1234"), hash_password("9999"))
        assert _check(c, "1234") == "user"
        assert _check(c, "9999") == "admin"
        assert _check(c, "0000") == "deny"
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_pin_check_no_row_found_denies(monkeypatch):
    from app.api.deps import get_session
    from app.core.config import settings
    monkeypatch.setattr(settings, "internal_api_token", "tok")

    class _Res:
        def first(self):
            return None

    class _Session:
        async def execute(self, stmt):
            return _Res()

    async def fake_session():
        yield _Session()

    app.dependency_overrides[get_session] = fake_session
    try:
        c = TestClient(app)
        assert _check(c, "1234") == "deny"
    finally:
        app.dependency_overrides.pop(get_session, None)
