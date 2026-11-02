"""M6 kampaniyalar — bazaga tegadigan qism (m6-contract.md §1–§2): tekshiruv, statistika,
CSV import, holat o'tishlari, opt-out/qora ro'yxat. Sof qoidalar — `campaign_rules.py`."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import case, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.lookups import get_tenant_scoped_or_404
from app.db.models import AudioFile, Blacklist, Campaign, CampaignContact, CampaignOptout, DialNumber, Extension
from app.schemas_campaigns import CampaignFields, CampaignOut, CampaignStats
from app.services import campaign_rules as rules

NOT_FOUND = "Kampaniya topilmadi"
EDITABLE_FIELDS = tuple(CampaignFields.model_fields)

# Holat o'tishlari: amal -> (ruxsat etilgan joriy holatlar, yangi holat).
_TRANSITIONS: dict[str, tuple[tuple[str, ...], str]] = {
    "start": (("draft", "paused"), "running"),
    "pause": (("running",), "paused"),
    "stop": (("draft", "running", "paused"), "stopped"),
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def get_campaign_or_404(session: AsyncSession, tenant_id: str, campaign_id: str) -> Campaign:
    return await get_tenant_scoped_or_404(session, Campaign, tenant_id, campaign_id, not_found_message=NOT_FOUND)


def merge_fields(current: dict, changes: dict) -> CampaignFields:
    """PATCH: joriy qiymat + o'zgarish → to'liq tekshiruv (pydantic xatosi → 422 validation_error)."""
    try:
        return CampaignFields(**{**current, **changes})
    except ValidationError as exc:
        first = exc.errors()[0]
        field = ".".join(str(p) for p in first.get("loc", ())) or None
        raise ApiError(422, "validation_error", "So'rov ma'lumotlari yaroqsiz", field=field) from None


def current_fields(item: Campaign) -> dict:
    return {name: getattr(item, name) for name in EDITABLE_FIELDS}


def _check_shape(fields: CampaignFields) -> None:
    _check_mode(fields)
    _check_dtmf(fields)
    _check_schedule(fields)


def _check_mode(fields: CampaignFields) -> None:
    if fields.mode == "message" and not fields.audio_id:
        raise ApiError(422, "campaign_audio_required", "Xabar kampaniyasi uchun audio tanlang", field="audio_id")
    if fields.mode == "connect" and not fields.target_number:
        raise ApiError(422, "campaign_target_required", "Ulanadigan raqamni kiriting", field="target_number")


def _check_dtmf(fields: CampaignFields) -> None:
    if fields.mode != "message" and (fields.dtmf_connect or fields.dtmf_optout):
        raise ApiError(422, "campaign_dtmf_mode", "Tugma bosish faqat xabar kampaniyasida", field="dtmf_connect")
    if fields.dtmf_connect and not fields.target_number:
        raise ApiError(422, "campaign_target_required", "«1» uchun ulanadigan raqamni kiriting",
                       field="target_number")


def _check_schedule(fields: CampaignFields) -> None:
    if fields.window_start == fields.window_end:
        raise ApiError(422, "campaign_window", "Oyna boshi va oxiri bir xil bo'lmasin", field="window_end")
    if len(set(fields.days)) != len(fields.days) or not set(fields.days) <= set(range(1, 8)):
        raise ApiError(422, "campaign_days", "Hafta kunlari 1..7, takrorsiz", field="days")


async def _check_audio(session: AsyncSession, tenant_id: str, audio_id: str | None) -> None:
    if audio_id is None:
        return
    await get_tenant_scoped_or_404(session, AudioFile, tenant_id, audio_id,
                                   not_found_message="Audio topilmadi", field="audio_id")


async def _check_target(session: AsyncSession, tenant_id: str, number: str | None) -> None:
    if number is None:
        return
    ext = select(Extension.number).where(Extension.tenant_id == tenant_id, Extension.number == number)
    dial = select(DialNumber.number).where(DialNumber.tenant_id == tenant_id, DialNumber.number == number)
    if (await session.execute(ext.union(dial))).first() is None:
        raise ApiError(422, "campaign_bad_target", "Bunday ichki raqam/navbat/guruh raqami yo'q",
                       field="target_number")


async def validate_campaign(session: AsyncSession, tenant_id: str, fields: CampaignFields,
                            *, exclude_id: str | None = None) -> None:
    _check_shape(fields)
    try:
        await _check_audio(session, tenant_id, fields.audio_id)
    except ApiError:
        raise ApiError(422, "campaign_bad_audio", "Audio topilmadi", field="audio_id") from None
    await _check_target(session, tenant_id, fields.target_number)
    taken = select(Campaign.id).where(Campaign.tenant_id == tenant_id, Campaign.name == fields.name)
    if exclude_id:
        taken = taken.where(Campaign.id != exclude_id)
    if (await session.execute(taken)).first() is not None:
        raise ApiError(422, "name_taken", "Bu nomli kampaniya bor", field="name")


async def stats_for(session: AsyncSession, campaign_ids: list[str]) -> dict[str, CampaignStats]:
    if not campaign_ids:
        return {}
    rows = (await session.execute(
        select(CampaignContact.campaign_id, CampaignContact.status, func.count(),
               func.count(case((CampaignContact.key == "1", 1))), func.count(case((CampaignContact.key == "9", 1))))
        .where(CampaignContact.campaign_id.in_(campaign_ids))
        .group_by(CampaignContact.campaign_id, CampaignContact.status)
    )).all()
    out = {cid: CampaignStats() for cid in campaign_ids}
    for campaign_id, status, count, connected, optout in rows:
        stats = out[str(campaign_id)]
        setattr(stats, status, count)
        stats.total += count
        stats.connected += connected
        stats.optout += optout
    return out


async def audio_names(session: AsyncSession, audio_ids: set[str]) -> dict[str, str]:
    if not audio_ids:
        return {}
    rows = (await session.execute(select(AudioFile.id, AudioFile.name).where(AudioFile.id.in_(audio_ids)))).all()
    return {str(i): n for i, n in rows}


async def campaigns_out(session: AsyncSession, items: list[Campaign]) -> list[CampaignOut]:
    stats = await stats_for(session, [str(c.id) for c in items])
    names = await audio_names(session, {str(c.audio_id) for c in items if c.audio_id})
    return [
        CampaignOut(
            **current_fields(c), id=str(c.id), status=c.status,
            audio_name=names.get(str(c.audio_id)) if c.audio_id else None,
            started_at=c.started_at, finished_at=c.finished_at, created_at=c.created_at,
            updated_at=c.updated_at, stats=stats[str(c.id)],
        )
        for c in items
    ]


async def blocked_reasons(session: AsyncSession, tenant_id: str, numbers: list[str]) -> dict[str, str]:
    """Raqam → `BLACKLIST` | `OPTOUT` (terilmaydi). Qora ro'yxat ustun."""
    if not numbers:
        return {}
    optouts = (await session.execute(select(CampaignOptout.number).where(
        CampaignOptout.tenant_id == tenant_id, CampaignOptout.number.in_(numbers)))).scalars().all()
    black = (await session.execute(select(Blacklist.number).where(
        Blacklist.tenant_id == tenant_id, Blacklist.number.in_(numbers)))).scalars().all()
    return {**{n: "OPTOUT" for n in optouts}, **{n: "BLACKLIST" for n in black}}


