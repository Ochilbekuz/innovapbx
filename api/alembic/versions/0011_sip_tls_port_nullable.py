"""M1c §3: SIP TLS. `system_settings.sip_tls_port` endi NULL bo'lishi mumkin
(TLS o'chirilgan holatni bildiradi) — API qatlami bu semantikani allaqachon
qo'llab-quvvatlaydi (`app/services/sip_transport.py`, `app/api/v1/settings.py`).

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-28
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0011_sip_tls_port_nullable.sql")


def downgrade() -> None:
    run_sql_text(
        "update system_settings set sip_tls_port = 5061 where sip_tls_port is null;"
        "alter table system_settings alter column sip_tls_port set not null;"
    )
