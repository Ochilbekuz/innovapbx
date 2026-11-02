"""M1c ovozli pochta proof'i uchun SIP chaqiruvchi: `OutboundCaller` ning
INVITE/ACK/INFO/BYE mantiqi + HAQIQIY RTP.

`OutboundCaller` SDP'da `0.0.0.0:10000` e'lon qiladi va RTP yubormaydi —
`VoiceMail()` yozish uchun audio kerak (aks holda `maxsilence`/`minsecs`
xabarni tashlaydi). Bu yerda SDP'da konteynerning o'z IP'si va RTP porti,
200 OK SDP'dan Asterisk RTP manzili olinadi va 20 ms li PCMU (sinus 440 Hz)
paketlari yuboriladi.

Foydalanish (proof heredoc'ida):
    from vm_caller import VmCaller
    c = VmCaller("asterisk", 5060, 5070, "trunk-caller", "unused", rtp_port=12000)
    r = c.invite("998712000001"); c.ack(); c.stream_rtp(14); c.bye(); c.close()
"""
from __future__ import annotations

import math
import re
import socket
import struct
import time

from outbound_invite import OutboundCaller

_PTIME_S = 0.02
_SAMPLES = 160  # 8 kHz * 20 ms


def _linear_to_ulaw(sample: int) -> int:
    bias, clip = 0x84, 32635
    sign = 0x80 if sample < 0 else 0
    sample = min(abs(sample), clip) + bias
    exponent = 7
    mask = 0x4000
    while exponent > 0 and not sample & mask:
        exponent -= 1
        mask >>= 1
    mantissa = (sample >> (exponent + 3)) & 0x0F
    return ~(sign | (exponent << 4) | mantissa) & 0xFF


def tone_payloads(freq: float = 440.0, amplitude: int = 8000):
    """Cheksiz 160 baytli PCMU kadrlari (uzluksiz faza)."""
    n = 0
    while True:
        yield bytes(_linear_to_ulaw(int(amplitude * math.sin(2 * math.pi * freq * (n + i) / 8000)))
                    for i in range(_SAMPLES))
        n += _SAMPLES


def parse_sdp_media(resp: str) -> tuple[str, int] | None:
    c = re.search(r"^c=IN IP4 (\S+)", resp, re.M)
    m = re.search(r"^m=audio (\d+)", resp, re.M)
    return (c.group(1), int(m.group(1))) if c and m else None


class VmCaller(OutboundCaller):
    def __init__(self, host: str, port: int, local_port: int, username: str, password: str, *,
                 rtp_port: int = 12000, final_timeout_s: float = 25.0) -> None:
        super().__init__(host, port, local_port, username, password)
        # Asterisk Dial() uzoq jiringlashi mumkin — yakuniy javobni kutish.
        self.sock.settimeout(final_timeout_s)
        self.sdp_ip = socket.gethostbyname(socket.gethostname())
        self.rtp_port = rtp_port
        self.rtp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rtp.bind(("0.0.0.0", rtp_port))
        self.rtp.setblocking(False)
        self.remote_rtp: tuple[str, int] | None = None

    def invite(self, dialed: str) -> list[str]:
        responses = super().invite(dialed)
        if responses and responses[-1].startswith("SIP/2.0 200"):
            self.remote_rtp = parse_sdp_media(responses[-1])
        self.sock.settimeout(8)
        return responses

    def stream_rtp(self, seconds: float, dtmf: str = "", dtmf_after_s: float = 1.0) -> int:
        """`seconds` davomida RTP yuboradi; `dtmf` — `dtmf_after_s` dan so'ng
        SIP INFO bilan (har raqam orasi 0.4 s). Qaytaradi: yuborilgan paketlar."""
        if self.remote_rtp is None:
            raise RuntimeError("200 OK SDP topilmadi")
        ssrc, seq, ts, sent = 0x1A2B3C4D, 0, 0, 0
        frames = tone_payloads()
        digits = list(dtmf)
        next_digit_at = dtmf_after_s
        start = time.monotonic()
        while (elapsed := time.monotonic() - start) < seconds:
            header = struct.pack("!BBHII", 0x80, 0, seq & 0xFFFF, ts & 0xFFFFFFFF, ssrc)
            self.rtp.sendto(header + next(frames), self.remote_rtp)
            seq, ts, sent = seq + 1, ts + _SAMPLES, sent + 1
            self._drain_rtp()
            if digits and elapsed >= next_digit_at:
                self.send_dtmf_digit(digits.pop(0))
                next_digit_at = elapsed + 0.4
            time.sleep(max(0.0, start + sent * _PTIME_S - time.monotonic()))
        return sent

    def ring_without_answer(self, seconds: float) -> dict[str, int]:
        """Ro'yxatdan o'tgan ext sifatida `seconds` davomida tinglaydi: INVITE'ga
        faqat `180 Ringing` (HECH QACHON 200 emas), CANCEL/NOTIFY(MWI)/OPTIONS/
        BYE'ga `200 OK`, INVITE yakuni uchun `487`. Qaytaradi: so'rovlar soni."""
        seen: dict[str, int] = {}
        deadline = time.monotonic() + seconds
        self.sock.settimeout(0.3)
        while time.monotonic() < deadline:
            try:
                data, addr = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            text = data.decode(errors="replace")
            method = text.split(" ", 1)[0]
            if method.startswith("SIP/") or not method.isalpha():
                continue
            seen[method] = seen.get(method, 0) + 1
            print(f"REQ {method}", flush=True)
            if method == "INVITE":
                self._respond(text, addr, "180 Ringing")
            elif method == "CANCEL":
                self._respond(text, addr, "200 OK")
                self._respond(text.replace("CANCEL", "INVITE", 1), addr, "487 Request Terminated", invite=True)
            elif method != "ACK":
                self._respond(text, addr, "200 OK")
        self.sock.settimeout(8)
        return seen

    def _respond(self, request: str, addr, status: str, *, invite: bool = False) -> None:
        h: dict[str, str] = {}
        for line in request.split("\r\n")[1:]:
            k, sep, v = line.partition(":")
            if sep and k.strip().lower() not in h:
                h[k.strip().lower()] = v.strip()
        cseq = h.get("cseq", "")
        if invite:
            cseq = cseq.split(" ")[0] + " INVITE"
        to = h.get("to", "")
        to = to if ";tag=" in to else f"{to};tag=vmring01"
        resp = (f"SIP/2.0 {status}\r\nVia: {h.get('via', '')}\r\nFrom: {h.get('from', '')}\r\n"
                f"To: {to}\r\nCall-ID: {h.get('call-id', '')}\r\n"
                f"CSeq: {cseq}\r\nContent-Length: 0\r\n\r\n")
        self.sock.sendto(resp.encode(), addr)

    def _drain_rtp(self) -> None:
        try:
            while self.rtp.recv(2048):
                pass
        except (BlockingIOError, OSError):
            pass

    def close(self) -> None:
        self.rtp.close()
        super().close()
