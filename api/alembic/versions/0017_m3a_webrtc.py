"""M3a: WebRTC softfon — security_events.transport (+ `ws_auth_failed`), webrtc raqamda DTMF rfc4733.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-29
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0017_m3a_webrtc.sql")


def downgrade() -> None:
    # ps_endpoints 0013 holatiga qaytadi (dtmf_mode doim `info`) — view matni 0017 dan olinadi.
    sql = (_SQL_DIR / "0017_m3a_webrtc.sql").read_text()
    view = sql[sql.index("create or replace view ps_endpoints"):]
    run_sql_text(view.replace("case when e.webrtc then 'rfc4733' else 'info' end", "'info'"))
    run_sql_text(
        "delete from security_events where kind = 'ws_auth_failed';"
        "alter table security_events drop constraint if exists security_events_kind_check;"
        "alter table security_events add constraint security_events_kind_check check (kind in "
        "('ip_banned','ip_unbanned','ban_expired','toll_blocked','toll_unblocked','concurrent_limit'));"
        "alter table security_events drop column if exists transport;"
    )
