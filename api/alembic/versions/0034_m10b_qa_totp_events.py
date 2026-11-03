"""M10 Bo'lak B: QA baholash (qa_checklists/qa_criteria/qa_evaluations),
2FA TOTP (users.totp_* + totp_challenges + system_settings.require_2fa) va
tashqi WS hodisalar uchun zamin (api_keys.scopes — Python tomonida).

DIQQAT (ub-mode §0, parallel agentlar): `down_revision` ataylab
"0033_m10a" (Agent A yaratadigan callback/missed-call/TTS migratsiyasiga
zanjirlangan) — bu loyihaning odatdagi sof-raqamli revizion andozasidan
(masalan "0032") ATAYLAB chetlanish, faqat shu parallel ishlov uchun.
Agent A o'z faylida `revision = "0033_m10a"` (aynan shu satr) ishlatishi
SHART, aks holda zanjir uzilidi.

Revision ID: 0034_m10b
Revises: 0033_m10a
Create Date: 2026-11-03
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0034_m10b"
down_revision = "0033_m10a"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0034_m10b_qa_totp_events.sql")


def downgrade() -> None:
    run_sql_text(
        "drop table if exists totp_challenges;"
        "alter table system_settings drop constraint if exists system_settings_require_2fa_check;"
        "alter table system_settings drop column if exists require_2fa;"
        "alter table users drop column if exists totp_last_step;"
        "alter table users drop column if exists totp_recovery_hashes;"
        "alter table users drop column if exists totp_enabled_at;"
        "drop table if exists qa_evaluations;"
        "drop table if exists qa_criteria;"
        "drop table if exists qa_checklists;"
    )
