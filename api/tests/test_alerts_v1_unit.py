"""`app/api/v1/alerts.py` — M2c §4: `GET /alerts` (faqat o'qish, `alert_log`)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import alerts as al_v1

USER = SimpleNamespace(id="u1", tenant_id="t1")
NOW = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return SimpleNamespace(all=lambda: self._rows)


class _Session:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _stmt):
        return _Result(self.rows)


def _row(**kw):
    base = dict(id=1, at=NOW, kind="toll_blocked", key="201", body="matn", status="sent",
                error=None, sent_at=NOW)
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_list_alerts_maps_body_to_text():
    session = _Session([_row()])
    out = await al_v1.list_alerts(limit=50, kind=None, session=session, user=USER)
    assert out.items[0].text == "matn"
    assert out.items[0].kind == "toll_blocked"


@pytest.mark.asyncio
async def test_list_alerts_empty():
    session = _Session([])
    out = await al_v1.list_alerts(limit=50, kind=None, session=session, user=USER)
    assert out.items == []
