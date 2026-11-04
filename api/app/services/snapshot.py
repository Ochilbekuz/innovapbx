"""Bazadan `DialplanSnapshot` yig'adi — compiler.py'ning sof funksiyasiga
beriladigan yagona NOSOF qadam (DB so'rovlari shu yerda, boshqa joyda emas)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models import (
    Announcement,
    AudioFile,
    CallbackWidget,
    CallTarget,
    Conference,
    DayNight,
    DialNumber,
    Disa,
    Extension,
    ExtensionOutboundRoute,
    FeatureCode,
    Holiday,
    InboundRoute,
    Ivr,
    MiscApplication,
    MiscDestination,
    OutboundRoute,
    OutboundRouteTrunk,
    PageGroup,
    PageGroupMember,
    Queue,
    RingGroup,
    RingGroupMember,
    SystemSettings,
    Tenant,
    TimeCondition,
    TimeGroup,
    VoicemailBox,
)
from app.services.compiler import (
    AnnouncementSnapshot,
    ConferenceSnapshot,
    DayNightSnapshot,
    DialNumberSnapshot,
    DialplanSnapshot,
    DisaSnapshot,
    ExtensionCallerIdSnapshot,
    ExtensionSnapshot,
    InboundRouteSnapshot,
    IvrOptionSnapshot,
    IvrSnapshot,
    MiscApplicationSnapshot,
    MiscDestinationSnapshot,
    OutboundPatternSnapshot,
    OutboundRouteSnapshot,
    OutboundTrunkSnapshot,
    PageGroupSnapshot,
    QueueSnapshot,
    RingGroupMemberSnapshot,
    RingGroupSnapshot,
    TargetSnapshot,
    TimeConditionSnapshot,
    TimeRangeSnapshot,
    VoicemailBoxSnapshot,
)
from app.services.parking_settings import get_parking_settings
from app.services.security_config import parse_toll_fraud


async def build_snapshot(session: AsyncSession, tenant_id: str) -> DialplanSnapshot:
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise ValueError(f"Tenant topilmadi: {tenant_id}")

    extensions = (await session.execute(
        select(Extension).where(Extension.tenant_id == tenant_id))).scalars().all()
    routes = (await session.execute(
        select(InboundRoute).where(InboundRoute.tenant_id == tenant_id))).scalars().all()
    targets = (await session.execute(
        select(CallTarget).where(CallTarget.tenant_id == tenant_id))).scalars().all()
    dial_numbers = (await session.execute(
        select(DialNumber).where(DialNumber.tenant_id == tenant_id))).scalars().all()
    holidays = (await session.execute(
        select(Holiday).where(Holiday.tenant_id == tenant_id))).scalars().all()
    audio_files = (await session.execute(
        select(AudioFile).where(AudioFile.tenant_id == tenant_id))).scalars().all()
    time_conditions = (await session.execute(
        select(TimeCondition)
        .where(TimeCondition.tenant_id == tenant_id)
        .options(selectinload(TimeCondition.time_group).selectinload(TimeGroup.ranges)),
    )).scalars().all()
    ivrs = (await session.execute(
        select(Ivr).where(Ivr.tenant_id == tenant_id).options(selectinload(Ivr.options)),
    )).scalars().all()
    ring_groups = (await session.execute(
        select(RingGroup)
        .where(RingGroup.tenant_id == tenant_id)
        .options(selectinload(RingGroup.members).selectinload(RingGroupMember.extension)),
    )).scalars().all()
    queues = (await session.execute(
        select(Queue).where(Queue.tenant_id == tenant_id))).scalars().all()
    voicemail_boxes = (await session.execute(
        select(VoicemailBox).where(VoicemailBox.tenant_id == tenant_id))).scalars().all()
    conferences = (await session.execute(
        select(Conference).where(Conference.tenant_id == tenant_id))).scalars().all()
    feature_codes = (await session.execute(
        select(FeatureCode).where(FeatureCode.tenant_id == tenant_id, FeatureCode.enabled))).scalars().all()
    outbound_routes = (await session.execute(
        select(OutboundRoute)
        .where(OutboundRoute.tenant_id == tenant_id)
        .options(
            selectinload(OutboundRoute.patterns),
            selectinload(OutboundRoute.route_trunks).selectinload(OutboundRouteTrunk.trunk),
            selectinload(OutboundRoute.extension_links).selectinload(ExtensionOutboundRoute.extension),
        ),
    )).scalars().all()
    system_settings = await session.get(SystemSettings, tenant_id)
    toll_fraud_cfg = parse_toll_fraud(system_settings.toll_fraud if system_settings else None)

    # M9 A1/A2/A3/A4.
    announcements = (await session.execute(
        select(Announcement).where(Announcement.tenant_id == tenant_id))).scalars().all()
    misc_destinations = (await session.execute(
        select(MiscDestination).where(MiscDestination.tenant_id == tenant_id))).scalars().all()
    misc_applications = (await session.execute(
        select(MiscApplication).where(MiscApplication.tenant_id == tenant_id,
                                       MiscApplication.enabled))).scalars().all()
    page_groups = (await session.execute(
        select(PageGroup)
        .where(PageGroup.tenant_id == tenant_id)
        .options(selectinload(PageGroup.members).selectinload(PageGroupMember.extension)),
    )).scalars().all()
    parking = await get_parking_settings(session, tenant_id)
    # M12 A1/A2.
    day_night_rows = (await session.execute(
        select(DayNight).where(DayNight.tenant_id == tenant_id))).scalars().all()
    disa_rows = (await session.execute(
        select(Disa).where(Disa.tenant_id == tenant_id, Disa.enabled))).scalars().all()
    # M10 A1 — faqat operator `target_id`lari kerak (`<code>-dest-<target_id>`
    # umumiy manzil kontekstini majburan yozish uchun; vidjetning o'zi
    # dialplan'ga ta'sir qilmaydi, shu sabab boshqa maydon olinmaydi).
    callback_widget_target_ids = tuple(sorted(set((await session.execute(
        select(CallbackWidget.target_id).where(CallbackWidget.tenant_id == tenant_id))).scalars().all())))

    return DialplanSnapshot(
        tenant_code=tenant.code,
        extensions=[
            ExtensionSnapshot(
                id=str(e.id), number=e.number, name=e.name, ring_seconds=e.ring_seconds,
                target_id=str(e.target_id),
                no_answer_target_id=str(e.no_answer_target_id) if e.no_answer_target_id else None,
            )
            for e in extensions
        ],
        targets={
            str(t.id): TargetSnapshot(id=str(t.id), kind=t.kind, label=t.label) for t in targets
        },
        inbound_routes=[
            InboundRouteSnapshot(
                id=str(r.id), did=r.did, callerid_pattern=r.callerid_pattern,
                target_id=str(r.target_id), enabled=r.enabled,
                cid_name_prefix=r.callerid_name_prefix or None, alert_info=r.alert_info or None,
                cid_lookup_source_id=str(r.cid_lookup_source_id) if r.cid_lookup_source_id else None,
            )
            for r in routes
        ],
        dial_numbers=[
            DialNumberSnapshot(number=d.number, target_id=str(d.target_id)) for d in dial_numbers
        ],
        time_conditions=[
            TimeConditionSnapshot(
                id=str(tc.id), target_id=str(tc.target_id), name=tc.name,
                ranges=tuple(
                    TimeRangeSnapshot(
                        weekdays=tuple(r.weekdays), start=r.start_time.strftime("%H:%M"),
                        end=r.end_time.strftime("%H:%M"),
                    )
                    for r in tc.time_group.ranges
                ),
                honor_holidays=tc.honor_holidays, override=tc.override,
                open_target_id=str(tc.open_target_id), closed_target_id=str(tc.closed_target_id),
                toggle_code=tc.toggle_code,
            )
            for tc in time_conditions
        ],
        ivrs=[
            IvrSnapshot(
                id=str(ivr.id), target_id=str(ivr.target_id), name=ivr.name,
                greeting_audio_id=str(ivr.greeting_audio_id),
                invalid_audio_id=str(ivr.invalid_audio_id) if ivr.invalid_audio_id else None,
                timeout_seconds=ivr.timeout_seconds, repeats=ivr.repeats,
                direct_dial=ivr.direct_dial,
                timeout_target_id=str(ivr.timeout_target_id),
                invalid_target_id=str(ivr.invalid_target_id),
                options=tuple(
                    IvrOptionSnapshot(digit=o.digit, target_id=str(o.target_id))
                    for o in ivr.options
                ),
            )
            for ivr in ivrs
        ],
        ring_groups=[
            RingGroupSnapshot(
                id=str(rg.id), target_id=str(rg.target_id), name=rg.name, strategy=rg.strategy,
                ring_seconds=rg.ring_seconds, no_answer_target_id=str(rg.no_answer_target_id),
                members=tuple(
                    RingGroupMemberSnapshot(
                        position=m.position,
                        extension_number=m.extension.number if m.extension else m.external_number,
                        is_external=m.extension is None,
                    )
                    for m in rg.members
                ),
            )
            for rg in ring_groups
        ],
        queues=[
            QueueSnapshot(
                id=str(q.id), target_id=str(q.target_id), name=q.name,
                max_wait_seconds=q.max_wait_seconds, timeout_target_id=str(q.timeout_target_id),
            )
            for q in queues
        ],
        holidays_mmdd=tuple(sorted({(h.day.month, h.day.day) for h in holidays})),
        audio_paths={str(a.id): f"/var/lib/innova/{a.storage_path}" for a in audio_files},
        outbound_routes=[_outbound_route_snapshot(r) for r in outbound_routes],
        extension_callerids=tuple(
            ExtensionCallerIdSnapshot(number=e.number, outbound_callerid=e.outbound_callerid)
            for e in extensions if e.outbound_callerid
        ),
        outbound_blocked_extension_numbers=tuple(
            sorted(e.number for e in extensions if not e.outbound_allowed)
        ),
        internal_api_base_url=settings.internal_api_base_url,
        internal_api_token=settings.internal_api_token,
        voicemail_boxes=[
            VoicemailBoxSnapshot(target_id=str(b.target_id), mailbox=b.mailbox) for b in voicemail_boxes
        ],
        feature_codes={fc.feature: fc.code for fc in feature_codes},
        conferences=[
            ConferenceSnapshot(
                id=str(c.id), target_id=str(c.target_id), name=c.name,
                has_pin=c.pin_hash is not None, has_admin_pin=c.admin_pin_hash is not None,
            )
            for c in conferences
        ],
        toll_max_concurrent_outbound=(
            toll_fraud_cfg.max_concurrent_outbound if toll_fraud_cfg.enabled else 0
        ),
        announcements=[
            AnnouncementSnapshot(
                id=str(a.id), target_id=str(a.target_id), name=a.name,
                audio_file_id=str(a.audio_file_id), next_target_id=str(a.next_target_id),
                allow_skip=a.allow_skip, repeat_key=a.repeat_key or None, answer=a.answer,
            )
            for a in announcements
        ],
        misc_destinations=[
            MiscDestinationSnapshot(id=str(m.id), target_id=str(m.target_id), name=m.name, dial=m.dial)
            for m in misc_destinations
        ],
        misc_applications=[
            MiscApplicationSnapshot(
                id=str(m.id), name=m.name, code=m.code, target_id=str(m.target_id), enabled=m.enabled,
            )
            for m in misc_applications
        ],
        page_groups=[
            PageGroupSnapshot(
                id=str(pg.id), name=pg.name, number=pg.number,
                member_numbers=tuple(m.extension.number for m in pg.members if m.extension),
                duplex=pg.duplex, skip_busy=pg.skip_busy, beep=pg.beep,
            )
            for pg in page_groups
        ],
        parking=parking,
        callback_widget_target_ids=callback_widget_target_ids,
        day_night=[
            DayNightSnapshot(
                id=str(dn.id), target_id=str(dn.target_id), name=dn.name, code=dn.code,
                day_target_id=str(dn.day_target_id), night_target_id=str(dn.night_target_id),
                has_pin=dn.pin_hmac is not None,
            )
            for dn in day_night_rows
        ],
        disa=[
            DisaSnapshot(
                id=str(d.id), target_id=str(d.target_id), name=d.name,
                has_pin=d.pin_hmac is not None, cid_override=d.cid_override or None,
                digit_timeout=d.digit_timeout, response_timeout=d.response_timeout,
                max_attempts=d.max_attempts,
            )
            for d in disa_rows
        ],
    )


def _outbound_route_snapshot(r: OutboundRoute) -> OutboundRouteSnapshot:
    """Bitta `OutboundRoute` ORM qatorini `compiler.py` sof snapshot'iga
    o'giradi — alohida (CRAP pasaytirish, `build_snapshot()` juda uzun bo'lmasin)."""
    ext_links = list(r.extension_links)
    allowed = tuple(sorted(link.extension.number for link in ext_links)) if ext_links else None
    # Bo'sh ro'yxat (hech qaysi ichki raqamga aniq biriktirilmagan) = "all"
    # (m1b-contract.md bo'lim 2: `extension_ids: "all" | [...]`).
    return OutboundRouteSnapshot(
        id=str(r.id), name=r.name, priority=r.priority, enabled=r.enabled,
        international=r.international,
        patterns=tuple(
            OutboundPatternSnapshot(strip_prefix=p.strip_prefix, pattern=p.pattern, add_prefix=p.add_prefix)
            for p in r.patterns
        ),
        trunks=tuple(
            OutboundTrunkSnapshot(
                position=rt.position, id=str(rt.trunk_id), name=rt.trunk.name,
                outbound_callerid=rt.trunk.outbound_callerid,
            )
            for rt in sorted(r.route_trunks, key=lambda rt: rt.position)
        ),
        callerid=r.callerid, override_extension_callerid=r.override_extension_callerid,
        has_pin=r.pin_hash is not None, allowed_extension_numbers=allowed,
        pin_set_id=str(r.pin_set_id) if r.pin_set_id else None,
    )