async def import_contacts(session: AsyncSession, tenant_id: str, campaign: Campaign,
                          csv_text: str, replace: bool) -> dict:
    if len(csv_text.encode()) > rules.MAX_CSV_BYTES:
        raise ApiError(422, "csv_too_large", "CSV 1 MB dan katta", field="csv")
    if replace:
        _require_not_running(campaign)
        await session.execute(delete(CampaignContact).where(CampaignContact.campaign_id == campaign.id))
    existing = set((await session.execute(
        select(CampaignContact.number).where(CampaignContact.campaign_id == campaign.id))).scalars().all())
    parsed = rules.parse_contacts_csv(csv_text, existing)
    if len(existing) + len(parsed.rows) > rules.MAX_CONTACTS:
        raise ApiError(422, "csv_too_many", f"Kampaniyada {rules.MAX_CONTACTS} dan ortiq kontakt bo'lmaydi",
                       field="csv")
    reasons = await blocked_reasons(session, tenant_id, [n for n, _ in parsed.rows])
    if parsed.rows:
        await session.execute(pg_insert(CampaignContact).values([
            {"campaign_id": campaign.id, "number": n, "name": name,
             "status": "skipped" if n in reasons else "pending", "result": reasons.get(n)}
            for n, name in parsed.rows
        ]).on_conflict_do_nothing())
    return {"added": len(parsed.rows) - len(reasons), "duplicates": parsed.duplicates, "skipped": len(reasons),
            "invalid_count": parsed.invalid_count, "invalid": parsed.invalid}


def _require_not_running(campaign: Campaign) -> None:
    if campaign.status == "running":
        raise ApiError(409, "campaign_running", "Kampaniya ishlayapti — avval to'xtatib turing")


def require_editable(campaign: Campaign) -> None:
    _require_not_running(campaign)


async def transition(session: AsyncSession, campaign: Campaign, action: str) -> None:
    allowed, new_status = _TRANSITIONS[action]
    if campaign.status not in allowed:
        raise ApiError(409, "campaign_bad_state", f"Bu holatda ({campaign.status}) amal bajarilmaydi")
    if action == "start":
        await _require_contacts(session, campaign)
        campaign.started_at = campaign.started_at or utcnow()
    if new_status == "stopped":
        campaign.finished_at = utcnow()
        await _close_open_contacts(session, campaign)
    campaign.status = new_status


async def _close_open_contacts(session: AsyncSession, campaign: Campaign) -> None:
    """To'xtatish yakuniy: terilmagan kontaktlar «Navbatda» qolmaydi → skipped/STOPPED.
    `dialing` tegilmaydi — natijasi hangup'da keladi (`contact_outcome(stopped=True)`)."""
    await session.execute(update(CampaignContact).where(
        CampaignContact.campaign_id == campaign.id, CampaignContact.status.in_(("pending", "retry")),
    ).values(status="skipped", result=rules.STOPPED_RESULT, next_attempt_at=None))


async def _require_contacts(session: AsyncSession, campaign: Campaign) -> None:
    open_count = (await session.execute(select(func.count()).where(
        CampaignContact.campaign_id == campaign.id,
        CampaignContact.status.in_(rules.OPEN_STATUSES)))).scalar_one()
    if open_count == 0:
        raise ApiError(409, "campaign_empty", "Teriladigan kontakt yo'q — CSV yuklang")
