"""`ps_auths.realm` trunk (register) qatorlari uchun NULL (wildcard) qilindi
(ishlab chiqarish xatosi: register-rejimli trunklar haqiqiy provayderga HECH
QACHON registratsiyadan o'ta olmasdi, chunki chiquvchi auth uchun realm aniq
"asterisk" bilan solishtirilardi -- m1b-proof.sh ssenariy 7 orqali topilgan,
2026-10-28).

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-28
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

_SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "0009_trunk_auth_realm_wildcard.sql"


def upgrade() -> None:
    run_sql_file(_SQL_FILE)


def downgrade() -> None:
    run_sql_text(
        "create or replace view ps_auths as "
        "select t.code || '-' || e.number as id, 'userpass' as auth_type, "
        "t.code || '-' || e.number as username, sip_secret(e.sip_password_enc) as password, "
        "'asterisk' as realm from extensions e join tenants t on t.id = e.tenant_id "
        "union all "
        "select t.code || '-trunk-' || tr.id::text, 'userpass', tr.username, "
        "sip_secret(tr.password_enc), 'asterisk' from trunks tr join tenants t on t.id = tr.tenant_id "
        "where tr.auth_mode = 'register';"
    )
