"""M5a: FreePBX'dan ko'chirish (migration_jobs, migration_items, backups.kind +pre_import).

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-30
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0022_m5a_migration.sql")


def downgrade() -> None:
    run_sql_text(
        "drop table if exists migration_items;"
        "drop table if exists migration_jobs;"
        "alter table backups drop constraint if exists backups_kind_check;"
        "alter table backups add constraint backups_kind_check "
        "check (kind in ('scheduled', 'manual', 'pre_restore', 'uploaded'));"
    )
