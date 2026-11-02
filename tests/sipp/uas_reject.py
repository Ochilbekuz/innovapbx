"""Faqat sinov uchun: trunk-UAS rolini o'ynaydi, LEKIN har qanday INVITE'ga
DARHOL 503 Service Unavailable bilan javob beradi (pure Python, `sip-tester`
paketi kerak emas) — m1b-contract.md bo'lim 9 ssenariy 1 ("trunk A UAS 503
qaytaradi") uchun `uas_reject_503.xml` (SIPp)ning bir xil vazifali, lekin
tashqi paketsiz muqobili.

MUHIM (bu segmentda jonli isbotda topilgan race-condition): Asterisk IP-rejim
trunk kontaktini `qualify_frequency`/`max_initial_qualify_time` bo'yicha
davriy OPTIONS bilan "probe" qiladi — agar bu OPTIONS'ga JAVOB BERILMASA,
kontakt holati "Unavailable"ga o'tadi va keyingi HAQIQIY Dial() PJSIP
darajasida "Could not create dialog to invalid URI ..." bilan DARHOL
muvaffaqiyatsiz bo'ladi (sinov tomonidagi ishonchsizlik, mahsulot xatosi
EMAS). Shu sabab OPTIONS so'rovlarini 200 OK bilan e'tiborsiz qoldirib,
FAQAT INVITE'ga 503 bilan javob beramiz — skript istalgan son OPTIONS'dan
keyin ham to'g'ri ishlaydi."""
import socket
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5060
MAX_SECONDS = float(sys.argv[3]) if len(sys.argv) > 3 else 30.0

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# SO_REUSEADDR: ketma-ket ssenariylar orasida eski tinglovchi hali to'liq
# yopilmagan bo'lsa ham yangisi DARHOL bog'lana olishi uchun (`uas_log_and_
# answer.py`dagi bilan BIR XIL sabab — "Address already in use").
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((HOST, PORT))
sock.settimeout(MAX_SECONDS)


def headers_of(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.split("\r\n")[1:]:
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip().lower()] = v.strip()
    return out


def reply(h: dict[str, str], addr, status: str, tag: str) -> None:
    resp = (
        f"SIP/2.0 {status}\r\n"
        f"Via: {h.get('via', '')}\r\n"
        f"From: {h.get('from', '')}\r\n"
        f"To: {h.get('to', '')};tag={tag}\r\n"
        f"Call-ID: {h.get('call-id', '')}\r\n"
        f"CSeq: {h.get('cseq', '')}\r\n"
        "Content-Length: 0\r\n\r\n"
    )
    sock.sendto(resp.encode(), addr)


try:
    while True:
        try:
            data, addr = sock.recvfrom(65535)
        except socket.timeout:
            print("TIMEOUT: INVITE hech qachon kelmadi")
            sys.exit(1)
        text = data.decode(errors="replace")
        line0 = text.splitlines()[0]
        h = headers_of(text)
        if line0.startswith("OPTIONS"):
            reply(h, addr, "200 OK", "qualify01")  # qualify probe -- e'tiborsiz
            continue
        if not line0.startswith("INVITE"):
            continue
        print(f"REQUEST_LINE: {line0}")
        reply(h, addr, "503 Service Unavailable", "uasrej01")
        print("SENT: 503 Service Unavailable")
        break
finally:
    sock.close()
