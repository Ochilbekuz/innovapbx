"""MOH "Asosiy qilish" — `moh_classes.is_default` + tenant bo'yicha qisman
unique indeks (ko'pi bilan bitta asosiy sinf). Backfill: oldin nomi
"default" bo'lgan sinf — yangilangan serverda ko'rinish bir xil qoladi.

(Vaqt zonasi — A vazifa — ustunlar allaqachon mavjud, `tenant.timezone`;
migratsiya shart emas, faqat API/UI shuni ishlatadi.)

Revision ID: 0039_moh_tz
Revises: 0038_ringgroups_fpbx
Create Date: 2026-11-05
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0039_moh_tz"
down_revision = "0038_ringgroups_fpbx"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0039_moh_tz.sql")


def downgrade() -> None:
    run_sql_text(
        "drop index if exists ix_moh_classes_tenant_default;"
        "alter table moh_classes drop column if exists is_default;"
    )
