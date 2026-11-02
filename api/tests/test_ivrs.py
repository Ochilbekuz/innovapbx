"""`app/api/v1/ivrs.py` — birlik testlari, fake session/AMI bilan (DB/AMI'siz,
koordinator talabi 2026-10-27): validatsiya (`invalid_target`/`invalid_audio`),
409 `in_use`, 422 `duplicate_digit`, 422 `loop` (apply_config orqali propagatsiya)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.api.v1 import ivrs
from app.core.errors import ApiError
from app.db.models import Ivr, User
from app.schemas import CreateIvrPayload, IvrOptionIn


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    """`add`/`flush`/`commit` — hech narsa qilmaydi (yon ta'sirsiz); `execute`
    faqat `_get_audio_or_422` kabi to'g'ridan-to'g'ri chaqirilgan joylarda
    ishlatiladi, boshqa joylarda monkeypatch bilan chetlab o'tiladi."""

    def __init__(self, execute_result=None):
        self._execute_result = execute_result
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def execute(self, _stmt):
        return _FakeResult(self._execute_result)


def _user() -> User:
    user = User(tenant_id="00000000-0000-0000-0000-000000000000", username="admin",
                full_name="Admin", password_hash="x", role_id="r")
    user.id = "11111111-1111-1111-1111-111111111111"
    return user


def _ivr(**overrides) -> Ivr:
    ivr = Ivr(
        tenant_id="t1", target_id="target-1", name="M1aIvr1", greeting_audio_id="audio-1",
        timeout_seconds=5, repeats=1, timeout_target_id="target-2", invalid_target_id="target-2",
    )
    ivr.id = "ivr-1"
    ivr.updated_at = datetime.now(timezone.utc)
    for k, v in overrides.items():
        setattr(ivr, k, v)
    return ivr


def _payload(**overrides) -> CreateIvrPayload:
    defaults = dict(
        name="M1aIvr1", greeting_audio_id="audio-1", timeout_target_id="target-2",
        invalid_target_id="target-2", options=[],
    )
    defaults.update(overrides)
    return CreateIvrPayload(**defaults)


# --------------------------------------------------------------- validatsiya
async def test_validate_options_duplicate_digit_raises_422():
    options = [IvrOptionIn(digit="1", target_id="a"), IvrOptionIn(digit="1", target_id="b")]
    with pytest.raises(ApiError) as exc:
        await ivrs._validate_options(_FakeSession(), "t1", options)
    assert exc.value.status_code == 422
    assert exc.value.code == "duplicate_digit"


async def test_validate_options_invalid_target_raises_422(monkeypatch):
    monkeypatch.setattr(ivrs, "resolve_target", _async(None))
    options = [IvrOptionIn(digit="1", target_id="yoq")]
    with pytest.raises(ApiError) as exc:
        await ivrs._validate_options(_FakeSession(), "t1", options)
    assert exc.value.status_code == 422
    assert exc.value.code == "invalid_target"


async def test_validate_options_passes_when_targets_resolve(monkeypatch):
    monkeypatch.setattr(ivrs, "resolve_target", _async(object()))
    options = [IvrOptionIn(digit="1", target_id="a"), IvrOptionIn(digit="2", target_id="b")]
    await ivrs._validate_options(_FakeSession(), "t1", options)  # ko'tarmaydi


async def test_get_audio_or_422_raises_when_missing():
    with pytest.raises(ApiError) as exc:
        await ivrs._get_audio_or_422(_FakeSession(execute_result=None), "t1", "yoq", "greeting_audio_id")
    assert exc.value.status_code == 422
    assert exc.value.code == "invalid_audio"
    assert exc.value.field == "greeting_audio_id"


# ------------------------------------------------------------------ 409 in_use
async def test_delete_ivr_raises_409_when_in_use(monkeypatch):
    ivr = _ivr()
    monkeypatch.setattr(ivrs, "_get_ivr_or_404", _async(ivr))
    monkeypatch.setattr(ivrs, "usages_for_target", _async([
        {"kind": "inbound_route", "id": "r1", "label": "712099301"},
    ]))
    with pytest.raises(ApiError) as exc:
        await ivrs.delete_ivr("ivr-1", session=_FakeSession(), user=_user(), ami=None)
    assert exc.value.status_code == 409
    assert exc.value.code == "in_use"
    assert exc.value.details["usages"]


async def test_delete_ivr_succeeds_when_not_in_use(monkeypatch):
    ivr = _ivr()
    monkeypatch.setattr(ivrs, "_get_ivr_or_404", _async(ivr))
    monkeypatch.setattr(ivrs, "usages_for_target", _async([]))
    deleted: list = []

    async def fake_delete_satellite(_session, _entity, _target_id):
        deleted.append(_target_id)

    monkeypatch.setattr(ivrs, "delete_satellite_and_target", fake_delete_satellite)
    monkeypatch.setattr(ivrs, "apply_config", _async(_FakeApplyResult()))
    await ivrs.delete_ivr("ivr-1", session=_FakeSession(), user=_user(), ami=None)
    assert deleted == ["target-1"]


# ------------------------------------------------------------------ 422 loop
class _FakeApplyResult:
    def to_dict(self) -> dict:
        return {"status": "applied"}


async def test_create_ivr_propagates_422_loop_from_apply_config(monkeypatch):
    """`create_ivr` o'zi halqani aniqlamaydi — `apply_config` (kompilyator
    orqali) 422 `loop` ko'tarsa, router buni YUTMASDAN tashqariga chiqarishi
    SHART (m1a-contract.md ssenariy 4: IVR o'ziga chiqishsiz -> 422 loop)."""
    monkeypatch.setattr(ivrs, "_get_audio_or_422", _async(object()))
    monkeypatch.setattr(ivrs, "resolve_target", _async(object()))

    class _FakeTarget:
        id = "target-new"

    monkeypatch.setattr(ivrs, "create_target", _async(_FakeTarget()))

    async def fake_apply_config(*_a, **_kw):
        raise ApiError(422, "loop", "Qo'ng'iroq oqimida chiqishsiz halqa topildi")

    monkeypatch.setattr(ivrs, "apply_config", fake_apply_config)

    with pytest.raises(ApiError) as exc:
        await ivrs.create_ivr(_payload(), session=_FakeSession(), user=_user(), ami=None)
    assert exc.value.status_code == 422
    assert exc.value.code == "loop"


def _async(value):
    async def _fn(*_args, **_kwargs):
        return value
    return _fn
