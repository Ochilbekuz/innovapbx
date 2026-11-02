"""Ishga tushganda dialplan/navbat a'zosi/hint ma'lumotlarini majburan qayta
qo'llash (m-sip-login-plain-number, §5): migratsiya endpoint nomlashni
o'zgartirganda (0027), eski kompilyatsiya fayli keyingi `apply_config()`
chaqirilgunicha ESKIRGAN holda qolardi (manual CRUD yoki admin "qo'llash"
amaliga qadar). `apply_config` o'zi idempotent — hash bir xil bo'lsa hech
narsa yozmaydi — shu sabab har ishga tushishda chaqirish ARZON va xavfsiz
(`lifespan`, `startup_dialplan_regen_enabled` bayrog'i bilan o'chiriladi)."""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.db.models import Tenant
from app.services.apply import AmiLike, apply_config

log = logging.getLogger(__name__)


async def regenerate_dialplan_on_startup(session_factory, ami: AmiLike) -> None:
    """Har tenant uchun bir marta `apply_config` — bitta tenant ishlamasa ham
    (masalan hali bo'sh baza) qolganlariga ta'sir qilmasin (xato jim loglanadi)."""
    async with session_factory() as session:
        tenant_ids = (await session.execute(select(Tenant.id))).scalars().all()
        for tenant_id in tenant_ids:
            try:
                await apply_config(session, tenant_id=str(tenant_id), user_id=None, ami=ami)
                await session.commit()
            except Exception:  # noqa: BLE001 — bitta tenant yiqilsa ham API ko'tarilsin
                log.exception("ishga tushishda dialplan qayta qo'llanmadi (tenant=%s)", tenant_id)
                await session.rollback()
