"""M3a §2 — ichki raqamning WebRTC rejimi va kodeklari (admin PATCH/POST). Realtime
(`ps_endpoints` view — reload'siz), kodek tekshiruvi 422 `webrtc_codec`/`bad_codec` (`field="codecs"`)."""
from __future__ import annotations

import pytest

from app.core.errors import ApiError
from app.services.ext_media import WEBRTC_DEFAULT_CODECS, resolve_codecs
from tests.test_extensions_call_fields_unit import NOW, _patch, env  # noqa: F401 — fixture

DEFAULT_DB = ["ulaw", "alaw", "g722", "opus"]


# ---------------------------------------------------------------- sof qaror (create ham shu)
def test_create_webrtc_without_codecs_gets_browser_default():
    assert resolve_codecs(webrtc=True, requested=None, current=None, switching_on=True) == ["opus", "ulaw", "alaw"]
    assert list(WEBRTC_DEFAULT_CODECS) == ["opus", "ulaw", "alaw"]


def test_create_plain_without_codecs_keeps_db_default():
    assert resolve_codecs(webrtc=False, requested=None, current=None, switching_on=False) is None


def test_webrtc_accepts_full_browser_set():
    full = ["opus", "g722", "ulaw", "alaw"]
    assert resolve_codecs(webrtc=True, requested=full, current=None, switching_on=True) == full


def test_requested_codecs_are_deduplicated_in_order():
    assert resolve_codecs(webrtc=True, requested=["opus", "g722", "opus"], current=None,
                          switching_on=True) == ["opus", "g722"]


@pytest.mark.parametrize("codecs", [[], ["g729"], ["opus", "gsm"], ["OPUS"]])
def test_webrtc_codecs_must_be_browser_subset_and_non_empty(codecs):
    with pytest.raises(ApiError) as e:
        resolve_codecs(webrtc=True, requested=codecs, current=None, switching_on=True)
    assert (e.value.status_code, e.value.code, e.value.field) == (422, "webrtc_codec", "codecs")


@pytest.mark.parametrize("codecs", [[], ["ulaw,alaw"], ["a"], ["G729"]])
def test_plain_codecs_must_be_well_formed_and_non_empty(codecs):
    """Kodek nomi ps_endpoints `allow` satriga vergul bilan qo'shiladi — kirishda tekshiriladi."""
    with pytest.raises(ApiError) as e:
        resolve_codecs(webrtc=False, requested=codecs, current=None, switching_on=False)
    assert (e.value.status_code, e.value.code, e.value.field) == (422, "bad_codec", "codecs")


def test_plain_extension_may_use_non_browser_codec():
    assert resolve_codecs(webrtc=False, requested=["g729", "ulaw"], current=None, switching_on=False) == \
        ["g729", "ulaw"]


# ---------------------------------------------------------------- PATCH /extensions/{id}
@pytest.mark.asyncio
async def test_switching_webrtc_on_is_realtime_and_sets_browser_codecs(env):  # noqa: F811
    out = await _patch({"webrtc": True})
    assert env["applied"] == 0 and out.apply.status == "applied" and out.apply.revision is None
    assert out.item.webrtc is True and out.item.codecs == ["opus", "ulaw", "alaw"]
    assert env["audit"][0]["action"] == "extension.update"
    assert env["audit"][0]["diff"] == {"webrtc": {"from": False, "to": True},
                                       "codecs": {"from": DEFAULT_DB, "to": ["opus", "ulaw", "alaw"]}}


@pytest.mark.asyncio
async def test_switching_webrtc_on_with_explicit_codecs_keeps_them(env):  # noqa: F811
    out = await _patch({"webrtc": True, "codecs": ["g722", "opus"]})
    assert out.item.codecs == ["g722", "opus"]


@pytest.mark.asyncio
async def test_webrtc_already_on_codecs_unchanged_when_not_given(env):  # noqa: F811
    env["ext"].webrtc, env["ext"].codecs = True, ["alaw"]
    out = await _patch({"name": "Vali"})
    assert out.item.codecs == ["alaw"] and "codecs" not in env["audit"][0]["diff"]


@pytest.mark.asyncio
async def test_codecs_patch_on_webrtc_ext_validated_against_current_mode(env):  # noqa: F811
    env["ext"].webrtc = True
    with pytest.raises(ApiError) as e:
        await _patch({"codecs": ["g729"]})
    assert e.value.code == "webrtc_codec"
    assert env["audit"] == [] and env["ext"].codecs == DEFAULT_DB


@pytest.mark.asyncio
async def test_switching_webrtc_off_keeps_codecs_and_is_realtime(env):  # noqa: F811
    env["ext"].webrtc, env["ext"].codecs = True, ["opus", "ulaw"]
    out = await _patch({"webrtc": False})
    assert out.item.webrtc is False and out.item.codecs == ["opus", "ulaw"] and env["applied"] == 0


@pytest.mark.asyncio
async def test_webrtc_with_other_field_still_applies(env):  # noqa: F811
    await _patch({"webrtc": True, "name": "Vali"})
    assert env["applied"] == 1


def test_new_extension_sets_codecs_only_when_given():
    from app.api.v1.extensions import new_extension

    with_codecs = new_extension(number="101", name="A", webrtc=True, codecs=["opus", "ulaw"])
    assert (with_codecs.number, with_codecs.webrtc, with_codecs.codecs) == ("101", True, ["opus", "ulaw"])
    assert new_extension(number="102", name="B", webrtc=False, codecs=None).codecs is None  # DB default
