"""M5a SSH: `migration_jobs.status` ga `fetching` qo'shiladi (`/ssh/fetch` fon vazifasi).

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-30
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0023_m5a_ssh_status.sql")


def downgrade() -> None:
    run_sql_text(
        "alter table migration_jobs drop constraint if exists migration_jobs_status_check;"
        "alter table migration_jobs add constraint migration_jobs_status_check "
        "check (status in ('uploaded', 'analyzing', 'analyzed', 'applying', 'ok', 'failed'));"
    )
