"""M9 Bo'lak B: PIN to'plamlari (`pin_sets`/`pin_set_pins` + `outbound_routes.pin_set_id`),
telefon kitobi (`phonebook_contacts`/`phonebook_numbers`) va CID Lookup manbalari
(`cid_lookup_sources` + `inbound_routes.cid_lookup_source_id`), kiruvchi marshrutda
SIP Alert-Info (`inbound_routes.alert_info`).

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-03
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0032_m9b_pinsets_phonebook_cidlookup_alertinfo.sql")


def downgrade() -> None:
    run_sql_text(
        "alter table security_events drop constraint if exists security_events_kind_check;"
        "alter table security_events add constraint security_events_kind_check"
        " check (kind in ('ip_banned', 'ip_unbanned', 'ban_expired',"
        " 'toll_blocked', 'toll_unblocked', 'concurrent_limit', 'ws_auth_failed'));"
        "alter table cdr drop column if exists pin_label;"
        "alter table inbound_routes drop column if exists alert_info;"
        "alter table inbound_routes drop column if exists cid_lookup_source_id;"
        "drop table if exists cid_lookup_sources;"
        "drop table if exists phonebook_numbers;"
        "drop table if exists phonebook_contacts;"

        "alter table outbound_routes drop column if exists pin_set_id;"
        "drop table if exists pin_set_pins;"
        "drop table if exists pin_sets;"
    )
