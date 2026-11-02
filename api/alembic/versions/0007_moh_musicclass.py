"""M1b: `asterisk_queues.musiconhold` -> `musicclass` (real xato — Asterisk
app_queue realtime ustun nomini aynan shu deb kutadi, boshqacha nomlansa
sukut ravishda e'tiborsiz qoldiriladi). Qiymat ham tenant+MOH-id asosiga
o'tdi (`app/services/moh.py` `asterisk_class_name()` bilan BIR XIL formula).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-28
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

_SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "0007_moh_musicclass.sql"


def upgrade() -> None:
    run_sql_file(_SQL_FILE)


def downgrade() -> None:
    run_sql_text(
        """
        drop view asterisk_queues;
        create view asterisk_queues as
          select t.code || '-q-' || q.id::text as name, q.strategy, coalesce(m.name, 'default') as musiconhold,
                 q.agent_ring_seconds as timeout, q.retry_seconds as retry, q.wrapup_seconds as wrapuptime,
                 q.max_callers as maxlen, case when q.announce_position then 'yes' else 'no' end as announce_position,
                 q.announce_frequency_seconds as announce_frequency, q.sla_seconds as servicelevel,
                 case when q.join_empty then 'yes' else 'no' end as joinempty, 'no' as ringinuse
          from queues q join tenants t on t.id = q.tenant_id
          left join moh_classes m on m.id = q.moh_class_id;
        """
    )
