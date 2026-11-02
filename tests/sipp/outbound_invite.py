"""Faqat sinov uchun: ICHKI raqam (PJSIP ekstensiya) sifatida REGISTER (digest,
`register_only.py` bilan BIR XIL qolip) qiladi, so'ngra XUDDI SHU socket/port
orqali (Asterisk `endpoint_identifier_order = ip,...` — registratsiya
Contact manzili bilan keyingi so'rovlarni bog'laydi) autentifikatsiyalangan
INVITE yuboradi — m1b-contract.md bo'lim 9 ssenariy 1-3 (chiquvchi marshrut,
xalqaro bloklash, PIN DTMF) uchun ICHKI RAQAMDAN chiquvchi qo'ng'iroqni
HAQIQIY SIP darajasida isbotlaydi (API orqali emas).

DTMF — SIP INFO (application/dtmf-relay, `uac_ivr_dtmf.xml` BILAN BIR XIL
uslub) — PIN marshrutlarida `Read(INNOVA_PIN,beep,8)` kutayotgan raqamlarni
yuborish uchun (--dtmf 123456)."""
from __future__ import annotations

import argparse
import hashlib
import re
import socket
import sys
import time
import uuid


def md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def parse_challenge(resp: str) -> tuple[str, str, str | None]:
    realm = re.search(r'realm="([^"]+)"', resp).group(1)
    nonce = re.search(r'nonce="([^"]+)"', resp).group(1)
    opaque_m = re.search(r'opaque="([^"]+)"', resp)
    return realm, nonce, (opaque_m.group(1) if opaque_m else None)


def digest_response(username: str, password: str, method: str, uri: str, realm: str, nonce: str) -> tuple[str, str, str, str]:
    ha1 = md5(f"{username}:{realm}:{password}")
    ha2 = md5(f"{method}:{uri}")
    nc, cnonce, qop = "00000001", "sippcnonce1", "auth"
    resp = md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}")
    return resp, nc, cnonce, qop


def auth_header(username: str, realm: str, nonce: str, uri: str, resp: str, nc: str, cnonce: str, qop: str,
                 opaque: str | None) -> str:
    h = (f'Authorization: Digest username="{username}",realm="{realm}",nonce="{nonce}",'
         f'uri="{uri}",response="{resp}",cnonce="{cnonce}",nc={nc},qop={qop},algorithm=MD5')
    if opaque:
        h += f',opaque="{opaque}"'
    return h


