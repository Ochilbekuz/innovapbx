"""M2a §0–§3: pickup guruhi, funksiya kodlari (standartlar + seed), realtime DND/yo'naltirish view'i.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-28
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0013_m2a_call_features.sql")


def downgrade() -> None:
    run_sql_text(
        "drop trigger if exists tenants_seed_feature_codes on tenants;"
        "drop function if exists seed_tenant_feature_codes();"
        "drop view if exists asterisk_ext_state;"
        "drop function if exists asterisk_ext_state_update();"
        "delete from feature_codes where feature in ('cf_busy_on','cf_busy_off');"
        "drop table if exists feature_code_defaults;"
    )
