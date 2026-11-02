"""M3a §5.1/§5.7 isboti: `/sip-ws` darvozasi va WS orqali SIP REGISTER (faqat stdlib — xostda
qo'shimcha paket talab qilmaydi).

  m3a_ws.py probe <ws_url>
      -> "HTTP <kod> <Sec-WebSocket-Protocol|->"   (faqat handshake)
  m3a_ws.py register <ws_url> <auth_user> <sip_uri> <parol> <n>
      -> "HTTP 101 sip" + har urinish uchun "REGISTER <yakuniy kod>"
         (401 challenge -> digest bilan qayta; parol noto'g'ri bo'lsa yakuniy kod 401/403)
"""
from __future__ import annotations

import base64
import hashlib
import os
import random
import re
import socket
import string
import struct
import sys
from urllib.parse import urlsplit

SIP_DOMAIN = "innova"


def rnd(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


class WsClient:
    def __init__(self, url: str, timeout: float = 5.0) -> None:
        parts = urlsplit(url)
        self.sock = socket.create_connection((parts.hostname, parts.port or 80), timeout=timeout)
        path = parts.path + (f"?{parts.query}" if parts.query else "")
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((
            f"GET {path} HTTP/1.1\r\nHost: {parts.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: sip\r\n\r\n"
        ).encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            head += chunk
        lines = head.split(b"\r\n\r\n", 1)[0].decode(errors="replace").split("\r\n")
        self.status = int(lines[0].split()[1]) if lines and len(lines[0].split()) > 1 else 0
        hdrs = {k.strip().lower(): v.strip() for k, _, v in (ln.partition(":") for ln in lines[1:])}
        self.protocol = hdrs.get("sec-websocket-protocol", "-")

    def send(self, text: str) -> None:
        data = text.encode()
        mask = os.urandom(4)
        n = len(data)
        head = struct.pack("!BB", 0x81, 0x80 | n) if n < 126 else struct.pack("!BBH", 0x81, 0xFE, n)
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("ws yopildi")
            buf += chunk
        return buf

    def recv(self) -> str:
        while True:
            b0, b1 = self._exact(2)
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack("!H", self._exact(2))[0]
            elif n == 127:
                n = struct.unpack("!Q", self._exact(8))[0]
            payload = self._exact(n)
            if b0 & 0x0F == 0x1:
                return payload.decode(errors="replace")
            if b0 & 0x0F == 0x8:
                raise ConnectionError("ws close")

    def close(self) -> None:
        self.sock.close()


def register_msg(uri: str, cseq: int, call_id: str, tag: str, auth: str | None = None) -> str:
    lines = [
        f"REGISTER sip:{SIP_DOMAIN} SIP/2.0",
        f"Via: SIP/2.0/WS {rnd()}.invalid;branch=z9hG4bK{rnd(12)}",
        "Max-Forwards: 70", f"To: <{uri}>", f"From: <{uri}>;tag={tag}", f"Call-ID: {call_id}",
        f"CSeq: {cseq} REGISTER", f"Contact: <sip:{rnd()}@{rnd()}.invalid;transport=ws>;expires=60",
        "Expires: 60", "User-Agent: m3a-proof",
    ]
    if auth:
        lines.append(auth)
    return "\r\n".join([*lines, "Content-Length: 0"]) + "\r\n\r\n"


def digest(user: str, password: str, challenge: str) -> str:
    realm = re.search(r'realm="([^"]+)"', challenge).group(1)
    nonce = re.search(r'nonce="([^"]+)"', challenge).group(1)
    opaque = re.search(r'opaque="([^"]+)"', challenge)
    uri = f"sip:{SIP_DOMAIN}"
    ha1 = hashlib.md5(f"{user}:{realm}:{password}".encode()).hexdigest()
    ha2 = hashlib.md5(f"REGISTER:{uri}".encode()).hexdigest()
    cnonce, nc = rnd(16), "00000001"
    resp = hashlib.md5(f"{ha1}:{nonce}:{nc}:{cnonce}:auth:{ha2}".encode()).hexdigest()
    out = (f'Authorization: Digest username="{user}", realm="{realm}", nonce="{nonce}", uri="{uri}", '
           f'response="{resp}", algorithm=MD5, qop=auth, nc={nc}, cnonce="{cnonce}"')
    return out + (f', opaque="{opaque.group(1)}"' if opaque else "")


def status_of(msg: str) -> str:
    return msg.split("\r\n", 1)[0].split(" ")[1]


def register_once(ws: WsClient, user: str, uri: str, password: str) -> str:
    call_id, tag = rnd(20), rnd()
    ws.send(register_msg(uri, 1, call_id, tag))
    first = ws.recv()
    if status_of(first) != "401":
        return status_of(first)
    chal = next(ln for ln in first.split("\r\n") if ln.lower().startswith("www-authenticate"))
    ws.send(register_msg(uri, 2, call_id, tag, digest(user, password, chal)))
    return status_of(ws.recv())


def main(argv: list[str]) -> int:
    ws = WsClient(argv[1])
    print(f"HTTP {ws.status} {ws.protocol}")
    if argv[0] == "register" and ws.status == 101:
        user, uri, password, count = argv[2], argv[3], argv[4], int(argv[5])
        for _ in range(count):
            print(f"REGISTER {register_once(ws, user, uri, password)}")
    ws.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
