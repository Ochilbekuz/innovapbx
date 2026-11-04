"""Ichki raqamni terish — BARCHA kontaktlarga (bir raqamda bir nechta qurilma, `max_contacts>1`).

`Dial(PJSIP/<ep>)` Asterisk'da AOR'ning faqat BIRINCHI kontaktiga INVITE yuboradi (jonli isbot,
2026-11-04: ikkinchi qurilma faqat OPTIONS oldi). To'g'ri yo'l — `PJSIP_DIAL_CONTACTS(<ep>)`
(har kontakt `PJSIP/<ep>/<uri>`, `&` bilan). Hech kim ro'yxatda bo'lmasa — `PJSIP/<ep>`:
Dial CHANUNAVAIL qaytaradi, javobsiz/ovozli pochta oqimi avvalgidek.

Kontakt URI'da `:` bor — `${IF()}`/`ExecIf` shoxiga tushmasligi uchun URI faqat SHU subroutine
ichida ko'rinadi; chaqiruvchi qatorda faqat endpoint id. Natija `INNOVA_DIAL` ga `&<...>` bo'lib
qo'shiladi, terish — `${INNOVA_DIAL:1}` (`TARGETS`).
"""
from __future__ import annotations

SUBROUTINE = "innova-dial-contacts"
VAR = "INNOVA_DIAL"
TARGETS = f"${{{VAR}:1}}"


def reset_line() -> str:
    return f" same => n,Set({VAR}=)"


def add_endpoint_line(endpoint: str, *, when: str | None = None) -> str:
    """`when` — Asterisk ifodasi (masalan DND tekshiruvi); bo'lsa `GosubIf`."""
    call = f"{SUBROUTINE},s,1({endpoint})"
    if when is None:
        return f" same => n,Gosub({call})"
    return f" same => n,GosubIf($[{when}]?{call})"


def add_raw_line(target: str) -> str:
    """Kontakt emas manzil (`Local/...`) — to'plamga o'zgarishsiz qo'shiladi."""
    return f" same => n,Set({VAR}=${{{VAR}}}&{target})"


def endpoint_targets_lines(endpoint: str) -> list[str]:
    return [reset_line(), add_endpoint_line(endpoint)]


def context_lines() -> list[str]:
    return [
        f"[{SUBROUTINE}]",
        "exten => s,1,Set(LOCAL(C)=${PJSIP_DIAL_CONTACTS(${ARG1})})",
        " same => n,ExecIf($[${LEN(${C})}=0]?Set(C=PJSIP/${ARG1}))",
        f" same => n,Set({VAR}=${{{VAR}}}&${{C}})",
        " same => n,Return()",
    ]
