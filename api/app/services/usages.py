"""Manzil (`call_targets`) qayerda ishlatilgani — o'chirishdan oldin 409
`in_use` uchun (m1a-contract.md: `GET /targets/{id}/usages`)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Announcement,
    Extension,
    InboundRoute,
    Ivr,
    IvrOption,
    MiscApplication,
    OutboundRoute,
    OutboundRouteTrunk,
    ParkingSettings,
    Queue,
    RingGroup,
    TimeCondition,
)


async def usages_for_target(session: AsyncSession, tenant_id: str, target_id: str) -> list[dict]:
    items: list[dict] = []

    routes = (await session.execute(
        select(InboundRoute).where(InboundRoute.tenant_id == tenant_id,
                                     InboundRoute.target_id == target_id))).scalars().all()
    items += [{"kind": "inbound_route", "id": str(r.id), "label": r.name, "field": "target"} for r in routes]

    tcs = (await session.execute(
        select(TimeCondition).where(
            TimeCondition.tenant_id == tenant_id,
            (TimeCondition.open_target_id == target_id) | (TimeCondition.closed_target_id == target_id),
        ))).scalars().all()
    for tc in tcs:
        field = "open" if str(tc.open_target_id) == target_id else "closed"
        items.append({"kind": "time_condition", "id": str(tc.id), "label": tc.name, "field": field})

    ivrs = (await session.execute(
        select(Ivr).where(
            Ivr.tenant_id == tenant_id,
            (Ivr.timeout_target_id == target_id) | (Ivr.invalid_target_id == target_id),
        ))).scalars().all()
    for ivr in ivrs:
        field = "timeout" if str(ivr.timeout_target_id) == target_id else "invalid"
        items.append({"kind": "ivr", "id": str(ivr.id), "label": ivr.name, "field": field})

    ivr_options = (await session.execute(
        select(IvrOption, Ivr.name).join(Ivr, Ivr.id == IvrOption.ivr_id)
        .where(Ivr.tenant_id == tenant_id, IvrOption.target_id == target_id))).all()
    for opt, ivr_name in ivr_options:
        items.append({"kind": "ivr_option", "id": str(opt.ivr_id), "label": ivr_name,
                       "field": f"digit:{opt.digit}"})

    ring_groups = (await session.execute(
        select(RingGroup).where(RingGroup.tenant_id == tenant_id,
                                  RingGroup.no_answer_target_id == target_id))).scalars().all()
    items += [{"kind": "ring_group", "id": str(rg.id), "label": rg.name, "field": "no_answer"}
              for rg in ring_groups]

    queues = (await session.execute(
        select(Queue).where(Queue.tenant_id == tenant_id,
                              Queue.timeout_target_id == target_id))).scalars().all()
    items += [{"kind": "queue", "id": str(q.id), "label": q.name, "field": "timeout"} for q in queues]

    # M1c: ichki raqam javob bermasa (masalan ovozli pochta qutisi).
    extensions = (await session.execute(
        select(Extension).where(Extension.tenant_id == tenant_id,
                                  Extension.no_answer_target_id == target_id))).scalars().all()
    items += [{"kind": "extension", "id": str(e.id), "label": f"{e.number} · {e.name}", "field": "no_answer"}
              for e in extensions]

    # M9 A1: e'lon "keyingi manzil" (`next_target_id`).
    anns = (await session.execute(
        select(Announcement).where(Announcement.tenant_id == tenant_id,
                                     Announcement.next_target_id == target_id))).scalars().all()
    items += [{"kind": "announcement", "id": str(a.id), "label": a.name, "field": "next"} for a in anns]

    # M9 A2: boshqa ilova maqsadi (`target_id` — RESTRICT, lekin GET /usages orqali ham ko'rsatiladi).
    apps_ = (await session.execute(
        select(MiscApplication).where(MiscApplication.tenant_id == tenant_id,
                                        MiscApplication.target_id == target_id))).scalars().all()
    items += [{"kind": "misc_application", "id": str(m.id), "label": m.name, "field": "target"} for m in apps_]

    # M9 A3: parking muddati tugagach manzil (`on_timeout="target"`).
    park = await session.get(ParkingSettings, tenant_id)
    if park is not None and str(park.timeout_target_id) == target_id:
        items.append({"kind": "parking_settings", "id": tenant_id, "label": "Parking sozlamalari",
                      "field": "timeout_target"})

    return items


async def usages_for_trunk(session: AsyncSession, tenant_id: str, trunk_id: str) -> list[dict]:
    """Trunk qaysi chiquvchi marshrutlarda ishlatilgani — o'chirishdan oldin
    409 `in_use` (m1b-contract.md bo'lim 1: `usages[].kind = "outbound_route"`)."""
    rows = (await session.execute(
        select(OutboundRoute).join(OutboundRouteTrunk, OutboundRouteTrunk.route_id == OutboundRoute.id)
        .where(OutboundRoute.tenant_id == tenant_id, OutboundRouteTrunk.trunk_id == trunk_id)
    )).scalars().unique().all()
    return [{"kind": "outbound_route", "id": str(r.id), "label": r.name, "field": "trunks"} for r in rows]
