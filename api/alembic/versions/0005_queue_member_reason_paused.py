"""M1a: `asterisk_queue_members`ga `reason_paused` ustuni qo'shiladi
(sinovda topilgan `res_config_pgsql` ogohlantirishini bartaraf etish —
0005_queue_member_reason_paused.sql'da sabab).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-27
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "0005_queue_member_reason_paused.sql"


def upgrade() -> None:
    run_sql_file(_SQL_FILE)


def downgrade() -> None:
    run_sql_text(
        """
        create or replace view asterisk_queue_members as
          select t.code || '-q-' || q.id::text || '-' || e.number as uniqueid, t.code || '-q-' || q.id::text as queue_name,
                 'PJSIP/' || t.code || '-' || e.number as interface, e.name as membername,
                 'PJSIP/' || t.code || '-' || e.number as state_interface, qm.penalty, 0 as paused
          from queue_members qm join queues q on q.id = qm.queue_id
          join extensions e on e.id = qm.extension_id join tenants t on t.id = q.tenant_id;
        """
    )
