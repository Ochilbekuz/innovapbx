"""Umumiy FastAPI dependency'lar — sessiya, joriy foydalanuvchi, ruxsat tekshiruvi,
AMI mijozi. m0-contract.md «Ruxsatlar (M0)», m7-roles-contract.md §1 (markaziy
hudud:action tekshiruvi)."""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ApiError
from app.core.permissions import check_access
from app.core.security import decode_token
from app.db.models import User
from app.db.session import SessionLocal
from app.services.ami import AmiClient

_API_PREFIX = "/api/v1"

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


def _route_template(request: Request) -> str:
    """Marshrut shabloni (`/extensions/{ext_id}` kabi, `/api/v1` OLIB
    TASHLANGAN) — `request.scope["route"].path` (FastAPI buni so'rov
    moslashgandan keyin to'ldiradi; dependency ichida ishlaydi)."""
    path = getattr(request.scope.get("route"), "path", request.url.path)
    if path.startswith(_API_PREFIX):
        path = path[len(_API_PREFIX):]
    return path or "/"


async def require_access(request: Request, user: User = Depends(get_current_user)) -> User:
    """201 ta `require_admin` chaqiruvini almashtiradi (m7-roles-contract.md
    §1): marshrut → hudud, GET/HEAD → `view`, qolgani → `edit`; xaritada yo'q
    marshrut (users/roles/settings/security/backups/migration/audit/system/
    feature-codes/integrations) → faqat `*` (`check_access` — sof funksiya,
    `app/core/permissions.py`da unit testlangan)."""
    if not check_access(user.role.permissions, request.method, _route_template(request)):
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
