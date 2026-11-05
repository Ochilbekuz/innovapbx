"""FreePBX Ring Groups moduli parity: strategiya to'liq ro'yxati, e'lon audio,
jiringlashda MOH, Alert-Info, band a'zoni o'tkazib yuborish, tashqi a'zo uchun
tasdiqlash qo'ng'irog'i va yozib olish siyosatini bekor qilish.

Revision ID: 0038_ringgroups_fpbx
Revises: 0037_queues_fpbx
Create Date: 2026-11-05
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0038_ringgroups_fpbx"
down_revision = "0037_queues_fpbx"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0038_ringgroups_fpbx.sql")


def downgrade() -> None:
    run_sql_text(
        "alter table ring_groups drop constraint if exists ring_groups_recording_policy_check;"
        "alter table ring_groups drop column if exists recording_policy;"
        "alter table ring_groups drop column if exists remote_announce_audio_id;"
        "alter table ring_groups drop column if exists confirm_calls;"
        "alter table ring_groups drop column if exists skip_busy_agent;"
        "alter table ring_groups drop column if exists alert_info;"
        "alter table ring_groups drop column if exists moh_class_id;"
        "alter table ring_groups drop constraint if exists ring_groups_ring_strategy_sound_check;"
        "alter table ring_groups drop column if exists ring_strategy_sound;"
        "alter table ring_groups drop column if exists announcement_audio_id;"
        "alter table ring_groups drop constraint if exists ring_groups_strategy_check;"
        "alter table ring_groups add constraint ring_groups_strategy_check "
        "check (strategy in ('ringall','hunt','memoryhunt'));"
    )
