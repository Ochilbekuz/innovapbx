"""Ovozli pochta bildirishnomasi KAMIDA-BIR-MARTA: `voicemail_notifications`ga
`next_attempt_at` ustuni (qayta urinish vaqti) + `dead` holati (ulgurib
bo'lmagan, outbox qolipi bilan bir xil).

Revision ID: 0030
Revises: 0028
Create Date: 2026-11-02
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0030"
down_revision = "0028"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0030_vm_notify_retry.sql")


def downgrade() -> None:
    run_sql_text(
        "drop index if exists voicemail_notifications_status_next_attempt_at_idx;"
        "alter table voicemail_notifications drop constraint if exists voicemail_notifications_status_check;"
        "alter table voicemail_notifications"
        "  add constraint voicemail_notifications_status_check check (status in ('pending', 'sent', 'failed'));"
        "alter table voicemail_notifications drop column if exists next_attempt_at;"
    )
