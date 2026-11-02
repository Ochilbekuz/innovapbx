"""M6: kampaniyalar (avtoinformator / avtoterish) — campaigns, kontaktlar, urinishlar, opt-out.

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-01
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0025_m6_campaigns.sql")


def downgrade() -> None:
    run_sql_text(
        "drop table if exists campaign_optouts; drop table if exists campaign_attempts;"
        "drop table if exists campaign_contacts; drop table if exists campaigns;"
    )
