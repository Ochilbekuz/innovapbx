"""CONFIRMED HIGH tuzatish — dialplan injection: FreePBX migratsiyasi
(`app/services/fpbx/writers/routes.py`) `app/schemas.py` Pydantic validatsiyasini
CHETLAB O'TADI (bevosita FreePBX backup'idan DB'ga yozadi), shu sabab
`write_inbound_route`/`write_outbound_route`/`_patterns` o'zi ham tekshirishi
SHART (ikkinchi himoya chizig'i — DB'siz: xavfli qiymat `session.execute`
chaqirilishidan OLDIN rad etiladi, shu sabab `session=None` bilan ham sinaladi)."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.services.fpbx.mappers import Entry
from app.services.fpbx.writers.context import SkipItem, WriteCtx
from app.services.fpbx.writers.routes import _patterns, write_inbound_route, write_outbound_route

BAD_NUMBER = "${SHELL(id)}"
CRLF_NAME = "Ali\nexten => 999,1,System(rm -rf /)"


def _ctx() -> WriteCtx:
    return WriteCtx(session=None, tenant_id="t", tenant_code="t1", job_id="j",
                     bundle_dir=Path("."), sounds_dir=Path("."))


def _entry(kind: str, payload: dict) -> Entry:
    return Entry(kind=kind, source_ref=f"{kind}:1", name=payload.get("name") or "x", number=None,
                 action="create", payload=payload)


def test_write_inbound_route_rejects_bad_did():
    entry = _entry("inbound_route", {"name": "Route1", "did": BAD_NUMBER, "target_id": None})
    with pytest.raises(SkipItem):
        asyncio.run(write_inbound_route(_ctx(), entry))


def test_write_inbound_route_rejects_bad_cid():
    entry = _entry("inbound_route", {"name": "Route1", "callerid_pattern": BAD_NUMBER, "target_id": None})
    with pytest.raises(SkipItem):
        asyncio.run(write_inbound_route(_ctx(), entry))


def test_write_inbound_route_rejects_crlf_name():
    entry = _entry("inbound_route", {"name": CRLF_NAME, "target_id": None})
    with pytest.raises(SkipItem):
        asyncio.run(write_inbound_route(_ctx(), entry))


def test_write_inbound_route_rejects_crlf_cid_name_prefix():
    entry = _entry("inbound_route", {"name": "Route1", "callerid_name_prefix": CRLF_NAME, "target_id": None})
    with pytest.raises(SkipItem):
        asyncio.run(write_inbound_route(_ctx(), entry))


def test_write_outbound_route_rejects_bad_callerid():
    entry = _entry("outbound_route", {"name": "Route1", "callerid": BAD_NUMBER})
    with pytest.raises(SkipItem):
        asyncio.run(write_outbound_route(_ctx(), entry))


def test_write_outbound_route_rejects_crlf_name():
    entry = _entry("outbound_route", {"name": CRLF_NAME})
    with pytest.raises(SkipItem):
        asyncio.run(write_outbound_route(_ctx(), entry))


def test_patterns_skips_bad_add_prefix_with_warning():
    ctx = _ctx()
    entry = _entry("outbound_route", {"name": "Route1",
                                       "patterns": [{"pattern": "998XXXXXXXXX", "add_prefix": BAD_NUMBER}]})
    result = _patterns(ctx, entry)
    assert result == []
    assert ctx.warnings and ctx.warnings[0]["code"] == "add_prefix_invalid"


def test_patterns_accepts_valid_add_prefix():
    ctx = _ctx()
    entry = _entry("outbound_route", {"name": "Route1",
                                       "patterns": [{"pattern": "998XXXXXXXXX", "add_prefix": "0"}]})
    result = _patterns(ctx, entry)
    assert len(result) == 1
    assert result[0].add_prefix == "0"
