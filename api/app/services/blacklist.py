"""Qora ro'yxat (S27) — m2a-contract.md §5. Realtime: API yozadi, Asterisk
`asterisk_blacklist` view'dan (res_config_pgsql, `extconfig.conf`) kiruvchi
marshrutlashdan OLDIN o'qiydi — reload/apply shart emas."""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.db.models import Blacklist
from app.services.number_normalize import normalize_number

ANONYMOUS = "anonymous"
_SPECIAL_RAW = {"", "anonymous", "restricted", "hidden"}
_NUMBER_RE = re.compile(r"^[0-9]{3,15}$")


def validate_blacklist_number(raw: str) -> str:
    """`raw` ni saqlash uchun kanonik shaklga keltiradi: maxsus qiymatlar
    (yashirin/anonymous/restricted/bo'sh) → `"anonymous"`; aks holda
    `normalize_number()` (bitta joy — tuzatish (a) bilan BIR XIL funksiya),
    natija `^[0-9]{3,15}$` ga mos kelmasa — 422 `bad_number`."""
    if raw.strip().lower() in _SPECIAL_RAW:
        return ANONYMOUS
    normalized = normalize_number(raw)
    if not _NUMBER_RE.fullmatch(normalized):
        raise ApiError(422, "bad_number", "Raqam formati noto'g'ri (3-15 raqam)", field="number")
    return normalized


async def get_entry(session: AsyncSession, tenant_id: str, number: str) -> Blacklist | None:
    return (await session.execute(
        select(Blacklist).where(Blacklist.tenant_id == tenant_id, Blacklist.number == number)
    )).scalar_one_or_none()


async def list_entries(session: AsyncSession, tenant_id: str, q: str | None = None) -> list[Blacklist]:
    stmt = select(Blacklist).where(Blacklist.tenant_id == tenant_id)
    if q:
        stmt = stmt.where(Blacklist.number.ilike(f"%{q}%"))
    stmt = stmt.order_by(Blacklist.number)
    return list((await session.execute(stmt)).scalars().all())
