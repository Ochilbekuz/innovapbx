"""Umumiy FastAPI dependency'lar — sessiya, joriy foydalanuvchi, ruxsat tekshiruvi,
AMI mijozi. m0-contract.md «Ruxsatlar (M0)», m7-roles-contract.md §1 (markaziy
hudud:action tekshiruvi)."""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ApiError
from app.core.permissions import ALL, check_access, has_permission
from app.core.security import decode_token
from app.db.models import SystemSettings, User
from app.db.session import SessionLocal
from app.services.ami import AmiClient
from app.services.netd_client import NetdClient
from app.services.totp_policy import is_enrollment_exempt_path, must_enroll

_API_PREFIX = "/api/v1"

_UNAUTHORIZED = ApiError(401, "unauthorized", "Avtorizatsiya talab qilinadi")
_ENROLLMENT_REQUIRED = ApiError(403, "2fa_enrollment_required",
                                 "2FA ro'yxatdan o'tish talab qilinadi — avval /me/2fa/setup")


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise _UNAUTHORIZED
    return header[len("Bearer "):].strip()


def _route_template(request: Request) -> str:
    """Marshrut shabloni (`/extensions/{ext_id}` kabi, `/api/v1` OLIB
    TASHLANGAN) — `request.scope["route"].path` (FastAPI buni so'rov
    moslashgandan keyin to'ldiradi; dependency ichida ishlaydi)."""
    path = getattr(request.scope.get("route"), "path", request.url.path)
    if path.startswith(_API_PREFIX):
        path = path[len(_API_PREFIX):]
    return path or "/"


async def _check_2fa_enrollment(session: AsyncSession, request: Request, user: User) -> None:
    """M10 B2: `require_2fa` siyosati (`'admins'`/`'all'`) foydalanuvchidan
    2FA yoqishni talab qilsa va u HALI yoqmagan bo'lsa — `/auth/*` va
    `/me/2fa/*`dan BOSHQA hamma so'rov 403 `2fa_enrollment_required` bilan
    bloklanadi (frontend shu kodni ko'rib ro'yxatdan o'tish ekraniga o'tadi)."""
    if is_enrollment_exempt_path(_route_template(request)):
        return
    row = await session.get(SystemSettings, user.tenant_id)
    policy = row.require_2fa if row is not None else "off"
    is_admin = has_permission(user.role.permissions, ALL)
    if must_enroll(policy, is_admin=is_admin, totp_enabled=user.totp_enabled_at is not None):
        raise _ENROLLMENT_REQUIRED


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
    await _check_2fa_enrollment(session, request, user)
    return user


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


_netd_singleton: NetdClient | None = None


def get_netd_client() -> NetdClient:
    global _netd_singleton
    if _netd_singleton is None:
        _netd_singleton = NetdClient(settings.netd_socket_path, timeout=settings.netd_timeout_s)
    return _netd_singleton
