"""Tuzatish (b): vaqt sharti `toggle_code` yaratish/o'zgartirishda xususiyat kodlari
bilan to'qnashuvi (teng yoki prefiks) — `feature_codes.validate_feature_code` BIR XIL
qoida bilan, DB/AMI'siz (monkeypatch)."""
from __future__ import annotations

import pytest

from app.api.v1 import time_conditions as tcr
from app.core.errors import ApiError


@pytest.mark.asyncio
async def test_no_clash_passes(monkeypatch):
    async def fake_codes(session, tenant_id):
        return ["*72", "*97"]

    monkeypatch.setattr(tcr, "feature_code_strings", fake_codes)
    await tcr._validate_toggle_code(None, "t1", "*28")


@pytest.mark.asyncio
@pytest.mark.parametrize("code,others", [("*72", ["*72"]), ("*7", ["*72"]), ("*721", ["*72"])])
async def test_equal_or_prefix_clash_raises_409(monkeypatch, code, others):
    async def fake_codes(session, tenant_id):
        return others

    monkeypatch.setattr(tcr, "feature_code_strings", fake_codes)
    with pytest.raises(ApiError) as e:
        await tcr._validate_toggle_code(None, "t1", code)
    assert (e.value.status_code, e.value.code) == (409, "code_taken")


@pytest.mark.asyncio
async def test_resubmitting_own_current_code_skips_check(monkeypatch):
    async def fake_codes(session, tenant_id):
        raise AssertionError("tekshirilmasin — kod o'zgarmagan")

    monkeypatch.setattr(tcr, "feature_code_strings", fake_codes)
    await tcr._validate_toggle_code(None, "t1", "*28", current="*28")
