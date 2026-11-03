"""Dialplan matn/raqam xavfsizligi — YAGONA joy (ub-mode «Laziness Protocol»:
bir qaror — bir joy). `app/schemas.py` (Pydantic, kirishda tekshiradi) VA
`app/services/compiler.py` + boshqa dialplan generatorlari (`dialplan_*.py`,
`moh.py`, `conference.py`, `parking*.py`, `feature_codes.py`, `voicemail.py`,
`sip_identity.py` — render vaqtida, IKKINCHI himoya chizig'i: CSV import/
FreePBX migratsiyasi schema'ni chetlab o'tishi mumkin) BIR XIL funksiyalardan
foydalanadi.

Xavf (CONFIRMED HIGH, dialplan injection): Asterisk `extensions.conf`da
`${...}` o'zgaruvchi/funksiya almashtirish SODIR BO'LADIGAN joy — `NoOp()`,
`Set()`, istalgan ilova argumenti — qo'ng'iroq KELGANDA (parse vaqtida emas)
baholanadi. Shu sabab:
  - erkin matn (ism, prefiks, label) — `sanitize_dialplan_text()`: boshqaruv
    belgilar (`\\r`, `\\n`, `\\x00` va h.k.) VA Asterisk uchun maxsus ma'noli
    belgilar (`$ { } [ ] ( ) , ; \\ " '` va orqa tirnoq) OLIB TASHLANADI,
    uzunlik cheklanadi;
  - raqam/naqsh maydonlari (DID, CallerID, `add_prefix`, Asterisk naqshi) —
    `is_dialplan_number()`: FAQAT tor belgi to'plamiga ruxsat (shu belgi
    to'plamida `$`/`{`/`}`/`(`/`)` umuman yo'q — o'zgaruvchi almashtirish
    sintaksisini QURISH IMKONSIZ).
"""
from __future__ import annotations

import re

DIALPLAN_TEXT_MAX_LEN = 128

# Boshqaruv belgilar (CR/LF/NUL va h.k.) — yangi `exten =>`/`same =>` qatori
# qo'shib yuborish (CRLF injection) shu yerda to'xtatiladi.
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
# Asterisk dialplan sintaksisida maxsus ma'noli belgilar: `$`/`{`/`}` —
# o'zgaruvchi/funksiya almashtirish, `(`/`)`/`,` — ilova argumentlari
# ajratuvchisi, `;` — izoh boshlanishi, `\`/`"`/`` ` `` — ifoda/qochish.
_FORBIDDEN_RE = re.compile(r"""[${}\[\](),;\\"'`]""")

# DID / CallerID raqami / `add_prefix` / Asterisk naqshi (m1b-contract.md
# naqsh sintaksisi: X/Z/N, `.`/`!`, `[range]`) + FreePBX-uslubidagi oldi
# pastki chiziq (`_998XXXXXXXXX`). `$`/`{`/`}`/`(`/`)` YO'Q — shu sabab
# bu belgi to'plami bilan o'zgaruvchi almashtirish sintaksisi qurilMAYDI.
DIALPLAN_NUMBER_PATTERN = r"^[0-9+*#_XNZ.!\[\]-]{1,40}$"
_NUMBER_RE = re.compile(DIALPLAN_NUMBER_PATTERN)


def sanitize_dialplan_text(value: str | None, *, max_len: int = DIALPLAN_TEXT_MAX_LEN) -> str:
    """Erkin matnni (ism, label, prefiks) dialplan ichida YOZISH UCHUN
    XAVFSIZ qiladi. Bo'sh/`None` -> bo'sh satr (chaqiruvchi f-string ichida
    muammosiz qo'shishi uchun)."""
    if not value:
        return ""
    cleaned = _CONTROL_RE.sub("", str(value))
    cleaned = _FORBIDDEN_RE.sub("", cleaned)
    return cleaned[:max_len]


def is_dialplan_number(value: str | None) -> bool:
    """DID/CID/callerid/`add_prefix`/Asterisk naqshi — ruxsat etilgan belgi
    to'plamiga mos keladi (bo'sh satr — MOS EMAS, chaqiruvchi kerak bo'lsa
    o'zi bo'shni alohida ruxsat qiladi)."""
    return bool(_NUMBER_RE.fullmatch(value or ""))


def has_control_chars(value: str | None) -> bool:
    """`app/schemas.py` kirish validatsiyasi UCHUN: ism/label kabi erkin matn
    maydonlarida CR/LF/NUL kabi boshqaruv belgilari BOR-YO'QLIGINI tekshiradi
    (CRLF dialplan injection — yangi `exten =>`/`same =>` qatori qo'shish —
    shu YERDA, kiritishda, rad etiladi; `sanitize_dialplan_text()` esa
    render vaqtidagi IKKINCHI himoya chizig'i, bu ikkisi BIR XIL belgi
    to'plamini ishlatadi)."""
    return bool(_CONTROL_RE.search(value or ""))
