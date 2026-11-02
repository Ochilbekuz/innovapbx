"""Softfon WS ticket'i (m3a-contract.md §0/§2) — `/sip-ws?t=<ticket>` darvozasi.

Ticket = `base64url(json{uid, ext_id, exp}) "." base64url(HMAC-SHA256)`. Kalit — `SECRET_KEY`dan
domen-ajratib olinadi (`_derive_key`): JWT bilan bir kalit ishlatilmaydi, bir imzo boshqa
kontekstda qayta ishlatib bo'lmaydi. Holatsiz (DB'siz) — tekshiruv nginx `auth_request`
har WS ochilishida chaqiriladi; foydalanuvchi/raqam holati (faol, webrtc) chaqiruvchida
(`app/api/internal_softphone.py`) DB'dan tekshiriladi. Ticket logga yozilmaydi."""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

from app.core.config import settings

_KEY_CONTEXT = b"innova-softphone-ticket-v1:"


@dataclass(frozen=True)
class TicketClaims:
    uid: str
    ext_id: str
    exp: int


def _derive_key(secret: str) -> bytes:
    return hashlib.sha256(_KEY_CONTEXT + secret.encode("utf-8")).digest()


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "==")  # ortiqcha padding (non-strict) e'tiborsiz


def _sign(payload: str, secret: str) -> str:
    return _b64encode(hmac.new(_derive_key(secret), payload.encode("utf-8"), hashlib.sha256).digest())


def issue_ticket(*, uid: str, ext_id: str, now: float | None = None, ttl_s: int | None = None,
                 secret: str | None = None) -> tuple[str, datetime]:
    now = time.time() if now is None else now
    ttl_s = settings.softphone_ticket_ttl_s if ttl_s is None else ttl_s
    exp = int(now) + ttl_s
    payload = _b64encode(json.dumps({"uid": uid, "ext_id": ext_id, "exp": exp}, separators=(",", ":")).encode())
    ticket = f"{payload}.{_sign(payload, secret or settings.require_secret_key())}"
    return ticket, datetime.fromtimestamp(exp, tz=timezone.utc)


def _parse_claims(raw: bytes) -> TicketClaims | None:
    try:
        data = json.loads(raw)
        claims = TicketClaims(uid=data["uid"], ext_id=data["ext_id"], exp=data["exp"])
    except (ValueError, KeyError, TypeError):
        return None
    types_ok = isinstance(claims.uid, str) and isinstance(claims.ext_id, str) and isinstance(claims.exp, int)
    return claims if types_ok else None


def verify_ticket(ticket: str, *, now: float | None = None, secret: str | None = None) -> TicketClaims | None:
    """Imzo to'g'ri VA muddati o'tmagan (`now < exp`) bo'lsa — claims; aks holda `None` (xato ko'tarmaydi)."""
    payload, sep, signature = ticket.partition(".")
    expected = _sign(payload, secret or settings.require_secret_key()).encode("ascii")
    if not sep or not hmac.compare_digest(signature.encode("utf-8"), expected):  # bytes: ASCII bo'lmagan kirish ham xavfsiz
        return None
    try:
        claims = _parse_claims(_b64decode(payload))
    except (ValueError, binascii.Error):
        return None
    now = time.time() if now is None else now
    return claims if claims is not None and now < claims.exp else None


def ticket_from_uri(uri: str | None) -> str | None:
    """nginx `auth_request` `X-Original-URI` sarlavhasi (`/sip-ws?t=...`) dan `t`."""
    values = parse_qs(urlsplit(uri or "").query).get("t")
    return values[0] if values else None
