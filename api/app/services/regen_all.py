"""Tiklashdan keyin generatsiya qilinadigan BARCHA fayllarni qayta yaratish
(m4b-contract.md §0: "dialplan kompilyatsiya + reload, MOH, ACL, transport/RTP,
voicemail, pjsip_notify, TLS"). Mavjud generatorlarni CHAQIRADI — bu modul
hech qanday yangi generatsiya mantiqini YOZMAYDI (`restore_job.py` DB tiklab
`alembic upgrade head` qilgandan KEYIN bitta joyda chaqiradi).

Dialplan bosqichi `apply.apply_config()`ning "unchanged" qisqa yo'lidan ATAYLAB
qochadi (`restore`dan OLDINGI disk fayli ESKI holatda qolgan bo'lishi mumkin,
garchi DB'dagi so'nggi reviziya sha256'i bilan bir xil bo'lsa ham) — shu sabab
PUBLIC `apply.restore_revision()` orqali saqlangan dialplan matnini MAJBURAN
qayta yozadi/reload qiladi; hali "applied" reviziya yo'q bo'lsa (yangi/bo'sh
tenant) — `apply.apply_config()` zaxira yo'li."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConfigRevision, Extension, SystemSettings
from app.services.acl_apply import apply_acl
from app.services.apply import AmiLike, apply_config, restore_revision
from app.services.devices import notify_extension_devices
from app.services.moh import apply_moh
from app.services.sip_transport import apply_sip_config, current_sip_config
from app.services.voicemail import apply_voicemail


async def _last_applied_revision(session: AsyncSession, tenant_id: str) -> ConfigRevision | None:
    result = await session.execute(
        select(ConfigRevision)
        .where(ConfigRevision.tenant_id == tenant_id, ConfigRevision.status == "applied")
        .order_by(ConfigRevision.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _regen_dialplan(session: AsyncSession, *, tenant_id: str, tenant_code: str, ami: AmiLike) -> None:
    last_applied = await _last_applied_revision(session, tenant_id)
    if last_applied is None:
        await apply_config(session, tenant_id=tenant_id, user_id=None, ami=ami)
    else:
        await restore_revision(session, tenant_id=tenant_id, tenant_code=tenant_code,
                                user_id=None, ami=ami, target=last_applied)


async def _regen_transport(row: SystemSettings, ami: AmiLike) -> None:
    """Tiklash DB qatorini (`system_settings`) joriy Asterisk jarayoni holati bilan
    solishtirib bo'lmaydi (eski qiymat `pg_restore`dan keyin Python xotirasida
    yo'q) — shu sabab `settings.py`dagi `needs_restart()` qiyoslashidan FARQLI,
    har doim ehtiyotkorlik bilan `restart_required=True` (S32dagi mavjud
    «SIP qayta ishga tushirish» tugmasi orqali admin tasdiqlaydi)."""
    await apply_sip_config(ami, current_sip_config(row), reload_rtp=True)
    row.restart_required = True


async def _notify_all_devices(session: AsyncSession, ami: AmiLike, *, tenant_id: str, tenant_code: str) -> None:
    extensions = (await session.execute(
        select(Extension).where(Extension.tenant_id == tenant_id)
    )).scalars().all()
    for ext in extensions:
        await notify_extension_devices(session, ami, ext, tenant_code)


async def regenerate_all(session: AsyncSession, *, tenant_id: str, tenant_code: str, ami: AmiLike) -> None:
    """Tiklash ketma-ketligining so'nggi bosqichi (m4b-contract.md §0) — dialplan
    birinchi (eng ko'p narsaga — kontekstlar, park lot'ga — bog'liq), qolganlari
    mustaqil (tartib ahamiyatsiz)."""
    row = await session.get(SystemSettings, tenant_id)
    await _regen_dialplan(session, tenant_id=tenant_id, tenant_code=tenant_code, ami=ami)
    await apply_moh(session, tenant_id=tenant_id, tenant_code=tenant_code, ami=ami)
    await apply_acl(session, ami)
    await _regen_transport(row, ami)
    await apply_voicemail(session, tenant_id=tenant_id, tenant_code=tenant_code, ami=ami)
    await _notify_all_devices(session, ami, tenant_id=tenant_id, tenant_code=tenant_code)
