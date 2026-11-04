"""Manzil (`call_targets`) ko'rsatish — barcha M1a turlari uchun yagona joy.

`broken` qoida: DB darajasida egalik FK'lari CASCADE, shu sabab "sinig'ich"
manzil DB orqali kamdan-kam yuzaga keladi — lekin himoya sifatida qoldiq
qatorlar (masalan tashqi SQL bilan o'chirilgan) baribir xavfsiz ko'rsatiladi."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Announcement,
    CallTarget,
    Conference,
    DayNight,
    DialNumber,
    Disa,
    Extension,
    Ivr,
    MiscDestination,
    Queue,
    RingGroup,
    TimeCondition,
    VoicemailBox,
)
from app.schemas import RouteTarget

_SATELLITE_MODELS = {
    "time_condition": TimeCondition,
    "ivr": Ivr,
    "ring_group": RingGroup,
    "queue": Queue,
    "voicemail": VoicemailBox,
    "conference": Conference,
    # M9 A1/A2.
    "announcement": Announcement,
    "misc": MiscDestination,
    # M12 A1/A2.
    "day_night": DayNight,
    "disa": Disa,
}


async def _existing_target_ids(session: AsyncSession, tenant_id: str, kind: str) -> set[uuid.UUID]:
    model = _SATELLITE_MODELS.get(kind)
    if model is None:
        return set()
    rows = (await session.execute(
        select(model.target_id).where(model.tenant_id == tenant_id))).scalars().all()
    return set(rows)


async def list_targets(
    session: AsyncSession, tenant_id: str, *,
    kinds: list[str] | None = None, q: str | None = None, only_id: str | None = None,
) -> list[RouteTarget]:
    stmt = select(CallTarget).where(CallTarget.tenant_id == tenant_id)
    if kinds:
        stmt = stmt.where(CallTarget.kind.in_(kinds))
    if q:
        stmt = stmt.where(CallTarget.label.ilike(f"%{q}%"))
    if only_id:
        stmt = stmt.where(CallTarget.id == only_id)
    stmt = stmt.order_by(CallTarget.label)
    targets = (await session.execute(stmt)).scalars().all()
    if not targets:
        return []

    present_kinds = {t.kind for t in targets} & set(_SATELLITE_MODELS)
    by_kind_ids = {kind: await _existing_target_ids(session, tenant_id, kind) for kind in present_kinds}

    ext_numbers = dict((await session.execute(
        select(Extension.target_id, Extension.number).where(Extension.tenant_id == tenant_id)
    )).all())
    dial_numbers = dict((await session.execute(
        select(DialNumber.target_id, DialNumber.number).where(DialNumber.tenant_id == tenant_id)
    )).all())

    items: list[RouteTarget] = []
    for t in targets:
        if t.kind == "extension":
            number = ext_numbers.get(t.id)
            broken = number is None
        elif t.kind in ("hangup", "busy"):
            number, broken = None, False
        else:
            number = dial_numbers.get(t.id)
            broken = t.id not in by_kind_ids.get(t.kind, set())
        items.append(RouteTarget(id=str(t.id), kind=t.kind, label=t.label, number=number, broken=broken))
    return items


async def resolve_target(session: AsyncSession, tenant_id: str, target_id: str) -> RouteTarget | None:
    items = await list_targets(session, tenant_id, only_id=target_id)
    return items[0] if items else None


async def create_target(session: AsyncSession, tenant_id: str, kind: str, label: str) -> CallTarget:
    """Yangi satellit obyekt (ivr/ring_group/queue/time_condition) uchun
    `call_targets` yozuvini ochadi — flush qilinadi, `id` olinadi."""
    target = CallTarget(tenant_id=tenant_id, kind=kind, label=label)
    session.add(target)
    await session.flush()
    return target


async def rename_target(session: AsyncSession, target_id: str, label: str) -> None:
    target = await session.get(CallTarget, target_id)
    if target is not None:
        target.label = label


async def delete_satellite_and_target(session: AsyncSession, entity: object, target_id: str) -> None:
    """Satellit qatorni, keyin uning `call_targets` yozuvini o'chiradi
    (chaqiruvchi oldindan `usages_for_target` bilan 409 `in_use`ni tekshirgan bo'lishi kerak)."""
    await session.delete(entity)
    target = await session.get(CallTarget, target_id)
    if target is not None:
        await session.delete(target)
