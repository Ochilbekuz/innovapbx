"""Faqat sinov uchun: bitta INVITE yuboradi va BIRINCHI yakuniy (1xx dan
tashqari) javobni kutadi — m1a-proof.sh ssenariy 2 (`force_closed` ->
hangup yo'li, javob berilmagan kanal rad etilishi kerak). SIPp'ning qattiq
status-kod talabidan farqli, bu yerda FAQAT "200 EMAS"ligi tekshiriladi —
Asterisk'ning `Hangup()` qaytaradigan aniq SIP kodi (487/603/...) M1a
kontraktida belgilanmagan."""
import socket
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "asterisk"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5060
LOCAL_PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 5081
DID = sys.argv[4] if len(sys.argv) > 4 else "712099202"
LOCAL_IP = sys.argv[5] if len(sys.argv) > 5 else "0.0.0.0"

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", LOCAL_PORT))
sock.settimeout(10)

sdp = (
    f"v=0\r\no=uac 1 1 IN IP4 {LOCAL_IP}\r\ns=-\r\nc=IN IP4 {LOCAL_IP}\r\n"
    "t=0 0\r\nm=audio 40000 RTP/AVP 0\r\na=rtpmap:0 PCMU/8000\r\n"
)
msg = (
    f"INVITE sip:{DID}@{HOST}:{PORT} SIP/2.0\r\n"
    f"Via: SIP/2.0/UDP {LOCAL_IP}:{LOCAL_PORT};branch=z9hG4bK-invreject\r\n"
    f"From: <sip:trunkcaller@{LOCAL_IP}>;tag=rejtag\r\n"
    f"To: <sip:{DID}@{HOST}>\r\n"
    "Call-ID: invite-reject-check\r\n"
    "CSeq: 1 INVITE\r\n"
    f"Contact: <sip:trunkcaller@{LOCAL_IP}:{LOCAL_PORT}>\r\n"
    "Max-Forwards: 70\r\n"
    "Content-Type: application/sdp\r\n"
    f"Content-Length: {len(sdp)}\r\n\r\n{sdp}"
)
sock.sendto(msg.encode(), (HOST, PORT))

final = None
try:
    while True:
        data, _addr = sock.recvfrom(65535)
        text = data.decode(errors="replace")
        status_line = text.split("\r\n", 1)[0]
        code = int(status_line.split(" ", 2)[1]) if status_line.startswith("SIP/2.0") else 0
        if 100 <= code < 200:
            continue  # progress — final javobni kutamiz
        final = status_line
        break
except socket.timeout:
    pass
finally:
    sock.close()

if final is None:
    print("TIMEOUT: yakuniy javob kelmadi")
    sys.exit(1)
print(f"FINAL: {final}")
sys.exit(0 if "200" not in final else 1)
