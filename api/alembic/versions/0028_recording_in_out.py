"""Ichki raqamda ikkita alohida yozuv siyosati: `extensions.recording`
(nomi o'zgarmaydi) endi KIRUVCHI, yangi `extensions.recording_out` —
CHIQUVCHI (boshlang'ich qiymat = mavjud `recording`). `asterisk_ext_state`
view'iga `recording_out` ustuni OXIRIGA qo'shiladi.

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-02
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0028_recording_in_out.sql")


def downgrade() -> None:
    """0027'ning `asterisk_ext_state` ta'rifini (recording_out'siz) qayta
    tiklaydi va ustunni o'chiradi."""
    run_sql_text(
        "create or replace view asterisk_ext_state as"
        "  select e.number as endpoint, e.dnd, e.forward_always, e.forward_busy,"
        "         e.recording,"
        "         case when coalesce((s.recording ->> 'external_only')::boolean, false) then 't' else 'f' end"
        "           as rec_external_only,"
        "         coalesce((e.follow_me ->> 'enabled')::boolean, false) as fm_enabled,"
        "         e.follow_me ->> 'strategy' as fm_strategy,"
        "         (e.follow_me ->> 'ring_seconds')::int as fm_ring,"
        "         case when coalesce((e.follow_me ->> 'confirm')::boolean, true) then 't' else 'f' end"
        "           as fm_confirm,"
        "         (select string_agg(n, '&' order by o) from jsonb_array_elements_text(e.follow_me -> 'numbers')"
        "            with ordinality as x(n, o)) as fm_numbers,"
        "         (select string_agg('Local/' || n || '@' || t.code || '-fm-leg/n', '&' order by o)"
        "            from (select e.number as n, 0::bigint as o"
        "                   where coalesce((e.follow_me ->> 'include_extension')::boolean, true)"
        "                  union all"
        "                  select n, o from jsonb_array_elements_text(e.follow_me -> 'numbers')"
        "                    with ordinality as x(n, o)) legs)"
        "           as fm_dial"
        "  from extensions e join tenants t on t.id = e.tenant_id"
        "  left join system_settings s on s.tenant_id = e.tenant_id"
        "  where t.status = 'active';"

        "alter table extensions drop column if exists recording_out;"
    )
