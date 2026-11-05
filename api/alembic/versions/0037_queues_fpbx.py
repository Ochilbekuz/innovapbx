"""Navbatlar (Queues) — FreePBX Queues moduli bilan maksimal mos keluvchi
yangi maydonlar: CID prefiks, Alert-Info, qo'shilish/agent e'loni audiosi,
MOH/faqat-jiring rejimi, javob berilgan boshqa joyda belgisi, to'liq
strategiya/avtomat-pauza/bo'sh-navbat (join/leave) qiymatlari, vazn,
avto-toʻldirish, hisobot/a'zo kechikishi, davriy e'lon, IVR orqali chiqish
(context) — barchasi HAQIQIY Asterisk 22 `queues.conf`/`Queue()` kalitlari
(manba: `apps/app_queue.c`), xavfsiz/ishlamaydigan maydonlar QO'SHILMADI
(tafsilot: `docs/qollanma/queues.md`).

Revision ID: 0037_queues_fpbx
Revises: 0036_m_crm
Create Date: 2026-11-05
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0037_queues_fpbx"
down_revision = "0036_m_crm"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0037_queues_fpbx.sql")


def downgrade() -> None:
    run_sql_text(
        "drop view if exists asterisk_queues;"
        "alter table queues alter column join_empty drop default;"
        "alter table queues alter column join_empty type boolean using (join_empty = 'yes');"
        "alter table queues alter column join_empty set default false;"
        "alter table queues alter column announce_position drop default;"
        "alter table queues alter column announce_position type boolean using (announce_position = 'yes');"
        "alter table queues alter column announce_position set default true;"
        "alter table queues"
        " drop column if exists skip_busy_agents,"
        " drop column if exists weight,"
        " drop column if exists autofill,"
        " drop column if exists report_hold_time,"
        " drop column if exists member_delay_seconds,"
        " drop column if exists penalty_members_limit,"
        " drop column if exists auto_pause,"
        " drop column if exists auto_pause_delay_seconds,"
        " drop column if exists auto_pause_busy,"
        " drop column if exists auto_pause_unavail,"
        " drop column if exists agent_timeout_restart,"
        " drop column if exists max_wait_mode,"
        " drop column if exists leave_when_empty,"
        " drop column if exists announce_position_limit,"
        " drop column if exists announce_hold_time,"
        " drop column if exists min_announce_frequency_seconds,"
        " drop column if exists periodic_announce_audio_file_id,"
        " drop column if exists periodic_announce_frequency_seconds,"
        " drop column if exists ring_mode,"
        " drop column if exists mark_answered_elsewhere,"
        " drop column if exists cid_name_prefix,"
        " drop column if exists alert_info,"
        " drop column if exists join_announcement_audio_file_id,"
        " drop column if exists agent_announcement_audio_file_id,"
        " drop column if exists breakout_target_id;"
        "create or replace view asterisk_queues as"
        " select t.code || '-q-' || q.id::text as name, q.strategy,"
        " case when q.moh_class_id is null then 'default'"
        " else t.code || '-moh-' || q.moh_class_id::text end as musicclass,"
        " q.agent_ring_seconds as timeout, q.retry_seconds as retry, q.wrapup_seconds as wrapuptime,"
        " q.max_callers as maxlen, case when q.announce_position then 'yes' else 'no' end as announce_position,"
        " q.announce_frequency_seconds as announce_frequency, q.sla_seconds as servicelevel,"
        " case when q.join_empty then 'yes' else 'no' end as joinempty, 'no' as ringinuse"
        " from queues q join tenants t on t.id = q.tenant_id;",
    )
