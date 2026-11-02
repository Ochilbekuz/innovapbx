"""M3b (CRM): Bitrix24/amoCRM sozlamalari, foydalanuvchi xaritasi, qo'ng'iroq ↔ CRM kartasi bog'lanishi.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-29
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0019_m3b_crm.sql")


def downgrade() -> None:
    run_sql_text(
        "drop table if exists crm_call_links, crm_user_map, crm_users;"
        "delete from integration_subscriptions where kind in ('bitrix24', 'amocrm');"
        "drop index if exists integration_subscriptions_hook_token_uniq;"
        "drop index if exists integration_subscriptions_crm_uniq;"
        "drop trigger if exists integration_subscriptions_touch on integration_subscriptions;"
        "create trigger integration_subscriptions_touch before update on integration_subscriptions"
        " for each row execute function touch_updated_at();"
        "alter table integration_subscriptions drop column if exists last_error;"
    )
