"""extensions.enabled ustuni + ps_endpoints view yangilanishi.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-27
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "0002_extensions_enabled.sql"


def upgrade() -> None:
    run_sql_file(_SQL_FILE)


def downgrade() -> None:
    run_sql_text("alter table extensions drop column if exists enabled;")
