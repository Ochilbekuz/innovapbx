"""Faqat sinov uchun: trunk-UAS rolini o'ynaydi (uas_only.xml bilan bir xil
oqim — Ringing/200/ACK/pauza/BYE/200), LEKIN qabul qilingan INVITE'ning
Request-URI va From sarlavhasini STDOUT'ga chiqaradi — m1b-contract.md
bo'lim 9 ssenariy 1 ("UAS B qabul qilgan INVITE'da Request-URI = ...,
From/PAI'da route CallerID") buni tashqaridan (log orqali) tasdiqlash
uchun.

MUHIM (jonli isbotda topilgan race-condition, `uas_reject.py`dagi bilan BIR
XIL sabab): Asterisk IP-rejim trunk kontaktini davriy OPTIONS bilan "probe"
qiladi -- javobsiz qolsa kontakt "Unavailable"ga o'tib, HAQIQIY Dial()
PJSIP darajasida darhol muvaffaqiyatsiz bo'ladi. Shu sabab OPTIONS'larni 200
OK bilan e'tiborsiz qoldirib, FAQAT INVITE kutilgan vaziyatda asosiy
oqimga o'tamiz."""
import socket
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5060
MAX_SECONDS = float(sys.argv[3]) if len(sys.argv) > 3 else 30.0

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# SO_REUSEADDR: oldingi chaqiruvning tinglovchisi BYE kelishini kutib hali
# yopilmagan bo'lsa ham (Asterisk BYE'ni ikkinchi oyoqqa biroz kechikib
# yuboradi -- m1b-proof.sh'da ketma-ket ssenariylar orasida shu sabab
# "Address already in use" chiqishi sinovda topilgan), yangi tinglovchi
# bir xil portga DARHOL bog'lana olsin.
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


def send_response(h: dict[str, str], addr, status: str, body: str = "", extra_headers: str = "") -> None:
    resp = (
        f"SIP/2.0 {status}\r\n"
        f"Via: {h.get('via', '')}\r\n"
        f"From: {h.get('from', '')}\r\n"
        f"To: {h.get('to', '')};tag=uaslog01\r\n"
        f"Call-ID: {h.get('call-id', '')}\r\n"
        f"CSeq: {h.get('cseq', '')}\r\n"
        f"{extra_headers}"
        f"Content-Length: {len(body)}\r\n\r\n{body}"
    )
    sock.sendto(resp.encode(), addr)


try:
    while True:
        data, addr = sock.recvfrom(65535)
        text = data.decode(errors="replace")
        request_line = text.splitlines()[0]
        h = headers_of(text)
        if request_line.startswith("OPTIONS"):
            send_response(h, addr, "200 OK")  # qualify probe -- e'tiborsiz
            continue
        if not request_line.startswith("INVITE"):
            continue
        break
    print(f"REQUEST_LINE: {request_line}")
    print(f"FROM: {h.get('from', '')}")
    print(f"PAI: {h.get('p-asserted-identity', '(yo‘q)')}")

    send_response(h, addr, "180 Ringing")
    sdp = ("v=0\r\no=uas 1 1 IN IP4 0.0.0.0\r\ns=-\r\nc=IN IP4 0.0.0.0\r\nt=0 0\r\n"
           "m=audio 20000 RTP/AVP 0\r\na=rtpmap:0 PCMU/8000\r\n")
    send_response(h, addr, "200 OK", body=sdp,
                  extra_headers=f"Contact: <sip:uaslog@0.0.0.0:{PORT}>\r\nContent-Type: application/sdp\r\n")

    # ACK kutish (boshqa trafikni e'tiborsiz qoldirish)
    while True:
        data, _ = sock.recvfrom(65535)
        if data.decode(errors="replace").startswith("ACK"):
            break
    # BYE kutish
    while True:
        data, bye_addr = sock.recvfrom(65535)
        text2 = data.decode(errors="replace")
        if text2.startswith("BYE"):
            send_response(headers_of(text2), bye_addr, "200 OK")
            break
except socket.timeout:
    print("TIMEOUT: INVITE hech qachon kelmadi")
    sys.exit(1)
finally:
    sock.close()
