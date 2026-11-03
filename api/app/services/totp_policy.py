"""M10 Bo'lak B2 — 2FA siyosati sof qoidalari (`system_settings.require_2fa`).

`'off'` — hech kimdan talab qilinmaydi; `'admins'` — faqat `ALL` ruxsatli
(admin) rol; `'all'` — hamma foydalanuvchi. Bu funksiyalar DB/HTTP'dan holi —
`deps.py`/`auth.py` chaqiradi."""
from __future__ import annotations

from typing import Literal

Require2faPolicy = Literal["off", "admins", "all"]

# `app/api/deps.py::get_current_user`da `must_enroll_2fa` tekshiruvi SHU
# marshrutlarga TEGMAYDI (2FA ro'yxatdan o'tish/o'zi uchun kerak bo'lgan
# minimal yo'l) — `/api/v1` prefiksi OLIB TASHLANGAN shaklda.
ENROLLMENT_ALLOWED_PREFIXES: tuple[str, ...] = ("/auth", "/me/2fa")


def is_enrollment_exempt_path(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in ENROLLMENT_ALLOWED_PREFIXES)


def must_enroll(policy: Require2faPolicy, *, is_admin: bool, totp_enabled: bool) -> bool:
    """`True` — foydalanuvchi 2FA'ni YOQMAGAN va siyosat uni talab qiladi."""
    if totp_enabled:
        return False
    if policy == "all":
        return True
    if policy == "admins":
        return is_admin
    return False


def requires_totp_challenge(*, totp_enabled: bool) -> bool:
    """Login paytida ikkinchi bosqich (kod) kerakmi — faqat foydalanuvchi
    o'zi 2FA'ni YOQGAN bo'lsa (siyosatdan qat'i nazar — siyosat FAQAT
    yoqishni MAJBUR qiladi, kod so'ralishini o'zi belgilamaydi)."""
    return totp_enabled
