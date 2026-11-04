"""M12 Bo'lak A (asterisk-engineer): Kun/Tun rejimi (`day_night`, *28N funksiya
kodi, BLF) + DISA (`disa`, PIN 3 urinish, faqat chiquvchi marshrutlarga Goto).

`call_targets.kind`ga `day_night`/`disa` qo'shiladi.

Revision ID: 0035_m12a
Revises: 0034_m10b
Create Date: 2026-11-04
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0035_m12a"
down_revision = "0034_m10b"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0035_m12a_daynight_disa.sql")


def downgrade() -> None:
    run_sql_text(
        "drop table if exists disa;"
        "drop table if exists day_night;"

        "alter table call_targets drop constraint if exists call_targets_kind_check;"
        "alter table call_targets add constraint call_targets_kind_check check (kind in ("
        "  'extension','ring_group','queue','ivr','time_condition','announcement','voicemail',"
        "  'conference','external','hangup','busy','feature','misc'));"

        "alter table security_events drop constraint if exists security_events_kind_check;"
        "alter table security_events add constraint security_events_kind_check check (kind in ("
        "  'ip_banned','ip_unbanned','ban_expired','toll_blocked','toll_unblocked','concurrent_limit',"
        "  'ws_auth_failed','pinset_fail','pinset_rate_limited'));"
    )
