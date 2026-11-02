"""M2c §2 — Asterisk `security` logger kanali faylini o'qish (tail) va
hujum hodisalarini ajratish. Sof funksiyalar (DB/AMI'siz) — unit testda
to'liq qoplanadi.

Jonli tekshirilgan format (Asterisk 22.10.1, PJSIP, andrius/asterisk:22,
2026-10-28 — `res_security_log.c`, `logger reload` qilingandan keyin
`[logfiles]`ga qo'shilgan absolyut yo'l fayliga yoziladi):

    [Oct 28 21:27:18] SECURITY[118] res_security_log.c: SecurityEvent="ChallengeResponseFailed",
    EventTV="2026-10-28T21:27:18.055+0000",Severity="Error",Service="PJSIP",EventVersion="1",
    AccountID="t1-202",SessionID="register-only-t1-202",LocalAddress="IPV4/UDP/172.21.0.4/5060",
    RemoteAddress="IPV4/UDP/172.21.0.5/5090",Challenge="...",Response="...",ExpectedResponse=""

MUHIM topilma (shartnoma "jonli tekshirilsin" deb so'ragan): bu build'da
`chan_sip.so` UMUMAN YO'Q (Asterisk 22'da legacy SIP kanali olib
tashlangan) va PJSIP modullari ichida (`strings res_pjsip*.so`) `InvalidAccountID`/
`InvalidPassword` satrlari BUTUNLAY yo'q — faqat asosiy `asterisk` binarida
(umumiy xavfsizlik-hodisa RO'YXATI nomlari sifatida, hech kim ko'tarmaydi).
Noto'g'ri parol HAM, mavjud bo'lmagan AccountID HAM bir xil — PJSIP
`endpoint_identifier_order` nomzod topa olmasa ham, barcha REGISTER'lar bir
xil raqamli challenge bilan "ChallengeResponseFailed"ga tushadi (hisob
enumeratsiyasidan himoya — Asterisk'ning o'zi shunday ishlaydi). Shu sabab
amalda FAQAT `ChallengeResponseFailed` chiqadi; qolgan ikkisi kelajakdagi
Asterisk versiyasi/boshqa kanal uchun FORWARD-COMPATIBLE qoldirilgan
(hech qanday qo'shimcha narx — shart oddiy to'plam a'zoligi).

Ikkinchi topilma: `FailedACL` (bloklangan IP'ning qayta urinishi) `security`
kanaliga UMUMAN yozilmaydi — PJSIP ACL rad etishi (`res_pjsip_acl.c`)
`messages.log`ga oddiy NOTICE/WARNING sifatida tushadi ("SIP ACL: Rejecting
... ACL '(BASELINE)'"), `ast_security_event_report()` chaqirilmaydi (bu —
faqat o'chirilgan `chan_sip.c`da bor edi). Shartnoma §0 manbani FAQAT
`security` kanali bilan chegaralagani uchun (Boundary Discipline) bu yerda
`messages.log` o'QILMAYDI — `sip_attack_stats.blocked` shu sabab PJSIP ACL
rad etishlaridan ODDIY holatda hech qachon oshmaydi (ochiq muammo, hisobotda
aytilgan); u faqat ban qo'yilgan ONISH LAHZADA hali ACL qayta yuklanmagan
oynada kelgan `ChallengeResponseFailed`larni "failures" o'rniga "blocked"
deb sanashda ishlatiladi (`app/services/sip_guard.py`)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

# Amalda FAQAT ChallengeResponseFailed chiqadi (tepaga qarang) — qolgan
# ikkisi forward-compat uchun.
COUNTABLE_KINDS = frozenset({"ChallengeResponseFailed", "InvalidAccountID", "InvalidPassword"})

_EVENT_RE = re.compile(r'SecurityEvent="(?P<kind>[^"]*)"')
_REMOTE_RE = re.compile(r'RemoteAddress="[^/"]*/(?P<transport>[^/"]*)/(?P<ip>[^/"]+)/\d+"')
_ACCOUNT_RE = re.compile(r'AccountID="(?P<account>[^"]*)"')
# M3a §0: WS va WSS bitta toifa — `security_events.transport='ws'` (nginx orqali keladi).
_TRANSPORTS = {"UDP": "udp", "TCP": "tcp", "TLS": "tls", "WS": "ws", "WSS": "ws"}


@dataclass(frozen=True)
class SecurityLogEvent:
    kind: str
    ip: str
    transport: str = "udp"
    account: str | None = None

    @property
    def via_websocket(self) -> bool:
        """WebRTC softfon (nginx `/sip-ws` orqali) — Asterisk nginx IP'sini ko'radi."""
        return self.transport == "ws"


def parse_security_line(line: str) -> SecurityLogEvent | None:
    """Bitta log qatorini ajratadi; mos kelmasa (boshqa hodisa turi,
    banner qatori, bo'sh qator, IP topilmagan) — `None`."""
    event_m = _EVENT_RE.search(line)
    if event_m is None or event_m.group("kind") not in COUNTABLE_KINDS:
        return None
    remote_m = _REMOTE_RE.search(line)
    if remote_m is None:
        return None
    account_m = _ACCOUNT_RE.search(line)
    return SecurityLogEvent(kind=event_m.group("kind"), ip=remote_m.group("ip"),
                            transport=_TRANSPORTS.get(remote_m.group("transport").upper(), "udp"),
                            account=account_m.group("account") if account_m else None)


@dataclass
class TailState:
    """Fayl o'qish holati — jarayon xotirasida, BITTA fon vazifa BITTA
    nusxada ishlatadi (Separate Before Serializing Shared State: bitta
    yozuvchi, umumiy holat shart emas)."""

    offset: int = 0
    inode: int | None = None
    started: bool = False


def read_new_lines(path: str, state: TailState) -> list[str]:
    """Oxirgi o'qishdan keyingi TO'LIQ (yangi qatorli) qatorlarni qaytaradi.

    Birinchi chaqiruvda fayl OXIRIGA sakraydi (m2c-contract.md §0: "API
    ishga tushganda — fayl oxiridan") — eski hodisalar qayta o'ynalmaydi.
    Fayl qisqarsa yoki inode o'zgarsa (log aylanishi/rotate) — boshidan
    o'qishga qaytadi. Fayl hali yo'q bo'lsa — bo'sh ro'yxat, holat
    o'zgarmaydi (keyingi chaqiruvda qayta urinadi)."""
    try:
        st = os.stat(path)
    except OSError:
        return []
    if not state.started:
        state.offset, state.inode, state.started = st.st_size, st.st_ino, True
        return []
    if state.inode != st.st_ino or st.st_size < state.offset:
        state.offset, state.inode = 0, st.st_ino
    if st.st_size == state.offset:
        return []
    with open(path, "rb") as fh:
        fh.seek(state.offset)
        chunk = fh.read()
    complete, sep, _rest = chunk.rpartition(b"\n")
    if not sep:
        return []  # qator hali to'liq yozilmagan — keyingi aylanishda davom etamiz
    state.offset += len(complete) + 1
    return complete.decode("utf-8", "replace").split("\n")
