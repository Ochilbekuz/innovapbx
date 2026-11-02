"""API originate (m3b-contract.md §4) — `to` va `external_id` OQ RO'YXAT tekshiruvi + AMI maydonlari.

VoxBridge saboq: AMI so'roviga foydalanuvchi matni faqat oq ro'yxatdagi belgilar bilan kiradi —
CR/LF (AMI header in'ektsiyasi), `,` (Variable ajratgichi), `;`/`@`/`/` (kanal sintaksisi) rad etiladi.
Avval ichki raqam jiringlaydi; javob bergach `<code>-originate` konteksti `to`ni odatiy chiquvchi
qoidalar (toll-fraud, xalqaro blok, caller-id) bilan teradi.
"""
from __future__ import annotations

import re

from app.services.sip_identity import pjsip_interface

_FORMATTING = re.compile(r"[ \-().]")
_TO_RE = re.compile(r"\+?[0-9*#]{1,32}")
_EXTERNAL_ID_RE = re.compile(r"[A-Za-z0-9_.:-]{1,64}")
RING_TIMEOUT_MS = 30000


class InvalidNumber(ValueError):
    pass


class InvalidExternalId(ValueError):
    pass


def validate_to(raw: str) -> str:
    """`+998 90 123-45-67` → `998901234567`; faqat `[0-9+*#]` (formatlash belgilari olib tashlanadi), ≤ 32."""
    compact = _FORMATTING.sub("", raw)
    if not _TO_RE.fullmatch(compact):
        raise InvalidNumber(raw)
    return compact.lstrip("+")


def validate_external_id(raw: str | None) -> str | None:
    if raw is None:
        return None
    if not _EXTERNAL_ID_RE.fullmatch(raw):
        raise InvalidExternalId(raw)
    return raw


def originate_fields(code: str, extension: str, to: str, *, request_id: str, external_id: str | None) -> dict[str, str]:
    # `Channel` endi tenant kod prefiksisiz (sip_identity.endpoint_id,
    # m-sip-login-plain-number); `Context` o'zgarmaydi (tenant bo'yicha).
    return {
        "Channel": pjsip_interface(extension),
        "Context": f"{code}-originate",
        "Exten": to,
        "Priority": "1",
        "CallerID": f'"{to}" <{to}>',
        "Timeout": str(RING_TIMEOUT_MS),
        "Async": "true",
        "ChannelId": request_id,
        "Variable": f"INNOVA_ORIGIN=api,INNOVA_EXTID={external_id or ''},INNOVA_ORIG_EXT={extension}",
    }
