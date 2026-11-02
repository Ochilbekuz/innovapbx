"""`OutboundRoute` DB qatorlarini `outbound_rules.RouteRule` ro'yxatiga
o'giradi — BIR XIL yuklash mantiqi `app/api/v1/ring_groups.py` (tashqi a'zo
422 `no_outbound_route` tekshiruvi) VA `app/api/v1/outbound_routes.py`
(`/simulate`) uchun umumiy (m1b-contract.md bo'lim 2/3: "bitta Python
funksiya ... umumiy bo'lsin" — bu IO qatlami, qoida mantiqi `outbound_rules.py`
sof funksiyalarida)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import OutboundRoute
from app.services.outbound_rules import PatternRule, RouteRule, TrunkRef

_ROUTE_OPTIONS = (
    selectinload(OutboundRoute.patterns),
    selectinload(OutboundRoute.route_trunks),
    selectinload(OutboundRoute.extension_links),
)


def _to_rule(route: OutboundRoute) -> RouteRule:
    extension_links = route.extension_links
    allowed_ids = None if not extension_links else tuple(sorted(link.extension_id for link in extension_links))
    return RouteRule(
        id=str(route.id), name=route.name, priority=route.priority, enabled=route.enabled,
        international=route.international,
        patterns=tuple(
            PatternRule(strip_prefix=p.strip_prefix, pattern=p.pattern, add_prefix=p.add_prefix,
                        callerid_match=p.callerid_match)
            for p in route.patterns
        ),
        trunks=tuple(
            TrunkRef(id=str(rt.trunk_id), name=rt.trunk.name)
            for rt in sorted(route.route_trunks, key=lambda r: r.position)
        ),
        callerid=route.callerid, override_extension_callerid=route.override_extension_callerid,
        has_pin=route.pin_hash is not None, allowed_extension_ids=allowed_ids,
    )


async def load_route_rules(session: AsyncSession, tenant_id: str) -> list[RouteRule]:
    rows = (await session.execute(
        select(OutboundRoute).where(OutboundRoute.tenant_id == tenant_id).options(*_ROUTE_OPTIONS)
    )).scalars().unique().all()
    return [_to_rule(r) for r in rows]
