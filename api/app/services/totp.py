"""M10 Bo'lak B2 — TOTP (RFC 6238) va tiklash kodlari, faqat stdlib.

Sof funksiyalar: `hotp`/`totp_at`/`verify` tashqi kutubxonasiz (hashlib/hmac/
struct/base64/secrets) — birlik testlari uchun vaqtni tashqaridan beriladi
(`for_time`/`now_fn` emas, chaqiruvchi `int` soniya beradi), tasodifiy
tuzilish/sekret generatsiyasidan ajratilgan. Takror himoyasi (`last_step`)
state'ni bu modulda SAQLAMAYDI — chaqiruvchi (router) DB ustunini
(`users.totp_last_step`) solishtiradi/yozadi; bu yerda faqat qiymatni
hisoblash uchun "shu step allaqachon ishlatilganmi" predikati beriladi."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct

STEP_SECONDS = 30
DIGITS = 6
TOLERANCE_STEPS = 1


def generate_secret(length: int = 20) -> str:
    """Base32 sekret (RFC 4648, padding'siz) — standart TOTP uzunligi 20 bayt."""
    return base64.b32encode(secrets.token_bytes(length)).decode("ascii").rstrip("=")


def _decode_secret(secret_b32: str) -> bytes:
    padded = secret_b32.upper()
    padded += "=" * (-len(padded) % 8)
    return base64.b32decode(padded)


def hotp(secret_b32: str, counter: int, *, digits: int = DIGITS) -> str:
    """RFC 4226 HOTP — `counter` 8 baytli big-endian, HMAC-SHA1, dinamik kesish."""
    key = _decode_secret(secret_b32)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    chunk = digest[offset:offset + 4]
    code_int = (struct.unpack(">I", chunk)[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code_int).zfill(digits)


def step_for(unix_time: int, *, step_seconds: int = STEP_SECONDS) -> int:
    return unix_time // step_seconds


def totp_at(secret_b32: str, unix_time: int, *, step_seconds: int = STEP_SECONDS,
            digits: int = DIGITS) -> str:
    return hotp(secret_b32, step_for(unix_time, step_seconds=step_seconds), digits=digits)


def verify(secret_b32: str, code: str, unix_time: int, *, last_step: int | None,
           tolerance: int = TOLERANCE_STEPS, step_seconds: int = STEP_SECONDS,
           digits: int = DIGITS) -> int | None:
    """Kodni ±`tolerance` qadam ichida tekshiradi; `last_step`dan katta (yoki
    `None`) bo'lgan BIRINCHI mos qadamni qaytaradi (replay himoyasi — eski
    yoki qayta yuborilgan qadam rad etiladi), aks holda `None`."""
    if not code or not code.isdigit() or len(code) != digits:
        return None
    current = step_for(unix_time, step_seconds=step_seconds)
    for delta in range(-tolerance, tolerance + 1):
        step = current + delta
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(hotp(secret_b32, step, digits=digits), code):
            return step
    return None


def otpauth_uri(secret_b32: str, *, account: str, issuer: str = "Innova PBX") -> str:
    from urllib.parse import quote

    label = quote(f"{issuer}:{account}")
    return (f"otpauth://totp/{label}?secret={secret_b32}&issuer={quote(issuer)}"
            f"&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}")


def generate_recovery_codes(count: int = 10) -> list[str]:
    """`xxxx-xxxx` shaklida (katta/kichik harf yo'q — base32'dan, chalkashuvchi
    0/O/1/I belgilarsiz emas, lekin oddiylik uchun to'liq base32 alifbosi)."""
    codes = []
    for _ in range(count):
        raw = secrets.token_hex(4)
        codes.append(f"{raw[:4]}-{raw[4:]}")
    return codes
