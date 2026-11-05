"""Tenant-skopli "id bo'yicha topish, bo'lmasa 404" — `extensions`/`trunks`/
`inbound_routes` routerlarida bir xil shaklda takrorlangan edi (dryer: 1.00
o'xshashlik). Bir joyga chiqarilgan (DRY)."""
from __future__ import annotations

from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.ids import parse_uuid
from app.db.base import Base
from app.db.models import Tenant, User

ModelT = TypeVar("ModelT", bound=Base)


async def get_tenant_code(session: AsyncSession, tenant_id: str) -> str:
    """`Tenant.code`ni oladi — `audio.py`/`extensions.py`da bir xil shaklda
    ("tenant = await session.get(Tenant, tenant_id); return tenant.code")
    takrorlangan edi (dryer), shu sabab shu yerga chiqarildi."""
    tenant = await session.get(Tenant, tenant_id)
    return tenant.code


async def get_tenant_code_and_timezone(session: AsyncSession, tenant_id: str) -> tuple[str, str]:
    """`get_tenant_code` kabi, lekin provizioning renderlash `Tenant.timezone`ga ham muhtoj
    (qurilma/apparat konfiguratsiyasi tizim vaqt zonasiga bog'lanishi uchun, `prov_settings.
    effective_timezone`) — ikkisi BIR so'rovda (qo'shimcha so'rov yo'q)."""
    tenant = await session.get(Tenant, tenant_id)
    return tenant.code, tenant.timezone


async def get_tenant_scoped_or_404(
    session: AsyncSession, model: type[ModelT], tenant_id: str, entity_id: str, *,
    not_found_message: str, options: tuple = (), field: str | None = None,
) -> ModelT:
    """`model`dan `tenant_id`/`id` bo'yicha bitta yozuv qaytaradi; topilmasa
    (yoki `entity_id` yaroqsiz UUID bo'lsa) 404 `not_found` ko'taradi.
    `options` — ixtiyoriy `selectinload(...)` kabi SQLAlchemy yuklash
    qoidalari; `field` — 404 xatosiga biriktiriladigan forma maydoni (masalan
    boshqa obyekt ichidagi xorijiy kalitni tekshirishda, `moh_class_id` kabi)
    — bu naqsh avval `_get_queue_or_404`/`_get_moh_or_404`/`_resolve_moh_class`
    da takrorlangan edi (dryer: 1.00 o'xshashlik)."""
    valid_id = parse_uuid(entity_id, not_found_message=not_found_message)
    query = select(model).where(model.tenant_id == tenant_id, model.id == valid_id)
    if options:
        query = query.options(*options)
    row = (await session.execute(query)).scalar_one_or_none()
    if row is None:
        raise ApiError(404, "not_found", not_found_message, field=field)
    return row


async def usernames_by_id(session: AsyncSession, user_ids: set[str]) -> dict[str, str]:
    """Bir nechta foydalanuvchi id'siga mos `username` (DTO'da `login`)ni BITTA
    so'rovda oladi — `backups.py`da `UserRef(id=..., login=...)` qurishda ishlatiladi
    (`audit.py::_user_refs` bilan bir xil g'oya, lekin javob shakli — xom
    `dict[id, login]` — chaqiruvchiga qoldirilgan, turli modullar turli DTO
    ishlatadi)."""
    if not user_ids:
        return {}
    rows = (await session.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
    return {str(u.id): u.username for u in rows}
