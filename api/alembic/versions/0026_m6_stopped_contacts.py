"""M6: to'xtatilgan kampaniyalardagi «Navbatda» qolib ketgan kontaktlar → skipped/STOPPED.

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-01
"""
from __future__ import annotations

from app.db.raw_sql import run_sql_text

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql_text(
        "update campaign_contacts c set status = 'skipped', result = 'STOPPED', next_attempt_at = null"
        " from campaigns k where k.id = c.campaign_id and k.status = 'stopped'"
        " and c.status in ('pending', 'retry');"
    )


def downgrade() -> None:
    """Ma'lumot tuzatish — qaytarilmaydi (to'xtatish yakuniy holat)."""
