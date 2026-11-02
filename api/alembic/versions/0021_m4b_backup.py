"""M4b: Zaxira nusxa va tiklash (backups kengaytmasi, backup_copies, restore_jobs, system_settings.backup).

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-29
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0021_m4b_backup.sql")


def downgrade() -> None:
    run_sql_text(
        "drop table if exists restore_jobs;"
        "drop table if exists backup_copies;"
        "alter table system_settings drop column if exists backup;"
        "alter table alert_log drop constraint if exists alert_log_kind_check;"
        "alter table alert_log add constraint alert_log_kind_check check (kind in ("
        " 'ip_banned', 'toll_blocked', 'concurrent_limit', 'trunk_down', 'trunk_up', 'test',"
        " 'webhook_disabled', 'recording_error', 'prov_bruteforce'));"
        "alter table backups drop constraint if exists backups_kind_check;"
        "alter table backups drop constraint if exists backups_status_check;"
        "alter table backups drop column if exists kind;"
        "alter table backups drop column if exists components;"
        "alter table backups drop column if exists step;"
        "alter table backups drop column if exists progress;"
        "alter table backups drop column if exists file_name;"
        "alter table backups drop column if exists sha256;"
        "alter table backups drop column if exists manifest;"
        "alter table backups drop column if exists created_by;"
        "alter table backups add column if not exists target text not null default 'local';"
        "alter table backups add column if not exists path text;"
        "alter table backups alter column target drop default;"
        "alter table backups add constraint backups_target_check check (target in ('local', 's3', 'sftp'));"
        "alter table backups add constraint backups_status_check check (status in ('running', 'ok', 'failed'));"
    )
