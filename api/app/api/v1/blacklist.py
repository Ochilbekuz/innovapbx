"""Qora ro'yxat (S27) — m2a-contract.md §5. Realtime (apply/reload shart emas):
qo'shish/o'chirish darhol kuchga kiradi, Asterisk `asterisk_blacklist` view'dan o'qiydi."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_admin
from app.core.errors import ApiError
from app.db.models import Blacklist, User
from app.schemas_blacklist import BlacklistCreated, BlacklistEntryOut, BlacklistList, CreateBlacklistPayload
from app.services.audit import record_audit
from app.services.blacklist import get_entry, list_entries, validate_blacklist_number

router = APIRouter(prefix="/blacklist", tags=["blacklist"])


def _out(entry: Blacklist) -> BlacklistEntryOut:
    return BlacklistEntryOut(number=entry.number, reason=entry.reason, created_at=entry.created_at)


@router.get("", response_model=BlacklistList)
async def list_blacklist(
    q: str | None = None, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> BlacklistList:
    items = await list_entries(session, str(user.tenant_id), q)
    return BlacklistList(items=[_out(e) for e in items])


@router.post("", response_model=BlacklistCreated, status_code=201)
async def add_blacklist_entry(
    payload: CreateBlacklistPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> BlacklistCreated:
    tenant_id = str(user.tenant_id)
    number = validate_blacklist_number(payload.number)
    if await get_entry(session, tenant_id, number) is not None:
        raise ApiError(409, "exists", "Bu raqam qora ro'yxatda allaqachon bor", field="number")

    entry = Blacklist(tenant_id=tenant_id, number=number, reason=payload.reason)
    session.add(entry)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="blacklist.create",
                        entity="blacklist", entity_id=number, diff={"number": number, "reason": payload.reason})
    await session.commit()
    return BlacklistCreated(item=_out(entry))


@router.delete("/{number}", status_code=204, response_model=None)
async def remove_blacklist_entry(
    number: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
) -> None:
    tenant_id = str(user.tenant_id)
    try:
        normalized = validate_blacklist_number(number)
    except ApiError:
        raise ApiError(404, "not_found", "Qora ro'yxatda bunday raqam yo'q") from None
    entry = await get_entry(session, tenant_id, normalized)
    if entry is None:
        raise ApiError(404, "not_found", "Qora ro'yxatda bunday raqam yo'q")

    await session.delete(entry)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="blacklist.delete",
                        entity="blacklist", entity_id=normalized)
    await session.commit()
