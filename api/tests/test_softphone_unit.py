"""M3a §2 — `GET /api/v1/me/softphone` va `GET /internal/softphone/ws-auth` (nginx `auth_request`).
DB/AMI'siz: `dependency_overrides` + monkeypatch; HTTP darajasida (status, sarlavha, tana) tekshiriladi.
Jonli oqim — m3a jonli tasdiq (nginx `/sip-ws` 401/101)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import internal_softphone
from app.api.deps import get_current_user, get_session
from app.api.v1 import softphone
from app.main import app
from app.services.softphone_ticket import issue_ticket, verify_ticket

KEY = "s" * 40


def _ext(**kw):
    base = dict(id="e1", tenant_id="t1", number="101", name="Ali", callerid_name=None, webrtc=True,
                enabled=True, sip_password_enc="ENC")
    return SimpleNamespace(**{**base, **kw})


def _user(**kw):
    base = dict(id="u1", tenant_id="t1", is_active=True, extension=_ext())
    return SimpleNamespace(**{**base, **kw})


class _Session:
    def __init__(self, user=None):
        self.user, self.commits = user, 0

    async def get(self, _model, _pk):
        return self.user

    async def commit(self):
        self.commits += 1


@pytest.fixture
def env(monkeypatch):
    state = {"user": _user(), "session": _Session(), "audit": []}

    async def fake_decrypt(_session, enc):
        return f"plain-{enc}"

    async def fake_code(_session, _tenant_id):
        return "t1"

    async def fake_audit(_session, **kw):
        state["audit"].append(kw)

    monkeypatch.setattr(softphone.settings, "secret_key", KEY)
    monkeypatch.setattr(softphone, "decrypt_secret", fake_decrypt)
    monkeypatch.setattr(softphone, "get_tenant_code", fake_code)
    monkeypatch.setattr(softphone, "record_audit", fake_audit)
    monkeypatch.setattr(softphone, "_limiter", softphone.SlidingWindowLimiter())
    app.dependency_overrides[get_current_user] = lambda: state["user"]
    app.dependency_overrides[get_session] = lambda: state["session"]
    yield state
    app.dependency_overrides.clear()


client = TestClient(app)


def test_routes_registered_and_bound_to_handlers():
    paths = {route.path for route in app.routes}
    assert "/api/v1/me/softphone" in paths and "/internal/softphone/ws-auth" in paths
    me_route = [r for r in softphone.router.routes if r.path == "/me/softphone"]
    ws_route = [r for r in internal_softphone.router.routes if r.path == "/internal/softphone/ws-auth"]
    assert me_route[0].endpoint is softphone.my_softphone
    status_route = [r for r in softphone.router.routes if r.path == "/me/softphone/status"]
    assert status_route[0].endpoint is softphone.my_softphone_status
    assert ws_route[0].endpoint is internal_softphone.ws_auth


# ---------------------------------------------------------------- /me/softphone
def test_softphone_returns_own_credentials_and_valid_ticket(env):
    r = client.get("/api/v1/me/softphone")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    body = r.json()
    assert body["number"] == "101" and body["display_name"] == "Ali" and body["ws_path"] == "/sip-ws"
    assert body["sip"] == {"uri": "sip:t1-101@innova", "auth_user": "t1-101", "password": "plain-ENC",
                           "realm": "asterisk"}
    assert body["ice_servers"] == []
    claims = verify_ticket(body["ticket"], secret=KEY)
    assert claims is not None and (claims.uid, claims.ext_id) == ("u1", "e1")
    assert body["ticket_expires_at"].startswith("20")


def test_softphone_display_name_prefers_callerid_name(env):
    env["user"].extension.callerid_name = "Ali (sotuv)"
    assert client.get("/api/v1/me/softphone").json()["display_name"] == "Ali (sotuv)"


def test_softphone_audit_has_no_password_or_ticket(env):
    r = client.get("/api/v1/me/softphone")
    audit = env["audit"][0]
    assert audit["action"] == "softphone.credentials" and audit["entity_id"] == "e1"
    flat = repr(audit)
    assert "plain-ENC" not in flat and r.json()["ticket"] not in flat
    assert env["session"].commits == 1


@pytest.mark.parametrize("path", ["/api/v1/me/softphone", "/api/v1/me/softphone/status"])
@pytest.mark.parametrize("user,status,code", [
    (_user(extension=None), 404, "no_extension"),
    (_user(extension=_ext(webrtc=False)), 409, "webrtc_disabled"),
    (_user(extension=_ext(enabled=False)), 409, "extension_disabled"),
])
def test_softphone_refusals(env, path, user, status, code):
    env["user"] = user
    r = client.get(path)
    assert (r.status_code, r.json()["error"]["code"]) == (status, code)
    assert env["audit"] == []


def test_softphone_status_204_no_store_no_secrets(env):
    r = client.get("/api/v1/me/softphone/status")
    assert (r.status_code, r.content) == (204, b"")
    assert r.headers["cache-control"] == "no-store"
    assert env["audit"] == [] and env["session"].commits == 0


def test_softphone_rate_limited_per_user(env, monkeypatch):
    monkeypatch.setattr(softphone.settings, "softphone_rate_limit_per_min", 3)
    codes = [client.get("/api/v1/me/softphone").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    env["user"] = _user(id="u2")  # boshqa foydalanuvchi — o'z chegarasi
    assert client.get("/api/v1/me/softphone").status_code == 200


def test_rate_limiter_window_slides():
    now = [0.0]
    limiter = softphone.SlidingWindowLimiter(clock=lambda: now[0])
    assert [limiter.allow("u", limit=2, window_s=60) for _ in range(3)] == [True, True, False]
    now[0] = 59.9
    assert limiter.allow("u", limit=2, window_s=60) is False
    now[0] = 60.0  # aynan `window_s` yoshidagi urinish oynadan chiqadi
    assert limiter.allow("u", limit=2, window_s=60) is True


# ---------------------------------------------------------------- /internal/softphone/ws-auth
def _ws_auth(env, ticket: str | None):
    headers = {} if ticket is None else {"X-Original-URI": f"/sip-ws?t={ticket}"}
    return client.get("/internal/softphone/ws-auth", headers=headers)


def _ticket(uid="u1", ext_id="e1", ttl_s=600):
    return issue_ticket(uid=uid, ext_id=ext_id, ttl_s=ttl_s, secret=KEY)[0]


def test_ws_auth_valid_ticket_204_without_body(env):
    env["session"].user = _user()
    r = _ws_auth(env, _ticket())
    assert r.status_code == 204 and r.content == b""


@pytest.mark.parametrize("ticket", [None, "", "garbage", "x.y"])
def test_ws_auth_missing_or_bad_ticket_401(env, ticket):
    env["session"].user = _user()
    r = _ws_auth(env, ticket)
    assert r.status_code == 401 and r.content == b""


def test_ws_auth_expired_ticket_401(env):
    env["session"].user = _user()
    assert _ws_auth(env, _ticket(ttl_s=-1)).status_code == 401


@pytest.mark.parametrize("user", [
    None,
    _user(is_active=False),
    _user(extension=None),
    _user(extension=_ext(webrtc=False)),
    _user(extension=_ext(enabled=False)),
    _user(extension=_ext(id="e2")),
])
def test_ws_auth_user_or_extension_no_longer_eligible_401(env, user):
    env["session"].user = user
    assert _ws_auth(env, _ticket()).status_code == 401
