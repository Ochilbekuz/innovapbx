"""M2a §4/§5: konferensiya/qora ro'yxat + tuzatish (a) forward raqam normalizatsiyasi.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-28
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0014_m2a_conference_blacklist.sql")


def downgrade() -> None:
    run_sql_text(
        "drop view if exists asterisk_blacklist;"
        "alter table blacklist drop constraint if exists blacklist_number_check;"
        "alter table extensions drop constraint if exists extensions_forward_always_check;"
        "alter table extensions add constraint extensions_forward_always_check "
        "check (forward_always ~ '^\\+?[0-9]{2,15}$');"
        "alter table extensions drop constraint if exists extensions_forward_busy_check;"
        "alter table extensions add constraint extensions_forward_busy_check "
        "check (forward_busy ~ '^\\+?[0-9]{2,15}$');"
    )
