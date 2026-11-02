"""SIP identity — ichki raqamning yagona nomlash qoidasi (bir marta qaror
qilinadigan joy, "Laziness Protocol": bir qaror — bir joy).

Qaror (2026-11, m-sip-login-plain-number): endpoint/AOR/auth id va SIP
username = ichki raqamning o'zi (masalan `"103"`), tenant kod prefiksisiz
(FreePBX'dagidek). Sabab — tizimda doim BITTA tenant bo'ladi (`auth.py`
bootstrap'da yaratadi), shu sabab prefiks hech qanday to'qnashuvdan himoya
qilmaydi, faqat foydalanuvchiga ortiqcha qiyinchilik qo'shadi (telefonga
"t1-103" emas, "103" yozilishi kerak edi).

Trunk endpoint'lari (`{code}-trunk-{id}`) BUTUNLAY BOSHQA nom maydoni — bu
modulga tegishli emas, o'zgarishsiz qoladi (`app/services/trunk_health.py`).

Eski (prefiksli) kanal nomlari — `PJSIP/t1-103-...` — tarixiy CDR/yozuv
ma'lumotlarida hamon uchraydi (migratsiyadan oldingi qo'ng'iroqlar);
`extension_from_channel()` ikkala shaklni (eski va yangi) bir xil
ishonchlilik bilan tushunadi, chunki ichki raqam shakli (`[0-9*#]{2,10}`,
raqam/`*`/`#` bilan boshlanadi) va tenant kodi shakli (`[a-z][a-z0-9]{1,15}`,
harf bilan boshlanadi) hech qachon ustma-ust tushmaydi."""
from __future__ import annotations

import re

_TENANT_CODE = r"[a-z][a-z0-9]{1,15}"
_EXT_NUMBER = r"[0-9*#]{2,10}"
_IDENTITY_RE = re.compile(rf"^(?:{_TENANT_CODE}-)?({_EXT_NUMBER})(?:-[0-9a-f]+)?$")


def endpoint_id(number: str) -> str:
    """Ichki raqamning endpoint/AOR/auth id'si. Pythonning har qanday joyida
    `f"{code}-{number}"` o'rniga shu funksiya (yoki undan foydalanadigan
    `devices.endpoint_id()`) chaqirilsin — nomlash qoidasi faqat SHU YERDA
    o'zgaradi."""
    return number


def pjsip_interface(number: str) -> str:
    """AMI `Originate`/`QueuePause` kabi amallar uchun to'liq PJSIP kanal nomi."""
    return f"PJSIP/{endpoint_id(number)}"


def extension_from_channel(channel: str | None) -> str | None:
    """Kanal/qator matnidan ichki raqamni ajratadi — YANGI (`PJSIP/103-...`)
    VA ESKI (`PJSIP/t1-103-...`, yalang'och `t1-103`/`103`) shakllarning
    ikkisini ham tushunadi. Trunk oyog'i (`-trunk-` ichida) — `None`."""
    if not channel or "-trunk-" in channel:
        return None
    tail = channel.rsplit("/", 1)[-1]
    match = _IDENTITY_RE.match(tail)
    return match.group(1) if match else None
