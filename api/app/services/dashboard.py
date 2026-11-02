"""`GET /dashboard` — m1b-contract.md bo'lim 5. Sof (bazasiz/AMI'siz)
hisoblash funksiyalari: router faqat ma'lumot YIG'ADI (CDR qatorlari, AMI
javoblari), BUTUN mantiq shu yerda — testlash uchun."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Trunk, TrunkHealth
from app.schemas import (
    CallOut,
    DashboardAlertOut,
    DashboardTodayOut,
    DiskHealthOut,
    HourBucketOut,
    MissedCallOut,
    TrunkDashboardOut,
)
from app.services.live_status import trunk_registration_state
from app.services.trunk_health import endpoint_id_for, state_from_db_health, state_from_registration

_HOURS_IN_DAY = 24
_BYTES_PER_GB = 1024 ** 3


def disk_health(total_bytes: int, free_bytes: int) -> DiskHealthOut:
    used_pct = round((total_bytes - free_bytes) / total_bytes * 100) if total_bytes else 0
    return DiskHealthOut(used_pct=used_pct, free_gb=round(free_bytes / _BYTES_PER_GB, 1))


def local_midnight_utc(tz_name: str, local_date: date) -> datetime:
    """Tenant TZ'dagi `local_date` kuni 00:00'ni UTC'ga aylantiradi — `today_bounds_utc`
    VA hisobot oraliq chegaralari (`app/services/report_defs.py:range_bounds_utc`,
    m2b-contract.md §5) BIR XIL bu funksiyadan foydalanadi (ub-mode dryer)."""
    local_midnight = datetime(local_date.year, local_date.month, local_date.day, tzinfo=ZoneInfo(tz_name))
    return local_midnight.astimezone(ZoneInfo("UTC"))


def today_bounds_utc(tz_name: str, now_utc: datetime) -> tuple[datetime, datetime]:
    """Tenant TZ'dagi «bugun» (00:00..24:00) ni UTC chegaralarga aylantiradi
    — CDR so'rovi shu chegaralar bilan filtrlanadi (ustun `timestamptz`,
    index `cdr(accountcode, calldate)` mavjud)."""
    local_today = now_utc.astimezone(ZoneInfo(tz_name)).date()
    start = local_midnight_utc(tz_name, local_today)
    end = local_midnight_utc(tz_name, local_today + timedelta(days=1))
    return start, end


def _local_hour(dt: datetime, tz: ZoneInfo) -> int:
    return dt.astimezone(tz).hour


def build_today_stats(calls: list[CallOut], tz_name: str) -> DashboardTodayOut:
    """`calls` — allaqachon «bugun» oynasiga filtrlangan bo'lishi SHART
    (chaqiruvchi, `today_bounds_utc` bilan so'ragan)."""
    tz = ZoneInfo(tz_name)
    buckets = [{"in": 0, "out": 0, "missed": 0} for _ in range(_HOURS_IN_DAY)]
    answered = 0
    missed = 0
    out = 0
    wait_seconds: list[int] = []
    for call in calls:
        hour = _local_hour(call.started_at, tz)
        is_answered = call.disposition == "answered"
        if is_answered:
            answered += 1
            wait_seconds.append(max(call.duration - call.billsec, 0))
        if call.direction == "out":
            out += 1
            buckets[hour]["out"] += 1
        elif call.direction == "in":
            buckets[hour]["in"] += 1
            if not is_answered:
                missed += 1
                buckets[hour]["missed"] += 1
    avg_wait_s = round(sum(wait_seconds) / len(wait_seconds)) if wait_seconds else None
    by_hour = [HourBucketOut(hour=h, **buckets[h]) for h in range(_HOURS_IN_DAY)]
    return DashboardTodayOut(
        total=len(calls), answered=answered, missed=missed, out=out, avg_wait_s=avg_wait_s, by_hour=by_hour,
    )


def build_trunk_dashboard_items(
    trunks: list, db_health_by_id: dict, reg_by_trunk_id: dict,
) -> list[TrunkDashboardOut]:
    """`health.trunks` — `/trunks`dagi `compute_trunk_health` bilan BIR XIL
    holat qoidasini (`state_from_*`) ishlatadi (ub-mode DRY), lekin KIRISH
    — allaqachon (bulk SELECT/`asyncio.gather` bilan) YIG'ILGAN ma'lumot,
    shu sabab bu funksiya o'zi hech qanday DB/AMI so'rovi YUBORMAYDI (sof,
    bazasiz sinaladi) — m1b-contract.md bo'lim 5, 300ms chegarasi."""
    items = []
    for trunk in trunks:
        if not trunk.enabled:
            items.append(TrunkDashboardOut(id=str(trunk.id), name=trunk.name, state="disabled",
                                            registration=None, reason=None))
        elif trunk.auth_mode == "register":
            reg = reg_by_trunk_id[trunk.id]
            items.append(TrunkDashboardOut(id=str(trunk.id), name=trunk.name,
                                            state=state_from_registration(reg["registration"]),
                                            registration=reg["registration"], reason=reg["reason"]))
        else:
            health = db_health_by_id.get(trunk.id)
            state = state_from_db_health(health.state) if health else "unknown"
            items.append(TrunkDashboardOut(id=str(trunk.id), name=trunk.name, state=state,
                                            registration=None, reason=None))
    return items


async def trunk_dashboard_items(session: AsyncSession, ami, tenant_id: str, tenant_code: str,
                                 ) -> list[TrunkDashboardOut]:
    """Ma'lumotni YIG'ADI (DB/AMI) — holat QOIDASI `build_trunk_dashboard_items`da
    (sof, bazasiz sinaladi). Samaradorlik (m1b-contract.md bo'lim 5, 300ms
    chegarasi, o'lchab aniqlangan): `ip` rejim — BITTA bulk SELECT (N alohida
    emas), `register` rejim — AMI so'rovlari BIR VAQTDA (`asyncio.gather`,
    AMI mijozi ActionID bilan konkurent javoblarni to'g'ri taqsimlaydi) —
    N ketma-ket AMI round-trip 300ms chegarasini buzgani o'lchab aniqlandi.

    `/dashboard` VA `GET /system/status` ikkisi ham shu BITTA funksiyadan
    foydalanadi (ub-mode DRY: avval ikki routerda nusxalangan edi)."""
    trunks = (await session.execute(
        select(Trunk).where(Trunk.tenant_id == tenant_id).order_by(Trunk.name)
    )).scalars().all()
    enabled_ip_ids = [t.id for t in trunks if t.enabled and t.auth_mode != "register"]
    db_health_by_id = {}
    if enabled_ip_ids:
        rows = (await session.execute(
            select(TrunkHealth).where(TrunkHealth.trunk_id.in_(enabled_ip_ids))
        )).scalars().all()
        db_health_by_id = {row.trunk_id: row for row in rows}

    register_trunks = [t for t in trunks if t.enabled and t.auth_mode == "register"]
    registrations = await asyncio.gather(*(
        trunk_registration_state(ami, endpoint_id_for(tenant_code, t.id)) for t in register_trunks
    ))
    reg_by_trunk_id = dict(zip((t.id for t in register_trunks), registrations, strict=True))

    return build_trunk_dashboard_items(trunks, db_health_by_id, reg_by_trunk_id)


def _was_called_back(missed_call: CallOut, all_calls: list[CallOut]) -> bool:
    return any(
        c.direction == "out" and c.disposition == "answered"
        and c.dst == missed_call.src and c.started_at > missed_call.started_at
        for c in all_calls
    )


def build_missed_calls(calls: list[CallOut], *, limit: int = 10) -> list[MissedCallOut]:
    """Oxirgi `limit` ta o'tkazib yuborilgan (kiruvchi, javobsiz) qo'ng'iroq —
    qayta qo'ng'iroq QILINMAGANLARI avval (m1b-contract.md bo'lim 5)."""
    missed = [c for c in calls if c.direction == "in" and c.disposition != "answered"]
    enriched = [
        MissedCallOut(uniqueid=c.uniqueid, started_at=c.started_at, src=c.src, did=c.did,
                       called_back=_was_called_back(c, calls))
        for c in missed
    ]
    enriched.sort(key=lambda m: (m.called_back, -m.started_at.timestamp()))
    return enriched[:limit]


# `link` — panel sahifasi yo'li (web/src/shell/screens.ts); noto'g'ri yo'l «Ko'rish»ni bosh sahifaga qaytaradi.
_TRUNK_DOWN = DashboardAlertOut(level="danger", code="trunk_down", text="Trunk aloqasi uzilgan", link="/trunks")
_DISK_LOW = DashboardAlertOut(level="warn", code="disk_low", text="Diskda joy kam qoldi", link="/settings/status")
_ASTERISK_DOWN = DashboardAlertOut(level="danger", code="asterisk_down", text="Asterisk ishlamayapti", link="/settings/status")
_NO_OUTBOUND_ROUTE = DashboardAlertOut(
    level="warn", code="no_outbound_route", text="Chiquvchi marshrut sozlanmagan", link="/outbound",
)
_REVISION_ROLLED_BACK = DashboardAlertOut(
    level="danger", code="revision_rolled_back",
    text="Oxirgi konfiguratsiya qo'llanmadi, avvalgi holatga qaytarildi", link="/settings/revisions",
)

_DISK_LOW_THRESHOLD_PCT = 90


def build_alerts(
    *, asterisk_up: bool, disk_used_pct: int, trunk_down: bool, has_outbound_route: bool,
    last_revision_rolled_back: bool,
) -> list[DashboardAlertOut]:
    alerts: list[DashboardAlertOut] = []
    if not asterisk_up:
        alerts.append(_ASTERISK_DOWN)
    if trunk_down:
        alerts.append(_TRUNK_DOWN)
    if disk_used_pct >= _DISK_LOW_THRESHOLD_PCT:
        alerts.append(_DISK_LOW)
    if not has_outbound_route:
        alerts.append(_NO_OUTBOUND_ROUTE)
    if last_revision_rolled_back:
        alerts.append(_REVISION_ROLLED_BACK)
    return alerts
