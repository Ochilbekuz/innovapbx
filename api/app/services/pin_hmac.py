"""M9 B1: PIN to'plami — PIN ochiq matnda SAQLANMAYDI, faqat
`HMAC-SHA256(server sirri, pin)` ko'rinishida. bcrypt EMAS — chunki to'plam
ichida qaysi PIN mos kelganini ANIQ (tenglik bo'yicha) qidirish kerak,
bcrypt esa har safar boshqa tuz bilan hash qiladi va teng solishtirib bo'lmaydi.

Server sirri — mavjud `SECRET_KEY` (JWT uchun ishlatiladigan sir) qayta ishlatiladi,
yangi majburiy muhit o'zgaruvchisi qo'shmaslik uchun (`config.py::require_secret_key`).
"""
from __future__ import annotations

import hashlib
import hmac


def hash_pin(secret: str, pin: str) -> str:
    """`pin` (faqat raqamlar) uchun barqaror HMAC-SHA256 hex digest."""
    return hmac.new(secret.encode("utf-8"), pin.encode("utf-8"), hashlib.sha256).hexdigest()


def pin_matches(secret: str, pin: str, pin_hmac: str) -> bool:
    """Doimiy-vaqt solishtirish (timing-attack oldini olish uchun `compare_digest`)."""
    return hmac.compare_digest(hash_pin(secret, pin), pin_hmac)
