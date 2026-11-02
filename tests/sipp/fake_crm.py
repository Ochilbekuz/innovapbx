"""Soxta Bitrix24 REST + amoCRM API (faqat M3b CRM proof). Stdlib, `python:3.12-slim` konteynerida ishlaydi.

    python3 fake_crm.py 0.0.0.0 9001

Bitrix24 (incoming webhook `/rest/1/<kod>/<metod>.json`, form-encoded):
  user.get                         — BITRIX_USERS (UF_PHONE_INNER bilan, avto-xarita uchun)
  telephony.externalcall.register  — {"result": {"CALL_ID": "ext.<EXTERNAL_CALL_ID>"}}
  boshqa metod                     — {"result": true}
amoCRM (`Authorization: Bearer <AMO_TOKEN>`, aks holda 401):
  GET  /api/v4/users               — AMO_USERS
  POST /api/v4/calls               — telefon `known` ro'yxatida → calls; aks holda `_embedded.errors` (kontakt yo'q)
  POST /api/v4/leads/unsorted/sip  — {"_embedded": {"unsorted": [...]}}
Boshqaruv:
  POST /_config {"fail": [{"prefix": "/rest/", "status": 503, "n": 1, "retry_after": 2}], "known": ["998..."]}
  POST /_reset                     — yozuvlar va sozlamalar tozalanadi
  GET  /_requests                  — [{path, method, status, form|json, auth, t}] (kelish tartibida)
"""
from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

AMO_TOKEN = "amotok-M3b"
BITRIX_USERS = [{"ID": "7", "NAME": "Op", "LAST_NAME": "101", "UF_PHONE_INNER": "101"},
                {"ID": "9", "NAME": "Op", "LAST_NAME": "103", "UF_PHONE_INNER": "103"},
                {"ID": "11", "NAME": "Op", "LAST_NAME": "104", "UF_PHONE_INNER": "104"}]
AMO_USERS = [{"id": 55, "name": "Amo 101"}, {"id": 56, "name": "Amo 103"}]

_lock = threading.Lock()
_state: dict = {"fail": [], "known": []}
_requests: list[dict] = []


def _parse(body: bytes, ctype: str):
    if "json" in ctype:
        try:
            return {"json": json.loads(body)}
        except ValueError:
            return {"json": None}
    return {"form": {k: v[0] for k, v in parse_qs(body.decode()).items()}}


def injected_failure(path: str) -> tuple[int, dict] | None:
    """Yo'l prefiksiga mos birinchi qoida (n > 0) → (status, sarlavhalar); qoida har ishlatilganda n kamayadi."""
    rule = next((f for f in _state["fail"] if f.get("n", 0) > 0 and path.startswith(f.get("prefix", ""))), None)
    if rule is None:
        return None
    rule["n"] -= 1
    headers = {"Retry-After": str(rule["retry_after"])} if rule.get("retry_after") else {}
    return int(rule.get("status", 503)), headers


def bitrix_reply(method: str, form: dict) -> tuple[int, object]:
    if method == "user.get":
        return 200, {"result": BITRIX_USERS, "total": len(BITRIX_USERS)}
    if method == "telephony.externalcall.register":
        return 200, {"result": {"CALL_ID": f"ext.{form.get('EXTERNAL_CALL_ID', '')}", "CRM_CREATED_LEAD": None}}
    return 200, {"result": True}


def amo_reply(method: str, path: str, data) -> tuple[int, object]:
    if method == "GET" and path == "/api/v4/users":
        return 200, {"_embedded": {"users": AMO_USERS}}
    if path == "/api/v4/calls":
        call = (data or [{}])[0]
        if call.get("phone") in _state["known"]:
            return 200, {"_embedded": {"calls": [{"id": 1, "uniq": call.get("uniq")}]}}
        return 200, {"_embedded": {"errors": [{"code": 404, "title": "Contact not found"}], "calls": []}}
    if path == "/api/v4/leads/unsorted/sip":
        return 200, {"_embedded": {"unsorted": [{"uid": "u1"}]}}
    return 404, {"title": "Not found"}


def route(method: str, path: str, headers, parsed: dict) -> tuple[int, dict, object]:
    failure = injected_failure(path)
    if failure:
        return failure[0], failure[1], {"error": "INJECTED", "error_description": "proof"}
    if path.startswith("/rest/"):
        name = path.rsplit("/", 1)[-1].removesuffix(".json")
        status, body = bitrix_reply(name, parsed.get("form") or {})
        return status, {}, body
    if path.startswith("/api/v4/"):
        if headers.get("Authorization") != f"Bearer {AMO_TOKEN}":
            return 401, {}, {"title": "Unauthorized"}
        status, body = amo_reply(method, path, parsed.get("json"))
        return status, {}, body
    return 404, {}, {"error": "not_found"}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload, headers: dict | None = None) -> None:
        data = json.dumps(payload).encode()
        self.send_response(status)
        for key, value in {"Content-Type": "application/json", **(headers or {})}.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle(self, method: str) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0") or 0))
        path = urlsplit(self.path).path
        if path == "/_requests":
            with _lock:
                return self._send(200, list(_requests))
        if path == "/_config":
            with _lock:
                _state.update(json.loads(body or b"{}"))
            return self._send(200, {"ok": True})
        if path == "/_reset":
            with _lock:
                _requests.clear()
                _state.update({"fail": [], "known": []})
            return self._send(200, {"ok": True})
        parsed = _parse(body, self.headers.get("Content-Type", ""))
        with _lock:
            status, headers, payload = route(method, path, self.headers, parsed)
            _requests.append({"path": path, "method": method, "status": status, "t": time.time(),
                              "auth": self.headers.get("Authorization"), **parsed})
        self._send(status, payload, headers)

    def do_GET(self) -> None:  # noqa: N802
        self._handle("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._handle("POST")

    def log_message(self, *args) -> None:
        return None


if __name__ == "__main__":
    ThreadingHTTPServer((sys.argv[1], int(sys.argv[2])), Handler).serve_forever()
