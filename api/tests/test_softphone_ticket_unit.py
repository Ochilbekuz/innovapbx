"""M3a §0/§2 — softfon WS ticket'i: HMAC-SHA256 (`SECRET_KEY`) imzoli `{uid, ext_id, exp}`.
Sof funksiyalar (vaqt va kalit parametr) — DB'siz."""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

import pytest

from app.services.softphone_ticket import TicketClaims, issue_ticket, ticket_from_uri, verify_ticket

KEY = "k" * 40
T0 = 1_800_000_000.0


def _issue(**kw):
    args = dict(uid="u1", ext_id="e1", now=T0, ttl_s=600, secret=KEY)
    args.update(kw)
    return issue_ticket(**args)


def test_round_trip_returns_claims_and_expiry():
    ticket, expires_at = _issue()
    assert verify_ticket(ticket, now=T0 + 1, secret=KEY) == TicketClaims(uid="u1", ext_id="e1", exp=int(T0) + 600)
    assert expires_at == datetime.fromtimestamp(T0 + 600, tz=timezone.utc)


def test_ticket_is_url_safe():
    ticket, _ = _issue()
    assert all(c.isalnum() or c in "-_." for c in ticket)


@pytest.mark.parametrize("delta,ok", [(599, True), (600, False), (601, False)])
def test_expiry_is_exclusive(delta, ok):
    ticket, _ = _issue()
    assert (verify_ticket(ticket, now=T0 + delta, secret=KEY) is not None) is ok


def test_other_secret_rejected():
    ticket, _ = _issue()
    assert verify_ticket(ticket, now=T0, secret="x" * 40) is None


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def test_tampered_payload_rejected():
    """Imzo o'zgarmagan holda payload'dagi `ext_id` almashtirilsa — rad."""
    ticket, _ = _issue()
    _payload, sig = ticket.split(".")
    forged = _b64(json.dumps({"uid": "u1", "ext_id": "e2", "exp": int(T0) + 600}).encode())
    assert verify_ticket(f"{forged}.{sig}", now=T0, secret=KEY) is None


@pytest.mark.parametrize("bad", ["", ".", "abc", "a.b.c", "!!!.???", "e30.e30", "ü.ü", "e30.ü"])
def test_garbage_rejected(bad):
    assert verify_ticket(bad, now=T0, secret=KEY) is None


def test_validly_signed_but_malformed_claims_rejected():
    """Imzo to'g'ri, lekin payload shakli yaroqsiz (kalit yo'q / tur noto'g'ri / JSON emas) — rad, xato emas."""
    import hashlib
    import hmac as _hmac
    from app.services import softphone_ticket as mod
    exp = int(T0) + 600
    for raw in (b'{"uid":"u1"}', b"[]", b"\xff",
                # har maydon turi ALOHIDA buzilgan (biri to'g'ri bo'lsa ham o'tmasin)
                json.dumps({"uid": 1, "ext_id": "e1", "exp": exp}).encode(),
                json.dumps({"uid": "u1", "ext_id": 2, "exp": exp}).encode(),
                json.dumps({"uid": "u1", "ext_id": "e1", "exp": str(exp)}).encode()):
        payload = _b64(raw)
        sig = _b64(_hmac.new(mod._derive_key(KEY), payload.encode(), hashlib.sha256).digest())
        assert verify_ticket(f"{payload}.{sig}", now=T0, secret=KEY) is None


@pytest.mark.parametrize("uri,expected", [
    ("/sip-ws?t=abc.def", "abc.def"),
    ("/sip-ws?x=1&t=abc.def&y=2", "abc.def"),
    ("/sip-ws", None),
    ("/sip-ws?t=", None),
    (None, None),
])
def test_ticket_from_original_uri(uri, expected):
    assert ticket_from_uri(uri) == expected


def test_defaults_come_from_settings(monkeypatch):
    from app.services import softphone_ticket as mod
    monkeypatch.setattr(mod.settings, "secret_key", KEY)
    monkeypatch.setattr(mod.settings, "softphone_ticket_ttl_s", 5)
    ticket, expires_at = issue_ticket(uid="u1", ext_id="e1")
    claims = verify_ticket(ticket)
    assert claims is not None and claims.uid == "u1"
    assert 0 < (expires_at - datetime.now(timezone.utc)).total_seconds() <= 5
