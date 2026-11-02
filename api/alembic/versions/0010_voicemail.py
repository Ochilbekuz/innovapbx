"""M1c §2: ovozli pochta — `voicemail_boxes.email/telegram_chat_id`,
`notify_settings`, `voicemail_notifications`, `ps_endpoints.mailboxes`
(faqat qutisi bor ichki raqam uchun — sabab SQL faylida).

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-28
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0010_voicemail.sql")


def downgrade() -> None:
    # View avval 0004 shakliga (mailboxes = NULL) qaytariladi — u yangi
    # jadvallarga bog'liq bo'lmasin, keyin jadval/ustunlar olib tashlanadi.
    run_sql_file(_SQL_DIR / "0004_dtmf_info.sql")
    run_sql_text(
        "drop table if exists voicemail_notifications;"
        "drop table if exists notify_settings;"
        "alter table voicemail_boxes drop constraint if exists voicemail_boxes_mailbox_check;"
        "alter table voicemail_boxes drop column if exists telegram_chat_id;"
        "alter table voicemail_boxes drop column if exists email;"
    )
