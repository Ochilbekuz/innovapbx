"""Trunk salomatligi — bitta joyda hisoblanadi (ub-mode DRY: `/trunks` VA
`/dashboard` ikkisi ham AYNAN BIR XIL qoidani ishlatishi SHART, aks holda
panelda ko'rsatilgan holat trunk sahifasidagi holatdan farq qilib qoladi).

`register` rejimida JONLI AMI so'rovi (`trunk_health` jadvali hech kim
yozmaydi — m1b-contract.md bo'lim 1); `ip` rejimida eski qualify-asosli
ustunlik (M0 xulq-atvori)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Tenant, Trunk, TrunkHealth
from app.services.live_status import trunk_registration_state


@dataclass(frozen=True)
class TrunkHealthResult:
    state: str
    rtt_ms: int | None
    checked_at: datetime | None
    registration: str | None = None
    reason: str | None = None


async def trunk_endpoint_id(session: AsyncSession, trunk: Trunk) -> str:
    tenant_obj = await session.get(Tenant, trunk.tenant_id)
    return f"{tenant_obj.code}-trunk-{trunk.id}"


def endpoint_id_for(tenant_code: str, trunk_id: str) -> str:
    """`trunk_endpoint_id` bilan BIR XIL qoida, lekin sessiyasiz (tenant kodi
    chaqiruvchida allaqachon yuklangan bo'lsa — masalan `/dashboard`, ko'p
    trunk uchun bir martalik `session.get(Tenant, ...)` o'rniga)."""
    return f"{tenant_code}-trunk-{trunk_id}"


def state_from_registration(registration: str | None) -> str:
    """`register` rejim trunk uchun AMI registratsiya holatidan `health.state`
    qoidasi — BITTA joyda (`compute_trunk_health` VA `/dashboard`ning
    ko'p-trunk konkurent tekshiruvi ikkisi ham shu qoidadan foydalanadi)."""
    if registration == "registered":
        return "ok"
    if registration in ("rejected", "unregistered"):
        return "unreachable"
    return "unknown"


def state_from_db_health(db_state: str) -> str:
    """`ip` rejim trunk uchun `trunk_health` jadvalidagi eski qualify
    holatidan `health.state` qoidasi — BITTA joyda."""
    if db_state == "ok":
        return "ok"
    if db_state == "down":
        return "unreachable"
    return "unknown"


async def compute_trunk_health(session: AsyncSession, ami, trunk: Trunk) -> TrunkHealthResult:
    if not trunk.enabled:
        return TrunkHealthResult(state="disabled", rtt_ms=None, checked_at=None)
    if trunk.auth_mode == "register":
        reg = await trunk_registration_state(ami, await trunk_endpoint_id(session, trunk))
        return TrunkHealthResult(state=state_from_registration(reg["registration"]), rtt_ms=None, checked_at=None,
                                  registration=reg["registration"], reason=reg["reason"])
    health = await session.get(TrunkHealth, trunk.id)
    if health is None:
        return TrunkHealthResult(state="unknown", rtt_ms=None, checked_at=None)
    return TrunkHealthResult(state=state_from_db_health(health.state), rtt_ms=health.qualify_rtt_ms,
                              checked_at=health.checked_at)
