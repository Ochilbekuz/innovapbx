"""`endpoint_states` — `pjsip show endpoints` chiqishidan kontakt holati. Namuna JONLI olingan
(`innova-m0-asterisk-1`, Asterisk 22, 2026-10-29): URI va holat orasida <Hash> ustuni bor
(oldingi regex uni hisobga olmagani uchun `/live` va `/extensions` HAMMA raqamni offline ko'rsatardi)."""
from __future__ import annotations

import asyncio

from app.services.ami import AmiError
from app.services.live_status import endpoint_states

_OUTPUT = (
    "      Contact:  <Aor/ContactUri..........................> <Hash....> <Status> <RTT(ms)..>\n"
    " Endpoint:  t1-102/102                                           Unavailable   0 of inf\n"
    "      Contact:  t1-102/sip:t1-102@172.21.0.180:5070;x-ast- 30637b21bd Unavail        -nan\n"
    " Endpoint:  t1-103/103                                           Not in use    0 of inf\n"
    "      Contact:  t1-103/sip:jyhgk8rv@172.21.0.5:59158;trans 0fb0660acf NonQual        -nan\n"
    " Endpoint:  t1-101/101                                           Not in use    0 of inf\n"
    "      Contact:  t1-101/sip:1bb01e02@172.21.0.5:48136;trans 8ae50b7954 Avail         7.260\n"
    "      Contact:  t1-trunk-a1bf/sip:172.21.0.181:5060 d057726c07 Unknown        -nan\n"
)


class _FakeAmi:
    def __init__(self, output: str | None = _OUTPUT, error: Exception | None = None) -> None:
        self.output, self.error, self.commands = output, error, []

    async def ensure_connected(self) -> None:
        if self.error:
            raise self.error

    async def action(self, action: str, **fields) -> dict:
        self.commands.append((action, fields))
        return {"Output": self.output}


def _states(ami, ids):
    return asyncio.run(endpoint_states(ami, ids))


def test_hash_column_and_states_parsed():
    s = _states(_FakeAmi(), ["t1-101", "t1-102", "t1-103", "t1-104", "t1-trunk-a1bf"])
    assert s["t1-101"] == {"status": "online", "contact": "sip:1bb01e02@172.21.0.5:48136;trans", "user_agent": None}
    assert s["t1-103"]["status"] == "online"  # NonQual — ro'yxatdan o'tgan, hali qualify qilinmagan
    assert s["t1-102"] == {"status": "offline", "contact": "sip:t1-102@172.21.0.180:5070;x-ast-", "user_agent": None}
    assert s["t1-trunk-a1bf"]["status"] == "offline"
    assert s["t1-104"] == {"status": "unknown", "contact": None, "user_agent": None}


def test_header_row_and_foreign_endpoints_ignored():
    s = _states(_FakeAmi(), ["t1-105"])
    assert s == {"t1-105": {"status": "unknown", "contact": None, "user_agent": None}}


def test_state_without_hash_column_still_parsed():
    out = "      Contact:  t1-101/sip:a@b:5060 Avail 1.0\n"
    assert _states(_FakeAmi(out), ["t1-101"])["t1-101"]["status"] == "online"


def test_status_word_must_be_whole_word():
    out = "      Contact:  t1-101/sip:a@b:5060 0fb0660acf Availx 1.0\n"
    assert _states(_FakeAmi(out), ["t1-101"])["t1-101"]["status"] == "unknown"


def test_no_ids_no_ami_call_and_ami_down_unknown():
    ami = _FakeAmi()
    assert _states(ami, []) == {} and ami.commands == []
    down = _states(_FakeAmi(error=AmiError("down")), ["t1-101"])
    assert down["t1-101"]["status"] == "unknown"
