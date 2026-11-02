"""M1a: `ps_endpoints` realtime view'iga `dtmf_mode='info'` qo'shiladi
(SIP INFO DTMF — m1a-proof.sh ssenariy 1 uchun, build-log.md'da sabab).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-27
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "0004_dtmf_info.sql"


def upgrade() -> None:
    run_sql_file(_SQL_FILE)


def downgrade() -> None:
    run_sql_text(
        """
        create or replace view ps_endpoints as
          select t.code || '-' || e.number as id, 'transport-' || case when e.webrtc then 'wss' else 'udp' end as transport,
                 t.code || '-' || e.number as aors, t.code || '-' || e.number as auth,
                 t.code || '-from-internal' as context, 'all' as disallow, array_to_string(e.codecs, ',') as allow,
                 'no' as direct_media, 'yes' as rtp_symmetric, 'yes' as force_rport,
                 'yes' as rewrite_contact,
                 '"' || coalesce(e.callerid_name, e.name) || '" <' || e.number || '>' as callerid,
                 t.code as accountcode, null::text as mailboxes,
                 case when e.webrtc then 'yes' else 'no' end as webrtc
          from extensions e join tenants t on t.id = e.tenant_id where t.status = 'active'
          union all
          select t.code || '-trunk-' || tr.id::text, 'transport-' || tr.transport, t.code || '-trunk-' || tr.id::text,
                 case when tr.auth_mode = 'register' then t.code || '-trunk-' || tr.id::text end,
                 t.code || '-from-trunk', 'all', array_to_string(tr.codecs, ','), 'no', 'yes', 'yes', 'no',
                 null, t.code, null, 'no'
          from trunks tr join tenants t on t.id = tr.tenant_id where tr.enabled and t.status = 'active';
        """
    )
