"""Webhook yetkazuvchisi (m3b-contract.md §3).

`POST url`, `Content-Type: application/json`, sarlavhalar `X-Innova-Event`, `X-Innova-Delivery`
(qabul qiluvchi uchun idempotentlik), `X-Innova-Signature: t=<unix>,v1=<hex HMAC-SHA256(secret, "<t>.<body>")>`.
Timeout 10 s, redirect KUZATILMAYDI, 2xx = muvaffaqiyat, javob tanasi ≤ 1 KB saqlanadi.
URL har yuborishda qayta tekshiriladi (DNS rebinding) — taqiqlangan bo'lsa `dead`.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Callable, Mapping

import httpx

from app.core.config import settings
from app.services.integrations import ssrf
from app.services.integrations.providers import DeliveryContext, DeliveryResult, register_provider

RESPONSE_BODY_LIMIT = 1024
ERROR_LIMIT = 500
DEFAULT_RETRY_AFTER_S = 60


def signature_header(secret: str, body: bytes, now_unix: int) -> str:
    mac = hmac.new(secret.encode(), f"{now_unix}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={now_unix},v1={mac}"


def request_headers(secret: str, body: bytes, *, event_type: str, delivery_id: str, now_unix: int) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "User-Agent": "InnovaPBX-Webhook/1",
        "X-Innova-Event": event_type,
        "X-Innova-Delivery": delivery_id,
        "X-Innova-Signature": signature_header(secret, body, now_unix),
    }


def _retry_after(headers: Mapping[str, str]) -> float:
    try:
        return max(1.0, float(headers.get("retry-after", "")))
    except ValueError:
        return float(DEFAULT_RETRY_AFTER_S)


def classify_response(status: int, headers: Mapping[str, str], body: str) -> DeliveryResult:
    """HTTP holati qaror qiladi: 2xx ok; 429 — rate-limit (Retry-After); qolgani vaqtinchalik."""
    stored = body[:RESPONSE_BODY_LIMIT]
    if 200 <= status < 300:
        return DeliveryResult(ok=True, status_code=status, response_body=stored)
    retry_after = _retry_after(headers) if status == 429 else None
    return DeliveryResult(ok=False, status_code=status, retry_after_s=retry_after,
                          error=f"HTTP {status}", response_body=stored)


def mask_secret(text: str, secret: str) -> str:
    return (text.replace(secret, "***") if secret else text)[:ERROR_LIMIT]


def encode_body(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()


class WebhookProvider:
    def __init__(self, *, url_check: Callable[[str], None] = ssrf.check_url_default,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._url_check = url_check
        self._transport = transport

    async def deliver(self, ctx: DeliveryContext) -> DeliveryResult:
        url = str(ctx.subscription.config.get("url", ""))
        secret = ctx.subscription.secret or ""
        try:
            self._url_check(url)
        except ssrf.UrlForbidden as exc:
            return DeliveryResult(ok=False, error=f"url_forbidden:{exc.reason}", permanent=True)
        body = encode_body(ctx.event.payload)
        headers = request_headers(secret, body, event_type=ctx.event.type,
                                  delivery_id=ctx.delivery_id, now_unix=int(time.time()))
        try:
            async with httpx.AsyncClient(timeout=settings.integration_http_timeout_s, follow_redirects=False,
                                         transport=self._transport) as client:
                resp = await client.post(url, content=body, headers=headers)
        except httpx.HTTPError as exc:
            return DeliveryResult(ok=False, error=mask_secret(f"{type(exc).__name__}: {exc}", secret))
        return classify_response(resp.status_code, resp.headers, resp.text)


register_provider("webhook", WebhookProvider())
