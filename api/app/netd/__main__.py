"""netd jarayon kirish nuqtasi: `python -m app.netd`. DB/FastAPI importsiz —
faqat stdlib + pydantic (m8-network-contract.md bo'lim 1). Boshlanishda
qolgan `pending.json` bo'lsa — DARHOL qaytariladi (restart-time rollback);
shundan keyin muddat tugashini kuzatuvchi davriy tekshiruv ishga tushadi."""
from __future__ import annotations

import asyncio
import logging

from app.netd.executor import Executor
from app.netd.server import serve
from app.netd.service import NetdService
from app.netd.settings import load_settings

logger = logging.getLogger("netd")
_SWEEP_INTERVAL_S = 5.0


async def _sweep_expired(service: NetdService) -> None:
    """API chaqiruvlarisiz ham muddat tugashini aniqlaydi (`state()` har safar
    tekshirsa ham, hech kim so'ramasa kutilmagan holatda qoladi)."""
    while True:
        await asyncio.sleep(_SWEEP_INTERVAL_S)
        try:
            await service._maybe_expire()  # noqa: SLF001 — service o'z muddatini biladi
        except Exception:  # noqa: BLE001
            logger.exception("muddat tekshiruvida xato")


async def _main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s netd %(levelname)s %(message)s")
    settings = load_settings()
    executor = Executor(settings.exec_mode, settings.host_root)
    service = NetdService(executor, settings)
    await service.startup_recover()
    server = await serve(service, settings.socket_path)
    logger.info("netd tayyor: %s (backend-exec=%s, readonly=%s)",
                settings.socket_path, settings.exec_mode, settings.readonly)
    sweep_task = asyncio.create_task(_sweep_expired(service))
    try:
        async with server:
            await server.serve_forever()
    finally:
        sweep_task.cancel()


if __name__ == "__main__":
    asyncio.run(_main())
