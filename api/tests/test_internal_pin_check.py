"""`/internal/outbound-routes/{id}/pin-check` — dialplan `CURL()` chaqiradigan
ichki endpoint (m1b-contract.md bo'lim 2). Token noto'g'ri bo'lsa DB'ga
umuman murojaat qilinmaydi (tezkor rad) — shu qism DB'siz sinaladi;
to'liq (to'g'ri token + haqiqiy marshrut) oqim jonli integratsion testda
(`test_integration_live.py`, stack kerak)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_wrong_token_returns_plain_text_zero_without_touching_db():
    r = client.get("/internal/outbound-routes/00000000-0000-0000-0000-000000000000/pin-check",
                    params={"token": "wrong-token", "pin": "1234"})
    assert r.status_code == 200
    assert r.text == "0"
    assert r.headers["content-type"].startswith("text/plain")


def test_missing_internal_token_setting_denies_by_default(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "internal_api_token", "")
    r = client.get("/internal/outbound-routes/x/pin-check", params={"token": "anything", "pin": "1234"})
    assert r.text == "0"


# ------------------------------------------------------------ M1c: ovozli pochta
def test_voicemail_pin_check_wrong_token_denies():
    r = client.get("/internal/voicemail/pin-check",
                   params={"token": "wrong-token", "context": "t1", "mailbox": "201", "pin": "1234"})
    assert r.status_code == 200
    assert r.text == "0"


def test_voicemail_pin_check_non_digit_input_denies_without_db(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "internal_api_token", "tok")
    for params in ({"mailbox": "", "pin": "1234"}, {"mailbox": "201", "pin": ""},
                   {"mailbox": "201'--", "pin": "1234"}, {"mailbox": "201", "pin": "12a4"}):
        r = client.get("/internal/voicemail/pin-check", params={"token": "tok", "context": "t1", **params})
        assert r.text == "0"


def _client_with_pin_hash(monkeypatch, pin_hash):
    from app.api.deps import get_session
    from app.core.config import settings
    monkeypatch.setattr(settings, "internal_api_token", "tok")

    class _Res:
        def scalar_one_or_none(self):
            return pin_hash

    class _Session:
        async def execute(self, stmt):
            return _Res()

    async def fake_session():
        yield _Session()

    app.dependency_overrides[get_session] = fake_session
    return TestClient(app)


def _vm_check(c, pin, context="t1"):
    return c.get("/internal/voicemail/pin-check",
                 params={"token": "tok", "context": context, "mailbox": "201", "pin": pin}).text


def test_voicemail_pin_check_against_hash(monkeypatch):
    from app.api.deps import get_session
    from app.core.security import hash_password
    try:
        c = _client_with_pin_hash(monkeypatch, hash_password("4826"))
        assert _vm_check(c, "4826") == "1"
        assert _vm_check(c, "4827") == "0"
        assert _vm_check(c, "4826", context="") == "0"
        c = _client_with_pin_hash(monkeypatch, None)  # quti yo'q
        assert _vm_check(c, "4826") == "0"
    finally:
        app.dependency_overrides.pop(get_session, None)
