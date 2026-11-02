"""M2c §5 — trunk monitoringi fon vazifasi (`trunk_monitor`, har
`TRUNK_MONITOR_INTERVAL_S`, sukut 30). Yoqilgan trunklar uchun mavjud
`compute_trunk_health` (`app/services/trunk_health.py`, `/trunks`/`/dashboard`
BILAN BIR XIL qoida — ub-mode DRY) chaqiradi, natijani `trunk_health`ga
yozadi (bu jadvalni M2c'gacha HECH KIM yozmagan — faqat o'qilgan, `register`
rejim uchun esa hali ham faqat JONLI AMI ishlatiladi, bu yozuv shunchaki
tarixiy yozuv/kelajakdagi UI uchun; `/trunks`/`/dashboard` o'zi hamon jonli
`compute_trunk_health`ni chaqiradi — ular O'ZGARMAYDI). Holat
"ishlaydi" <-> "ishlamaydi" ga o'zgarsa — `trunk_down`/`trunk_up`
ogohlantirish; `unknown` o'tish HISOBLANMAYDI, birinchi kuzatuv ham
ogohlantirmaydi (oldingi holat jarayon xotirasida yo'q)."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Trunk, TrunkHealth
from app.services.alerts import alert_text, raise_alert, tenant_language
from app.services.trunk_health import TrunkHealthResult, compute_trunk_health

log = logging.getLogger("innova.trunk_monitor")

_UP_STATES = frozenset({"ok"})
_DOWN_STATES = frozenset({"unreachable"})
_WATCHED_STATES = _UP_STATES | _DOWN_STATES


def transition_kind(prev: str | None, current: str) -> str | None:
    """Sof qoida: `disabled`/`unknown` hech qachon o'tish hisoblanmaydi —
    na manba, na maqsad sifatida; faqat `ok` <-> `unreachable` orasidagi
    HAQIQIY o'zgarish (birinchi kuzatuv — `prev is None` — ham ogohlantirmaydi)."""
    if prev is None or prev == current:
        return None
    if prev not in _WATCHED_STATES or current not in _WATCHED_STATES:
        return None
    return "trunk_up" if current in _UP_STATES else "trunk_down"


# `trunk_health.state` ustuni XOM qiymat kutadi (`state_from_db_health`:
# "ok"->ok, "down"->unreachable, aks holda unknown) — `compute_trunk_health`
# esa ALLAQACHON mapping qilingan natijani qaytaradi ("unreachable"/"unknown").
# Shu ikkisini ARALASHTIRSAK — keyingi aylanishda `ip` rejim trunk uchun
# o'zimiz yozgan "unreachable"ni qayta o'qib, mos kelmagani uchun "unknown"ga
# aylanib qolardi (soxta "tuzalish" — o'z-o'zini buzish). Shu sabab yozishdan
# oldin TESKARI xaritalaymiz (round-trip xavfsiz).
_RAW_STATE_FOR = {"ok": "ok", "unreachable": "down"}


async def _write_trunk_health(session: AsyncSession, trunk_id: str, result: TrunkHealthResult) -> None:
    row = await session.get(TrunkHealth, trunk_id)
    if row is None:
        row = TrunkHealth(trunk_id=trunk_id)
        session.add(row)
    row.state = _RAW_STATE_FOR.get(result.state, "unknown")
    row.registration = result.registration
    row.reason = result.reason
    if result.rtt_ms is not None:
        row.qualify_rtt_ms = result.rtt_ms
    row.checked_at = datetime.now(timezone.utc)


async def _alert_transition(session: AsyncSession, trunk: Trunk, kind: str, result: TrunkHealthResult) -> None:
    lang = await tenant_language(session, trunk.tenant_id)
    if kind == "trunk_down":
        text = alert_text(lang, "trunk_down", name=trunk.name, reason=result.reason or result.state)
    else:
        text = alert_text(lang, "trunk_up", name=trunk.name)
    await raise_alert(session, trunk.tenant_id, kind, trunk.id, text)


async def _monitor_trunk(session: AsyncSession, ami, trunk: Trunk, last_state: dict[str, str]) -> None:
    result = await compute_trunk_health(session, ami, trunk)
    kind = transition_kind(last_state.get(trunk.id), result.state)
    last_state[trunk.id] = result.state
    await _write_trunk_health(session, trunk.id, result)
    if kind is not None:
        await _alert_transition(session, trunk, kind, result)


async def trunk_monitor_cycle(session_factory: async_sessionmaker, ami, last_state: dict[str, str]) -> None:
    async with session_factory() as session:
        trunks = (await session.execute(select(Trunk).where(Trunk.enabled.is_(True)))).scalars().all()
        for trunk in trunks:
            await _monitor_trunk(session, ami, trunk, last_state)
        await session.commit()


async def run_forever(session_factory: async_sessionmaker, ami, interval_s: float) -> None:
    from app.services import maintenance

    last_state: dict[str, str] = {}
    while True:
        if maintenance.state.enabled:
            await asyncio.sleep(interval_s)
            continue
        try:
            await trunk_monitor_cycle(session_factory, ami, last_state)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — fon vazifa hech qachon o'lmasin
            log.exception("trunk_monitor aylanishida xato")
        await asyncio.sleep(interval_s)
