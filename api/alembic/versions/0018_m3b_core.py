"""M3b (core): yozuvlar, hodisalar outbox'i, webhook obunalari, API kalitlari.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-29
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0018_m3b_core.sql")


def downgrade() -> None:
    run_sql_text(
        "drop table if exists api_originate_requests, api_keys, integration_deliveries,"
        " integration_subscriptions, integration_events, call_event_state, call_recordings;"
        # PG view'dan ustun olib tashlashga ruxsat bermaydi — qayta yaratiladi (+ 0013 trigger'i).
        "drop view if exists asterisk_ext_state;"
        "create view asterisk_ext_state as select t.code || '-' || e.number as endpoint,"
        " e.dnd, e.forward_always, e.forward_busy from extensions e join tenants t on t.id = e.tenant_id"
        " where t.status = 'active';"
        "create trigger asterisk_ext_state_update instead of update on asterisk_ext_state"
        " for each row execute function asterisk_ext_state_update();"
        "delete from alert_log where kind in ('webhook_disabled', 'recording_error');"
        "alter table alert_log drop constraint if exists alert_log_kind_check;"
        "alter table alert_log add constraint alert_log_kind_check check (kind in"
        " ('ip_banned', 'toll_blocked', 'concurrent_limit', 'trunk_down', 'trunk_up', 'test'));"
        "alter table system_settings drop column if exists recording, drop column if exists integrations;"
    )
