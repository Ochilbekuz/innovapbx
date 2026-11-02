"""M2c §2 — SIP hujum himoyasi fon vazifasi (`sip_guard`, har `SIP_GUARD_INTERVAL_S`,
sukut 5). `app/services/security_log_tail.py`dan yangi qatorlarni oladi, IP
bo'yicha `window_s` oynasida muvaffaqiyatsiz urinishlarni jarayon xotirasida
sanaydi (bitta fon vazifa — bitta yozuvchi, DB'ga har urinish alohida
YOZILMAYDI, faqat soat-agregat `sip_attack_stats`), chegaradan oshsa ban
qo'yadi (`ip_bans` + `security_events` + Telegram ogohlantirish), muddati
tugaganlarni ochadi. ACL fayli har aylanishda joriy `ip_bans`dan HASH orqali
solishtirilib, FAQAT o'zgarganda (yoki oldingi urinish muvaffaqiyatsiz
bo'lganda) qayta qo'llanadi — idempotent reconciliation, alohida "dirty"
bayroq shart emas (Attack the Premise: holat ikki joyda — fon vazifa va API
router — saqlanishi shart emas, DB o'zi yagona haqiqat manbai)."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.models import IpBan, SecurityEvent, SipAttackStat, SystemSettings
from app.services.acl_apply import active_banned_ips, apply_acl_ips, hash_ips
from app.services.alerts import alert_text, raise_alert, tenant_language
from app.services.security_config import SipGuardConfig, is_trusted, parse_sip_guard
from app.services.security_log_tail import SecurityLogEvent, TailState, parse_security_line, read_new_lines
from app.services.tenant_scope import only_tenant_id

log = logging.getLogger("innova.sip_guard")


@dataclass
class SipGuardState:
    tail: TailState = field(default_factory=TailState)
    recent_failures: dict[str, deque] = field(default_factory=lambda: defaultdict(deque))
    last_applied_hash: str | None = None
    last_apply_ok: bool = True


def _trim_window(times: deque, window_s: int, now: float) -> None:
    while times and now - times[0] > window_s:
        times.popleft()


async def _load_sip_guard_config(session: AsyncSession, tenant_id: str) -> SipGuardConfig:
    row = await session.get(SystemSettings, tenant_id)
    return parse_sip_guard(row.sip_guard if row else None)


async def active_ban_for(session: AsyncSession, tenant_id: str, ip: str) -> IpBan | None:
    """Berilgan IP uchun FAOL ban (`lifted_at is null`) — fon vazifa (avtomatik
    ban/poyga tekshiruvi) VA `app/api/v1/sip_bans.py` (qo'lda ban) BIR XIL
    so'rovni ishlatadi (dryer: bitta qaror — bitta joy).

    JONLI XATO (bu ssenariy-isbot orqali topilgan, asyncpg + `postgresql.INET`
    ustuniga oddiy Python `str` bilan solishtirish): asyncpg kengaytirilgan
    so'rov protokoli bog'langan parametr turini QIYMATDAN (varchar) chiqaradi,
    ustun turidan (inet) EMAS -- natijada Postgres "operator does not exist:
    inet = character varying" xatosi bilan rad etadi (fon vazifa HAR aylanishda
    shu yerda yiqilib, hech qachon ban qo'ymaydi). Tuzatish: parametrni ANIQ
    `CAST(... AS inet)` bilan o'raymiz (indeks ishlatishga TO'SQINLIK qilmaydi,
    ustunning o'zi o'girilmaydi — faqat qiymat tomoni)."""
    return (await session.execute(
        select(IpBan).where(IpBan.tenant_id == tenant_id, IpBan.ip == cast(ip, INET), IpBan.lifted_at.is_(None))
    )).scalar_one_or_none()


async def _bump_stat(session: AsyncSession, tenant_id: str, ip: str, *, failure: bool, blocked: bool) -> None:
    hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    # `session.get()` EMAS: kompozit PK'da `ip` (INET) bo'lgani — `active_ban_for`
    # (yuqorida) BILAN AYNAN BIR XIL jonli asyncpg xatosiga uchraydi (bind
    # parametri "varchar" deb aniqlanadi, "inet = character varying" operatori
    # yo'q) — shu sabab ANIQ `cast(..., INET)` bilan SELECT (autoflush bir xil
    # aylanishda oldin `add()` qilingan qatorni ko'rishni kafolatlaydi).
    row = (await session.execute(
        select(SipAttackStat).where(SipAttackStat.tenant_id == tenant_id, SipAttackStat.hour == hour,
                                    SipAttackStat.ip == cast(ip, INET))
    )).scalar_one_or_none()
    if row is None:
        # `failures=0, blocked=0` ANIQ berilishi SHART — `mapped_column(default=0)`
        # faqat flush/INSERT paytida qo'llanadi, obyekt yangi yaratilganda ustun
        # HALI `None` (jonli xato: shu yerda `+= 1` qilsa `TypeError` bo'lardi).
        row = SipAttackStat(tenant_id=tenant_id, hour=hour, ip=ip, failures=0, blocked=0)
        session.add(row)
    if failure:
        row.failures += 1
    if blocked:
        row.blocked += 1
    row.last_at = datetime.now(timezone.utc)


async def _auto_ban(session: AsyncSession, tenant_id: str, ip: str, failures: int, cfg: SipGuardConfig) -> None:
    if await active_ban_for(session, tenant_id, ip) is not None:
        return  # poyga: allaqachon (masalan qo'lda) bloklangan — qayta yozmaymiz
    expires_at = None if cfg.ban_s == 0 else datetime.now(timezone.utc) + timedelta(seconds=cfg.ban_s)
    session.add(IpBan(tenant_id=tenant_id, ip=ip, reason="auto", failures=failures, expires_at=expires_at))
    session.add(SecurityEvent(tenant_id=tenant_id, kind="ip_banned", ip=ip,
                              details={"failures": failures, "window_s": cfg.window_s}))
    lang = await tenant_language(session, tenant_id)
    text = alert_text(lang, "ip_banned", ip=ip, failures=failures, window_s=cfg.window_s)
    await raise_alert(session, tenant_id, "ip_banned", ip, text)


async def _expire_bans(session: AsyncSession, tenant_id: str) -> bool:
    now = datetime.now(timezone.utc)
    rows = (await session.execute(
        select(IpBan).where(IpBan.tenant_id == tenant_id, IpBan.lifted_at.is_(None),
                            IpBan.expires_at.is_not(None), IpBan.expires_at <= now)
    )).scalars().all()
    for row in rows:
        row.lifted_at = now
        row.lift_reason = "expired"
        session.add(SecurityEvent(tenant_id=tenant_id, kind="ban_expired", ip=row.ip,
                                  details={"failures": row.failures}))
    return bool(rows)


async def _handle_event(session: AsyncSession, tenant_id: str, state: SipGuardState,
                        ev: SecurityLogEvent, cfg: SipGuardConfig, now: float) -> None:
    if ev.via_websocket:
        # M3a §0: WS orqali Asterisk nginx IP'sini ko'radi — sanalsa bitta foydalanuvchi BARCHA
        # softfonlarni bloklaydi. Darvoza = panel login + ticket; bu yerda faqat iz qoladi.
        session.add(SecurityEvent(tenant_id=tenant_id, kind="ws_auth_failed", ip=ev.ip, transport="ws",
                                  details={"account": ev.account}))
        return
    if is_trusted(ev.ip, cfg.trusted_nets):
        return  # §2: ishonchli tarmoqlar hech qachon avtomatik bloklanmaydi/sanalmaydi
    if await active_ban_for(session, tenant_id, ev.ip) is not None:
        # ACL hali qayta yuklanmagan qisqa oynada kelgan urinish — "blocked"ga
        # (yangi ban yaratilmaydi, oyna cho'zilmaydi).
        await _bump_stat(session, tenant_id, ev.ip, failure=False, blocked=True)
        return
    await _bump_stat(session, tenant_id, ev.ip, failure=True, blocked=False)
    if not cfg.enabled:
        return
    times = state.recent_failures[ev.ip]
    times.append(now)
    _trim_window(times, cfg.window_s, now)
    if len(times) >= cfg.max_failures:
        await _auto_ban(session, tenant_id, ev.ip, len(times), cfg)
        times.clear()


async def _reconcile_acl(session: AsyncSession, ami, state: SipGuardState) -> None:
    """DB (`ip_bans`) — yagona haqiqat manbai: fayl HASH orqali solishtiriladi
    va FAQAT o'zgarganda (yoki oldingi urinish muvaffaqiyatsiz bo'lsa) qayta
    yoziladi/qo'llanadi — har aylanishda keraksiz AMI murojaati yo'q, lekin
    har qanday manbadan (auto ban, qo'lda ban/blokdan chiqarish, muddat
    tugashi) kelgan o'zgarish KEYINGI aylanishda o'zi payqaladi."""
    ips = await active_banned_ips(session)
    digest = hash_ips(ips)
    if digest == state.last_applied_hash and state.last_apply_ok:
        return
    result = await apply_acl_ips(ips, ami)
    state.last_apply_ok = result.status == "applied"
    if state.last_apply_ok:
        state.last_applied_hash = digest
    else:
        log.warning("sip_guard: ACL qo'llash muvaffaqiyatsiz: %s", result.message)


async def sip_guard_cycle(session_factory: async_sessionmaker, ami, state: SipGuardState) -> None:
    lines = read_new_lines(settings.security_log_path, state.tail)
    events = [ev for ev in (parse_security_line(ln) for ln in lines) if ev is not None]
    now = time.monotonic()
    async with session_factory() as session:
        tenant_id = await only_tenant_id(session)
        if tenant_id is None:
            return  # hali setup qilinmagan — yozadigan joy yo'q
        cfg = await _load_sip_guard_config(session, tenant_id)
        for ev in events:
            await _handle_event(session, tenant_id, state, ev, cfg, now)
        await _expire_bans(session, tenant_id)
        await session.flush()
        await _reconcile_acl(session, ami, state)
        await session.commit()


async def run_forever(session_factory: async_sessionmaker, ami, interval_s: float) -> None:
    from app.services import maintenance

    state = SipGuardState()
    while True:
        if maintenance.state.enabled:
            await asyncio.sleep(interval_s)
            continue
        try:
            await sip_guard_cycle(session_factory, ami, state)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — fon vazifa hech qachon o'lmasin
            log.exception("sip_guard aylanishida xato")
        await asyncio.sleep(interval_s)
