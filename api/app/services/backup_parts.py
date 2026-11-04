"""Zaxira qismlari — DB jadvallari (config/history) va fayl papkalari (m4b-contract.md §0/§1).

`HISTORY_TABLES`/`CONFIG_TABLES`/`ALWAYS_EXCLUDED_TABLES` — UCH tomonlama, bir-biriga
TO'QNASHMAYDIGAN ro'yxat; har bir jadval ULARDAN BIRIGA tegishli bo'lishi SHART.
`tests/test_backup_parts.py` `alembic/sql/*.sql` dagi barcha `create table`larni
skanerlab, hech biri "jim" tushib qolmaganini (uch ro'yxatning birida ekanini)
tekshiradi — yangi migratsiya yangi jadval qo'shsa, shu faylga yozish SHART bo'ladi.
"""
from __future__ import annotations

# Zaxira/tiklash o'zining tarixi — HECH QACHON dump qilinmaydi (tiklashda eski
# qatorlar tegilmaydi, `restore_jobs`/`backups` tarixi yo'qolmaydi).
ALWAYS_EXCLUDED_TABLES: frozenset[str] = frozenset({
    "backups", "backup_copies", "restore_jobs",
    "totp_challenges",  # M10 B2: 5 daqiqalik oraliq login holati — tiklashga umuman mantiqsiz
})

# "history": vaqt bo'yicha o'sadigan jurnal/metrik jadvallar. `history` qismi
# TANLANMASA sxema zaxiraga kiradi, lekin qatorlar (MA'LUMOT) kiradi.
HISTORY_TABLES: frozenset[str] = frozenset({
    "cdr", "cel", "queue_log", "agent_events", "alert_log", "audit_log", "provision_requests",
    "integration_events", "integration_deliveries", "outbound_attempts", "security_events",
    "sip_attack_stats", "ip_bans", "trunk_health", "call_event_state", "voicemail_notifications",
    "discovered_devices", "crm_call_links", "api_originate_requests", "call_recordings",
    "qr_provision_tokens",  # M5b: 15 daqiqalik xeshlar (FK extensions'ga — ALWAYS_EXCLUDED emas)
    "campaign_attempts",  # M6: har terish urinishi (kontakt natijasi `campaign_contacts`da qoladi)
    "qa_evaluations",  # M10 B1: har baholash — vaqt bo'yicha o'sadigan jurnal (audit_log kabi)
    "callback_requests",  # M10 A1: har qayta chaqirish so'rovi (vidjet sozlamasi `callback_widgets`da qoladi)
    "missed_call_notices",  # M10 A2: har yuborilgan/muvaffaqiyatsiz bildirishnoma
})

# "config": joriy holat — `config` qismi DOIM yoqilgan, hamma vaqt to'liq kiradi.
CONFIG_TABLES: frozenset[str] = frozenset({
    "tenants", "roles", "users", "refresh_tokens", "call_targets", "dial_numbers", "extensions",
    "feature_code_defaults", "feature_codes", "audio_files", "moh_classes", "moh_class_files",
    "time_groups", "time_ranges", "holidays", "time_conditions", "announcements", "ivrs",
    "ivr_options", "ring_groups", "ring_group_members", "queues", "queue_members", "trunks",
    "inbound_routes", "outbound_routes", "outbound_route_patterns", "outbound_route_trunks",
    "extension_outbound_routes", "config_revisions", "system_settings", "voicemail_boxes",
    "conferences", "external_numbers", "blacklist", "notify_settings", "integration_subscriptions",
    "api_keys", "crm_users", "crm_user_map", "devices", "device_keys",
    "migration_jobs", "migration_items",
    "campaigns", "campaign_contacts", "campaign_optouts",  # M6
    "misc_destinations", "misc_applications", "parking_settings",  # M9 A2/A3
    "page_groups", "page_group_members",  # M9 A4
    "pin_sets", "pin_set_pins",  # M9 B1
    "phonebook_contacts", "phonebook_numbers", "cid_lookup_sources",  # M9 B2
    "qa_checklists", "qa_criteria",  # M10 B1: baholash varaqalari ta'rifi
    "callback_widgets", "missed_call_rules", "missed_notify_cursor", "tts_settings",  # M10 A
    "day_night", "disa",  # M12 A1/A2
})

# Fayl qismlari — api konteynerida ulangan hajm ildizlari (`deploy/docker-compose.yml`).
FILE_COMPONENTS: dict[str, str] = {
    "sounds": "/var/lib/innova/sounds",
    "voicemail": "/var/spool/asterisk/voicemail",
    "recordings": "/var/spool/asterisk/monitor",
    "certs": "/etc/innova/certs",
}

DB_COMPONENTS: tuple[str, ...] = ("config", "history")
ALL_COMPONENTS: tuple[str, ...] = DB_COMPONENTS + tuple(FILE_COMPONENTS)
# Sukut: hammasi, `recordings` ixtiyoriy (katta hajm bo'lishi mumkin — §0).
DEFAULT_COMPONENTS: tuple[str, ...] = ("config", "history", "sounds", "voicemail", "certs")


def validate_components(components: list[str]) -> list[str]:
    unknown = sorted(set(components) - set(ALL_COMPONENTS))
    if unknown:
        raise ValueError(f"noma'lum qism(lar): {unknown}")
    if "config" not in components:
        raise ValueError("'config' qismi DOIM shart")
    return components


def pg_dump_args(components: list[str]) -> list[str]:
    """`pg_dump -Fc` uchun qo'shimcha argumentlar: zaxira/tiklash jadvallari hech
    qachon chiqmaydi; tarix jadvallari faqat 'history' tanlanmaganda qatorsiz."""
    args = [f"--exclude-table={t}" for t in sorted(ALWAYS_EXCLUDED_TABLES)]
    if "history" not in components:
        args += [f"--exclude-table-data={t}" for t in sorted(HISTORY_TABLES)]
    return args
