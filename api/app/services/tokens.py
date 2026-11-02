"""Refresh tokenlarni bekor qilish. m2b-contract.md §3:
"Faolsizlantirish, rol yoki parol o'zgarishi -> shu foydalanuvchining refresh
tokenlari bekor (keyingi refresh 401)". `app/api/v1/users.py` (admin PATCH/DELETE)
VA `app/api/v1/auth.py` (`/auth/change-password`) shu funksiyani chaqiradi.

`revoke_all_refresh_tokens` -- m4b-contract.md §0: tiklashdan keyin BARCHA
tenant foydalanuvchilarining sessiyasi bekor (DB butunlay eski holatga qaytgan
bo'lishi mumkin, eski refresh tokenlar endi noma'lum/yaroqsiz bo'lishi mumkin)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RefreshToken, User


async def revoke_refresh_tokens(session: AsyncSession, user_id: str) -> None:
    """Hali bekor qilinmagan barcha tokenlarni bitta so'rovda yopadi (keyingi
    `/auth/refresh` 401 `invalid_token` qaytaradi — `revoked_at is not None`)."""
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc)),
    )


async def revoke_all_refresh_tokens(session: AsyncSession, tenant_id: str) -> None:
    """`revoke_refresh_tokens`ning tenant-keng versiyasi (`RefreshToken`da bevosita
    `tenant_id` ustuni yo'q -- `User` orqali bog'lanadi)."""
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id.in_(select(User.id).where(User.tenant_id == tenant_id)),
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc)),
    )
