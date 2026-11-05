"""v1 API — barcha routerlarni `/api/v1` ostida birlashtiradi."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    access,
    alerts,
    announcements,
    audio,
    audit,
    auth,
    backups,
    blacklist,
    calls,
    callback_requests,
    callback_widgets,
    campaigns,
    cidsources,
    conferences,
    crm,
    dashboard,
    day_night,
    devices,
    disa,
    extensions,
    feature_codes,
    firewall,
    flow,
    follow_me,
    holidays,
    inbound_routes,
    integrations,
    ivrs,
    live,
    me,
    migration,
    migration_ssh,
    missed_call_rules,
    misc_applications,
    misc_destinations,
    moh_classes,
    network,
    notify_settings,
    numbers,
    onec,
    outbound_routes,
    page_groups,
    parking,
    phonebook,
    pinsets,
    qa,
    queues,
    recordings,
    reports,
    ring_groups,
    roles,
    security,
    settings,
    settings_alerts,
    settings_backup,
    settings_integrations,
    settings_provisioning,
    sip_bans,
    softphone,
    system,
    system_power,
    system_time,
    system_update,
    targets,
    time_conditions,
    time_groups,
    trunks,
    tts_settings,
    users,
    voicemail_boxes,
)

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(extensions.router)
router.include_router(follow_me.router)
router.include_router(devices.router)
router.include_router(settings_provisioning.router)
router.include_router(trunks.router)
router.include_router(inbound_routes.router)
router.include_router(targets.router)
router.include_router(calls.router)
router.include_router(system.router)
router.include_router(time_groups.router)
router.include_router(holidays.router)
router.include_router(time_conditions.router)
router.include_router(ivrs.router)
router.include_router(ring_groups.router)
router.include_router(queues.router)
router.include_router(audio.router)
router.include_router(numbers.router)
router.include_router(flow.router)
router.include_router(outbound_routes.router)
router.include_router(settings.router)
router.include_router(audit.router)
router.include_router(dashboard.router)
router.include_router(moh_classes.router)
router.include_router(voicemail_boxes.router)
router.include_router(notify_settings.router)
router.include_router(feature_codes.router)
router.include_router(parking.router)
router.include_router(conferences.router)
router.include_router(blacklist.router)
router.include_router(live.router)
router.include_router(reports.router)
router.include_router(users.router)
router.include_router(roles.router)
router.include_router(me.router)
router.include_router(softphone.router)
router.include_router(security.router)
router.include_router(sip_bans.router)
router.include_router(settings_alerts.router)
router.include_router(alerts.router)
router.include_router(integrations.router)
router.include_router(crm.router)
router.include_router(onec.router)
router.include_router(recordings.router)
router.include_router(settings_integrations.router)
router.include_router(backups.router)
router.include_router(settings_backup.router)
router.include_router(migration.router)
router.include_router(migration_ssh.router)
router.include_router(campaigns.router)
router.include_router(network.router)
router.include_router(pinsets.router)
router.include_router(phonebook.router)
router.include_router(cidsources.router)
router.include_router(announcements.router)
router.include_router(misc_destinations.router)
router.include_router(misc_applications.router)
router.include_router(page_groups.router)
router.include_router(qa.router)  # M10 B1 — sifat baholash
router.include_router(callback_widgets.router)  # M10 A1 — qayta chaqirish vidjeti
router.include_router(callback_requests.router)
router.include_router(missed_call_rules.router)  # M10 A2 — o'tkazib yuborilgan qo'ng'iroq
router.include_router(tts_settings.router)  # M10 A3 — Yandex SpeechKit TTS
router.include_router(system_update.router)  # M11 — paneldan yangilash
router.include_router(system_time.router)  # M12 B1 — sana va vaqt
router.include_router(system_power.router)  # M12 B2 — qayta yuklash/o'chirish
router.include_router(firewall.router)  # M12 B3 — firewall GUI
router.include_router(access.router)  # M12 B4 — kirish (SSH/Veb portlari)
router.include_router(day_night.router)  # M12 A1 — kun/tun rejimi
router.include_router(disa.router)  # M12 A2 — DISA
