"""Soxta Telegram Bot API (faqat M1c proof): har so'rovni bir qator qilib
log faylga yozadi va `{"ok": true}` qaytaradi. `chat_id == "0"` -> 400
`chat not found` (`/settings/notify/test` 502 `notify_failed` ssenariysi).

    python3 fake_telegram.py 0.0.0.0 8081 /tmp/tg.log
Log qatori: `REQ path=/bot<token>/sendAudio chat_id=42 filename=201-msg0000.wav riff=1 bytes=N`
`sendMessage` (M2c §4 ogohlantirishlar, JSON `{"chat_id","text"}`) uchun qatorga
QO'SHIMCHA `text_b64=<base64(text)>` ham yoziladi (eski maydonlar/tartib
O'ZGARMAGAN — m1c-proof.sh grep'lari shu sabab buzilmaydi, faqat qator
OXIRIGA biror narsa qo'shiladi). Dekodlash uchun `scripts/lib/m2c_common.sh`
dagi `tg_text_of()`ga qarang."""
from __future__ import annotations

import base64
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST, PORT, LOG = sys.argv[1], int(sys.argv[2]), sys.argv[3]


def _field(body: bytes, name: str) -> str:
    m = re.search(rb'name="' + name.encode() + rb'"\r\n\r\n(.*?)\r\n', body, re.S)
    return m.group(1).decode(errors="replace") if m else ""


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 — http.server nomlash qoidasi
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        text_b64 = "-"
        if self.headers.get("Content-Type", "").startswith("application/json"):
            payload = json.loads(body or b"{}")
            chat_id = str(payload.get("chat_id", ""))
            text = payload.get("text")
            if text is not None:
                text_b64 = base64.b64encode(text.encode()).decode()
        else:
            chat_id = _field(body, "chat_id")
        fn = re.search(rb'filename="([^"]*)"', body)
        line = (f"REQ path={self.path} chat_id={chat_id} filename={fn.group(1).decode() if fn else '-'} "
                f"riff={int(b'RIFF' in body)} bytes={len(body)} text_b64={text_b64}\n")
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line)
        status, reply = (400, {"ok": False, "description": "Bad Request: chat not found"}) if chat_id == "0" \
            else (200, {"ok": True, "result": {"message_id": 1}})
        data = json.dumps(reply).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args) -> None:
        pass


HTTPServer((HOST, PORT), Handler).serve_forever()
