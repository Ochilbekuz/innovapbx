"""M4a: telefon apparatlarini avtoprovizioning (devices kengaytmasi, tugmalar, topilganlar, jurnal, sozlamalar).

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-29
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0020_m4a_provisioning.sql")


def downgrade() -> None:
    run_sql_text(
        "delete from alert_log where kind = 'prov_bruteforce';"
        "alter table alert_log drop constraint if exists alert_log_kind_check;"
        "alter table alert_log add constraint alert_log_kind_check check (kind in ("
        " 'ip_banned', 'toll_blocked', 'concurrent_limit', 'trunk_down', 'trunk_up', 'test',"
        " 'webhook_disabled', 'recording_error'));"
        "drop index if exists system_settings_prov_token_uniq;"
        "alter table system_settings drop column if exists provisioning;"
        "drop table if exists provision_requests, discovered_devices, device_keys;"
        "drop trigger if exists devices_touch on devices;"
        "create trigger devices_touch before update on devices for each row execute function touch_updated_at();"
        "drop index if exists devices_tenant_idx;"
        "alter table devices drop column if exists label, drop column if exists last_seen_at,"
        " drop column if exists last_ip, drop column if exists user_agent, drop column if exists firmware,"
        " drop column if exists config_hash, drop column if exists enabled, drop column if exists notes;"
    )
