"""S32 — `PATCH /settings/sip` kirish qoidalari (sof funksiyalar, Asterisk/DB'siz)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1.settings import _changes, _validate_sip_update
from app.core.errors import ApiError
from app.schemas import UpdateSipSettingsItem

ROW = SimpleNamespace(sip_udp_port=5060, sip_tls_port=5061, rtp_start=10000, rtp_end=20000)


def _item(**body) -> UpdateSipSettingsItem:
    return UpdateSipSettingsItem.model_validate(body)


def test_changes_omitted_fields_are_absent():
    assert _changes(_item(rtp_end=15000)) == {"rtp_end": 15000}


def test_changes_explicit_null_clears_nullable_fields():
    assert _changes(_item(external_ip=None, external_host=None, sip_tls_port=None)) == {
        "external_ip": None, "external_host": None, "sip_tls_port": None}


def test_changes_explicit_null_ignored_for_required_fields():
    assert _changes(_item(sip_udp_port=None, local_nets=None, codecs=None)) == {}


def _code(changes: dict) -> str:
    with pytest.raises(ApiError) as exc:
        _validate_sip_update(changes, ROW)
    return exc.value.code


@pytest.mark.parametrize("changes, code", [
    ({"external_ip": "999.1.1.1"}, "bad_ip"),
    ({"local_nets": ["10.0.0.0/33"]}, "bad_cidr"),
    ({"sip_udp_port": 70000}, "bad_port"),
    ({"sip_tls_port": 0}, "bad_port"),
    ({"rtp_start": 0}, "bad_port"),
    ({"rtp_end": 70000}, "bad_port"),
    ({"rtp_end": 10050}, "rtp_range"),
    ({"sip_udp_port": 15000}, "rtp_range"),
    ({"sip_tls_port": 12000}, "rtp_range"),
])
def test_invalid_updates_rejected(changes, code):
    assert _code(changes) == code


def test_valid_update_passes_and_tls_can_be_disabled():
    _validate_sip_update({"external_ip": "203.0.113.7", "sip_tls_port": None,
                          "local_nets": ["192.168.1.0/24"], "rtp_start": 30000, "rtp_end": 30999}, ROW)


def test_merged_values_use_row_for_omitted_fields():
    # rtp_end 20000 qatordan olinadi — 19950..20000 = 50 port < 100
    assert _code({"rtp_start": 19950}) == "rtp_range"
