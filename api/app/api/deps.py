"""Umumiy FastAPI dependency'lar — sessiya, joriy foydalanuvchi, ruxsat tekshiruvi,
AMI mijozi. m0-contract.md «Ruxsatlar (M0)»."""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ApiError
from app.core.permissions import ALL, has_permission
from app.core.security import decode_token
from app.db.models import User
from app.db.session import SessionLocal
from app.services.ami import AmiClient

_UNAUTHORIZED = ApiError(401, "unauthorized", "Avtorizatsiya talab qilinadi")


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise _UNAUTHORIZED
    return header[len("Bearer "):].strip()


async def get_current_user(
    request: Request, session: AsyncSession = Depends(get_session),
) -> User:
    token = _bearer_token(request)
    payload = decode_token(token, expected_type="access")
    if payload is None:
        raise _UNAUTHORIZED
    user = await session.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise _UNAUTHORIZED
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not has_permission(user.role.permissions, ALL):
        raise ApiError(403, "forbidden", "Ruxsat yo'q")
    return user


_ami_singleton: AmiClient | None = None


def get_ami() -> AmiClient:
    global _ami_singleton
    if _ami_singleton is None:
        _ami_singleton = AmiClient(
            settings.ami_host, settings.ami_port, settings.ami_username, settings.ami_password,
        )
    return _ami_singleton
