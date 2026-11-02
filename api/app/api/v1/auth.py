"""Setup (sehrgar) va autentifikatsiya — m0-contract.md «Setup / auth»."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.core.config import settings
from app.core.errors import ApiError
from app.core.permissions import permissions_for
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    validate_password,
    verify_password,
)
from app.db.models import AudioFile, RefreshToken, Role, SystemSettings, Tenant, User
from app.schemas import (
    AuthResult,
    ExtensionRef,
    LoginPayload,
    RefreshPayload,
    SetupPayload,
    SetupState,
    TokenPair,
    UpdateMePayload,
    UserOut,
)
from app.schemas_users import ChangePasswordPayload
from app.services.audio_tools import synth_tone_wav
from app.services.audit import record_audit
from app.services.sip_transport import BOOT_DEFAULT, current_sip_config, needs_restart, write_sip_files
from app.services.tokens import revoke_refresh_tokens

router = APIRouter(tags=["auth"])


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=str(user.id), login=user.username, full_name=user.full_name,
        role=user.role.name, permissions=list(user.role.permissions), language=user.language or user.tenant.language,
        must_change_password=user.must_change_password,
        extension=ExtensionRef(id=str(ext.id), number=ext.number, name=ext.name) if (ext := user.extension) else None,
    )


async def _any_admin_exists(session: AsyncSession) -> bool:
    res = await session.execute(select(Tenant.id).limit(1))
    return res.first() is not None


@router.get("/setup/state", response_model=SetupState)
async def setup_state(session: AsyncSession = Depends(get_session)) -> SetupState:
    needed = not await _any_admin_exists(session)
    return SetupState(needed=needed)


async def _issue_tokens(session: AsyncSession, user: User) -> TokenPair:
    access = create_access_token(
        user_id=str(user.id), tenant_id=str(user.tenant_id), role=user.role.name,
        permissions=list(user.role.permissions),
    )
    refresh, refresh_hash = create_refresh_token(user_id=str(user.id))
    session.add(RefreshToken(
        user_id=user.id, token_hash=refresh_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_ttl_days),
    ))
    return TokenPair(access=access, refresh=refresh)


@router.post("/setup", response_model=AuthResult)
async def setup(payload: SetupPayload, session: AsyncSession = Depends(get_session)) -> AuthResult:
    if await _any_admin_exists(session):
        raise ApiError(409, "setup_done", "Tizim allaqachon sozlangan")

    errors = validate_password(payload.admin.password)
    if errors:
        raise ApiError(422, "weak_password", errors[0], field="admin.password")

    tenant = Tenant(code=settings.default_tenant_code, name="Innova", timezone=payload.timezone,
                     language=payload.language)
    session.add(tenant)
    await session.flush()

    admin_role = Role(tenant_id=tenant.id, name="admin", permissions=permissions_for("admin"), is_system=True)
    operator_role = Role(tenant_id=tenant.id, name="operator", permissions=permissions_for("operator"),
                          is_system=True)
    session.add_all([admin_role, operator_role])
    await session.flush()

    sip_row = SystemSettings(tenant_id=tenant.id, external_ip=payload.external_ip, local_nets=payload.local_nets)
    session.add(sip_row)
    await session.flush()
    # S32: sehrgar tarmog'i fayllarga yoziladi; Asterisk hali image standartida —
    # farq bo'lsa admin panelda «qayta ishga tushirish kerak» ko'radi.
    sip_cfg = current_sip_config(sip_row)
    write_sip_files(sip_cfg)
    sip_row.restart_required = needs_restart(BOOT_DEFAULT, sip_cfg)

    # Tizim «salomlashuv» namunasi — sof Python bilan generatsiya qilingan
    # ohang (Asterisk/FreePBX ovoz fayllari NUSXALANMAYDI, m1a-contract.md S11).
    greeting = AudioFile(
        tenant_id=tenant.id, name="Salomlashuv (tizim)", language="uz", source="system",
        storage_path="", duration_ms=1,
    )
    session.add(greeting)
    await session.flush()
    wav_path = Path(settings.sounds_dir) / tenant.code / f"{greeting.id}.wav"
    greeting.duration_ms = synth_tone_wav(wav_path, duration_ms=800)
    greeting.storage_path = f"sounds/{tenant.code}/{greeting.id}"
    await session.flush()

    user = User(
        tenant_id=tenant.id, username=payload.admin.login, full_name=payload.admin.full_name,
        password_hash=hash_password(payload.admin.password), role_id=admin_role.id,
        must_change_password=False,
    )
    session.add(user)
    await session.flush()
    user.role = admin_role
    user.tenant = tenant

    tokens = await _issue_tokens(session, user)
    await session.commit()
    return AuthResult(access=tokens.access, refresh=tokens.refresh, user=_user_out(user))


async def _find_user_by_login(session: AsyncSession, login: str) -> User | None:
    res = await session.execute(select(User).where(User.username == login))
    return res.scalar_one_or_none()


def _is_locked(user: User) -> bool:
    return user.locked_until is not None and user.locked_until > datetime.now(timezone.utc)


async def _register_failed_login(session: AsyncSession, user: User) -> None:
    user.failed_logins += 1
    if user.failed_logins >= settings.login_max_attempts:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=settings.login_lock_minutes)
    await session.flush()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


async def _fallback_tenant_id(session: AsyncSession) -> str | None:
    """Login noma'lum (`user is None`) bo'lganda `login_failed`ni qaysi
    tenant'ga yozishni bilish uchun — bu PBX bir ekzemplyar/bitta tenant
    modeli (`default_tenant_code`), shu sabab birinchi (yagona) tenant
    ishlatiladi. Tenant umuman yo'q bo'lsa (setup hali qilinmagan) — audit
    yozilmaydi, chunki yozadigan joy yo'q."""
    res = await session.execute(select(Tenant.id).limit(1))
    row = res.first()
    return row[0] if row else None


