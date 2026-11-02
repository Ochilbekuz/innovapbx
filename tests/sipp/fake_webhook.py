"""Soxta webhook qabul qiluvchi (faqat M3b proof). Stdlib, `python:3.12-slim` konteynerida ishlaydi.

    python3 fake_webhook.py 0.0.0.0 9000

Har yo'l (`/a`, `/b`, ...) — alohida "qabul qiluvchi": o'z secret'i va "keyingi N so'rovga 500" hisoblagichi.
  POST /_config {"path": "/a", "secret": "whsec_...", "fail": 2}   — sozlash (fail — keyingi N ta POST'ga 500)
  POST /_reset                                                    — barcha yozilgan so'rovlarni tozalash
  GET  /_requests[?path=/a]                                       — yozilgan so'rovlar (JSON ro'yxat)
  POST /<boshqa yo'l>                                             — webhook: HMAC tekshiriladi, so'rov yoziladi
Yozuv: {path, event, delivery, sig_ok, status, body (JSON yoki null), t}. `sig_ok` — `X-Innova-Signature:
t=<unix>,v1=<hex HMAC-SHA256(secret, "<t>.<body>")>` to'g'ri va |now - t| <= 300 s.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

TOLERANCE_S = 300
_lock = threading.Lock()
_config: dict[str, dict] = {}
_requests: list[dict] = []


def signature_ok(header: str, body: bytes, secret: str, now: float) -> bool:
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    t, v1 = parts.get("t", ""), parts.get("v1", "")
    if not t.isdigit() or not secret or abs(now - int(t)) > TOLERANCE_S:
        return False
    expected = hmac.new(secret.encode(), t.encode() + b"." + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


def _json_or_none(body: bytes):
    try:
        return json.loads(body)
    except ValueError:
        return None


def handle_hook(path: str, headers, body: bytes) -> int:
    with _lock:
        cfg = _config.setdefault(path, {"secret": "", "fail": 0})
        status = 500 if cfg["fail"] > 0 else 200
        if status == 500:
            cfg["fail"] -= 1
        _requests.append({
            "path": path, "event": headers.get("X-Innova-Event"), "delivery": headers.get("X-Innova-Delivery"),
            "sig_ok": signature_ok(headers.get("X-Innova-Signature", ""), body, cfg["secret"], time.time()),
            "status": status, "body": _json_or_none(body), "t": time.time(),
        })
    return status


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload) -> None:
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        url = urlsplit(self.path)
        if url.path != "/_requests":
            return self._send(404, {"error": "not_found"})
        want = parse_qs(url.query).get("path", [None])[0]
        with _lock:
            items = [r for r in _requests if want is None or r["path"] == want]
        self._send(200, items)

    def do_POST(self) -> None:  # noqa: N802
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        path = urlsplit(self.path).path
        if path == "/_config":
            cfg = json.loads(body)
            with _lock:
                _config[cfg["path"]] = {"secret": cfg.get("secret", ""), "fail": int(cfg.get("fail", 0))}
            return self._send(200, {"ok": True})
        if path == "/_reset":
            with _lock:
                _requests.clear()
            return self._send(200, {"ok": True})
        status = handle_hook(path, self.headers, body)
        self._send(status, {"ok": status == 200})

    def log_message(self, *args) -> None:  # jim
        return


if __name__ == "__main__":
    ThreadingHTTPServer((sys.argv[1], int(sys.argv[2])), Handler).serve_forever()
