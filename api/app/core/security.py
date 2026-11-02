"""Parol hashlash va JWT tokenlar.

Manba: callcenter/backend/app/core/security.py (bcrypt + python-jose,
passlib ishlatilmaydi). Moslashtirish: user_id — UUID (str), "typ" maydoni
access/refresh ni ajratadi, `jti` refresh tokenni bazada bitta marta ishlatish
uchun ham kerak bo'ladi (rotatsiya).
"""
from __future__ import annotations

import hashlib
import re
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

_BCRYPT_MAX_BYTES = 72
_ROUNDS = 12

_COMMON = {
    "password", "parol", "123456", "12345678", "qwerty", "admin", "admin123",
    "letmein", "welcome", "iloveyou",
}


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt(rounds=_ROUNDS)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.checkpw(pw, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def validate_password(password: str, *, min_length: int | None = None) -> list[str]:
    """Parolni tekshiradi. Bo'sh ro'yxat = parol yaroqli."""
    min_length = min_length or settings.password_min_length
    errors: list[str] = []
    if len(password) < min_length:
        errors.append(f"Parol kamida {min_length} ta belgidan iborat bo'lsin")
    if len(password.encode("utf-8")) > _BCRYPT_MAX_BYTES:
        errors.append("Parol juda uzun (72 baytdan oshmasin)")
    if not re.search(r"[a-z]", password):
        errors.append("Kamida bitta kichik harf bo'lsin")
    if not re.search(r"[A-Z]", password):
        errors.append("Kamida bitta katta harf bo'lsin")
    if not re.search(r"\d", password):
        errors.append("Kamida bitta raqam bo'lsin")
    if password.lower() in _COMMON:
        errors.append("Bu parol juda oson topiladi — boshqasini tanlang")
    return errors


# --------------------------------------------------------------------------
# SIP sirlari — Asterisk realtime parolidan farqli, foydalanuvchi ko'rmaydi
# --------------------------------------------------------------------------
_SIP_ALPHABET = string.ascii_letters + string.digits


def generate_sip_secret(length: int = 20) -> str:
    """16+ belgili, lug'atda yo'q, taxmin qilib bo'lmaydigan SIP paroli."""
    if length < 16:
        length = 16
    return "".join(secrets.choice(_SIP_ALPHABET) for _ in range(length))


# --------------------------------------------------------------------------
# JWT
# --------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(payload: dict, ttl: timedelta, token_type: str) -> str:
    to_encode = payload.copy()
    to_encode.update({
        "iat": int(_now().timestamp()),
        "exp": int((_now() + ttl).timestamp()),
        "typ": token_type,
        "jti": uuid.uuid4().hex,
    })
    return jwt.encode(to_encode, settings.require_secret_key(), algorithm=settings.jwt_algorithm)


def create_access_token(*, user_id: str, tenant_id: str, role: str,
                         permissions: list[str]) -> str:
    ttl = timedelta(minutes=settings.access_token_ttl_min)
    return _encode(
        {"sub": user_id, "tenant_id": tenant_id, "role": role, "perms": permissions},
        ttl, "access",
    )


def create_refresh_token(*, user_id: str) -> tuple[str, str]:
    """(token, token_hash) qaytaradi — bazada faqat hash saqlanadi."""
    ttl = timedelta(days=settings.refresh_token_ttl_days)
    token = _encode({"sub": user_id}, ttl, "refresh")
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def decode_token(token: str, *, expected_type: str = "access") -> dict | None:
    try:
        payload = jwt.decode(token, settings.require_secret_key(), algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if payload.get("typ") != expected_type:
        return None
    return payload
