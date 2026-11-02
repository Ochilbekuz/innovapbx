"""Umumiy raqam nom maydoni — `extensions.number`, `dial_numbers` VA umumiy (ext'siz)
ovozli pochta qutilarining `mailbox`i — uchalasi ham tekshiriladi (m1a-contract.md:
«ichki raqam bilan to'qnashsa 409 `number_taken`»; m1c-contract.md §2: umumiy quti
raqami boshqa manzil raqami bilan to'qnashmasin, va teskarisi — 1.0.4 §2)."""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.db.models import DialNumber, Extension, VoicemailBox
from app.services.dialplan_features import is_park_number


async def _shared_mailbox_taken(session: AsyncSession, tenant_id: str, number: str) -> bool:
    """Ext'siz (umumiy) ovozli pochta qutisi — ext'ga bog'langan quti mailbox'i
    ext.number bilan bir xil, u allaqachon Extension so'rovi bilan qamrab olinadi."""
    box = (await session.execute(
        select(VoicemailBox.id).where(VoicemailBox.tenant_id == tenant_id, VoicemailBox.extension_id.is_(None),
                                      VoicemailBox.mailbox == number)
    )).scalar_one_or_none()
    return box is not None


async def number_taken(
    session: AsyncSession, tenant_id: str, number: str, *, exclude_target_id: str | None = None,
) -> bool:
    ext = (await session.execute(
        select(Extension.id).where(Extension.tenant_id == tenant_id, Extension.number == number)
    )).scalar_one_or_none()
    if ext is not None:
        return True
    stmt = select(DialNumber.target_id).where(DialNumber.tenant_id == tenant_id, DialNumber.number == number)
    if exclude_target_id:
        stmt = stmt.where(DialNumber.target_id != exclude_target_id)
    dn = (await session.execute(stmt)).scalar_one_or_none()
    if dn is not None:
        return True
    return await _shared_mailbox_taken(session, tenant_id, number)


async def ensure_number_free(
    session: AsyncSession, tenant_id: str, number: str, *, exclude_target_id: str | None = None, field: str = "number",
) -> None:
    """409 `number_taken`: park raqamlari (700–720, m2a-contract.md §3) — `details.reason="reserved"`;
    ichki raqam/manzil raqami/umumiy ovozli pochta qutisi bilan to'qnashuv — oddiy. `field` —
    409 javobidagi forma maydoni (chaqiruvchining payload shakliga mos: `number` yoki `mailbox`)."""
    if is_park_number(number):
        raise ApiError(409, "number_taken", "Bu raqam park uchun band qilingan", field=field,
                       details={"reason": "reserved"})
    if await number_taken(session, tenant_id, number, exclude_target_id=exclude_target_id):
        raise ApiError(409, "number_taken", "Bu raqam band", field=field)


async def set_dial_number(session: AsyncSession, tenant_id: str, target_id: str, number: str | None) -> None:
    """`dial_numbers`dagi mavjud yozuvni almashtiradi (o'chirish + ixtiyoriy qo'shish)."""
    await session.execute(
        delete(DialNumber).where(DialNumber.tenant_id == tenant_id, DialNumber.target_id == target_id)
    )
    if number:
        session.add(DialNumber(tenant_id=tenant_id, number=number, target_id=target_id))


async def dial_number_for_target(session: AsyncSession, tenant_id: str, target_id: str) -> str | None:
    return (await session.execute(
        select(DialNumber.number).where(DialNumber.tenant_id == tenant_id, DialNumber.target_id == target_id)
    )).scalar_one_or_none()


async def free_numbers(
    session: AsyncSession, tenant_id: str, *, from_n: int, to_n: int, limit: int,
) -> list[str]:
    ext_numbers = (await session.execute(
        select(Extension.number).where(Extension.tenant_id == tenant_id))).scalars().all()
    dial_numbers = (await session.execute(
        select(DialNumber.number).where(DialNumber.tenant_id == tenant_id))).scalars().all()
    mailbox_numbers = (await session.execute(
        select(VoicemailBox.mailbox).where(VoicemailBox.tenant_id == tenant_id,
                                           VoicemailBox.extension_id.is_(None)))).scalars().all()
    taken = set(ext_numbers) | set(dial_numbers) | set(mailbox_numbers)

    items: list[str] = []
    for n in range(from_n, to_n + 1):
        candidate = str(n)
        if candidate not in taken and not is_park_number(candidate):
            items.append(candidate)
        if len(items) >= limit:
            break
    return items
