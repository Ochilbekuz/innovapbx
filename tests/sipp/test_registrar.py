"""Faqat sinov uchun: Asterisk'ning OUTBOUND registratsiyasini (register-rejim
trunk, `ps_registrations`) qabul qiladigan soxta SIP registrar — m1b-contract.md
bo'lim 9 ssenariy 7 ("test registrar: SIPp UAS REGISTER->401->200").

Haqiqiy operator emas, shu sabab digest javobini TEKSHIRMAYDI (faqat
Authorization sarlavhasi BORLIGINI) — maqsad Asterisk'ning REGISTER/401/
REGISTER+Authorization/200 oqimini to'liq bosib o'tishini va natijada
`pjsip show registration` "Registered" ko'rsatishini isbotlash."""
import socket
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5060
MAX_SECONDS = float(sys.argv[3]) if len(sys.argv) > 3 else 30.0

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# SO_REUSEADDR: boshqa UAS skriptlaridagi bilan bir xil sabab -- ketma-ket
# ishga tushirishlar orasidagi portni DARHOL qayta egallash.
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((HOST, PORT))
sock.settimeout(MAX_SECONDS)

NONCE = "innova-test-nonce-1"
REALM = "innova-test-registrar"


def headers_of(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.split("\r\n")[1:]:
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip().lower()] = v.strip()
    return out


def reply(status: str, h: dict[str, str], addr, extra: str = "") -> None:
    resp = (
        f"SIP/2.0 {status}\r\n"
        f"Via: {h.get('via', '')}\r\n"
        f"From: {h.get('from', '')}\r\n"
        f"To: {h.get('to', '')}\r\n"
        f"Call-ID: {h.get('call-id', '')}\r\n"
        f"CSeq: {h.get('cseq', '')}\r\n"
        f"{extra}"
        "Content-Length: 0\r\n\r\n"
    )
    sock.sendto(resp.encode(), addr)


try:
    while True:
        data, addr = sock.recvfrom(65535)
        text = data.decode(errors="replace")
        if not text.startswith("REGISTER"):
            continue
        h = headers_of(text)
        if "authorization" not in h:
            reply("401 Unauthorized", h, addr,
                  f'WWW-Authenticate: Digest realm="{REALM}",nonce="{NONCE}",qop="auth"\r\n')
            print(f"REGISTER (1-qadam) -> 401 ({addr})")
        else:
            reply("200 OK", h, addr, f"Expires: {h.get('expires', '3600')}\r\n")
            print(f"REGISTER (2-qadam) -> 200 OK ({addr})")
except socket.timeout:
    pass
finally:
    sock.close()
