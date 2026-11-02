"""M2c §2 — SIP hujum himoyasi: `/security/bans` (qo'lda ban/blokdan chiqarish)
va `/security/stats` (24/soat agregat + top IP). Avtomatik ban/muddat
tugashi — `app/services/sip_guard.py` fon vazifasi (BU FAYLDA EMAS).
`/security/settings`, `/security/toll-blocks`, `/security/events` —
`app/api/v1/security.py` (BOSHQA agent/BOSHQA bo'lim, qayta yozilmadi)."""
from __future__ import annotations

import ipaddress
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ami, get_session, require_access
from app.core.errors import ApiError
from app.db.models import IpBan, SecurityEvent, SipAttackStat, SystemSettings, User
from app.schemas_security import (
    CreateIpBanPayload,
    CreateIpBanResult,
    DeleteIpBanResult,
    IpBanList,
    IpBanOut,
    SecurityStatsOut,
    StatsHourOut,
    StatsTopIpOut,
    StatsTotalsOut,
)
from app.services.acl_apply import apply_acl
from app.services.audit import record_audit
from app.services.security_config import is_trusted, parse_sip_guard
from app.services.sip_guard import active_ban_for

router = APIRouter(prefix="/security", tags=["security"])


def _ban_out(row: IpBan) -> IpBanOut:
    return IpBanOut(id=str(row.id), ip=str(row.ip), reason=row.reason, failures=row.failures,
                    note=row.note, created_at=row.created_at, expires_at=row.expires_at,
                    created_by=str(row.created_by) if row.created_by else None)


def _parse_ip(raw: str) -> str:
    """Faqat BITTA IP manzili (CIDR emas) — `trusted_nets` tarmoqlardan farqli
    o'laroq, ban nuqtai IP bo'yicha."""
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        raise ApiError(422, "bad_ip", "Noto'g'ri IP manzil", field="ip") from None


@router.get("/bans", response_model=IpBanList)
async def list_ip_bans(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> IpBanList:
    rows = (await session.execute(
        select(IpBan).where(IpBan.tenant_id == user.tenant_id, IpBan.lifted_at.is_(None))
        .order_by(IpBan.created_at.desc())
    )).scalars().all()
    return IpBanList(items=[_ban_out(r) for r in rows])


@router.post("/bans", response_model=CreateIpBanResult, status_code=201)
async def create_ip_ban(
    payload: CreateIpBanPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> CreateIpBanResult:
    tenant_id = str(user.tenant_id)
    ip = _parse_ip(payload.ip)

    settings_row = await session.get(SystemSettings, tenant_id)
    cfg = parse_sip_guard(settings_row.sip_guard if settings_row else None)
    if is_trusted(ip, cfg.trusted_nets):
        raise ApiError(409, "trusted_ip", "Bu IP ishonchli tarmoqda — qo'lda bloklab bo'lmaydi")
    if await active_ban_for(session, tenant_id, ip) is not None:
        raise ApiError(409, "already_banned", "Bu IP allaqachon faol bloklangan")

    ban_s = payload.ban_s if payload.ban_s is not None else cfg.ban_s
    expires_at = None if ban_s == 0 else datetime.now(timezone.utc) + timedelta(seconds=ban_s)
    row = IpBan(tenant_id=tenant_id, ip=ip, reason="manual", failures=0, note=payload.note,
                created_by=user.id, expires_at=expires_at)
    session.add(row)
    session.add(SecurityEvent(tenant_id=tenant_id, kind="ip_banned", ip=ip, details={"reason": "manual"}))
    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="security.ban_create",
                        entity="ip_ban", entity_id=row.id, diff={"ip": ip, "ban_s": ban_s})
    apply_result = (await apply_acl(session, ami)).to_dict()
    await session.commit()
    return CreateIpBanResult(item=_ban_out(row), apply=apply_result)


@router.delete("/bans/{ban_id}", response_model=DeleteIpBanResult)
async def delete_ip_ban(
    ban_id: str, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access), ami=Depends(get_ami),
) -> DeleteIpBanResult:
    tenant_id = str(user.tenant_id)
    row = (await session.execute(
        select(IpBan).where(IpBan.id == ban_id, IpBan.tenant_id == tenant_id, IpBan.lifted_at.is_(None))
    )).scalar_one_or_none()
    if row is None:
        raise ApiError(404, "not_found", "Faol ban topilmadi")

    now = datetime.now(timezone.utc)
    row.lifted_at = now
    row.lift_reason = "manual"
    session.add(SecurityEvent(tenant_id=tenant_id, kind="ip_unbanned", ip=row.ip, details={}))
    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="security.ban_delete",
                        entity="ip_ban", entity_id=row.id, diff={"ip": str(row.ip)})
    apply_result = (await apply_acl(session, ami)).to_dict()
    await session.commit()
    return DeleteIpBanResult(apply=apply_result)


def _fill_hours(rows: dict[datetime, tuple[int, int]], hours: int, now: datetime) -> list[StatsHourOut]:
    """To'liq qator ro'yxati — bo'sh soat ham `0` bilan (contract §2)."""
    start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=hours - 1)
    out = []
    for i in range(hours):
        hour = start + timedelta(hours=i)
        failures, blocked = rows.get(hour, (0, 0))
        out.append(StatsHourOut(hour=hour, failures=failures, blocked=blocked))
    return out


@router.get("/stats", response_model=SecurityStatsOut)
async def get_security_stats(
    hours: int = Query(default=24, ge=1, le=168),
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> SecurityStatsOut:
    tenant_id = str(user.tenant_id)
    now = datetime.now(timezone.utc)
    since = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=hours - 1)

    stat_rows = (await session.execute(
        select(SipAttackStat).where(SipAttackStat.tenant_id == tenant_id, SipAttackStat.hour >= since)
    )).scalars().all()

    by_hour: dict[datetime, tuple[int, int]] = {}
    by_ip: dict[str, dict] = {}
    for r in stat_rows:
        fh, bh = by_hour.get(r.hour, (0, 0))
        by_hour[r.hour] = (fh + r.failures, bh + r.blocked)
        agg = by_ip.setdefault(str(r.ip), {"failures": 0, "last_at": r.last_at})
        agg["failures"] += r.failures
        agg["last_at"] = max(agg["last_at"], r.last_at)

    active_ips = set((await session.execute(
        select(IpBan.ip).where(IpBan.tenant_id == tenant_id, IpBan.lifted_at.is_(None))
    )).scalars().all())
    active_ips = {str(ip) for ip in active_ips}

    top_ips = sorted(
        ({"ip": ip, **v, "banned": ip in active_ips} for ip, v in by_ip.items()),
        key=lambda i: i["failures"], reverse=True,
    )[:10]

    bans_period = (await session.execute(
        select(func.count()).select_from(IpBan).where(
            IpBan.tenant_id == tenant_id, IpBan.created_at >= since,
        )
    )).scalar_one()

    totals = StatsTotalsOut(
        failures=sum(f for f, _ in by_hour.values()),
        blocked=sum(b for _, b in by_hour.values()),
        bans_active=len(active_ips),
        bans_period=bans_period,
    )
    return SecurityStatsOut(
        hours=_fill_hours(by_hour, hours, now),
        top_ips=[StatsTopIpOut(**i) for i in top_ips],
        totals=totals,
    )
