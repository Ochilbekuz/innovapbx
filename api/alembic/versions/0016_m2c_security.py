"""M2c: SIP hujum himoyasi (ip_bans, sip_attack_stats, security_events), toll-fraud
(extensions.toll_*, outbound_attempts), ogohlantirishlar (alert_log), system_settings.sip_guard.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-28
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0016_m2c_security.sql")


def downgrade() -> None:
    run_sql_text(
        "drop table if exists alert_log;"
        "drop table if exists outbound_attempts;"
        "drop table if exists security_events;"
        "drop table if exists sip_attack_stats;"
        "drop table if exists ip_bans;"
        "alter table extensions drop column if exists toll_blocked_at;"
        "alter table extensions drop column if exists toll_block_reason;"
        "alter table extensions drop column if exists toll_unblocked_at;"
        "alter table system_settings drop column if exists sip_guard;"
    )
