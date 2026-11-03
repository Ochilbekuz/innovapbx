"""M10 Bo'lak B2 — 2FA (TOTP, RFC 6238) Pydantic sxemalari.

`app/schemas.py`dagi `UserOut`/`AuthResult`dan ALOHIDA (bu fayl faqat 2FA
oqimiga tegishli so'rov/javoblar) — asosiy auth sxemalari bilan
aralashtirmaslik uchun (ub-mode DRY emas, aniqlik uchun ajratish)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class TotpSetupOut(BaseModel):
    """`POST /me/2fa/setup` — sekret hali YOQILMAGAN (`totp_enabled_at` NULL
    qoladi, `enable` chaqirilmaguncha); qayta chaqirilsa yangi sekret beradi
    (eskisi bekor bo'ladi — faqat `enable` orqali tasdiqlangani kuchda)."""
    secret: str
    otpauth_uri: str


class TotpEnablePayload(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class TotpEnableOut(BaseModel):
    recovery_codes: list[str]


class TotpDisablePayload(BaseModel):
    """Kodni (yoki tiklash kodini) talab qiladi — faqat parol bilan o'chirish
    xavfli (sessiya o'g'irlansa 2FA'ni o'chirib qo'yish mumkin bo'lardi)."""
    code: str


class TotpRecoveryCodesOut(BaseModel):
    recovery_codes: list[str]


class LoginTotpPayload(BaseModel):
    challenge: str
    code: str = Field(min_length=1, max_length=20)  # 6 xonali KOD yoki "xxxx-xxxx" tiklash kodi


class Totp2faResetOut(BaseModel):
    """`POST /users/{id}/2fa/reset` (admin) — 2FA to'liq o'chiriladi, foydalanuvchi
    keyingi kirishda (agar siyosat talab qilsa) qaytadan ro'yxatdan o'tadi."""
    ok: bool = True