class OutboundCaller:
    def __init__(self, host: str, port: int, local_port: int, username: str, password: str) -> None:
        self.host, self.port, self.local_port = host, port, local_port
        self.username, self.password = username, password
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", local_port))
        self.sock.settimeout(8)
        # MUHIM (M1c'da topilgan): Via branch HAR so'rov uchun YAGONA bo'lishi
        # SHART (RFC 3261 §8.1.1.7). ILGARI `z9hG4bK-info-{cseq}` barcha
        # qo'ng'iroqlarda BIR XIL edi — PJSIP non-INVITE tranzaksiyani UDP'da
        # 32 s (Timer J) saqlaydi, shu oraliqdagi KEYINGI qo'ng'iroqning
        # INFO'si «retransmissiya» deb 200 OK bilan javob olardi, lekin DTMF
        # dialogga YETMASDI (`Read()` timeout). m1b ssenariy 3'dagi
        # qayta-urinish halqasi aynan shu belgining oqibati edi.
        self._branch_tag = f"{local_port}-{uuid.uuid4().hex[:10]}"

    def _send_recv_final(self, msg: str) -> list[str]:
        self.sock.sendto(msg.encode(), (self.host, self.port))
        responses: list[str] = []
        while True:
            try:
                data, _ = self.sock.recvfrom(65535)
            except socket.timeout:
                break
            text = data.decode(errors="replace")
            if not text.startswith("SIP/2.0"):
                continue  # OPTIONS kabi so'rovlar — e'tiborsiz
            responses.append(text)
            code = int(text.split(" ", 2)[1])
            if code >= 200:
                break
        return responses

    def register(self, expires: str = "3600") -> bool:
        uri = f"sip:{self.host}:{self.port}"

        # MUHIM (bu segmentda topilgan, SHU SKRIPTdagi xato): Call-ID/From-tag
        # ILGARI faqat username'ga bog'liq bo'lib, bitta skript ichida (yoki
        # ketma-ket ishga tushirilgan bir nechta jarayonda) BIR XIL usernameга
        # qayta REGISTER qilinganda (masalan m1b-proof.sh ssenariy 1/2/3'da har
        # biri o'z OutboundCaller nusxasini yaratadi) IKKI MUSTAQIL jarayon
        # BIR XIL (Call-ID, From-tag, CSeq=1,2) juftligini ishlatardi -- PJSIP
        # buni ESKI (allaqachon qayta ishlangan) dialogning TAKRORI deb hisoblab,
        # ikkinchi REGISTER'ga JAVOB BERMAY qoldirardi ("javob yo'q"). Tuzatish:
        # local_port'ni Call-ID/tag'ga qo'shib, har bir jarayon/nusxa uchun
        # NOYOB dialog identitetini kafolatlaymiz (haqiqiy UA'lar ham har doim
        # shunday qiladi).
        def build(cseq: int, auth: str | None) -> str:
            lines = [
                f"REGISTER {uri} SIP/2.0",
                f"Via: SIP/2.0/UDP 0.0.0.0:{self.local_port};branch=z9hG4bK-reg-{self._branch_tag}-{cseq}",
                f"From: <sip:{self.username}@{self.host}>;tag=regtag-{self.local_port}",
                f"To: <sip:{self.username}@{self.host}>",
                f"Call-ID: register-{self.username}-{self.local_port}",
                f"CSeq: {cseq} REGISTER",
                f"Contact: <sip:{self.username}@0.0.0.0:{self.local_port}>",
                "Max-Forwards: 70",
                f"Expires: {expires}",
            ]
            if auth:
                lines.append(auth)
            lines += ["Content-Length: 0", "", ""]
            return "\r\n".join(lines)

        r1 = self._send_recv_final(build(1, None))
        if not r1 or not r1[-1].startswith("SIP/2.0 401"):
            print(f"REGISTER FAILED (1-qadam): {r1[-1][:120] if r1 else 'javob yo‘q'}")
            return False
        realm, nonce, opaque = parse_challenge(r1[-1])
        resp, nc, cnonce, qop = digest_response(self.username, self.password, "REGISTER", uri, realm, nonce)
        auth = auth_header(self.username, realm, nonce, uri, resp, nc, cnonce, qop, opaque)
        r2 = self._send_recv_final(build(2, auth))
        ok = bool(r2) and r2[-1].startswith("SIP/2.0 200")
        if not ok:
            print(f"REGISTER FAILED (2-qadam): {r2[-1][:120] if r2 else 'javob yo‘q'}")
        return ok

    def invite(self, dialed: str) -> list[str]:
        # MUHIM: Call-ID'ga local_port qo'shilgan -- aks holda BIR XIL
        # username+dialed juftligi bilan ketma-ket chaqirilgan ikki mustaqil
        # test (masalan ssenariy 3'da "7001234567" ikki marta -- xato va
        # to'g'ri PIN bilan) BIR XIL Call-ID'ni ishlatib, PJSIP ikkinchi
        # INVITE'ni ESKI (BYE bilan tugagan) dialogning davomi/takrori deb
        # chalkashtirib yuborishi mumkin edi (register()dagi bilan BIR XIL
        # sabab, shu segmentda tuzatildi).
        self.call_id = f"outbound-invite-{self.username}-{dialed}-{self.local_port}"
        self.to_uri = f"sip:{dialed}@{self.host}:{self.port}"

        def build(cseq: int, auth: str | None) -> str:
            lines = [
                f"INVITE {self.to_uri} SIP/2.0",
                f"Via: SIP/2.0/UDP 0.0.0.0:{self.local_port};branch=z9hG4bK-inv-{self._branch_tag}-{cseq}",
                f"From: <sip:{self.username}@{self.host}>;tag=invtag-{self.local_port}",
                f"To: <sip:{dialed}@{self.host}>",
                f"Call-ID: {self.call_id}",
                f"CSeq: {cseq} INVITE",
                f"Contact: <sip:{self.username}@0.0.0.0:{self.local_port}>",
                "Max-Forwards: 70",
                "Content-Type: application/sdp",
            ]
            if auth:
                lines.append(auth)
            # `sdp_ip`/`rtp_port` — M1c `vm_caller.py` haqiqiy RTP yuboradi
            # (standart qiymatlar avvalgi xatti-harakat bilan AYNAN bir xil).
            ip, port = getattr(self, "sdp_ip", "0.0.0.0"), getattr(self, "rtp_port", 10000)
            sdp = (f"v=0\r\no=uac 1 1 IN IP4 {ip}\r\ns=-\r\nc=IN IP4 {ip}\r\nt=0 0\r\n"
                   f"m=audio {port} RTP/AVP 0\r\na=rtpmap:0 PCMU/8000\r\n")
            lines.append(f"Content-Length: {len(sdp)}")
            # IKKI bo'sh qator kerak (sarlavha/tana orasidagi ajratuvchi "\r\n\r\n"
            # — bitta "" bilan join qilinganda faqat BIR "\r\n" hosil bo'ladi,
            # natijada SDP sarlavha sifatida o'qilib PJSIP uni rad etadi/tashlaydi).
            lines.append("")
            lines.append("")
            return "\r\n".join(lines) + sdp

        self._invite_cseq = 1
        r1 = self._send_recv_final(build(1, None))
        if r1 and r1[-1].startswith("SIP/2.0 401"):
            realm, nonce, opaque = parse_challenge(r1[-1])
            resp, nc, cnonce, qop = digest_response(self.username, self.password, "INVITE", self.to_uri, realm, nonce)
            auth = auth_header(self.username, realm, nonce, self.to_uri, resp, nc, cnonce, qop, opaque)
            self._invite_cseq = 2
            r2 = self._send_recv_final(build(2, auth))
            self._last_invite_resp = r2[-1] if r2 else ""
            # MUHIM (bu segmentda topilgan, SHU SKRIPTdagi xato): dialog
            # ichidagi KEYINGI so'rovlar (INFO/BYE) uchun CSeq RFC 3261
            # bo'yicha KETMA-KET O'SIB BORISHI SHART. ILGARI `bye()` faqat
            # `self._invite_cseq + 1`ni ishlatardi -- agar oldin BIR NECHTA
            # INFO (DTMF) yuborilgan bo'lsa (ularning CSeq'i main()dagi
            # tashqi hisoblagich orqali 3,4,5...dan boshlanardi), BYE'ning
            # CSeq'i ULARDAN KICHIK bo'lib qolardi (masalan 2), Asterisk buni
            # ESKI/eskirgan so'rov deb E'TIBORSIZ qoldirardi -- natijada
            # kanal HECH QACHON tugamay, "Congestion()"da OSILIB QOLARDI
            # (m1b-proof.sh ssenariy 3'da ikkala -- xato VA to'g'ri PIN --
            # kanal ham shu sabab osilib qolgani aniqlandi, 2026-10-28).
            # Tuzatish: BIR XIL, DOIM O'SIB BORUVCHI `self._cseq` hisoblagich
            # -- `send_dtmf_digit()`/`bye()` ENDI o'zlari oshiradi, tashqi
            # kodga CSeq TANLASH ishonib topshirilMAYDI.
            self._cseq = self._invite_cseq
            return r2
        self._last_invite_resp = r1[-1] if r1 else ""
        self._cseq = self._invite_cseq
        return r1

    def ack(self) -> None:
        # MUHIM (bu segmentda topilgan, SHU SKRIPTdagi xato): RFC 3261 BARCHA
        # final javoblarga (2xx HAM, NON-2xx HAM) ACK SHART qiladi -- ILGARI
        # faqat 200 OK uchun chaqirilardi (main()da). ACK yuborilmagan
        # NON-2xx (masalan 503) INVITE tranzaksiyasini PJSIP ACK kelguncha
        # ~32 soniya davomida QAYTA-QAYTA jo'natadi (Timer G/H) -- bu orqa
        # fonda davom etayotgan "retransmissiya bo'roni" keyingi, MUSTAQIL
        # test chaqiruvlarining PJSIP ishlov berish navbatini kechiktirib,
        # ularning javobini "yo'qolgan" ko'rsatishi shu segmentda aniqlandi.
        # From-tag ham `invite()`dagi bilan BIR XIL (local_port asosida)
        # bo'lishi SHART -- aks holda dialog mos kelmaydi.
        self.sock.sendto((
            f"ACK {self.to_uri} SIP/2.0\r\n"
            f"Via: SIP/2.0/UDP 0.0.0.0:{self.local_port};branch=z9hG4bK-ack\r\n"
            f"From: <sip:{self.username}@{self.host}>;tag=invtag-{self.local_port}\r\n"
            f"To: {self._to_header_with_tag()}\r\n"
            f"Call-ID: {self.call_id}\r\n"
            f"CSeq: {self._invite_cseq} ACK\r\n"
            "Max-Forwards: 70\r\nContent-Length: 0\r\n\r\n"
        ).encode(), (self.host, self.port))

    def _to_header_with_tag(self) -> str:
        m = re.search(r"^To:\s*(.+)$", self._last_invite_resp, re.MULTILINE)
        return m.group(1).strip() if m else f"<sip:unknown@{self.host}>"

    def send_dtmf_digit(self, digit: str) -> None:
        # MUHIM (shu segmentda topilgan): From-tag `invite()`/`ack()`dagi bilan
        # BIR XIL (`invtag-{local_port}`) bo'lishi SHART -- aks holda bu INFO
        # Asterisk uchun BOSHQA (mavjud bo'lmagan) dialogga tegishli deb
        # ko'rinadi va 481 "Call/Transaction Does Not Exist" bilan rad
        # etiladi, DTMF HECH QACHON `Read()`ga yetib bormaydi (m1b-proof.sh
        # ssenariy 3 -- PIN TO'G'RI bo'lsa ham doim Congestion() natijasi
        # shu sabab edi, 2026-10-28).
        # CSeq -- TASHQARIDAN emas, `self._cseq` ICHKI hisoblagichdan olinadi
        # (`invite()`dagi izohga qarang -- BYE bilan ketma-ketlik buzilishi
        # muammosi).
        self._cseq += 1
        cseq = self._cseq
        body = f"Signal={digit}\r\nDuration=250\r\n"
        msg = (
            f"INFO {self.to_uri} SIP/2.0\r\n"
            f"Via: SIP/2.0/UDP 0.0.0.0:{self.local_port};branch=z9hG4bK-info-{self._branch_tag}-{cseq}\r\n"
            f"From: <sip:{self.username}@{self.host}>;tag=invtag-{self.local_port}\r\n"
            f"To: {self._to_header_with_tag()}\r\n"
            f"Call-ID: {self.call_id}\r\n"
            f"CSeq: {cseq} INFO\r\n"
            "Max-Forwards: 70\r\nContent-Type: application/dtmf-relay\r\n"
            f"Content-Length: {len(body)}\r\n\r\n{body}"
        )
        self.sock.sendto(msg.encode(), (self.host, self.port))
        try:
            self.sock.recvfrom(65535)  # 200 OK kutish (natija e'tiborsiz — best-effort)
        except socket.timeout:
            pass

    def bye(self) -> None:
        # MUHIM (shu segmentda topilgan, `send_dtmf_digit()`dagi bilan BIR
        # XIL sabab): From-tag `invite()` BILAN BIR XIL bo'lishi SHART,
        # aks holda Asterisk BYE'ni 481 bilan rad etadi -- kanal HECH QACHON
        # tugamaydi va keyingi (--fresh bo'lmagan) ishga tushirishlarda
        # "osilib qolgan" kanallar to'planib qoladi (qo'lda `core show
        # channels` orqali aniqlangan: bir necha daqiqa oldingi chaqiruvlar
        # hali "Up" holatda turgan edi).
        # CSeq -- ILGARI `self._invite_cseq + 1` ishlatilardi, BU INFO
        # (DTMF) so'rovlaridan KEYIN chaqirilganda CSeq'ni ORQAGA
        # QAYTARARDI (masalan INFO'lar 3..7 ishlatgandan keyin BYE=2) --
        # Asterisk buni eskirgan/retransmissiya deb E'TIBORSIZ qoldirib,
        # kanal "Congestion()"da OSILIB QOLARDI (`send_dtmf_digit()`dagi
        # izohga qarang, 2026-10-28). Endi `self._cseq` ICHKI, DOIM
        # O'SUVCHI hisoblagichdan olinadi.
        self._cseq += 1
        msg = (
            f"BYE {self.to_uri} SIP/2.0\r\n"
            f"Via: SIP/2.0/UDP 0.0.0.0:{self.local_port};branch=z9hG4bK-bye-{self._branch_tag}\r\n"
            f"From: <sip:{self.username}@{self.host}>;tag=invtag-{self.local_port}\r\n"
            f"To: {self._to_header_with_tag()}\r\n"
            f"Call-ID: {self.call_id}\r\n"
            f"CSeq: {self._cseq} BYE\r\n"
            "Max-Forwards: 70\r\nContent-Length: 0\r\n\r\n"
        )
        self.sock.sendto(msg.encode(), (self.host, self.port))
        try:
            self.sock.recvfrom(65535)
        except socket.timeout:
            pass

    def close(self) -> None:
        self.sock.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("host")
    p.add_argument("port", type=int)
    p.add_argument("local_port", type=int)
    p.add_argument("username")
    p.add_argument("password")
    p.add_argument("dialed")
    p.add_argument("--dtmf", default="", help="Javobdan keyin SIP INFO orqali yuboriladigan raqamlar")
    p.add_argument("--hold-ms", type=int, default=1500, help="BYE yuborishdan oldin kutish (ms)")
    p.add_argument("--no-register", action="store_true",
                    help="REGISTER qilmasdan to'g'ridan-to'g'ri INVITE yuborish -- "
                         "endpoint `identify_by=username` bo'lsa REGISTER SHART EMAS "
                         "(Asterisk digest'ni Authorization sarlavhasidan to'g'ridan-to'g'ri "
                         "tekshiradi). Bitta ichki raqamga QATOR-QATOR mustaqil jarayonlarda "
                         "ketma-ket REGISTER qilish AOR `max_contacts` chegarasini tezda "
                         "to'ldirib, PJSIP registrator javobini vaqtincha yo'qotadigan "
                         "beqarorlikka olib kelishi shu segmentda aniqlangan -- bu sof "
                         "sinov-infratuzilma muammosi (mahsulot kodida EMAS), shu bayroq bilan "
                         "chetlab o'tiladi.")
    args = p.parse_args()

    caller = OutboundCaller(args.host, args.port, args.local_port, args.username, args.password)
    try:
        if not args.no_register and not caller.register():
            print("FINAL: REGISTER_FAILED")
            return 1
        responses = caller.invite(args.dialed)
        if not responses:
            print("FINAL: NO_RESPONSE")
            return 1
        final = responses[-1]
        status_line = final.splitlines()[0]
        code = int(status_line.split(" ", 2)[1])
        print(f"INVITE_FINAL: {status_line}")
        if code == 200:
            caller.ack()
            if args.dtmf:
                time.sleep(0.8)
                for digit in args.dtmf:
                    caller.send_dtmf_digit(digit)
                    # MUHIM (shu segmentda topilgan): har bir SIP INFO
                    # "Duration=250"(ms) bilan jo'natiladi -- navbatdagi
                    # raqam shu davr TUGAMASDAN yuborilsa, Asterisk ICHKI
                    # DTMF emulyatsiyasida ikkala signalni BIR-BIRIGA
                    # ustma-ust tushib, biri YO'QOLISHI (chan_pjsip/
                    # core DTMF begin-end freymlari to'qnashuvi) sinovda
                    # kuzatilgan -- `Read(INNOVA_PIN,...)` ba'zan 4
                    # o'rniga 3 raqam qabul qilib qolardi
                    # (m1b-proof.sh ssenariy 3, 2026-10-28). 0.3s oraliq
                    # 250ms davomiylikdan atigi 50ms uzoq bo'lib, bu
                    # chegara juda tor edi -- 0.5s'ga oshirildi (250ms'dan
                    # yetarlicha uzoq xavfsiz farq).
                    time.sleep(0.5)
            time.sleep(args.hold_ms / 1000)
            caller.bye()
            print("FINAL: 200")
            return 0
        caller.ack()  # RFC 3261 -- non-2xx final javoblar ham ACK talab qiladi
        print(f"FINAL: {code}")
        return 0
    finally:
        caller.close()


if __name__ == "__main__":
    sys.exit(main())
