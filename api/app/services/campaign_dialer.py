"""M6 §3 — kampaniya dialer fon vazifasi: running kampaniyalar uchun bo'sh joy bo'yicha kontakt olib,
AMI Originate qiladi; natija dialplan hangup handler → `/internal/campaigns/result` → `record_result`."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import AudioFile, Campaign, CampaignAttempt, CampaignContact, CampaignOptout, Tenant
from app.services import campaign_rules as rules
from app.services.campaigns import blocked_reasons, utcnow

log = logging.getLogger(__name__)


def tenant_now(tz_name: str, now: datetime) -> datetime:
    try:
        return now.astimezone(ZoneInfo(tz_name))
    except (ZoneInfoNotFoundError, ValueError):
        return now.astimezone(ZoneInfo("Asia/Tashkent"))


async def _open_attempts(session: AsyncSession, campaign_id: str) -> int:
    return (await session.execute(select(func.count()).select_from(CampaignAttempt).where(
        CampaignAttempt.campaign_id == campaign_id, CampaignAttempt.ended_at.is_(None)))).scalar_one()


async def _due_contacts(session: AsyncSession, campaign_id: str, limit: int, now: datetime) -> list[CampaignContact]:
    due = (CampaignContact.status == "pending") | (
        (CampaignContact.status == "retry") & (CampaignContact.next_attempt_at <= now))
    return list((await session.execute(
        select(CampaignContact).where(CampaignContact.campaign_id == campaign_id, due)
        .order_by(CampaignContact.status, CampaignContact.next_attempt_at.nulls_first(), CampaignContact.id)
        .limit(limit).with_for_update(skip_locked=True))).scalars().all())


async def _maybe_complete(session: AsyncSession, campaign: Campaign) -> bool:
    left = (await session.execute(select(func.count()).where(
        CampaignContact.campaign_id == campaign.id,
        CampaignContact.status.in_(rules.OPEN_STATUSES)))).scalar_one()
    if left:
        return False
    campaign.status = "completed"
    campaign.finished_at = utcnow()
    return True


async def _audio_path(session: AsyncSession, campaign: Campaign) -> str:
    if not campaign.audio_id:
        return ""
    audio = await session.get(AudioFile, campaign.audio_id)
    return rules.audio_playback_path(audio.storage_path) if audio else ""


async def claim_contacts(session: AsyncSession, campaign: Campaign, now: datetime) -> list[tuple[int, CampaignContact]]:
    """Bo'sh joy bo'yicha kontaktlarni oladi: qora ro'yxat/opt-out → skipped, qolgani → attempt + dialing.
    Natija: [(attempt_id, contact)]. Commit — chaqiruvchida."""
    free = campaign.max_concurrent - await _open_attempts(session, campaign.id)
    if free <= 0:
        return []
    contacts = await _due_contacts(session, campaign.id, free, now)
    reasons = await blocked_reasons(session, campaign.tenant_id, [c.number for c in contacts])
    claimed = []
    for contact in contacts:
        if contact.number in reasons:
            contact.status, contact.result, contact.next_attempt_at = "skipped", reasons[contact.number], None
            continue
        attempt = CampaignAttempt(campaign_id=campaign.id, contact_id=contact.id, started_at=now)
        session.add(attempt)
        contact.status, contact.attempts, contact.last_attempt_at = "dialing", contact.attempts + 1, now
        await session.flush()
        claimed.append((attempt.id, contact))
    return claimed


async def _revert(session_factory: async_sessionmaker, attempt_id: int, contact_id: int, prev: str) -> None:
    """Originate amalga oshmadi — urinish hisoblanmaydi."""
    async with session_factory() as session:
        await session.execute(delete(CampaignAttempt).where(CampaignAttempt.id == attempt_id))
        await session.execute(update(CampaignContact).where(CampaignContact.id == contact_id).values(
            status=prev, attempts=CampaignContact.attempts - 1))
        await session.commit()


async def _originate(ami, req: rules.DialRequest) -> bool:
    try:
        resp = await ami.action("Originate", **rules.originate_fields(req))
    except Exception:  # noqa: BLE001 — AMI uzilgan / xavfli qiymat
        log.exception("campaign originate xato (attempt %s)", req.attempt_id)
        return False
    return (resp or {}).get("Response") == "Success"


def _dial_request(campaign: Campaign, code: str, audio_path: str, attempt_id: int, number: str) -> rules.DialRequest:
    return rules.DialRequest(
        code=code, number=number, attempt_id=attempt_id, campaign_id=str(campaign.id), mode=campaign.mode,
        ring_seconds=campaign.ring_seconds, callerid=campaign.callerid, audio_path=audio_path,
        dtmf=campaign.dtmf_connect or campaign.dtmf_optout, target_number=campaign.target_number)


async def dial_campaign(session_factory: async_sessionmaker, ami, campaign_id: str, now: datetime) -> int:
    """Bitta kampaniya: oyna tekshiruvi → kontakt olish (commit) → Originate. Terilgan soni."""
    async with session_factory() as session:
        campaign = await session.get(Campaign, campaign_id)
        tenant = await session.get(Tenant, campaign.tenant_id) if campaign else None
        if campaign is None or tenant is None or campaign.status != "running":
            return 0
        if await _maybe_complete(session, campaign):
            await session.commit()
            return 0
        if not rules.in_window(tenant_now(tenant.timezone, now), campaign.window_start, campaign.window_end,
                               campaign.days):
            return 0
        claimed = await claim_contacts(session, campaign, now)
        audio_path = await _audio_path(session, campaign)
        requests = [(_dial_request(campaign, tenant.code, audio_path, aid, c.number), c.id, _prev(c))
                    for aid, c in claimed]
        await session.commit()
    dialed = 0
    for req, contact_id, prev in requests:
        if await _originate(ami, req):
            dialed += 1
        else:
            await _revert(session_factory, req.attempt_id, contact_id, prev)
    return dialed


def _prev(contact: CampaignContact) -> str:
    """Claim'dan oldingi holat: birinchi urinish → pending, aks holda retry."""
    return "pending" if contact.attempts <= 1 else "retry"