async def _audit_login_failure(
    session: AsyncSession, user: User | None, login: str, ip: str | None,
) -> None:
    """`user` noma'lum bo'lsa ham (login xato kiritilgan) `login_failed`
    yozilishi SHART (m1b-contract.md bo'lim 6) — tenant faqat `user` orqali
    ma'lum bo'lmagani uchun yagona (bitta ekzemplyar) tenant'ga tushadi."""
    tenant_id = str(user.tenant_id) if user is not None else await _fallback_tenant_id(session)
    if tenant_id is None:
        return
    await record_audit(
        session, tenant_id=tenant_id, user_id=str(user.id) if user is not None else None,
        action="login_failed", entity="auth", diff={"login": login}, ip=ip,
    )


@router.post("/auth/login", response_model=AuthResult)
async def login(
    payload: LoginPayload, request: Request, session: AsyncSession = Depends(get_session),
) -> AuthResult:
    ip = _client_ip(request)
    user = await _find_user_by_login(session, payload.login)
    if user is not None and _is_locked(user):
        raise ApiError(423, "locked", "Hisob vaqtincha bloklangan — keyinroq urining")
    # M2b §3: faolsizlantirilgan foydalanuvchi kira olmaydi — hisob holatini
    # OSHKOR qilmaslik uchun (web/src/api/fake.ts bilan bir xil) parol xato
    # bilan BIR XIL xato (`bad_credentials`) qaytariladi, alohida kod YO'Q.
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        if user is not None:
            await _register_failed_login(session, user)
        await _audit_login_failure(session, user, payload.login, ip)
        await session.commit()
        raise ApiError(401, "bad_credentials", "Login yoki parol xato")

    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc)
    tokens = await _issue_tokens(session, user)
    await record_audit(
        session, tenant_id=str(user.tenant_id), user_id=str(user.id),
        action="login", entity="auth", entity_id=str(user.id), diff={}, ip=ip,
    )
    await session.commit()
    return AuthResult(access=tokens.access, refresh=tokens.refresh, user=_user_out(user))


@router.post("/auth/refresh", response_model=TokenPair)
async def refresh_token_endpoint(
    payload: RefreshPayload, session: AsyncSession = Depends(get_session),
) -> TokenPair:
    token_payload = decode_token(payload.refresh, expected_type="refresh")
    if token_payload is None:
        raise ApiError(401, "invalid_token", "Token yaroqsiz")

    token_hash = hash_token(payload.refresh)
    res = await session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    stored = res.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if stored is None or stored.revoked_at is not None or stored.expires_at < now:
        raise ApiError(401, "invalid_token", "Token yaroqsiz")

    user = await session.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise ApiError(401, "invalid_token", "Token yaroqsiz")

    stored.revoked_at = now
    tokens = await _issue_tokens(session, user)
    await session.commit()
    return tokens


@router.post("/auth/logout", status_code=204, response_model=None)
async def logout(payload: RefreshPayload, session: AsyncSession = Depends(get_session)) -> None:
    token_hash = hash_token(payload.refresh)
    res = await session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    stored = res.scalar_one_or_none()
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = datetime.now(timezone.utc)
        await session.commit()


@router.get("/auth/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)


@router.patch("/auth/me", response_model=UserOut)
async def update_me(payload: UpdateMePayload, user: User = Depends(get_current_user),
                    session: AsyncSession = Depends(get_session)) -> UserOut:
    """Foydalanuvchi faqat o'z interfeys tilini o'zgartiradi (M1c §4)."""
    user.language = payload.language
    await session.commit()
    return _user_out(user)


@router.post("/auth/change-password", response_model=TokenPair)
async def change_password(
    payload: ChangePasswordPayload, user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    """m2b-contract.md §3: `must_change_password=true` bo'lsa ham login ishlaydi —
    web shu endpoint orqali majburiy parol almashtirishni amalga oshiradi.
    Barcha refresh tokenlar bekor qilinadi (boshqa qurilmalar chiqadi), JORIY sessiyaga esa
    yangi juftlik qaytariladi — aks holda u ham access muddati tugashi bilan chiqib ketardi."""
    if not verify_password(payload.current, user.password_hash):
        raise ApiError(401, "bad_credentials", "Joriy parol xato", field="current")
    errors = validate_password(payload.new)
    if errors:
        raise ApiError(422, "weak_password", errors[0], field="new")

    user.password_hash = hash_password(payload.new)
    user.must_change_password = False
    # Parol o'zgardi — boshqa joylardagi sessiyalar majburiy qayta kirsin
    # (m2b-contract.md §3: "...parol o'zgarishi -> refresh tokenlari bekor").
    await revoke_refresh_tokens(session, str(user.id))
    await record_audit(session, tenant_id=str(user.tenant_id), user_id=str(user.id),
                        action="user.update", entity="user", entity_id=str(user.id),
                        diff={"password": payload.new})
    tokens = await _issue_tokens(session, user)
    await session.commit()
    return tokens
