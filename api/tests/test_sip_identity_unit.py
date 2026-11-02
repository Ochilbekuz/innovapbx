"""`app/services/sip_identity.py` — ichki raqam SIP nomlashining yagona qoidasi:
endpoint id prefiks O'CHIRILGAN, lekin eski (tenant-prefiksli) kanal nomlarini
tarixiy hisobot/yozuvlar uchun hamon tanish kerak (dual-format)."""
from __future__ import annotations

from app.services import sip_identity as si


def test_endpoint_id_is_the_raw_number():
    assert si.endpoint_id("103") == "103"


def test_pjsip_interface_has_no_tenant_prefix():
    assert si.pjsip_interface("103") == "PJSIP/103"


def test_extension_from_channel_new_format():
    assert si.extension_from_channel("PJSIP/103-00000001") == "103"


def test_extension_from_channel_legacy_format_with_tenant_prefix():
    assert si.extension_from_channel("PJSIP/t1-103-00000001") == "103"


def test_extension_from_channel_legacy_bare_no_pjsip_prefix():
    assert si.extension_from_channel("t1-101") == "101"


def test_extension_from_channel_new_bare_no_hex_suffix():
    assert si.extension_from_channel("PJSIP/201") == "201"


def test_extension_from_channel_none_for_trunk_leg_new_format():
    assert si.extension_from_channel("PJSIP/t1-trunk-1-00000002") is None


def test_extension_from_channel_none_for_unmatched_channel():
    assert si.extension_from_channel("Local/700@parkedcalls-00000001;2") is None


def test_extension_from_channel_none_for_falsy_input():
    assert si.extension_from_channel(None) is None
    assert si.extension_from_channel("") is None


def test_extension_from_channel_feature_codes_not_mistaken_for_numbers():
    # Raqam shakli `[0-9*#]{2,10}` ichida `*`/`#` ham bo'lishi mumkin (schema cheklovi).
    assert si.extension_from_channel("PJSIP/*98-00000001") == "*98"