async def _finish_attempt(session: AsyncSession, attempt: CampaignAttempt, result: str, billsec: int,
                          now: datetime) -> None:
    attempt.ended_at, attempt.dial_status, attempt.billsec = now, result, billsec
    contact = await session.get(CampaignContact, attempt.contact_id)
    campaign = await session.get(Campaign, attempt.campaign_id)
    if contact is None or campaign is None:
        return
    if result == "ANSWER":
        contact.billsec = billsec
    if contact.status == "skipped":  # «9» bosgan — opt-out ustun, natija OPTOUT qoladi
        return
    contact.status, contact.next_attempt_at = rules.contact_outcome(
        result, contact.attempts, campaign.max_attempts, now, campaign.retry_delay_s,
        stopped=campaign.status == "stopped")
    contact.result = result


async def record_result(session: AsyncSession, attempt_id: int, raw_status: str, raw_answered: str,
                        now: datetime | None = None) -> bool:
    """Hangup handler natijasi. Idempotent: yopilgan attempt — e'tiborsiz (False)."""
    attempt = await session.get(CampaignAttempt, attempt_id, with_for_update=True)
    if attempt is None or attempt.ended_at is not None:
        return False
    result = rules.classify_dial_status(raw_status)
    billsec = rules.parse_billsec(raw_answered) if result == "ANSWER" else 0
    await _finish_attempt(session, attempt, result, billsec, now or utcnow())
    return True


async def record_key(session: AsyncSession, attempt_id: int, key: str) -> str:
    """Mijoz tugmasi → `connect` | `optout` | `none`. optout — raqam tenant bo'yicha opt-out ro'yxatiga."""
    attempt = await session.get(CampaignAttempt, attempt_id)
    if attempt is None or attempt.ended_at is not None or not key or key not in "0123456789*#" or len(key) != 1:
        return "none"
    campaign = await session.get(Campaign, attempt.campaign_id)
    contact = await session.get(CampaignContact, attempt.contact_id)
    action = rules.key_action(key, mode=campaign.mode, dtmf_connect=campaign.dtmf_connect,
                              dtmf_optout=campaign.dtmf_optout, target_number=campaign.target_number)
    attempt.key = contact.key = key
    if action == "optout":
        contact.status, contact.result = "skipped", "OPTOUT"
        await session.execute(pg_insert(CampaignOptout).values(
            tenant_id=campaign.tenant_id, number=contact.number, campaign_id=campaign.id).on_conflict_do_nothing())
    return action


async def sweep_lost(session: AsyncSession, now: datetime) -> int:
    """3 soatdan eski ochiq attempt (hangup handler kelmadi) → LOST + retry qoidasi."""
    stale = (await session.execute(select(CampaignAttempt).where(
        CampaignAttempt.ended_at.is_(None), CampaignAttempt.started_at < now - rules.LOST_AFTER)
        .with_for_update(skip_locked=True))).scalars().all()
    for attempt in stale:
        await _finish_attempt(session, attempt, "LOST", 0, now)
    return len(stale)


async def dialer_cycle(session_factory: async_sessionmaker, ami, now: datetime | None = None) -> int:
    now = now or utcnow()
    async with session_factory() as session:
        await sweep_lost(session, now)
        await session.commit()
        ids = (await session.execute(select(Campaign.id).where(Campaign.status == "running"))).scalars().all()
    dialed = 0
    for campaign_id in ids:
        dialed += await dial_campaign(session_factory, ami, campaign_id, now)
    return dialed


async def run_forever(session_factory: async_sessionmaker, ami, interval_s: float) -> None:
    from app.services import maintenance

    while True:
        if not maintenance.state.enabled:
            try:
                await dialer_cycle(session_factory, ami)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 — fon vazifa hech qachon o'lmasin
                log.exception("campaign_dialer aylanishida xato")
        await asyncio.sleep(interval_s)
