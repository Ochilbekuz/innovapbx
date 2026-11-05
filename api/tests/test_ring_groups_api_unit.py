"""`app/api/v1/ring_groups.py` — DB/AMI'siz birlik testlar (0038: FreePBX Ring
Groups parity). Ikki narsa tekshiriladi:
1) Yangi maydonlar (announcement/MOH/alert-info/skip-busy-agent/confirm-calls/
   remote-announce/recording-policy) create/update yo'lida to'g'ri validatsiya
   qilinadi va saqlanadi (`_apply_rg_*`/`_resolve_*`/`_audio_ref`/`_rg_out`).
2) Avval mavjud bo'lgan xato: `_apply_rg_members` aniqlanmagan
   `_validate_extension_ids` funksiyasini chaqirardi (NameError) — bu yerda
   hech qanday test yo'q edi, shu sabab sezilmagan edi. Endi `_validate_members`
   chaqiriladi va NameError ko'tarilmaydi."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import ring_groups as rg
from app.core.errors import ApiError
from app.schemas import CreateRingGroupPayload, UpdateRingGroupPayload

USER = SimpleNamespace(id="u1", tenant_id="t1")
UPDATED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _group(**overrides):
    base = dict(
        id="g1", target_id="tg1", name="Savdo", strategy="ringall", ring_seconds=20,
        no_answer_target_id="nt1", callerid_prefix=None,
        announcement_audio_id=None, ring_strategy_sound="ring", moh_class_id=None, moh_class=None,
        alert_info=None, skip_busy_agent=False, confirm_calls=False,
        remote_announce_audio_id=None, recording_policy="dontcare",
        members=[], updated_at=UPDATED_AT,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class _Session:
    def __init__(self):
        self.added: list = []
        self.flushes = 0
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1


# ------------------------------------------------------------- oldin xato edi
@pytest.mark.asyncio
async def test_apply_rg_members_calls_validate_members_not_undefined_function(monkeypatch):
    calls = []

    async def fake_validate(session, tenant_id, members):
        calls.append(members)

    monkeypatch.setattr(rg, "_validate_members", fake_validate)
    group = _group()
    payload = UpdateRingGroupPayload(updated_at=UPDATED_AT, members=[])
    diff: dict = {}
    await rg._apply_rg_members(_Session(), "t1", group, payload, diff)
    assert calls == [[]]
    assert diff["members"] == 0


# --------------------------------------------------------------- oddiy maydonlar
def test_apply_simple_rg_fields_sets_new_scalar_fields():
    group = _group()
    payload = UpdateRingGroupPayload(
        updated_at=UPDATED_AT, ring_strategy_sound="moh", skip_busy_agent=True,
        confirm_calls=True, recording_policy="force",
    )
    diff: dict = {}
    rg._apply_simple_rg_fields(group, payload, diff)
    assert group.ring_strategy_sound == "moh"
    assert group.skip_busy_agent is True
    assert group.confirm_calls is True
    assert group.recording_policy == "force"
    assert diff == {
        "ring_strategy_sound": "moh", "skip_busy_agent": True,
        "confirm_calls": True, "recording_policy": "force",
    }


def test_apply_simple_rg_fields_leaves_untouched_when_none():
    group = _group(skip_busy_agent=True)
    payload = UpdateRingGroupPayload(updated_at=UPDATED_AT)
    diff: dict = {}
    rg._apply_simple_rg_fields(group, payload, diff)
    assert group.skip_busy_agent is True
    assert diff == {}


# --------------------------------------------------------------- alert_info
@pytest.mark.asyncio
async def test_apply_rg_alert_info_sets_and_clears():
    group = _group()
    await rg._apply_rg_alert_info(group, UpdateRingGroupPayload(updated_at=UPDATED_AT, alert_info="Ichki"), {})
    assert group.alert_info == "Ichki"

    diff: dict = {}
    await rg._apply_rg_alert_info(
        group, UpdateRingGroupPayload(updated_at=UPDATED_AT, alert_info_clear=True), diff,
    )
    assert group.alert_info is None
    assert diff["alert_info"] is None


# --------------------------------------------------------------- moh_class
@pytest.mark.asyncio
async def test_apply_rg_moh_class_sets_clears_and_404s(monkeypatch):
    moh = SimpleNamespace(id="m1")

    async def resolve_ok(session, tenant_id, moh_class_id):
        return moh

    monkeypatch.setattr(rg, "_resolve_moh_class", resolve_ok)
    group = _group()
    diff: dict = {}
    await rg._apply_rg_moh_class(None, "t1", group, UpdateRingGroupPayload(updated_at=UPDATED_AT, moh_class_id="m1"), diff)
    assert group.moh_class_id == "m1"
    assert diff["moh_class_id"] == "m1"

    diff = {}
    await rg._apply_rg_moh_class(
        None, "t1", group, UpdateRingGroupPayload(updated_at=UPDATED_AT, moh_class_id_clear=True), diff,
    )
    assert group.moh_class_id is None
    assert diff["moh_class_id"] is None

    async def resolve_404(session, tenant_id, moh_class_id):
        raise ApiError(404, "not_found", "Kutish musiqasi sinfi topilmadi", field="moh_class_id")

    monkeypatch.setattr(rg, "_resolve_moh_class", resolve_404)
    with pytest.raises(ApiError) as exc:
        await rg._apply_rg_moh_class(
            None, "t1", group, UpdateRingGroupPayload(updated_at=UPDATED_AT, moh_class_id="bad"), {},
        )
    assert exc.value.status_code == 404


# --------------------------------------------------------------- audio FK (umumiy)
@pytest.mark.asyncio
async def test_apply_rg_audio_fk_sets_and_clears(monkeypatch):
    audio = SimpleNamespace(id="a1")

    async def resolve_ok(session, tenant_id, audio_id):
        return audio

    monkeypatch.setattr(rg, "_resolve_audio", resolve_ok)
    group = _group()
    diff: dict = {}
    await rg._apply_rg_audio_fk(
        None, "t1", group, UpdateRingGroupPayload(updated_at=UPDATED_AT, announcement_audio_id="a1"), diff,
        payload_field="announcement_audio_id",
    )
    assert group.announcement_audio_id == "a1"
    assert diff["announcement_audio_id"] == "a1"

    diff = {}
    await rg._apply_rg_audio_fk(
        None, "t1", group,
        UpdateRingGroupPayload(updated_at=UPDATED_AT, remote_announce_audio_id_clear=True), diff,
        payload_field="remote_announce_audio_id",
    )
    assert group.remote_announce_audio_id is None
    assert diff["remote_announce_audio_id"] is None


# --------------------------------------------------------------- _resolve_*/_audio_ref
@pytest.mark.asyncio
async def test_resolve_audio_and_moh_class_none_passthrough():
    assert await rg._resolve_audio(None, "t1", None) is None
    assert await rg._resolve_moh_class(None, "t1", None) is None


def test_audio_ref_none_and_value():
    assert rg._audio_ref(None) is None
    audio = SimpleNamespace(
        id="a1", name="Salom", duration_ms=1000, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    out = rg._audio_ref(audio)
    assert out is not None and out.id == "a1" and out.format == "wav"


# --------------------------------------------------------------- _rg_out
@pytest.mark.asyncio
async def test_rg_out_includes_new_fpbx_fields(monkeypatch):
    announcement = SimpleNamespace(id="a1", name="Kirish", duration_ms=500, created_at=UPDATED_AT)
    remote = SimpleNamespace(id="a2", name="Uzoqdan", duration_ms=600, created_at=UPDATED_AT)
    moh = SimpleNamespace(id="m1", name="Jazz")
    group = _group(
        announcement_audio_id="a1", remote_announce_audio_id="a2", moh_class=moh,
        alert_info="Ichki", skip_busy_agent=True, confirm_calls=True, recording_policy="force",
    )

    async def fake_dial_number(session, tenant_id, target_id):
        return "100"

    async def fake_resolve_target(session, tenant_id, target_id):
        return {"kind": "extension", "id": "e1", "label": "101", "number": "101", "broken": False}

    async def fake_resolve_audio(session, tenant_id, audio_id):
        return {"a1": announcement, "a2": remote}.get(audio_id)

    monkeypatch.setattr(rg, "dial_number_for_target", fake_dial_number)
    monkeypatch.setattr(rg, "resolve_target", fake_resolve_target)
    monkeypatch.setattr(rg, "_resolve_audio", fake_resolve_audio)

    out = await rg._rg_out(None, "t1", group)
    assert out.announcement is not None and out.announcement.id == "a1"
    assert out.remote_announce is not None and out.remote_announce.id == "a2"
    assert out.moh_class is not None and out.moh_class.name == "Jazz"
    assert out.alert_info == "Ichki"
    assert out.skip_busy_agent is True
    assert out.confirm_calls is True
    assert out.recording_policy == "force"
