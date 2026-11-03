"""Foydalanuvchilar — m2b-contract.md §3 (S31, minimal). Faqat `admin`.

Qoidalar bir joyda (CRAP/dryer): `username_taken`/`extension_taken` — IntegrityError
yoki oldindan tekshiruv; `self_lockout`/`last_admin` — o'zini bloklash va oxirgi
faol adminni yo'qotib qo'ymaslik (`web/src/api/fake.ts` `checkSelfLockout`/
`checkLastAdmin` bilan BIR XIL mantiq, backend bazaga qarab tekshiradi).
Faolsizlantirish/rol/parol o'zgarishi — refresh tokenlar bekor (`app/services/tokens.py`)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_access
from app.core.errors import ApiError
from app.core.lookups import get_tenant_scoped_or_404
from app.core.optimistic import check_not_stale
from app.core.security import hash_password, validate_password
from app.db.models import Extension, Role, User
from app.schemas import ExtensionRef
from app.schemas_2fa import Totp2faResetOut
from app.schemas_users import CreateUserPayload, ManagedUserOut, UpdateUserPayload, UserMutated
from app.services.audit import record_audit
from app.services.tokens import revoke_refresh_tokens

router = APIRouter(prefix="/users", tags=["users"])


def _user_out(user: User) -> ManagedUserOut:
    ext = user.extension
    return ManagedUserOut(
        id=str(user.id), username=user.username, full_name=user.full_name, email=user.email,
        role=user.role.name, extension=ExtensionRef(id=str(ext.id), number=ext.number, name=ext.name) if ext else None,
        is_active=user.is_active, language=user.language or user.tenant.language,
        must_change_password=user.must_change_password, last_login_at=user.last_login_at,
        updated_at=user.updated_at, totp_enabled=user.totp_enabled_at is not None,
    )


async def _get_user_or_404(session: AsyncSession, tenant_id: str, user_id: str) -> User:
    return await get_tenant_scoped_or_404(session, User, tenant_id, user_id, not_found_message="Foydalanuvchi topilmadi")


async def _role_for(session: AsyncSession, tenant_id: str, name: str) -> Role:
    """Setup bosqichida har doim `admin`/`operator` yaratiladi — topilmasa 422
    (amalda yuz bermaydi, `Role` literal ikkisi bilan cheklangan)."""
    row = (await session.execute(
        select(Role).where(Role.tenant_id == tenant_id, Role.name == name)
    )).scalar_one_or_none()
    if row is None:
        raise ApiError(422, "validation_error", "Noma'lum rol", field="role")
    return row


async def _ensure_extension_free(session: AsyncSession, tenant_id: str, ext: Extension, *,
                                  exclude_user_id: str | None = None) -> None:
    """Ext boshqa foydalanuvchida bo'lsa 409 `extension_taken` (`details.username`)."""
    stmt = select(User).where(User.tenant_id == tenant_id, User.extension_id == ext.id)
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    other = (await session.execute(stmt)).scalar_one_or_none()
    if other is not None:
        raise ApiError(409, "extension_taken", f"{ext.number} allaqachon «{other.username}»ga bog'langan",
                        field="extension_id", details={"username": other.username})


def _check_self_lockout(actor: User, target: User, *, next_is_active: bool, next_role: str) -> None:
    """O'zini bloklab qo'yish — `web/src/api/fake.ts` `checkSelfLockout` bilan bir xil:
    faqat AKTOR = NISHON bo'lganda tekshiriladi."""
    if str(actor.id) != str(target.id):
        return
    if not next_is_active:
        raise ApiError(409, "self_lockout", "O'zingizni faolsizlantira olmaysiz")
    if next_role != "admin" and target.role.name == "admin":
        raise ApiError(409, "self_lockout", "O'zingizni admin rolidan pastga tushira olmaysiz")


