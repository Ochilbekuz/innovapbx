import socket, hashlib, re, sys

def md5(s): return hashlib.md5(s.encode()).hexdigest()

HOST = sys.argv[1] if len(sys.argv) > 1 else "innova-smoke-ast"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5060
LOCAL_PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 5080
USERNAME = sys.argv[4] if len(sys.argv) > 4 else "101"
PASSWORD = sys.argv[5] if len(sys.argv) > 5 else "TestSecret12345"
EXPIRES = sys.argv[6] if len(sys.argv) > 6 else "3600"
# CONTACT_PORT: Contact sarlavhasida e'lon qilinadigan port (masalan, allaqachon
# boshqa jarayon — SIPp UAS — tinglab turgan port). LOCAL_PORT esa shu REGISTER
# UDP socket'ining o'z porti (ikkisi bir xil bo'lsa, "Address already in use"
# xatosi chiqadi, chunki UAS allaqachon shu portni band qilgan).
CONTACT_PORT = int(sys.argv[7]) if len(sys.argv) > 7 else LOCAL_PORT

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", LOCAL_PORT))
sock.settimeout(5)

def send_register(cseq, auth_header=None):
    # branch RFC 3261 bo'yicha GLOBAL noyob bo'lishi SHART — faqat cseq'ga bog'lab
    # qo'yilsa (foydalanuvchi nomisiz), bir nechta UAS bir vaqtda ro'yxatdan
    # o'tayotganda bitta branch ikkita turli REGISTER so'roviga to'g'ri kelib qolishi
    # mumkin; Asterisk buni ALLAQACHON yakunlangan tranzaksiyaning takror yuborilgan
    # nusxasi deb hisoblab, HECH QANDAY javob qaytarmaydi (sinovda topilgan va
    # Asterisk pjsip logger orqali tasdiqlangan haqiqiy race holati).
    branch = f"z9hG4bK-reg-{USERNAME}-{cseq}"
    lines = [
        f"REGISTER sip:{HOST}:{PORT} SIP/2.0",
        f"Via: SIP/2.0/UDP 0.0.0.0:{LOCAL_PORT};branch={branch}",
        f"From: <sip:{USERNAME}@{HOST}>;tag=regtag",
        f"To: <sip:{USERNAME}@{HOST}>",
        f"Call-ID: register-only-{USERNAME}",
        f"CSeq: {cseq} REGISTER",
        f"Contact: <sip:{USERNAME}@0.0.0.0:{CONTACT_PORT}>",
        "Max-Forwards: 70",
        f"Expires: {EXPIRES}",
    ]
    if auth_header:
        lines.append(auth_header)
    lines.append("Content-Length: 0")
    lines.append("")
    lines.append("")
    msg = "\r\n".join(lines)
    sock.sendto(msg.encode(), (HOST, PORT))
    # Eski/qoldiq kontaktlarga yuborilgan "qualify" OPTIONS so'rovlari xuddi
    # shu portga tushib qolishi mumkin (sinovda topilgan poyga holati) —
    # ularni rad etib, faqat REGISTER'ga tegishli SIP javobini kutamiz.
    while True:
        data, addr = sock.recvfrom(65535)
        text = data.decode(errors="replace")
        if text.startswith("SIP/2.0"):
            return text
        # so'rov (masalan OPTIONS) kelgan bo'lsa — e'tiborsiz qoldiramiz

def parse_challenge(resp):
    realm = re.search(r'realm="([^"]+)"', resp).group(1)
    nonce = re.search(r'nonce="([^"]+)"', resp).group(1)
    opaque_m = re.search(r'opaque="([^"]+)"', resp)
    return realm, nonce, (opaque_m.group(1) if opaque_m else None)

uri = f"sip:{HOST}:{PORT}"
r1 = send_register(1)
if not r1.startswith("SIP/2.0 401"):
    print("UNEXPECTED first response:", r1[:200]); sys.exit(1)
realm, nonce, opaque = parse_challenge(r1)
ha1 = md5(f"{USERNAME}:{realm}:{PASSWORD}")
ha2 = md5(f"REGISTER:{uri}")
nc, cnonce, qop = "00000001", "sippcnonce1", "auth"
resp = md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}")
auth_h = (f'Authorization: Digest username="{USERNAME}",realm="{realm}",nonce="{nonce}",'
          f'uri="{uri}",response="{resp}",cnonce="{cnonce}",nc={nc},qop={qop},algorithm=MD5')
if opaque:
    auth_h += f',opaque="{opaque}"'
r2 = send_register(2, auth_h)
sock.close()
if r2.startswith("SIP/2.0 200"):
    print(f"REGISTER OK: {USERNAME} contact 0.0.0.0:{CONTACT_PORT} expires={EXPIRES}")
    sys.exit(0)
else:
    print("REGISTER FAILED:", r2[:300])
    sys.exit(1)
