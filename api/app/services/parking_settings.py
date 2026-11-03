"""M9 A3: tenant `parking_settings` yozuvini `dialplan_features.ParkingSettingsData`ga
o'giradi — YAGONA joy (compiler/snapshot.py VA so'rov vaqtidagi raqam-to'qnashuv/`##700`
tekshiruvlari BIR XIL funksiyadan foydalanadi, dryer: takror yo'q)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MohClass, ParkingSettings
from app.services import dialplan_features as feat


async def get_parking_settings(session: AsyncSession, tenant_id: str) -> feat.ParkingSettingsData:
    """Qator topilmasa (hali `/setup` chaqirilmagan eski tenant) — sukut qiymatlar."""
    row = await session.get(ParkingSettings, tenant_id)
    if row is None:
        return feat.ParkingSettingsData()
    moh_name = None
    if row.moh_class_id:
        moh = await session.get(MohClass, row.moh_class_id)
        moh_name = moh.name if moh else None
    return feat.ParkingSettingsData(
        lot_number=row.lot_number, first_slot=row.first_slot, slot_count=row.slot_count,
        timeout_s=row.timeout_s, on_timeout=row.on_timeout,
        timeout_target_id=str(row.timeout_target_id) if row.timeout_target_id else None,
        moh_class_name=moh_name,
    )
