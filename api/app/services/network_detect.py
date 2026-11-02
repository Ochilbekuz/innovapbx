"""Lokal tarmoq aniqlash — m1b-contract.md bo'lim 4 `detected.local_ips`/
`public_ip`. Qo'shimcha kutubxonasiz (faqat stdlib `socket`) — konteyner
ichida tashqi internetga chiqish KAFOLATLANMAGAN, shu sabab `public_ip`
har doim `None` (ochiq aytiladi — soxta/noto'g'ri qiymat o'rniga)."""
from __future__ import annotations

import socket


def detect_local_ips() -> list[str]:
    """Konteynerning o'z (ichki tarmoq) IP manzillari — UDP `connect()`
    HAQIQIY paket yubormaydi (yo'naltirish jadvali orqali manba IP'ni
    tanlaydi), shu sabab internet yo'qligida ham ishlaydi."""
    ips: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            ips.append(sock.getsockname()[0])
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in ips and ip != "127.0.0.1":
                ips.append(ip)
    except OSError:
        pass
    return ips


def detect_public_ip() -> str | None:
    """Tashqi xizmatga murojaat qilmaydi (sir/tarmoq siyosati talab qilmaydi
    uchun qasddan) — shu sabab doim `None`; admin `external_ip`ni QO'LDA
    kiritadi (`PATCH /settings/sip`)."""
    return None
