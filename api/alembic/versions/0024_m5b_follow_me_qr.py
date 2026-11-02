"""M5b: Follow Me (realtime view ustunlari, *21) + QR orqali sozlash tokenlari.

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-01
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0024_m5b_follow_me_qr.sql")


def downgrade() -> None:
    # View ustunlarini PG `create or replace` bilan olib tashlab bo'lmaydi — 0018 holatiga qayta yaratiladi.
    run_sql_text(
        "drop table if exists qr_provision_tokens;"
        "delete from feature_codes where feature = 'followme_toggle';"
        "delete from feature_code_defaults where feature = 'followme_toggle';"
        "alter table extensions drop constraint if exists extensions_follow_me_shape;"
        "drop view if exists asterisk_ext_state;"
        "create view asterisk_ext_state as"
        "  select t.code || '-' || e.number as endpoint, e.dnd, e.forward_always, e.forward_busy, e.recording,"
        "         case when coalesce((s.recording ->> 'external_only')::boolean, false) then 't' else 'f' end"
        "           as rec_external_only"
        "  from extensions e join tenants t on t.id = e.tenant_id"
        "  left join system_settings s on s.tenant_id = e.tenant_id where t.status = 'active';"
        "create or replace function asterisk_ext_state_update() returns trigger language plpgsql as $$"
        " begin update extensions e set dnd = new.dnd, forward_always = nullif(new.forward_always, ''),"
        " forward_busy = nullif(new.forward_busy, '') from tenants t"
        " where t.id = e.tenant_id and t.code || '-' || e.number = old.endpoint; return new; end $$;"
        "create trigger asterisk_ext_state_update instead of update on asterisk_ext_state"
        "  for each row execute function asterisk_ext_state_update();"
    )
