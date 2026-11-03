"""M2a proof'i uchun SIP telefon (faqat sinov): ro'yxatdan o'tgan ext (UAS) va chaqiruvchi (UAC).

UAS (`serve`) — butun proof davomida BITTA jarayon (qayta REGISTER/kontakt
to'planishi yo'q). Har yangi INVITE'da rejim `mode_file` dan o'qiladi:
  ring            — faqat `180` (javob yo'q; CANCEL'ga 200 + 487);
  busy            — `486 Busy Here`;
  answer          — `200 OK` (SDP bilan);
  answer:<raqam>  — javob, ACK'dan so'ng dialog ICHIDA SIP INFO bilan DTMF
                    (`,` = 1 s pauza; masalan `answer:##,,203` — blind transfer).
Har hodisa logga qator: `INVITE n=.. from=.. ruri=.. mode=..`, `ANSWERED`,
`XFER_SENT`, `REQ BYE`, `REQ CANCEL`. Proof qator sonlari bo'yicha tekshiradi.

UAC (`call`) — `VmCaller` INVITE/ACK + RTP; gaplashish paytida masofadan BYE
kelsa 200 bilan javob beradi va o'z BYE'sini yubormaydi.

Foydalanish:
  python3 m2a_phone.py serve <user> <password|-> <port> <rtp_port> <mode_file> <seconds>
      (`-` — ro'yxatdan o'tmaydi: trunk UAS)
  python3 m2a_phone.py call <user> <password> <port> <rtp_port> <dialed> <talk_s> [dtmf] [dtmf_after_s]
"""
from __future__ import annotations

import socket
import struct
import sys
import time

from vm_caller import VmCaller, tone_payloads

_TAG = "m2aphone"


def _headers(msg: str) -> dict[str, str]:
    h: dict[str, str] = {}
    for line in msg.split("\r\n")[1:]:
        if not line:
            break
        k, sep, v = line.partition(":")
        if sep and k.strip().lower() not in h:
            h[k.strip().lower()] = v.strip()
    return h


def _uri_user(value: str) -> str:
    """`"x" <sip:202@host>;tag=..` -> `202`."""
    start = value.find("sip:")
    if start < 0:
        return ""
    rest = value[start + 4:]
    return rest.split("@", 1)[0].split(";", 1)[0].split(">", 1)[0]


def _contact_uri(value: str) -> str:
    if "<" in value:
        return value.split("<", 1)[1].split(">", 1)[0]
    return value.split(";", 1)[0]


def dtmf_plan(digits: str, start: float) -> list[tuple[float, str]]:
    """`##,,203` -> [(t, '#'), (t+.3, '#'), (t+2.6, '2'), ...] — `,` = 1 s pauza."""
    plan: list[tuple[float, str]] = []
    at = start
    for ch in digits:
        if ch == ",":
            at += 1.0
            continue
        plan.append((at, ch))
        at += 0.3
    return plan


class Dialog:
    def __init__(self, invite: str, addr, local_tag: str) -> None:
        h = _headers(invite)
        self.addr = addr
        self.call_id = h.get("call-id", "")
        self.remote = h.get("from", "")            # bizga nisbatan To
        self.local = f"{h.get('to', '')};tag={local_tag}"
        self.target = _contact_uri(h.get("contact", "")) or invite.split(" ", 2)[1]
        self.cseq = 0
        self.plan: list[tuple[float, str]] = []