async def _check_last_admin(session: AsyncSession, tenant_id: str, target: User, *,
                             next_is_active: bool, next_role: str) -> None:
    """Oxirgi faol adminni yo'qotib qo'ymaslik — `checkLastAdmin` bilan bir xil."""
    if target.role.name != "admin":
        return
    if next_is_active and next_role == "admin":
        return
    others = (await session.execute(
        select(User.id).join(Role, User.role_id == Role.id).where(
            User.tenant_id == tenant_id, User.id != target.id, Role.name == "admin", User.is_active.is_(True),
        )
    )).first()
    if others is None:
        raise ApiError(409, "last_admin", "Tizimda kamida bitta faol admin qolishi kerak")


@router.get("")
async def list_users(session: AsyncSession = Depends(get_session), user: User = Depends(require_access)) -> dict:
    rows = (await session.execute(
        select(User).where(User.tenant_id == user.tenant_id).order_by(User.username)
    )).scalars().all()
    return {"items": [_user_out(u) for u in rows]}


@router.post("", response_model=UserMutated, status_code=201)
async def create_user(
    payload: CreateUserPayload, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> UserMutated:
    tenant_id = str(user.tenant_id)
    username = payload.username.strip()
    if not username:
        raise ApiError(422, "bad_username", "Login kiritilishi shart", field="username")
    errors = validate_password(payload.password)
    if errors:
        raise ApiError(422, "weak_password", errors[0], field="password")

    role_row = await _role_for(session, tenant_id, payload.role)
    ext: Extension | None = None
    if payload.extension_id is not None:
        ext = await get_tenant_scoped_or_404(session, Extension, tenant_id, payload.extension_id,
                                             not_found_message="Ichki raqam topilmadi", field="extension_id")
        await _ensure_extension_free(session, tenant_id, ext)

    new_user = User(
        tenant_id=tenant_id, username=username, full_name=payload.full_name.strip(),
        email=payload.email or None, password_hash=hash_password(payload.password),
        role_id=role_row.id, extension_id=ext.id if ext else None, language=payload.language,
    )
    session.add(new_user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "username_taken", f"«{username}» login band", field="username") from exc

    # Bog'lanishlarni qo'lda to'ldirish — async sessiyada lazy-load ishlamaydi
    # (auth.py `setup()`dagi bilan BIR XIL naqsh).
    new_user.role = role_row
    new_user.tenant = user.tenant
    new_user.extension = ext

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="user.create",
                        entity="user", entity_id=str(new_user.id),
                        diff={"username": username, "password": payload.password})
    await session.commit()
    return UserMutated(item=_user_out(new_user))


def _apply_identity_fields(target: User, payload: UpdateUserPayload, given: set[str]) -> dict:
    """`username`/`full_name`/`email`/`language` — refresh token bekor QILINMAYDI
    (CRAP pasaytirish: `update_user`dan ajratilgan, mustaqil sinaladi)."""
    diff: dict = {}
    if payload.username is not None and payload.username.strip() != target.username:
        target.username = payload.username.strip()
        diff["username"] = target.username
    if payload.full_name is not None:
        target.full_name = payload.full_name.strip()
        diff["full_name"] = target.full_name
    if "email" in given and payload.email != target.email:
        target.email = payload.email
        diff["email"] = target.email
    if "language" in given and payload.language != target.language:
        target.language = payload.language
        diff["language"] = target.language
    return diff


async def _apply_role(session: AsyncSession, tenant_id: str, target: User, payload: UpdateUserPayload) -> dict:
    """Rol o'zgarsa — chaqiruvchi tomonda `revoke_tokens=True` qilinadi."""
    diff: dict = {}
    if payload.role is not None and payload.role != target.role.name:
        target.role = await _role_for(session, tenant_id, payload.role)
        diff["role"] = payload.role
    return diff


def _apply_active(target: User, payload: UpdateUserPayload) -> dict:
    diff: dict = {}
    if payload.is_active is not None and payload.is_active != target.is_active:
        target.is_active = payload.is_active
        diff["is_active"] = target.is_active
    return diff


