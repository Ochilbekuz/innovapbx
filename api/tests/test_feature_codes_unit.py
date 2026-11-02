"""M2a §2–§3: `/feature-codes`, `/parking` marshrutlari va raqam bandligi (park 700–720) — DB/AMI'siz."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1 import feature_codes as fcr
from app.api.v1 import parking as pr
from app.core.errors import ApiError
from app.schemas_features import UpdateFeatureCodePayload
from app.services import numbers
from app.services.dialplan_features import FEATURE_ORDER
from app.services.feature_codes import validate_feature_code

USER = SimpleNamespace(id="u1", tenant_id="t1")
DEFAULTS = {"voicemail": "*97", "voicemail_other": "*98", "dnd_toggle": "*76", "cf_always_on": "*72",
            "cf_always_off": "*73", "cf_busy_on": "*90", "cf_busy_off": "*91", "pickup_group": "*8",
            "pickup_direct": "**", "park": "*70", "echo_test": "*43", "speaking_clock": "*60"}


# ------------------------------------------------------------------ sof tekshiruv
@pytest.mark.parametrize("code", ["*1", "*123456", "**", "*#1", "*9*"])
def test_valid_codes(code):
    validate_feature_code(code, ["*500"])


@pytest.mark.parametrize("code", ["*", "76", "*1234567", "*7a", " *76", "#76"])
def test_bad_code(code):
    with pytest.raises(ApiError) as e:
        validate_feature_code(code, [])
    assert (e.value.status_code, e.value.code, e.value.field) == (422, "bad_code", "code")


@pytest.mark.parametrize("code,others", [("*72", ["*72"]), ("*7", ["*72"]), ("*721", ["*72"])])
def test_code_taken_equal_or_prefix(code, others):
    with pytest.raises(ApiError) as e:
        validate_feature_code(code, others)
    assert (e.value.status_code, e.value.code) == (409, "code_taken")
    assert e.value.details == {"conflict": "*72"}


def test_toggle_code_equal_clashes_but_prefix_does_not():
    validate_feature_code("*28", [], ["*281"])
    with pytest.raises(ApiError) as e:
        validate_feature_code("*281", [], ["*281"])
    assert e.value.details == {"conflict": "*281"}


def test_defaults_do_not_clash_with_each_other():
    for feature, code in DEFAULTS.items():
        validate_feature_code(code, [c for f, c in DEFAULTS.items() if f != feature])


# ------------------------------------------------------------------ marshrutlar
class _Session:
    def __init__(self):
        self.commits = self.flushes = 0

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1


@pytest.fixture
def env(monkeypatch):
    state = {
        "codes": {f: SimpleNamespace(feature=f, code=c, enabled=True) for f, c in DEFAULTS.items()},
        "toggles": [], "audit": [], "applied": 0,
    }

    async def load_codes(session, tenant_id):
        return state["codes"]

    async def load_defaults(session):
        return dict(DEFAULTS)

    async def toggles(session, tenant_id):
        return state["toggles"]

    async def audit(session, **kw):
        state["audit"].append(kw)

    async def apply(session, *, tenant_id, user_id, ami):
        state["applied"] += 1
        return SimpleNamespace(to_dict=lambda: {"status": "applied", "revision": 3, "message": None})

    monkeypatch.setattr(fcr, "_load_codes", load_codes)
    monkeypatch.setattr(fcr, "_load_defaults", load_defaults)
    monkeypatch.setattr(fcr, "_toggle_codes", toggles)
    monkeypatch.setattr(fcr, "record_audit", audit)
    monkeypatch.setattr(fcr, "apply_config", apply)
    return state


@pytest.mark.asyncio
async def test_list_in_contract_order_without_unused(env):
    env["codes"]["queue_login"] = SimpleNamespace(feature="queue_login", code="*45", enabled=True)
    env["codes"]["queue_pause"] = SimpleNamespace(feature="queue_pause", code="*46", enabled=True)
    env["codes"]["followme_toggle"] = SimpleNamespace(feature="followme_toggle", code="*21", enabled=True)
    del env["codes"]["echo_test"]
    out = await fcr.list_feature_codes(session=_Session(), user=USER)
    assert [i.feature for i in out.items] == [f for f in FEATURE_ORDER if f != "echo_test"]
    assert out.items[0].model_dump() == {"feature": "voicemail", "code": "*97", "default_code": "*97",
                                         "enabled": True}


@pytest.mark.asyncio
async def test_patch_code_and_enabled_applies_and_audits(env):
    session = _Session()
    out = await fcr.update_feature_code("dnd_toggle", UpdateFeatureCodePayload(code="*77", enabled=False),
                                        session=session, user=USER, ami=None)
    assert out.item.model_dump() == {"feature": "dnd_toggle", "code": "*77", "default_code": "*76",
                                     "enabled": False}
    assert out.apply.revision == 3 and env["applied"] == 1 and session.commits == 1
    assert env["audit"][0]["action"] == "feature_code.update"
    assert env["audit"][0]["diff"] == {"code": {"from": "*76", "to": "*77"},
                                       "enabled": {"from": True, "to": False}}


@pytest.mark.asyncio
async def test_patch_same_code_skips_validation(env):
    env["toggles"] = ["*76"]  # o'z kodi qayta yuborilsa — to'qnashuv emas
    out = await fcr.update_feature_code("dnd_toggle", UpdateFeatureCodePayload(code="*76"),
                                        session=_Session(), user=USER, ami=None)
    assert out.item.code == "*76" and env["audit"][0]["diff"] == {}


@pytest.mark.asyncio
async def test_patch_prefix_conflict_with_other_feature(env):
    with pytest.raises(ApiError) as e:
        await fcr.update_feature_code("echo_test", UpdateFeatureCodePayload(code="*7"),
                                      session=_Session(), user=USER, ami=None)
    assert e.value.code == "code_taken" and env["applied"] == 0


@pytest.mark.asyncio
async def test_patch_conflict_with_toggle_code(env):
    env["toggles"] = ["*281"]
    with pytest.raises(ApiError) as e:
        await fcr.update_feature_code("echo_test", UpdateFeatureCodePayload(code="*281"),
                                      session=_Session(), user=USER, ami=None)
    assert e.value.code == "code_taken"


@pytest.mark.asyncio
@pytest.mark.parametrize("feature", ["nope", "queue_login"])
async def test_patch_unknown_feature_404(env, feature):
    with pytest.raises(ApiError) as e:
        await fcr.update_feature_code(feature, UpdateFeatureCodePayload(enabled=False),
                                      session=_Session(), user=USER, ami=None)
    assert (e.value.status_code, e.value.code) == (404, "not_found")


@pytest.mark.asyncio
async def test_reset_restores_default_and_enables(env):
    env["codes"]["park"].code = "*71"
    env["codes"]["park"].enabled = False
    out = await fcr.reset_feature_code("park", session=_Session(), user=USER, ami=None)
    assert out.item.code == "*70" and out.item.enabled is True
    assert env["audit"][0]["action"] == "feature_code.reset"


@pytest.mark.asyncio
async def test_reset_unknown_404(env):
    with pytest.raises(ApiError) as e:
        await fcr.reset_feature_code("queue_login", session=_Session(), user=USER, ami=None)
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_get_parking_route(monkeypatch):
    seen = {}

    async def fake_code(session, tenant_id):
        seen["tenant"] = tenant_id
        return "t9"

    async def fake_status(ami, code):
        seen["code"] = code
        return {"lot": "700", "slots": "701-720", "timeout_s": 60,
                "parked": [{"slot": "701", "callerid": "202", "parked_by": "201", "since": "x"}]}

    monkeypatch.setattr(pr, "get_tenant_code", fake_code)
    monkeypatch.setattr(pr, "parking_status", fake_status)
    out = await pr.get_parking(session=None, user=USER, ami=None)
    assert out.parked[0].slot == "701" and seen == {"tenant": "t1", "code": "t9"}


# ------------------------------------------------------------------ raqam bandligi
@pytest.mark.asyncio
@pytest.mark.parametrize("number", ["700", "701", "720"])
async def test_park_numbers_reserved(number):
    with pytest.raises(ApiError) as e:
        await numbers.ensure_number_free(None, "t1", number)
    assert (e.value.status_code, e.value.code, e.value.field) == (409, "number_taken", "number")
    assert e.value.details == {"reason": "reserved"}


@pytest.mark.asyncio
@pytest.mark.parametrize("taken", [True, False])
async def test_number_taken_plain(monkeypatch, taken):
    seen = {}

    async def fake_taken(session, tenant_id, number, *, exclude_target_id=None):
        seen["args"] = (tenant_id, number, exclude_target_id)
        return taken

    monkeypatch.setattr(numbers, "number_taken", fake_taken)
    if taken:
        with pytest.raises(ApiError) as e:
            await numbers.ensure_number_free(None, "t1", "699", exclude_target_id="x")
        assert e.value.details == {} and e.value.code == "number_taken"
    else:
        await numbers.ensure_number_free(None, "t1", "721", exclude_target_id="x")
    assert seen["args"][2] == "x"
