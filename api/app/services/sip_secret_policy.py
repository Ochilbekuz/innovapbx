"""SIP paroli siyosati (FreePBX-uslubida, foydalanuvchi o'zi belgilaydi) — nazorat
BITTA joyda (Laziness Protocol): `extensions.create_extension` VA `PUT .../secret`
ikkisi ham shu BITTA funksiyani chaqiradi (dryer, ikkinchi mustaqil mantiq yo'q).

Qoida: 8-64 belgi; faqat harf/raqam va `!@#$%^*_+=.,:-`; kamida bitta harf VA bitta
raqam; ichki raqamning o'zini (yoki uni o'z ichiga olgan qatorni) ishlatmaslik —
aks holda SIP parolini taxmin qilish oson bo'ladi (raqam ommaviy ma'lumot)."""
from __future__ import annotations

import re

from app.core.errors import ApiError

MIN_LENGTH = 8
MAX_LENGTH = 64
_ALLOWED_RE = re.compile(r"^[A-Za-z0-9!@#$%^*_+=.,:-]+$")
_LETTER_RE = re.compile(r"[A-Za-z]")
_DIGIT_RE = re.compile(r"\d")


def validate_sip_password(password: str, number: str) -> None:
    """Qoidabuzarlik — 422 `weak_password` (`field: "password"`, sababi o'zbekcha)."""
    if not (MIN_LENGTH <= len(password) <= MAX_LENGTH):
        raise ApiError(422, "weak_password",
                       f"Parol {MIN_LENGTH}-{MAX_LENGTH} belgidan iborat bo'lishi kerak", field="password")
    if not _ALLOWED_RE.fullmatch(password):
        raise ApiError(422, "weak_password",
                       "Parolda faqat lotin harflari, raqamlar va !@#$%^*_+=.,:- belgilari ruxsat etilgan",
                       field="password")
    if not (_LETTER_RE.search(password) and _DIGIT_RE.search(password)):
        raise ApiError(422, "weak_password", "Parolda kamida bitta harf VA bitta raqam bo'lishi kerak",
                       field="password")
    if number and number in password:
        raise ApiError(422, "weak_password", "Parol ichki raqamning o'zini o'z ichiga olmasligi kerak",
                       field="password")
