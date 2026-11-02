"""M4a isbot «apparati» — haqiqiy telefon kabi: provizioning URL'idan config oladi (haqiqiy UA bilan), undagi
login/parol bilan REGISTER qiladi, `NOTIFY Event: check-sync` kelsa config'ni qayta olib qayta ro'yxatdan o'tadi.

Rejimlar (python:3.12-slim — faqat stdlib):
  fetch <url> <ua> <out>                       -> stdout: HTTP kodi; javob tanasi <out> ga
  creds <vendor> <file>                        -> stdout: "user<TAB>password<TAB>host<TAB>port"
  register <user> <pass> <host> <port> <lport> -> stdout: "REGISTER <kod>" (auth'dan keyingi yakuniy javob); exit 0 = 200
  burst <url> <ua> <n>                         -> stdout: n ta so'rov HTTP kodlari (bo'sh joy bilan)
  phone <vendor> <url> <ua> <lport> <log> <max_s> [reload_delay_s]
                                               -> fetch+register; NOTIFY/OPTIONS ga 200; check-sync -> (kechikish)
                                                  qayta fetch+register (haqiqiy apparat ham darhol yuklamaydi)
"""
from __future__ import annotations

import re
import socket
import sys
import time
import urllib.error
import urllib.request
import uuid
import xml.etree.ElementTree as ET

from outbound_invite import auth_header, digest_response, parse_challenge


# ------------------------------------------------------------------ HTTP
def fetch(url: str, ua: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


# ------------------------------------------------------------------ config -> login/parol
def _kv(text: str, sep: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if sep in line and not line.lstrip().startswith(("#", "<")):
            key, value = line.split(sep, 1)
            out[key.strip()] = value.strip()
    return out


def creds(vendor: str, body: bytes) -> tuple[str, str, str, int]:
    text = body.decode()
    if vendor == "yealink":
        kv = _kv(text, "=")
        return (kv["account.1.auth_name"], kv["account.1.password"], kv["account.1.sip_server.1.address"],
                int(kv["account.1.sip_server.1.port"]))
    if vendor == "grandstream":
        cfg = ET.fromstring(body).find("config")
        p = {el.tag: (el.text or "") for el in cfg}
        host, _, port = p["P47"].rpartition(":")
        return p["P35"], p["P34"], host, int(port)
    kv = _kv(text, ":")
    return kv["SIP1 Register User"], kv["SIP1 Register Pswd"], kv["SIP1 Register Addr"], int(kv["SIP1 Register Port"])


# ------------------------------------------------------------------ SIP
def _header(msg: str, name: str) -> str:
    m = re.search(rf"^{name}:\s*(.*)$", msg, re.M | re.I)
    return m.group(1).strip() if m else ""


def _status(msg: str) -> int:
    return int(msg.split(" ", 2)[1]) if msg.startswith("SIP/2.0") else 0


class Phone:
    def __init__(self, lport: int, log=None) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", lport))
        self.sock.settimeout(1.0)
        self.lport, self.log = lport, log or (lambda _m: None)
        self.call_id = f"m4a-{uuid.uuid4().hex}"
        self.cseq = 0
        self.notifies: list[str] = []

    def reply_ok(self, msg: str, addr) -> None:
        heads = "\r\n".join(f"{h}: {_header(msg, h)}" for h in ("Via", "From", "To", "Call-ID", "CSeq"))
        self.sock.sendto(f"SIP/2.0 200 OK\r\n{heads}\r\nContent-Length: 0\r\n\r\n".encode(), addr)

    def handle_request(self, msg: str, addr) -> None:
        """Kelgan so'rov (OPTIONS qualify, NOTIFY) -> 200; NOTIFY hodisasi navbatga."""
        self.reply_ok(msg, addr)
        if msg.startswith("NOTIFY "):
            event = _header(msg, "Event")
            self.log(f"NOTIFY Event: {event}")
            self.notifies.append(event)

    def _send_register(self, user: str, host: str, port: int, auth: str | None) -> str:
        self.cseq += 1
        lines = [f"REGISTER sip:{host}:{port} SIP/2.0",
                 f"Via: SIP/2.0/UDP 0.0.0.0:{self.lport};branch=z9hG4bK-{uuid.uuid4().hex}",
                 f"From: <sip:{user}@{host}>;tag={self.call_id[-8:]}", f"To: <sip:{user}@{host}>",
                 f"Call-ID: {self.call_id}", f"CSeq: {self.cseq} REGISTER",
                 f"Contact: <sip:{user}@0.0.0.0:{self.lport}>", "Max-Forwards: 70", "Expires: 600"]
        if auth:
            lines.append(auth)
        self.sock.sendto(("\r\n".join(lines) + "\r\nContent-Length: 0\r\n\r\n").encode(), (host, port))
        deadline = time.time() + 8
        while time.time() < deadline:
            try:
                data, addr = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            msg = data.decode(errors="replace")
            if msg.startswith("SIP/2.0"):
                if _header(msg, "CSeq").startswith(f"{self.cseq} "):
                    return msg
                continue
            self.handle_request(msg, addr)
        return ""

    def register(self, user: str, password: str, host: str, port: int) -> int:
        first = self._send_register(user, host, port, None)
        if _status(first) != 401:
            return _status(first)
        realm, nonce, opaque = parse_challenge(first)
        uri = f"sip:{host}:{port}"
        resp, nc, cnonce, qop = digest_response(user, password, "REGISTER", uri, realm, nonce)
        return _status(self._send_register(user, host, port, auth_header(user, realm, nonce, uri, resp, nc, cnonce,
                                                                        qop, opaque)))

    def poll(self) -> None:
        try:
            data, addr = self.sock.recvfrom(65535)
        except socket.timeout:
            return
        msg = data.decode(errors="replace")
        if not msg.startswith("SIP/2.0"):
            self.handle_request(msg, addr)


# ------------------------------------------------------------------ rejimlar
def _provision(phone: Phone, vendor: str, url: str, ua: str) -> None:
    code, body = fetch(url, ua)
    phone.log(f"FETCH {code}")
    if code != 200:
        return
    user, password, host, port = creds(vendor, body)
    phone.log(f"REGISTER {phone.register(user, password, host, port)} {user}")


def _phone(argv: list[str]) -> int:
    vendor, url, ua, lport, log_path, max_s = argv[0], argv[1], argv[2], int(argv[3]), argv[4], float(argv[5])
    delay = float(argv[6]) if len(argv) > 6 else 0.0

    def log(line: str) -> None:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(f"{line}\n")

    phone = Phone(lport, log)
    _provision(phone, vendor, url, ua)
    end = time.time() + max_s
    while time.time() < end:
        phone.poll()
        if phone.notifies:
            event = phone.notifies.pop(0)
            if event.lower() == "check-sync":
                time.sleep(delay)
                _provision(phone, vendor, url, ua)
    return 0


def main(argv: list[str]) -> int:
    mode, args = argv[0], argv[1:]
    if mode == "fetch":
        code, body = fetch(args[0], args[1])
        with open(args[2], "wb") as fh:
            fh.write(body)
        print(code)
        return 0
    if mode == "burst":
        print(" ".join(str(fetch(args[0], args[1])[0]) for _ in range(int(args[2]))))
        return 0
    if mode == "creds":
        with open(args[1], "rb") as fh:
            print("\t".join(str(v) for v in creds(args[0], fh.read())))
        return 0
    if mode == "register":
        code = Phone(int(args[4])).register(args[0], args[1], args[2], int(args[3]))
        print(f"REGISTER {code}")
        return 0 if code == 200 else 1
    if mode == "phone":
        return _phone(args)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
