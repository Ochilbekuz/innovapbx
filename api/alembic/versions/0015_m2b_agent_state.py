"""M2b §0/§1: queue_members dinamik/pauza ustunlari, agent_events, asterisk_agent_state
realtime view+trigger, asterisk_queue_members yangilanishi, *45/*46 funksiya kodlari.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-28
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0015_m2b_agent_state.sql")


def downgrade() -> None:
    run_sql_text(
        "drop trigger if exists asterisk_agent_state_update on asterisk_agent_state;"
        "drop function if exists asterisk_agent_state_update();"
        "drop view if exists asterisk_agent_state;"
        "drop trigger if exists queue_members_log_agent_event on queue_members;"
        "drop function if exists queue_members_log_agent_event();"
        "drop table if exists agent_events;"
        "delete from feature_codes where feature in ('queue_login', 'queue_pause');"
        "delete from feature_code_defaults where feature in ('queue_login', 'queue_pause');"
        "alter table queue_members drop column if exists dynamic;"
        "alter table queue_members drop column if exists logged_in;"
        "alter table queue_members drop column if exists paused;"
        "alter table queue_members drop column if exists pause_reason;"
        "alter table queue_members drop column if exists state_at;"
        "create or replace view asterisk_queue_members as "
        "  select t.code || '-q-' || q.id::text || '-' || e.number as uniqueid, "
        "         t.code || '-q-' || q.id::text as queue_name, "
        "         'PJSIP/' || t.code || '-' || e.number as interface, e.name as membername, "
        "         'PJSIP/' || t.code || '-' || e.number as state_interface, qm.penalty, 0 as paused "
        "  from queue_members qm join queues q on q.id = qm.queue_id "
        "  join extensions e on e.id = qm.extension_id join tenants t on t.id = q.tenant_id;"
    )