class Phone(VmCaller):
    def __init__(self, user: str, password: str, port: int, rtp_port: int) -> None:
        super().__init__("asterisk", 5060, port, user, password, rtp_port=rtp_port, final_timeout_s=40)
        self.dialogs: dict[str, Dialog] = {}
        self.invites = 0
        self._info_n = 0

    # ------------------------------------------------------------------ UAS
    def _reply(self, request: str, addr, status: str, *, tag: str | None = None, sdp: bool = False,
               cseq_method: str | None = None) -> None:
        h = _headers(request)
        to = h.get("to", "")
        if tag and ";tag=" not in to:
            to = f"{to};tag={tag}"
        cseq = h.get("cseq", "")
        if cseq_method:
            cseq = f"{cseq.split(' ')[0]} {cseq_method}"
        body = self._sdp() if sdp else ""
        extra = (f"Contact: <sip:{self.username}@{self.sdp_ip}:{self.local_port}>\r\n"
                 "Content-Type: application/sdp\r\n") if sdp else ""
        resp = (f"SIP/2.0 {status}\r\nVia: {h.get('via', '')}\r\nFrom: {h.get('from', '')}\r\n"
                f"To: {to}\r\nCall-ID: {h.get('call-id', '')}\r\nCSeq: {cseq}\r\n{extra}"
                f"Content-Length: {len(body)}\r\n\r\n{body}")
        self.sock.sendto(resp.encode(), addr)

    def _sdp(self) -> str:
        ip = self.sdp_ip
        return (f"v=0\r\no=uas 1 1 IN IP4 {ip}\r\ns=-\r\nc=IN IP4 {ip}\r\nt=0 0\r\n"
                f"m=audio {self.rtp_port} RTP/AVP 0\r\na=rtpmap:0 PCMU/8000\r\n")

    def _on_invite(self, text: str, addr, mode_file: str) -> None:
        h = _headers(text)
        call_id = h.get("call-id", "")
        if ";tag=" in h.get("to", ""):  # dialog ichidagi re-INVITE
            self._reply(text, addr, "200 OK", sdp=True)
            return
        if call_id in self.dialogs:  # retransmissiya — e'tiborsiz
            return
        mode = _read_mode(mode_file)
        self.invites += 1
        tag = f"{_TAG}{self.invites}"
        print(f"INVITE n={self.invites} from={_uri_user(h.get('from', ''))} "
              f"ruri={text.split(' ', 2)[1]} mode={mode}", flush=True)
        # M9 A4 — Alert-Info/Call-Info sarlavhalarini kuzatish (intercom
        # avto-javob isboti uchun; `b(innova-predial-hdr^s^1)` ularni qo'shadi).
        alert_info = h.get("alert-info", "")
        call_info = h.get("call-info", "")
        if alert_info or call_info:
            print(f"HDR alert-info={alert_info!r} call-info={call_info!r}", flush=True)
        if mode == "busy":
            self.dialogs[call_id] = None  # type: ignore[assignment]
            self._reply(text, addr, "486 Busy Here", tag=tag)
            return
        self._reply(text, addr, "180 Ringing", tag=tag)
        if mode.startswith("answer"):
            dialog = Dialog(text, addr, tag)
            digits = mode.partition(":")[2]
            if digits:
                dialog.plan = dtmf_plan(digits, time.monotonic() + 1.5)
            self.dialogs[call_id] = dialog
            self._reply(text, addr, "200 OK", tag=tag, sdp=True)
            print("ANSWERED", flush=True)
        else:
            self.dialogs[call_id] = None  # type: ignore[assignment]  # jiringlayapti (CANCEL kutiladi)

    def _send_info(self, d: Dialog, digit: str) -> None:
        # Branch BUTUN jarayon bo'yicha yagona bo'lsin (dialog CSeq emas): aks holda keyingi
        # dialogdagi INFO PJSIP uchun «retransmissiya» (Timer J, 32 s) — DTMF yetib bormaydi.
        d.cseq += 1
        self._info_n += 1
        body = f"Signal={digit}\r\nDuration=250\r\n"
        msg = (f"INFO {d.target} SIP/2.0\r\n"
               f"Via: SIP/2.0/UDP {self.sdp_ip}:{self.local_port};branch=z9hG4bK-uasinfo-{self._branch_tag}-{self._info_n}\r\n"
               f"From: {d.local}\r\nTo: {d.remote}\r\nCall-ID: {d.call_id}\r\nCSeq: {d.cseq} INFO\r\n"
               f"Max-Forwards: 70\r\nContent-Type: application/dtmf-relay\r\n"
               f"Content-Length: {len(body)}\r\n\r\n{body}")
        self.sock.sendto(msg.encode(), d.addr)

    def _tick(self) -> None:
        now = time.monotonic()
        for d in self.dialogs.values():
            if d is None or not d.plan:
                continue
            while d.plan and d.plan[0][0] <= now:
                self._send_info(d, d.plan.pop(0)[1])
                if not d.plan:
                    print("XFER_SENT", flush=True)

    def _on_request(self, text: str, addr, mode_file: str) -> None:
        method = text.split(" ", 1)[0]
        call_id = _headers(text).get("call-id", "")
        if method == "INVITE":
            self._on_invite(text, addr, mode_file)
        elif method == "CANCEL":
            print("REQ CANCEL", flush=True)
            self._reply(text, addr, "200 OK")
            self._reply(text, addr, "487 Request Terminated", tag=f"{_TAG}{self.invites}", cseq_method="INVITE")
            self.dialogs.pop(call_id, None)
        elif method == "BYE":
            print("REQ BYE", flush=True)
            self._reply(text, addr, "200 OK")
            self.dialogs.pop(call_id, None)
        elif method != "ACK":
            self._reply(text, addr, "200 OK")

    def serve(self, mode_file: str, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        self.sock.settimeout(0.1)
        while time.monotonic() < deadline:
            self._tick()
            self._drain_rtp()
            try:
                data, addr = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            text = data.decode(errors="replace")
            method = text.split(" ", 1)[0]
            if method.startswith("SIP/") or not method.isalpha():
                continue
            self._on_request(text, addr, mode_file)

    # ------------------------------------------------------------------ UAC
    def talk(self, seconds: float, dtmf: str = "", dtmf_after_s: float = 1.0) -> tuple[int, bool]:
        """RTP yuboradi; masofadan BYE kelsa — 200 va to'xtaydi. Qaytaradi: (paketlar, remote_bye)."""
        if self.remote_rtp is None:
            raise RuntimeError("200 OK SDP topilmadi")
        ssrc, seq, ts, sent = 0x5A5A0001, 0, 0, 0
        frames = tone_payloads()
        plan = dtmf_plan(dtmf, time.monotonic() + dtmf_after_s)
        start = time.monotonic()
        self.sock.setblocking(False)
        try:
            while time.monotonic() - start < seconds:
                header = struct.pack("!BBHII", 0x80, 0, seq & 0xFFFF, ts & 0xFFFFFFFF, ssrc)
                self.rtp.sendto(header + next(frames), self.remote_rtp)
                seq, ts, sent = seq + 1, ts + 160, sent + 1
                self._drain_rtp()
                if self._remote_bye():
                    return sent, True
                if plan and plan[0][0] <= time.monotonic():
                    self.sock.setblocking(True)
                    self.sock.settimeout(1)
                    self.send_dtmf_digit(plan.pop(0)[1])
                    self.sock.setblocking(False)
                time.sleep(max(0.0, start + sent * 0.02 - time.monotonic()))
        finally:
            self.sock.setblocking(True)
            self.sock.settimeout(8)
        return sent, False

    def _remote_bye(self) -> bool:
        try:
            data, addr = self.sock.recvfrom(65535)
        except (BlockingIOError, OSError):
            return False
        text = data.decode(errors="replace")
        method = text.split(" ", 1)[0]
        if method.startswith("SIP/") or not method.isalpha():
            return False
        self._reply(text, addr, "200 OK")
        return method == "BYE"


def _read_mode(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip() or "ring"
    except FileNotFoundError:
        return "ring"


def _serve(argv: list[str]) -> int:
    user, password, port, rtp_port, mode_file, seconds = argv
    phone = Phone(user, password, int(port), int(rtp_port))
    if password != "-":
        print("REGISTER_RESULT:", "OK" if phone.register() else "FAIL", flush=True)
    else:
        print("REGISTER_RESULT: SKIP", flush=True)
    phone.serve(mode_file, float(seconds))
    phone.close()
    return 0


def _call(argv: list[str]) -> int:
    user, password, port, rtp_port, dialed, talk_s = argv[:6]
    dtmf = argv[6] if len(argv) > 6 else ""
    after = float(argv[7]) if len(argv) > 7 else 1.0
    phone = Phone(user, password, int(port), int(rtp_port))
    try:
        responses = phone.invite(dialed)
        final = responses[-1] if responses else "SIP/2.0 000 NO_RESPONSE"
        print("INVITE_FINAL:", final.splitlines()[0], flush=True)
        if responses:
            phone.ack()
        if final.startswith("SIP/2.0 200"):
            sent, remote_bye = phone.talk(float(talk_s), dtmf, after)
            print("RTP_SENT:", sent, flush=True)
            if remote_bye:
                print("REMOTE_BYE", flush=True)
            else:
                phone.bye()
                print("BYE_SENT", flush=True)
    finally:
        phone.close()
    return 0


if __name__ == "__main__":
    cmd, rest = sys.argv[1], sys.argv[2:]
    sys.exit(_serve(rest) if cmd == "serve" else _call(rest))
