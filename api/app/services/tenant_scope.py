"""Bitta ekzemplyar/bitta tenant modeli (`app/core/config.py` `default_tenant_code`,
`app/api/v1/auth.py` sehrgar BIRINCHI tenant'ni yaratadi). SIP xavfsizlik logi
(`security.log`) o'z-o'zidan tenant kontekstini bermaydi (Asterisk — fizik
ulashiladigan yagona ekzemplyar) — `app/services/sip_guard.py` shu yordamchi
bilan YAGONA tenant'ni topadi (`app/api/v1/auth.py`dagi BIR XIL so'rov YANGI
chaqiruvchi uchun shu yerga chiqarildi)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Tenant


async def only_tenant_id(session: AsyncSession) -> str | None:
    """Tenant umuman yo'q bo'lsa (setup hali qilinmagan) — `None`."""
    row = (await session.execute(select(Tenant.id).order_by(Tenant.created_at).limit(1))).first()
    return row[0] if row else None
