"""M-CRM §1 — fon vazifa: `auto_sync_users=true` bo'lgan YOQILGAN bitrix24
obunalarini davriy sinxronlash (`crm_settings.test_connection` BILAN BIR XIL
yadro — DRY). Bitta obuna xatosi BOSHQALARINI to'xtatmasin — har biri alohida
`try/except`, xato `sub.last_error`ga yoziladi (dispetcher qolipi)."""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import IntegrationSubscription
from app.services import crm_settings

log = logging.getLogger("innova.crm_users_sync")


async def sync_once(session_factory: async_sessionmaker) -> int:
    """Yoqilgan + `auto_sync_users` bitrix24 obunalarini bittalab sinxronlaydi; muvaffaqiyatli soni qaytadi."""
    done = 0
    async with session_factory() as session:
        subs = (await session.execute(select(IntegrationSubscription).where(
            IntegrationSubscription.kind == "bitrix24", IntegrationSubscription.enabled.is_(True)))).scalars().all()
        for sub in subs:
            if not bool((sub.config or {}).get("auto_sync_users", True)):
                continue
            try:
                result = await crm_settings.test_connection(session, sub)
                if result.ok:
                    done += 1
            except Exception as exc:  # noqa: BLE001 — bitta obuna xatosi boshqalarini TO'XTATMASIN
                sub.last_error = str(exc)
                log.exception("crm_users_sync: obuna %s sinxronida xato", sub.id)
            await session.commit()
    return done


async def run_forever(session_factory: async_sessionmaker, interval_s: float) -> None:
    from app.services import maintenance

    while True:
        if not maintenance.state.enabled:
            try:
                await sync_once(session_factory)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 — fon vazifa hech qachon o'lmasin
                log.exception("crm_users_sync aylanishida xato")
        await asyncio.sleep(interval_s)
