"""M10 Bo'lak A: qayta chaqirish vidjeti (`callback_widgets`/`callback_requests`),
o'tkazib yuborilgan qo'ng'iroq bildirishnomasi (`missed_call_rules`/`missed_call_notices`/
`missed_notify_cursor`) va Yandex SpeechKit TTS sozlamalari (`tts_settings`).

DIQQAT: B bo'lagi (`0034_m10b_*`) shu faylga ZANJIRLANADI (`down_revision="0033_m10a"`)
— shu sabab bu fayl birinchi yaratilgan (m10-onlinepbx-contract.md §0).

Revision ID: 0033_m10a
Revises: 0032
Create Date: 2026-11-03
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0033_m10a"
down_revision = "0032"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0033_m10a_callback_missed_tts.sql")


def downgrade() -> None:
    run_sql_text(
        "drop table if exists tts_settings;"
        "drop table if exists missed_notify_cursor;"
        "drop table if exists missed_call_notices;"
        "drop table if exists missed_call_rules;"
        "drop table if exists callback_requests;"
        "drop table if exists callback_widgets;"
    )
