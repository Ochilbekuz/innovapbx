"""M1a: tenant uchun tizim manzillari (hangup/busy) avtomatik seed.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-27
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "0003_m1a_seed.sql"


def upgrade() -> None:
    run_sql_file(_SQL_FILE)


def downgrade() -> None:
    run_sql_text("drop trigger if exists tenants_seed_defaults on tenants;")
    run_sql_text("drop function if exists innova_seed_tenant_defaults();")
