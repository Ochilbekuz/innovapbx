"""Faqat sinov uchun: PJSIP AOR `qualify_frequency` (OPTIONS keepalive)
so'rovlariga 200 OK bilan javob beradi, shunda Asterisk kontaktni
"Reachable" deb belgilaydi — aks holda Dial() "invalid URI"/"No route to
destination" bilan muvaffaqiyatsiz tugaydi (replica/build-log.md T07).
Qisqa umr: belgilangan soniyadan keyin yoki bitta OPTIONS javobidan so'ng
chiqib ketadi, shunda xuddi shu portni SIPp UAS egallab olishi mumkin."""
import socket
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5080
MAX_SECONDS = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, PORT))
sock.settimeout(MAX_SECONDS)

try:
    while True:
        data, addr = sock.recvfrom(65535)
        text = data.decode(errors="replace")
        if not text.startswith("OPTIONS"):
            continue
        lines = text.split("\r\n")
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, _, v = line.partition(":")
                headers[k.strip().lower()] = v.strip()
        resp = (
            "SIP/2.0 200 OK\r\n"
            f"Via: {headers.get('via', '')}\r\n"
            f"From: {headers.get('from', '')}\r\n"
            f"To: {headers.get('to', '')}\r\n"
            f"Call-ID: {headers.get('call-id', '')}\r\n"
            f"CSeq: {headers.get('cseq', '')}\r\n"
            "Content-Length: 0\r\n\r\n"
        )
        sock.sendto(resp.encode(), addr)
        print(f"OPTIONS -> 200 OK ({addr})")
except socket.timeout:
    pass
finally:
    sock.close()
