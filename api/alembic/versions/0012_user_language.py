"""M1c §4: `users.language` — har foydalanuvchining interfeys tili (NULL = tenant tili).

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-28
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0012_user_language.sql")


def downgrade() -> None:
    run_sql_text("alter table users drop column if exists language;")
