"""M9 B1/B2 — ichki (JWT'siz) endpoint'lar: `/internal/outbound-routes/{id}/pin-set-check`
va `/internal/cid-lookup` (dialplan `CURL()` chaqiradi, doim 200 + oddiy matn).
Qolip — `tests/test_internal_pin_check.py`dagi bilan bir xil (fake session +
`app.dependency_overrides[get_session]`)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_session
from app.core.config import settings
from app.db.models import CidLookupSource, OutboundRoute, PinSet, PinSetPin
from app.main import app
from app.services.pin_hmac import hash_pin

client = TestClient(app)


def _clear_overrides():
    app.dependency_overrides.pop(get_session, None)


# ============================================================ pin-set-check

def test_pin_set_check_wrong_token_denies_without_db():
    r = client.get(
        "/internal/outbound-routes/00000000-0000-0000-0000-000000000000/pin-set-check",
        params={"token": "wrong", "pin": "1234"},
    )
    assert r.status_code == 200
    assert r.text == "0"
    assert r.headers["content-type"].startswith("text/plain")


class _Res:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _PinSetSession:
    """1-chaqiruv -> OutboundRoute, 2-chaqiruv -> PinSet (`selectinload` sinov
    uchun muhim emas, `pins` to'g'ridan-to'g'ri ro'yxat sifatida ulanadi)."""

    def __init__(self, route, pin_set):
        self._route = route
        self._pin_set = pin_set
        self._n = 0
        self.added = []
        self.committed = False

    async def execute(self, stmt):
        self._n += 1
        return _Res(self._route if self._n == 1 else self._pin_set)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True


def _pinset_client(monkeypatch, *, route, pin_set):
    monkeypatch.setattr(settings, "internal_api_token", "tok")
    monkeypatch.setattr(settings, "secret_key", "test-secret-key")

    async def fake_session():
        yield _PinSetSession(route, pin_set)

    app.dependency_overrides[get_session] = fake_session
    return TestClient(app)


def _make_route_and_set(record_in_cdr: bool, pin: str, label: str = "guest"):
    route = OutboundRoute(id="r1", tenant_id="t1", pin_set_id="p1")
    pin_set = PinSet(id="p1", tenant_id="t1", record_in_cdr=record_in_cdr)
    pin_set.pins = [PinSetPin(pin_set_id="p1", pin_hmac=hash_pin("test-secret-key", pin), label=label)]
    return route, pin_set


def test_pin_set_check_matches_and_returns_label_when_record_in_cdr(monkeypatch):
    route, pin_set = _make_route_and_set(record_in_cdr=True, pin="4455", label="guest-line")
    try:
        c = _pinset_client(monkeypatch, route=route, pin_set=pin_set)
        r = c.get("/internal/outbound-routes/r1/pin-set-check", params={"token": "tok", "pin": "4455"})
        assert r.text == "1:guest-line"
    finally:
        _clear_overrides()


def test_pin_set_check_matches_but_hides_label_when_not_record_in_cdr(monkeypatch):
    route, pin_set = _make_route_and_set(record_in_cdr=False, pin="4455", label="guest-line")
    try:
        c = _pinset_client(monkeypatch, route=route, pin_set=pin_set)
        r = c.get("/internal/outbound-routes/r1/pin-set-check", params={"token": "tok", "pin": "4455"})
        assert r.text == "1:"
    finally:
        _clear_overrides()


def test_pin_set_check_wrong_pin_denies(monkeypatch):
    route, pin_set = _make_route_and_set(record_in_cdr=True, pin="4455")
    try:
        c = _pinset_client(monkeypatch, route=route, pin_set=pin_set)
        r = c.get("/internal/outbound-routes/r1/pin-set-check", params={"token": "tok", "pin": "0000"})
        assert r.text == "0"
    finally:
        _clear_overrides()


def test_pin_set_check_route_without_pin_set_denies(monkeypatch):
    route = OutboundRoute(id="r1", tenant_id="t1", pin_set_id=None)
    try:
        c = _pinset_client(monkeypatch, route=route, pin_set=None)
        r = c.get("/internal/outbound-routes/r1/pin-set-check", params={"token": "tok", "pin": "4455"})
        assert r.text == "0"
    finally:
        _clear_overrides()


def test_pin_set_check_rate_limits_after_attempt_limit(monkeypatch):
    """Alohida `route_id`/`caller` — boshqa testlarning limiter holatidan mustaqil
    (`_limiter` modul darajasida, jarayon davomida umumiy)."""
    route, pin_set = _make_route_and_set(record_in_cdr=True, pin="4455")
    route.id = "r-ratelimit"
    pin_set.id = "p-ratelimit"
    route.pin_set_id = "p-ratelimit"
    try:
        c = _pinset_client(monkeypatch, route=route, pin_set=pin_set)
        for _ in range(5):
            c.get("/internal/outbound-routes/r-ratelimit/pin-set-check",
                  params={"token": "tok", "pin": "0000", "caller": "isolated-caller"})
        r = c.get("/internal/outbound-routes/r-ratelimit/pin-set-check",
                  params={"token": "tok", "pin": "4455", "caller": "isolated-caller"})
        assert r.text == "0"  # hatto to'g'ri PIN bilan ham — limit tufayli
    finally:
        _clear_overrides()


# ============================================================ cid-lookup

def test_cid_lookup_wrong_token_returns_empty_without_db():
    r = client.get("/internal/cid-lookup", params={"token": "wrong", "source_id": "s1", "num": "901234567"})
    assert r.status_code == 200
    assert r.text == ""


def test_cid_lookup_missing_num_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_token", "tok")
    r = client.get("/internal/cid-lookup", params={"token": "tok", "source_id": "s1"})
    assert r.text == ""


class _SourceSession:
    def __init__(self, source):
        self._source = source

    async def execute(self, stmt):
        return _Res(self._source)


def test_cid_lookup_source_not_found_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_token", "tok")

    async def fake_session():
        yield _SourceSession(None)

    app.dependency_overrides[get_session] = fake_session
    try:
        r = client.get("/internal/cid-lookup", params={"token": "tok", "source_id": "s1", "num": "901234567"})
        assert r.text == ""
    finally:
        _clear_overrides()


def test_cid_lookup_disabled_source_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_token", "tok")
    source = CidLookupSource(id="s1", tenant_id="t1", name="x", kind="phonebook", enabled=False,
                              timeout_ms=1500, cache_ttl_s=0)

    async def fake_session():
        yield _SourceSession(source)

    app.dependency_overrides[get_session] = fake_session
    try:
        r = client.get("/internal/cid-lookup", params={"token": "tok", "source_id": "s1", "num": "901234567"})
        assert r.text == ""
    finally:
        _clear_overrides()
