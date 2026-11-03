"""M10 Bo'lak B2 — foydalanuvchi TOTP kodini (yoki tiklash kodini) tekshirish,
DB bilan bog'liq qism. Sof hisob `app/services/totp.py`da; bu yerda faqat
`User.totp_secret_enc` (shifrlangan) ochish va `totp_last_step`/
`totp_recovery_hashes`ni YANGILASH (chaqiruvchi commit qiladi — bu funksiya
`flush`/`commit` qilmaydi, faqat `user` obyektini xotirada o'zgartiradi)."""
from __future__ import annotations

import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.db.models import User
from app.services.crypto import decrypt_secret
from app.services.totp import verify as totp_verify


async def verify_user_code(session: AsyncSession, user: User, code: str, *, now: int | None = None) -> bool:
    """`True` — kod (TOTP YOKI bir martalik tiklash kodi) to'g'ri; `user`
    obyektidagi mos maydon(lar) (`totp_last_step` yoki `totp_recovery_hashes`
    dan bir dona olib tashlanadi) shu YERDA yangilanadi (chaqiruvchi keyin
    `session.commit()` qiladi)."""
    if not user.totp_secret_enc:
        return False
    unix_time = now if now is not None else int(time.time())

    clean_code = code.strip()
    if clean_code.isdigit():
        secret = await decrypt_secret(session, user.totp_secret_enc)
        step = totp_verify(secret, clean_code, unix_time, last_step=user.totp_last_step)
        if step is not None:
            user.totp_last_step = step
            return True
        return False

    normalized = clean_code.lower()
    for stored_hash in list(user.totp_recovery_hashes or []):
        if verify_password(normalized, stored_hash):
            user.totp_recovery_hashes = [h for h in user.totp_recovery_hashes if h != stored_hash]
            return True
    return False


def hash_recovery_codes(codes: list[str]) -> list[str]:
    return [hash_password(c.lower()) for c in codes]
