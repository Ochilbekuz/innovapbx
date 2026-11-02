"""M5b §1 — Follow Me: tekshiruv va saqlash (admin `/extensions/{id}/follow-me` VA operator `/me/follow-me`
BITTA funksiyadan — `save_follow_me`).

Raqam turlari: ichki raqam (tenant'da mavjud, o'zi emas) yoki tashqi raqam (≥ 5 raqam). Boshqa manzil raqami
(navbat/guruh/IVR `dial_numbers`) yoki park — 422: dialplan oyog'i faqat ichki raqamni to'g'ridan jiringlatadi.
Holat realtime (`asterisk_ext_state.fm_*`) — apply/reload kerak emas."""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.db.models import DialNumber, Extension
from app.schemas_follow_me import FollowMe
from app.services.audit import record_audit
from app.services.dialplan_features import is_park_number
from app.services.number_normalize import normalize_number

_NUMBER_RE = re.compile(r"^[0-9]{2,15}$")
EXTERNAL_MIN_DIGITS = 5


def _bad(code: str, message: str, index: int | None = None) -> ApiError:
    field = "numbers" if index is None else f"numbers.{index}"
    return ApiError(422, code, message, field=field)


def normalize_numbers(raw: list[str], own_number: str) -> list[str]:
    numbers: list[str] = []
    for index, item in enumerate(raw):
        number = normalize_number(item)
        if not _NUMBER_RE.fullmatch(number):
            raise _bad("bad_number", "Raqam noto'g'ri (2–15 raqam)", index)
        if number == own_number:
            raise _bad("follow_me_self", "O'z raqamingizni qo'shmang — «ichki raqam ham jiringlasin» bor", index)
        if number in numbers:
            raise _bad("follow_me_duplicate", "Raqam takrorlangan", index)
        numbers.append(number)
    return numbers


async def _classify(session: AsyncSession, tenant_id: str, numbers: list[str]) -> dict[str, str]:
    """raqam → `internal` | `external`; noto'g'ri manzil bo'lsa 422."""
    if not numbers:
        return {}
    exts = set((await session.execute(select(Extension.number).where(
        Extension.tenant_id == tenant_id, Extension.number.in_(numbers)))).scalars())
    others = set((await session.execute(select(DialNumber.number).where(
        DialNumber.tenant_id == tenant_id, DialNumber.number.in_(numbers)))).scalars())
    kinds: dict[str, str] = {}
    for index, number in enumerate(numbers):
        if number in exts:
            kinds[number] = "internal"
        elif number in others or is_park_number(number):
            raise _bad("follow_me_bad_target", "Faqat ichki raqam yoki tashqi telefon raqami", index)
        elif len(number) < EXTERNAL_MIN_DIGITS:
            raise _bad("follow_me_unknown_extension", "Bunday ichki raqam yo'q", index)
        else:
            kinds[number] = "external"
    return kinds


async def validate_follow_me(session: AsyncSession, ext: Extension, payload: FollowMe) -> FollowMe:
    numbers = normalize_numbers(payload.numbers, ext.number)
    kinds = await _classify(session, str(ext.tenant_id), numbers)
    if payload.enabled and not numbers:
        raise _bad("follow_me_empty", "Yoqish uchun kamida bitta raqam kerak")
    has_external = "external" in kinds.values()
    # O'chirilgan Follow Me'ni saqlash toll-blok paytida ham mumkin bo'lsin (faqat yoqishda tekshiriladi).
    if payload.enabled and has_external and (not ext.outbound_allowed or ext.toll_blocked_at is not None):
        raise _bad("follow_me_outbound_forbidden", "Bu ichki raqamga tashqi qo'ng'iroq ruxsat etilmagan")
    return payload.model_copy(update={"numbers": numbers})


async def save_follow_me(session: AsyncSession, ext: Extension, payload: FollowMe, *, user_id: str) -> FollowMe:
    clean = await validate_follow_me(session, ext, payload)
    old = FollowMe.model_validate(ext.follow_me or {}).model_dump()
    new = clean.model_dump()
    if new != old:
        ext.follow_me = new
        await session.flush()
        await session.refresh(ext)  # updated_at — DB triggeri
        await record_audit(session, tenant_id=str(ext.tenant_id), user_id=user_id, action="extension.update",
                           entity="extension", entity_id=str(ext.id), diff={"follow_me": {"from": old, "to": new}})
    await session.commit()
    return clean
