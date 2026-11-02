"""M1b: `system_settings.codecs`/`restart_required` ustunlari + har tenant
uchun o'chirib bo'lmaydigan `default` MOH sinfi (seed).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-27
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "0006_m1b_settings_moh.sql"


def upgrade() -> None:
    run_sql_file(_SQL_FILE)


def downgrade() -> None:
    run_sql_text(
        """
        drop trigger if exists tenants_seed_moh on tenants;
        drop function if exists innova_seed_tenant_moh();
        alter table system_settings drop column if exists codecs;
        alter table system_settings drop column if exists restart_required;
        """
    )
