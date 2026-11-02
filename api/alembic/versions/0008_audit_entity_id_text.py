"""`audit_log.entity_id` uuid -> text (ishlab chiqarish xatosi: config_revision
restore har doim 500 bilan yiqilardi, chunki revision.id bigint, uuid ustunga
sig'maydi -- m1b-proof.sh ssenariy 6 orqali topilgan, 2026-10-28).

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-28
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

_SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "0008_audit_entity_id_text.sql"


def upgrade() -> None:
    run_sql_file(_SQL_FILE)


def downgrade() -> None:
    run_sql_text("alter table audit_log alter column entity_id type uuid using entity_id::uuid;")
