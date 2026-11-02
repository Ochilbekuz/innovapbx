"""`PATCH /settings/sip` marshrut funksiyasi — DB/AMI'siz (soxta sessiya, tashqi qadamlar
monkeypatch). Jonli oqim `test_integration_live.py` va `scripts/m1b-proof.sh` da."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import settings as st
from app.core.errors import ApiError
from app.schemas import UpdateSipSettingsPayload

USER = SimpleNamespace(id="u1", tenant_id="t1")


def _row(**over):
    base = dict(external_ip=None, external_host=None, local_nets=["10.0.0.0/8"], sip_udp_port=5060,
                sip_tls_port=None, rtp_start=10000, rtp_end=20000, codecs=["ulaw"], restart_required=False,
                updated_at=datetime(2026, 10, 28, tzinfo=timezone.utc))
    return SimpleNamespace(**(base | over))


class _Session:
    def __init__(self, row):
        self.row, self.commits = row, 0

    async def get(self, model, key):
        return self.row if key == "t1" else None

    async def flush(self):
        pass

    async def commit(self):
        self.commits += 1


@pytest.fixture
def world(monkeypatch):
    calls = SimpleNamespace(audit=[], applied=[], apply_error=None)

    async def fake_audit(session, **kw):
        calls.audit.append(kw)

    async def fake_apply(ami, cfg, *, reload_rtp):
        if calls.apply_error:
            raise calls.apply_error
        calls.applied.append((cfg, reload_rtp))

    monkeypatch.setattr(st, "record_audit", fake_audit)
    monkeypatch.setattr(st, "apply_sip_config", fake_apply)
    monkeypatch.setattr(st, "detect_public_ip", lambda: None)
    monkeypatch.setattr(st, "detect_local_ips", lambda: [])
    monkeypatch.setattr("app.services.sip_transport.read_cert_metadata", lambda: None)
    return calls


async def _patch(row, apply=True, **item):
    session = _Session(row)
    payload = UpdateSipSettingsPayload.model_validate({"item": item, "apply": apply})
    out = await st.update_sip_settings(payload, session=session, user=USER, ami=object())
    return out, session


async def test_rtp_change_is_applied_live_without_restart(world):
    row = _row()
    out, session = await _patch(row, rtp_end=15000)
    assert (out.item.rtp_end, out.apply.status, out.apply.message) == (15000, "applied", None)
    assert session.commits == 1 and row.restart_required is False
    assert world.applied[0][0].rtp_end == 15000 and world.applied[0][1] is True
    assert world.audit[0]["diff"] == {"rtp_end": 15000} and world.audit[0]["entity"] == "sip_settings"


async def test_transport_change_marks_restart_required(world):
    row = _row()
    out, _ = await _patch(row, sip_udp_port=5070)
    assert out.apply.status == "restart_required" and row.restart_required is True


async def test_pending_restart_is_kept_after_unrelated_change(world):
    out, _ = await _patch(_row(restart_required=True), rtp_end=15000)
    assert out.apply.status == "restart_required"


async def test_apply_false_only_saves(world):
    out, session = await _patch(_row(), apply=False, rtp_end=15000)
    assert world.applied == [] and session.commits == 1
    assert out.apply.status == "applied" and "apply=false" in out.apply.message


async def test_asterisk_push_failure_is_502_after_commit(world):
    world.apply_error = RuntimeError("AMI yopiq")
    with pytest.raises(ApiError) as exc:
        await _patch(_row(), rtp_end=15000)
    assert (exc.value.status_code, exc.value.code) == (502, "sip_apply_failed")
    assert "AMI yopiq" in exc.value.message
