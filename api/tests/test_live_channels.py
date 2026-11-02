"""`active_calls_live`/`_parse_channel_table` — `core show channels verbose`
chiqishini tahlil qiladi. Namuna JONLI tasdiqlangan (`innova-m0-asterisk-1`
konteyneri, 2026-10-28, `channel originate Local/700@parkedcalls application
Wait 30` bilan sinovda olingan ustun kengliklari) — m1b-contract.md bo'lim 5
"live.calls"."""
from __future__ import annotations

import pytest

from app.services.live_status import (
    channel_creation_seq,
    duration_seconds,
    _group_rows_by_bridge,
    _live_call_from_bridge_group,
    _parse_channel_table,
    active_calls_live,
)

_HEADER = (
    "Channel                                                                          Context"
    "                  Extension                Prio State   Application  Data                      CallerID"
    "        Duration Accountcode PeerAccount BridgeID            "
)
_COLUMNS = (
    "Channel", "Context", "Extension", "Prio", "State", "Application", "Data",
    "CallerID", "Duration", "Accountcode", "PeerAccount", "BridgeID",
)


def _make_row(**values: str) -> str:
    """Sarlavha (`_HEADER`) ustun BOSHLANISH indekslariga qarab, har qiymatni
    o'z ustuniga (chapga tekislab) joylashtiradi — qo'lda probel sanash
    O'RNIGA (xato-moyil, sinovda bir marta aynan shu sabab yiqilgan edi)."""
    starts = [(name, _HEADER.index(name)) for name in _COLUMNS]
    row = [" "] * len(_HEADER)
    for i, (name, start) in enumerate(starts):
        end = starts[i + 1][1] if i + 1 < len(starts) else len(_HEADER)
        value = values.get(name, "")
        row[start:start + len(value)] = list(value)
        assert len(value) < end - start, f"{name} qiymati o'z ustuniga sig'madi"
    return "".join(row).rstrip() or "".join(row)


_ROW_A = _make_row(Channel="Local/700@parkedcalls-00000001;2", Context="parkedcalls", Extension="700",
                    Prio="1", State="Up", Application="Park", Data="(Empty)", CallerID="912345678",
                    Duration="00:00:05", BridgeID="bridge-xyz")
_ROW_B = _make_row(Channel="PJSIP/t1-trunk-1-00000002", Context="t1-outbound", Extension="998901234567",
                    Prio="1", State="Up", Application="Dial", Data="(Outgoing Line)", CallerID="912345678",
                    Duration="00:00:05", BridgeID="bridge-xyz")
_SAMPLE_OUTPUT = f"{_HEADER}\n{_ROW_A}\n{_ROW_B}\n2 active channels\n1 active call\n1 call processed\n"


def test_parse_channel_table_extracts_fixed_width_columns():
    rows = _parse_channel_table(_SAMPLE_OUTPUT)
    assert len(rows) == 2
    assert rows[0]["Channel"] == "Local/700@parkedcalls-00000001;2"
    assert rows[0]["BridgeID"] == "bridge-xyz"
    assert rows[1]["Extension"] == "998901234567"


def test_parse_channel_table_empty_output_returns_empty_list():
    assert _parse_channel_table("") == []
    assert _parse_channel_table("Header line only\n0 active channels\n") == []


def test_parse_channel_table_ignores_plural_calls_processed_trailer():
    """Regressiya (jonli `innova-m0-asterisk-1`, 2026-10-28): "3 calls
    processed" (ko'plik) soxta kanal qatori sifatida qo'shilib qolgan edi —
    eski filtr faqat birlik "call processed"ni tekshirardi."""
    output = f"{_HEADER}\n0 active channels\n0 active calls\n3 calls processed\n"
    assert _parse_channel_table(output) == []


def test_duration_seconds_parses_hms():
    assert duration_seconds("00:00:05") == 5
    assert duration_seconds("01:02:03") == 3723
    assert duration_seconds("garbage") == 0


def test_channel_creation_seq_orders_by_trailing_counter():
    assert channel_creation_seq("PJSIP/t1-trunk-1-00000002") == 2
    assert channel_creation_seq("Local/700@parkedcalls-00000001;2") == 1
    assert channel_creation_seq("no-suffix-here") == 0


def test_group_rows_by_bridge_groups_shared_bridge_id():
    rows = _parse_channel_table(_SAMPLE_OUTPUT)
    groups = _group_rows_by_bridge(rows)
    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_group_rows_by_bridge_treats_empty_bridge_as_its_own_call():
    rows = [{"Channel": "PJSIP/x-1", "BridgeID": ""}, {"Channel": "PJSIP/y-2", "BridgeID": ""}]
    groups = _group_rows_by_bridge(rows)
    assert len(groups) == 2


def test_live_call_from_bridge_group_classifies_outbound_via_later_trunk_leg():
    rows = _parse_channel_table(_SAMPLE_OUTPUT)
    call = _live_call_from_bridge_group(_group_rows_by_bridge(rows)[0])
    assert call["direction"] == "out"
    assert call["channel"] == "Local/700@parkedcalls-00000001;2"
    assert call["from"] == "912345678"
    assert call["to"] == "998901234567"
    assert call["duration_s"] == 5


class _FakeAmi:
    def __init__(self, output: str | None) -> None:
        self._output = output

    async def ensure_connected(self) -> None:
        return None

    async def action(self, action: str, **fields) -> dict:
        if self._output is None:
            raise ConnectionError("AMI yo'q")
        return {"Output": self._output}


@pytest.mark.asyncio
async def test_active_calls_live_returns_none_when_ami_unreachable():
    assert await active_calls_live(_FakeAmi(None)) is None


@pytest.mark.asyncio
async def test_active_calls_live_returns_grouped_calls():
    calls = await active_calls_live(_FakeAmi(_SAMPLE_OUTPUT))
    assert calls is not None
    assert len(calls) == 1
    assert calls[0]["direction"] == "out"


@pytest.mark.asyncio
async def test_active_calls_live_empty_when_no_channels():
    calls = await active_calls_live(_FakeAmi("Header\n0 active channels\n"))
    assert calls == []
