"""Boshlang'ich sxema — replica/schema.sql dan (yagona manba, api/alembic/sql/0001_schema.sql
sifatida ko'chirilgan; sinxronlikni `replica/build-log.md` da kuzatib boring).

Revision ID: 0001
Revises:
Create Date: 2026-10-27
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "0001_schema.sql"


def upgrade() -> None:
    # `op.execute`/`exec_driver_sql` EMAS — alembic/_psql_exec.py'dagi izohga
    # qarang (asyncpg ko'p-buyruqli bayonotni va PL/pgSQL `%I`ni rad etadi).
    run_sql_file(_SQL_FILE)


def downgrade() -> None:
    run_sql_text("drop schema public cascade; create schema public;")
