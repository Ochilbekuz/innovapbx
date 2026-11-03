"""CONFIRMED HIGH tuzatish — dialplan injection: ism/DID/CID/callerid/`add_prefix`
kabi maydonlar `app/services/compiler.py` orqali generatsiya qilinadigan Asterisk
dialplan matniga tushadi. Bu yerda — BIRINCHI himoya chizig'i (`app/schemas.py`
Pydantic validatsiyasi, admin/operator kiritgan payload rad etiladi, FastAPI buni
422ga aylantiradi); ikkinchi chiziq — render vaqtida `app/services/compiler.py`
(qarang `tests/test_compiler.py` dialplan injection bo'limi).

Uslub `tests/test_network_schemas_unit.py` bilan BIR XIL (dryer): to'g'ridan-to'g'ri
schema klassini chaqirib `pydantic.ValidationError` kutiladi — HTTP qatlami/DB
shart emas, chunki FastAPI har qanday `ValidationError`ni avtomatik 422ga o'giradi."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas import (
    CreateExtensionPayload,
    CreateInboundRoutePayload,
    CreateOutboundRoutePayload,
    CreateTrunkPayload,
    OutboundPatternIn,
    UpdateExtensionPayload,
    UpdateInboundRoutePayload,
    UpdateOutboundRoutePayload,
    UpdateTrunkPayload,
)

NOW = datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)
CRLF_NAME = "Dilnoza\nexten => 999,1,System(rm -rf /)"
BAD_NUMBER = "${SHELL(id)}"


def test_create_extension_rejects_crlf_name():
    with pytest.raises(ValidationError):
        CreateExtensionPayload(name=CRLF_NAME)


def test_create_extension_rejects_bad_outbound_callerid():
    with pytest.raises(ValidationError):
        CreateExtensionPayload(name="Dilnoza", outbound_callerid=BAD_NUMBER)


def test_update_extension_rejects_crlf_name():
    with pytest.raises(ValidationError):
        UpdateExtensionPayload(name=CRLF_NAME, updated_at=NOW)


def test_update_extension_rejects_bad_outbound_callerid():
    with pytest.raises(ValidationError):
        UpdateExtensionPayload(outbound_callerid=BAD_NUMBER, updated_at=NOW)


def test_create_trunk_rejects_crlf_name():
    with pytest.raises(ValidationError):
        CreateTrunkPayload(name=CRLF_NAME, host="sip.example.com")


def test_create_trunk_rejects_bad_outbound_callerid():
    with pytest.raises(ValidationError):
        CreateTrunkPayload(name="Trunk1", host="sip.example.com", outbound_callerid=BAD_NUMBER)


def test_update_trunk_rejects_crlf_name():
    with pytest.raises(ValidationError):
        UpdateTrunkPayload(name=CRLF_NAME)


def test_create_inbound_route_rejects_crlf_name():
    with pytest.raises(ValidationError):
        CreateInboundRoutePayload(name=CRLF_NAME, target_id="t1")


def test_create_inbound_route_rejects_bad_did():
    with pytest.raises(ValidationError):
        CreateInboundRoutePayload(name="Route1", did=BAD_NUMBER, target_id="t1")


def test_create_inbound_route_rejects_bad_cid():
    with pytest.raises(ValidationError):
        CreateInboundRoutePayload(name="Route1", cid=BAD_NUMBER, target_id="t1")


def test_create_inbound_route_rejects_crlf_cid_name_prefix():
    with pytest.raises(ValidationError):
        CreateInboundRoutePayload(name="Route1", target_id="t1", cid_name_prefix=CRLF_NAME)


def test_update_inbound_route_rejects_bad_did():
    with pytest.raises(ValidationError):
        UpdateInboundRoutePayload(did=BAD_NUMBER, updated_at=NOW)


def test_update_inbound_route_rejects_crlf_cid_name_prefix():
    with pytest.raises(ValidationError):
        UpdateInboundRoutePayload(cid_name_prefix=CRLF_NAME, updated_at=NOW)


def test_create_outbound_route_rejects_crlf_name():
    with pytest.raises(ValidationError):
        CreateOutboundRoutePayload(name=CRLF_NAME, patterns=[OutboundPatternIn(pattern="_998XXXXXXXXX")],
                                    trunk_ids=["tr1"])


def test_create_outbound_route_rejects_bad_callerid():
    with pytest.raises(ValidationError):
        CreateOutboundRoutePayload(name="Route1", patterns=[OutboundPatternIn(pattern="_998XXXXXXXXX")],
                                    trunk_ids=["tr1"], callerid=BAD_NUMBER)


def test_update_outbound_route_rejects_bad_callerid():
    with pytest.raises(ValidationError):
        UpdateOutboundRoutePayload(callerid=BAD_NUMBER, updated_at=NOW)


def test_outbound_pattern_rejects_bad_pattern():
    with pytest.raises(ValidationError):
        OutboundPatternIn(pattern=BAD_NUMBER)


def test_outbound_pattern_rejects_bad_add_prefix():
    with pytest.raises(ValidationError):
        OutboundPatternIn(pattern="_998XXXXXXXXX", add_prefix=BAD_NUMBER)


def test_valid_payloads_are_still_accepted():
    """Regressiya: tuzatish xavfsiz/odatiy qiymatlarni rad etmasin."""
    CreateExtensionPayload(name="Dilnoza", outbound_callerid="998901234567")
    CreateInboundRoutePayload(name="Route1", did="998901234567", cid="+99890*", target_id="t1",
                               cid_name_prefix="Call Center")
    CreateOutboundRoutePayload(name="Mobil", patterns=[OutboundPatternIn(pattern="_998XXXXXXXXX",
                                                                          add_prefix="0")],
                                trunk_ids=["tr1"], callerid="998901234567")