async def _apply_extension(session: AsyncSession, tenant_id: str, target: User,
                            payload: UpdateUserPayload, given: set[str]) -> dict:
    diff: dict = {}
    current = str(target.extension_id) if target.extension_id else None
    if "extension_id" in given and payload.extension_id != current:
        if payload.extension_id is None:
            target.extension = None
        else:
            ext = await get_tenant_scoped_or_404(session, Extension, tenant_id, payload.extension_id,
                                                  not_found_message="Ichki raqam topilmadi", field="extension_id")
            await _ensure_extension_free(session, tenant_id, ext, exclude_user_id=str(target.id))
            target.extension = ext
        diff["extension_id"] = payload.extension_id
    return diff


def _apply_password(target: User, payload: UpdateUserPayload) -> dict:
    diff: dict = {}
    if payload.password is not None:
        target.password_hash = hash_password(payload.password)
        target.must_change_password = True
        diff["password"] = payload.password
    return diff


@router.patch("/{user_id}", response_model=UserMutated)
async def update_user(
    user_id: str, payload: UpdateUserPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> UserMutated:
    tenant_id = str(user.tenant_id)
    target = await _get_user_or_404(session, tenant_id, user_id)
    check_not_stale(target.updated_at, payload.updated_at)

    next_is_active = payload.is_active if payload.is_active is not None else target.is_active
    next_role = payload.role if payload.role is not None else target.role.name
    _check_self_lockout(user, target, next_is_active=next_is_active, next_role=next_role)
    await _check_last_admin(session, tenant_id, target, next_is_active=next_is_active, next_role=next_role)

    if payload.password is not None:
        errors = validate_password(payload.password)
        if errors:
            raise ApiError(422, "weak_password", errors[0], field="password")

    given = payload.model_fields_set
    # Har bir maydon guruhi mustaqil funksiyada (CRAP pasaytirish, dryer) — diff'lar
    # birlashtiriladi, `revoke_tokens` faqat xavfli o'zgarishlarda (rol/faolsizlantirish/parol).
    diff = {
        **_apply_identity_fields(target, payload, given),
        **(await _apply_role(session, tenant_id, target, payload)),
        **_apply_active(target, payload),
        **(await _apply_extension(session, tenant_id, target, payload, given)),
        **_apply_password(target, payload),
    }
    revoke_tokens = bool(
        "role" in diff or diff.get("is_active") is False or "password" in diff
    )

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "username_taken", f"«{target.username}» login band", field="username") from exc

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="user.update",
                        entity="user", entity_id=str(target.id), diff=diff)
    if revoke_tokens:
        await revoke_refresh_tokens(session, str(target.id))
    await session.commit()
    target = await _get_user_or_404(session, tenant_id, user_id)
    return UserMutated(item=_user_out(target))


@router.delete("/{user_id}", status_code=204, response_model=None)
async def delete_user(
    user_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> None:
    tenant_id = str(user.tenant_id)
    target = await _get_user_or_404(session, tenant_id, user_id)
    _check_self_lockout(user, target, next_is_active=False, next_role=target.role.name)
    await _check_last_admin(session, tenant_id, target, next_is_active=False, next_role=target.role.name)

    username = target.username
    await revoke_refresh_tokens(session, str(target.id))
    await session.delete(target)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="user.delete",
                        entity="user", entity_id=str(user_id), diff={"username": username})
    await session.commit()


@router.post("/{user_id}/2fa/reset", response_model=Totp2faResetOut)
async def reset_user_2fa(
    user_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> Totp2faResetOut:
    """M10 B2 — qurilma yo'qolgan/buzilgan hollarda admin foydalanuvchining
    2FA'sini TO'LIQ o'chiradi (kodsiz — admin allaqachon tasdiqlangan);
    `require_2fa` siyosati 'admins'/'all' bo'lsa foydalanuvchi keyingi
    kirishda qaytadan ro'yxatdan o'tishga majburlanadi (`must_enroll_2fa`)."""
    tenant_id = str(user.tenant_id)
    target = await _get_user_or_404(session, tenant_id, user_id)
    target.totp_secret_enc = None
    target.totp_enabled_at = None
    target.totp_recovery_hashes = []
    target.totp_last_step = None
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="user.update",
                        entity="user", entity_id=str(target.id), diff={"totp_reset": True})
    await session.commit()
    return Totp2faResetOut()
