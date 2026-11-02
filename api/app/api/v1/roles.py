"""Rollar muharriri — m7-roles-contract.md §2 (S31 to'liq). FreePBX «User
Management → Groups» analogi: maxsus rollar, hudud bo'yicha `view`/`edit`
ruxsatlari. Faqat `*` (admin) — `require_access` xaritada `/roles` yo'q,
shu sabab fail-closed (`app/core/permissions.py::region_for_path`)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_access
from app.core.errors import ApiError
from app.core.lookups import get_tenant_scoped_or_404
from app.core.optimistic import check_not_stale
from app.core.permissions import normalize_permissions, validate_permission_keys
from app.db.models import Role, User
from app.schemas_users import CreateRolePayload, RoleMutated, RoleOut, RolesListOut, UpdateRolePayload
from app.services.audit import record_audit

router = APIRouter(prefix="/roles", tags=["roles"])

_SYSTEM_ROLE_ORDER = {"admin": 0, "operator": 1}


def _sort_key(role: Role) -> tuple[int, str]:
    """Tizim rollari avval (admin, operator), keyin maxsus rollar nom bo'yicha."""
    return (_SYSTEM_ROLE_ORDER.get(role.name, 2), role.name)


def _role_out(role: Role, user_count: int) -> RoleOut:
    return RoleOut(id=str(role.id), name=role.name, permissions=list(role.permissions),
                   is_system=role.is_system, user_count=user_count, updated_at=role.updated_at)


async def _user_count(session: AsyncSession, tenant_id: str, role_id: str) -> int:
    return (await session.execute(
        select(func.count()).select_from(User).where(User.tenant_id == tenant_id, User.role_id == role_id)
    )).scalar_one()


async def _user_counts_by_role(session: AsyncSession, tenant_id: str) -> dict[str, int]:
    """Ro'yxat sahifasi uchun BITTA so'rov (N+1 oldini olish)."""
    rows = (await session.execute(
        select(User.role_id, func.count()).where(User.tenant_id == tenant_id).group_by(User.role_id)
    )).all()
    return {str(role_id): count for role_id, count in rows}


async def _get_role_or_404(session: AsyncSession, tenant_id: str, role_id: str) -> Role:
    return await get_tenant_scoped_or_404(session, Role, tenant_id, role_id, not_found_message="Rol topilmadi")


def _reject_unknown_permissions(permissions: list[str]) -> None:
    bad = validate_permission_keys(permissions)
    if bad is not None:
        raise ApiError(422, "validation_error", f"Noma'lum ruxsat: {bad}", field="permissions")


def _normalized_name(raw: str) -> str:
    name = raw.strip()
    if not name:
        raise ApiError(422, "validation_error", "Nom kiritilishi shart", field="name")
    return name


def _name_taken(name: str) -> ApiError:
    """`admin`/`operator` HAM shu yo'l bilan ushlanadi — ular har tenantda
    setup paytida YARATILGAN (`auth.py::setup`), shu sabab unique indeks
    (`tenant_id`,`name`) ularga qayta nom qo'yishni ham to'sadi (DRY —
    `users.py::create_user` `username_taken` bilan BIR XIL naqsh)."""
    return ApiError(409, "role_name_taken", f"«{name}» nomi band", field="name")


def _system_role_error(action: str) -> ApiError:
    message = "tahrirlab" if action == "update" else "o'chirib"
    return ApiError(409, "system_role", f"Tizim rolini {message} bo'lmaydi")


@router.get("", response_model=RolesListOut)
async def list_roles(session: AsyncSession = Depends(get_session), user: User = Depends(require_access)) -> RolesListOut:
    tenant_id = str(user.tenant_id)
    rows = (await session.execute(select(Role).where(Role.tenant_id == tenant_id))).scalars().all()
    counts = await _user_counts_by_role(session, tenant_id)
    items = [_role_out(r, counts.get(str(r.id), 0)) for r in sorted(rows, key=_sort_key)]
    return RolesListOut(items=items)


@router.post("", response_model=RoleMutated, status_code=201)
async def create_role(
    payload: CreateRolePayload, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> RoleMutated:
    tenant_id = str(user.tenant_id)
    name = _normalized_name(payload.name)
    _reject_unknown_permissions(payload.permissions)
    permissions = normalize_permissions(payload.permissions)

    role = Role(tenant_id=tenant_id, name=name, permissions=permissions, is_system=False)
    session.add(role)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise _name_taken(name) from exc

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="role.create",
                        entity="role", entity_id=str(role.id), diff={"name": name, "permissions": permissions})
    await session.commit()
    return RoleMutated(item=_role_out(role, 0))


def _apply_role_fields(role: Role, payload: UpdateRolePayload) -> dict:
    """Nom/ruxsatlar — mustaqil ichki funksiyada (CRAP pasaytirish, dryer):
    `update_role`dan ajratilgan, `diff` qaytaradi."""
    diff: dict = {}
    if payload.name is not None:
        role.name = _normalized_name(payload.name)
        diff["name"] = role.name
    if payload.permissions is not None:
        _reject_unknown_permissions(payload.permissions)
        role.permissions = normalize_permissions(payload.permissions)
        diff["permissions"] = role.permissions
    return diff


@router.patch("/{role_id}", response_model=RoleMutated)
async def update_role(
    role_id: str, payload: UpdateRolePayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> RoleMutated:
    tenant_id = str(user.tenant_id)
    role = await _get_role_or_404(session, tenant_id, role_id)
    check_not_stale(role.updated_at, payload.updated_at)
    if role.is_system:
        raise _system_role_error("update")

    diff = _apply_role_fields(role, payload)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise _name_taken(role.name) from exc

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="role.update",
                        entity="role", entity_id=str(role.id), diff=diff)
    await session.commit()
    # Qayta o'qish — DB trigger (`touch_updated_at`) `updated_at`ni serverda
    # yangilaydi, ORM buni avtomatik bilmaydi (`extensions.py`/`moh_classes.py`
    # `update_*`dagi BIR XIL naqsh, `expire_on_commit=False`).
    role = await _get_role_or_404(session, tenant_id, str(role.id))
    count = await _user_count(session, tenant_id, str(role.id))
    return RoleMutated(item=_role_out(role, count))


@router.delete("/{role_id}", status_code=204, response_model=None)
async def delete_role(
    role_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> None:
    tenant_id = str(user.tenant_id)
    role = await _get_role_or_404(session, tenant_id, role_id)
    if role.is_system:
        raise _system_role_error("delete")
    count = await _user_count(session, tenant_id, str(role.id))
    if count > 0:
        raise ApiError(409, "role_in_use", f"«{role.name}» rolida {count} foydalanuvchi bor",
                        details={"user_count": count})

    name = role.name
    await session.delete(role)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="role.delete",
                        entity="role", entity_id=str(role_id), diff={"name": name})
    await session.commit()
