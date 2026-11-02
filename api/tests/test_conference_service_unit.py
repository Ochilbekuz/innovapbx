"""M2a §4 — `app/services/conference.py` TDD testlari. PIN hech qachon
ochiq matnda yozilmaydi/qaytmaydi — faqat `pin_role()` orqali bcrypt solishtiradi."""
from __future__ import annotations

import pytest

from app.core.security import hash_password
from app.services import conference as conf


# --------------------------------------------------------------- confbridge.conf
def test_build_confbridge_conf_empty_has_only_header():
    text = conf.build_confbridge_conf("t1", [])
    assert "tahrirlanmasin" in text
    assert "[t1-conf-" not in text


def test_build_confbridge_conf_one_item_bridge_user_admin_sections():
    item = conf.ConferenceConfItem(id="abc", record=False, max_members=None)
    text = conf.build_confbridge_conf("t1", [item])
    assert "[t1-conf-abc-bridge]" in text
    assert "[t1-conf-abc-user]" in text
    assert "[t1-conf-abc-admin]" in text
    assert "type=bridge" in text
    assert "admin=yes" in text
    assert "record_conference" not in text
    assert "max_members" not in text


def test_build_confbridge_conf_record_and_max_members():
    item = conf.ConferenceConfItem(id="abc", record=True, max_members=10)
    text = conf.build_confbridge_conf("t1", [item])
    assert "record_conference=yes" in text
    assert "max_members=10" in text


def test_build_confbridge_conf_sorted_by_id_deterministic():
    items = [conf.ConferenceConfItem(id="b", record=False, max_members=None),
             conf.ConferenceConfItem(id="a", record=False, max_members=None)]
    text = conf.build_confbridge_conf("t1", items)
    assert text.index("[t1-conf-a-bridge]") < text.index("[t1-conf-b-bridge]")


# --------------------------------------------------------------------- pin_role
def test_pin_role_admin_pin_wins():
    admin_hash = hash_password("9999")
    user_hash = hash_password("1234")
    assert conf.pin_role("9999", user_hash, admin_hash) == "admin"


def test_pin_role_user_pin():
    user_hash = hash_password("1234")
    assert conf.pin_role("1234", user_hash, None) == "user"


def test_pin_role_wrong_pin_is_deny():
    user_hash = hash_password("1234")
    assert conf.pin_role("0000", user_hash, None) == "deny"


def test_pin_role_no_hashes_is_deny():
    assert conf.pin_role("1234", None, None) == "deny"


# --------------------------------------------------------------- live_members
class _FakeAmi:
    def __init__(self, events: list[dict] | None = None, *, fail: bool = False):
        self._events = events or []
        self._fail = fail

    async def ensure_connected(self) -> None:
        if self._fail:
            raise ConnectionError("Asterisk yo'q")

    async def action(self, action: str, **fields: object) -> dict:
        raise NotImplementedError

    async def action_list(self, action: str, **fields: object) -> list[dict]:
        return self._events


@pytest.mark.asyncio
async def test_live_members_counts_confbridgelist_events():
    events = [{"Event": "ConfbridgeList"}, {"Event": "ConfbridgeList"}, {"Event": "ConfbridgeListComplete"}]
    assert await conf.live_members(_FakeAmi(events), "t1-conf-abc") == 2


@pytest.mark.asyncio
async def test_live_members_zero_when_ami_unreachable():
    assert await conf.live_members(_FakeAmi(fail=True), "t1-conf-abc") == 0


@pytest.mark.asyncio
async def test_live_members_zero_on_empty_room():
    assert await conf.live_members(_FakeAmi([]), "t1-conf-abc") == 0


# ------------------------------------------------------- reload+verify (AMI)
@pytest.mark.asyncio
async def test_reload_and_verify_confbridge_ok():
    class Ami(_FakeAmi):
        async def action(self, action: str, **fields: object) -> dict:
            if fields.get("Command") == "module reload app_confbridge.so":
                return {"Response": "Success"}
            return {"Response": "Success", "Output": "t1-conf-abc-bridge\n"}
    await conf._reload_and_verify_confbridge(Ami(), ["t1-conf-abc-bridge"])


@pytest.mark.asyncio
async def test_reload_and_verify_confbridge_reload_failure_raises():
    class Ami(_FakeAmi):
        async def action(self, action: str, **fields: object) -> dict:
            return {"Response": "Error", "Message": "yo'q"}
    with pytest.raises(RuntimeError):
        await conf._reload_and_verify_confbridge(Ami(), ["t1-conf-abc-bridge"])


@pytest.mark.asyncio
async def test_reload_and_verify_confbridge_profile_missing_raises():
    class Ami(_FakeAmi):
        async def action(self, action: str, **fields: object) -> dict:
            if fields.get("Command") == "module reload app_confbridge.so":
                return {"Response": "Success"}
            return {"Response": "Success", "Output": "No bridge profile named 'x' found!\n"}
    with pytest.raises(RuntimeError):
        await conf._reload_and_verify_confbridge(Ami(), ["t1-conf-abc-bridge"])
