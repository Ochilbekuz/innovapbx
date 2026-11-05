"""M-CRM §2 (Bitrix24 yozuv yuklash): `crm_call_links` ga `finished_at` +
`record_attached` — `finish` muvaffaqiyatli bo'lgach yozilgan, keyingi
retry'lar `finish`ni qayta YUBORMAYDI (`attachRecord` mustaqil qayta uriniladi).

Revision ID: 0036_m_crm
Revises: 0035_m12a
Create Date: 2026-11-05
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0036_m_crm"
down_revision = "0035_m12a"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0036_m_crm_call_state.sql")


def downgrade() -> None:
    run_sql_text(
        "alter table crm_call_links drop column if exists finished_at;"
        "alter table crm_call_links drop column if exists record_attached;"
    )
