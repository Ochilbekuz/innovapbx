"""`app/api/v1/me.py` — m2b-contract.md §4 birlik testlari (DB/AMI'siz: soxta
sessiya + monkeypatch). Diqqat markazida — ikkinchi mustaqil mantiq YO'Q
ekanligi (dryer): admin bilan BITTA funksiya (`apply_call_field_patch`,
`_member_action(source="portal")`), va 409 `no_extension` qamrovi. To'liq
oqim jonli testda (`scripts/m2b-proof.sh`, ssenariy 2)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import me
from app.core.errors import ApiError
from app.schemas_users import ManagedUserOut, MeQueueOut, MeToday, PatchMeExtensionPayload

OLD = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)


class _Session:
    def __init__(self, execute_rows: list | None = None):
        self._execute_rows = execute_rows or []
        self.flushes = self.commits = self.refreshed = 0

    async def flush(self) -> None:
        self.flushes += 1

    async def refresh(self, obj) -> None:
        self.refreshed += 1

    async def commit(self) -> None:
        self.commits += 1

    async def execute(self, _stmt):
        rows = self._execute_rows

        class _Result:
            def scalar_one_or_none(self):
                return rows[0] if rows else None

            def scalars(self):
                return SimpleNamespace(all=lambda: rows)

        return _Result()


def _ext(**kw) -> SimpleNamespace:
    base = dict(id="e1", number="201", name="Aziz", dnd=False, forward_always=None, forward_busy=None,
                outbound_allowed=True, updated_at=OLD)
    base.update(kw)
    return SimpleNamespace(**base)


def _user(**kw) -> SimpleNamespace:
    base = dict(id="u1", tenant_id="t1", extension=None,
                tenant=SimpleNamespace(code="innova", timezone="Asia/Tashkent", language="uz"))
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def audit(monkeypatch):
    rows: list = []

    async def fake_audit(session, **kw):
        rows.append(kw)

    monkeypatch.setattr(me, "record_audit", fake_audit)
    return rows


# ------------------------------------------------------- _require_own_extension
def test_require_own_extension_raises_no_extension_when_missing():
    with pytest.raises(ApiError) as exc:
        me._require_own_extension(_user(extension=None))
    assert exc.value.status_code == 409 and exc.value.code == "no_extension"


def test_require_own_extension_returns_extension_when_present():
    ext = _ext()
    assert me._require_own_extension(_user(extension=ext)) is ext


def _managed_user_sentinel() -> ManagedUserOut:
    return ManagedUserOut(id="u1", username="aziz", full_name="Aziz", email=None, role="operator",
                           extension=None, is_active=True, language="uz", must_change_password=False,
                           last_login_at=None, updated_at=OLD)


def _queue_sentinel() -> MeQueueOut:
    return MeQueueOut(id="q1", name="Savol", number="7001", dynamic=True, logged_in=True,
                       paused=False, pause_reason=None)


# --------------------------------------------------------------- my_overview
@pytest.mark.asyncio
async def test_my_overview_without_extension_returns_empty_shape(monkeypatch):
    sentinel = _managed_user_sentinel()
    monkeypatch.setattr(me, "_managed_user_out", lambda user: sentinel)
    out = await me.my_overview(session=_Session(), user=_user(extension=None))
    assert out.user is sentinel
    assert out.extension is None
    assert out.queues == []
    assert out.today == MeToday(answered=0, missed=0, talk_seconds=0)


@pytest.mark.asyncio
async def test_my_overview_with_extension_builds_full_response(monkeypatch):
    ext = _ext()
    sentinel = _managed_user_sentinel()
    queue = _queue_sentinel()
    monkeypatch.setattr(me, "_managed_user_out", lambda user: sentinel)

    async def fake_box(session, tenant_id, ext_id):
        return SimpleNamespace(id="box1")

    async def fake_queues(session, tenant_id, ext_id):
        return [queue]

    async def fake_today(session, user, number):
        assert number == "201"
        return MeToday(answered=1, missed=2, talk_seconds=30)

    monkeypatch.setattr(me, "_own_voicemail_box", fake_box)
    monkeypatch.setattr(me, "_my_queues", fake_queues)
    monkeypatch.setattr(me, "_today_stats", fake_today)

    out = await me.my_overview(session=_Session(), user=_user(extension=ext))
    assert out.user is sentinel
    assert out.extension.voicemail_box_id == "box1"
    assert out.queues == [queue]
    assert out.today.answered == 1


# --------------------------------------------------------------- _my_queues
@pytest.mark.asyncio
async def test_my_queues_filters_to_member_queues_only(monkeypatch):
    member = SimpleNamespace(extension_id="e1", dynamic=True, logged_in=True, paused=False, pause_reason=None)
    other_member = SimpleNamespace(extension_id="other", dynamic=False, logged_in=False, paused=False, pause_reason=None)
    q_with_member = SimpleNamespace(id="q1", name="Savol", target_id="tg1", members=[member])
    q_without_member = SimpleNamespace(id="q2", name="Boshqa", target_id="tg2", members=[other_member])

    async def fake_dial(session, tenant_id, target_id):
        return f"num-{target_id}"

    monkeypatch.setattr(me, "dial_number_for_target", fake_dial)
    session = _Session(execute_rows=[q_with_member, q_without_member])
    out = await me._my_queues(session, "t1", "e1")
    assert len(out) == 1
    assert out[0].id == "q1" and out[0].number == "num-tg1" and out[0].logged_in is True


@pytest.mark.asyncio
async def test_my_queues_empty_when_no_queues():
    out = await me._my_queues(_Session(execute_rows=[]), "t1", "e1")
    assert out == []


# ---------------------------------------------------------------- _today_stats
@pytest.mark.asyncio
async def test_today_stats_aggregates_only_own_calls(monkeypatch):
    monkeypatch.setattr(me, "today_bounds_utc", lambda tz, now: (OLD, NOW))
    answered_in = SimpleNamespace(src="999", dst="201", disposition="answered", direction="in", billsec=10)
    missed_in = SimpleNamespace(src="998", dst="201", disposition="no_answer", direction="in", billsec=0)
    other = SimpleNamespace(src="300", dst="400", disposition="answered", direction="out", billsec=99)
    monkeypatch.setattr(me, "calls_from_rows", lambda rows: [answered_in, missed_in, other])

    user = _user(tenant=SimpleNamespace(code="innova", timezone="Asia/Tashkent", language="uz"))
    out = await me._today_stats(_Session(execute_rows=["row1"]), user, "201")
    assert out.answered == 1 and out.missed == 1 and out.talk_seconds == 10


# ----------------------------------------------------------- patch_my_extension
@pytest.mark.asyncio
async def test_patch_my_extension_requires_own_extension():
    payload = PatchMeExtensionPayload(dnd=True, updated_at=OLD)
    with pytest.raises(ApiError) as exc:
        await me.patch_my_extension(payload, session=_Session(), user=_user(extension=None))
    assert exc.value.code == "no_extension"


@pytest.mark.asyncio
async def test_patch_my_extension_stale(audit):
    ext = _ext()
    payload = PatchMeExtensionPayload(dnd=True, updated_at=NOW)
    with pytest.raises(ApiError) as exc:
        await me.patch_my_extension(payload, session=_Session(), user=_user(extension=ext))
    assert exc.value.code == "stale"


@pytest.mark.asyncio
async def test_patch_my_extension_reuses_shared_validation_function(audit, monkeypatch):
    """§4 kontrakti: admin PATCH bilan BITTA funksiya — shu yerda faqat
    `dnd`/`forward_always`/`forward_busy` to'plami bilan chaqirilishi tekshiriladi."""
    ext = _ext()
    seen = {}

    def fake_apply(e, p, *, keep_if_none, clearable):
        seen["keep_if_none"] = keep_if_none
        seen["clearable"] = clearable
        e.dnd = True
        return {"dnd": {"from": False, "to": True}}

    monkeypatch.setattr(me, "apply_call_field_patch", fake_apply)

    async def fake_box(session, tenant_id, ext_id):
        return None

    monkeypatch.setattr(me, "_own_voicemail_box", fake_box)
    payload = PatchMeExtensionPayload(dnd=True, updated_at=OLD)
    out = await me.patch_my_extension(payload, session=_Session(), user=_user(extension=ext))
    assert seen == {"keep_if_none": ("dnd",), "clearable": ("forward_always", "forward_busy")}
    assert out.item.dnd is True
    assert audit[0]["action"] == "extension.update"


# ------------------------------------------------------------ act_on_my_queue
@pytest.mark.asyncio
async def test_act_on_my_queue_uses_source_portal(monkeypatch):
    ext = _ext()
    seen = {}

    async def fake_member_action(session, user, queue_id, extension_id, action, payload, ami, *, source):
        seen["source"] = source
        seen["extension_id"] = extension_id

    async def fake_get_queue(session, tenant_id, queue_id):
        member = SimpleNamespace(extension_id="e1", dynamic=True, logged_in=True, paused=False, pause_reason=None)
        return SimpleNamespace(id="q1", name="Savol", target_id="tg1", members=[member])

    async def fake_dial(session, tenant_id, target_id):
        return "7001"

    monkeypatch.setattr(me, "_member_action", fake_member_action)
    monkeypatch.setattr(me, "_get_queue_or_404", fake_get_queue)
    monkeypatch.setattr(me, "dial_number_for_target", fake_dial)

    out = await me.act_on_my_queue("q1", "login", session=_Session(), user=_user(extension=ext), ami=object())
    assert seen == {"source": "portal", "extension_id": "e1"}
    assert out.item.logged_in is True and out.item.number == "7001"


@pytest.mark.asyncio
async def test_act_on_my_queue_requires_own_extension():
    with pytest.raises(ApiError) as exc:
        await me.act_on_my_queue("q1", "login", session=_Session(), user=_user(extension=None), ami=object())
    assert exc.value.code == "no_extension"


@pytest.mark.asyncio
async def test_act_on_my_queue_404_when_not_a_member(monkeypatch):
    ext = _ext()

    async def fake_member_action(*a, **kw):
        return None

    async def fake_get_queue(session, tenant_id, queue_id):
        return SimpleNamespace(id="q1", name="Savol", target_id="tg1", members=[])

    monkeypatch.setattr(me, "_member_action", fake_member_action)
    monkeypatch.setattr(me, "_get_queue_or_404", fake_get_queue)
    with pytest.raises(ApiError) as exc:
        await me.act_on_my_queue("q1", "login", session=_Session(), user=_user(extension=ext), ami=object())
    assert exc.value.status_code == 404


# ----------------------------------------------------------------- my_calls
@pytest.mark.asyncio
async def test_my_calls_filters_to_own_extension_only(monkeypatch):
    ext = _ext(number="201")
    own_call = SimpleNamespace(src="201", dst="999", disposition="answered", direction="out", billsec=10,
                               linkedid=None)
    other_call = SimpleNamespace(src="300", dst="400", disposition="answered", direction="out", billsec=5,
                                 linkedid=None)

    monkeypatch.setattr(me, "_build_calls_query", lambda code, **kw: "STMT")
    monkeypatch.setattr(me, "calls_from_rows", lambda rows: [own_call, other_call])

    out = await me.my_calls(session=_Session(execute_rows=[]), user=_user(extension=ext))
    assert out["items"] == [own_call]
    assert out["total"] == 1
    assert own_call.recordings == []  # M3b §1: linkedid yo'q — yozuvlar bo'sh, bazaga so'rov yo'q


@pytest.mark.asyncio
async def test_my_calls_requires_own_extension():
    with pytest.raises(ApiError) as exc:
        await me.my_calls(session=_Session(), user=_user(extension=None))
    assert exc.value.code == "no_extension"


# -------------------------------------------------------------- voicemail
@pytest.mark.asyncio
async def test_my_voicemail_requires_own_box(monkeypatch):
    async def fake_box(session, tenant_id, ext_id):
        return None

    monkeypatch.setattr(me, "_own_voicemail_box", fake_box)
    with pytest.raises(ApiError) as exc:
        await me.my_voicemail(session=_Session(), user=_user(extension=_ext()))
    assert exc.value.code == "no_extension"


@pytest.mark.asyncio
async def test_my_voicemail_delegates_to_list_box_messages(monkeypatch):
    box = SimpleNamespace(id="box1")

    async def fake_require_box(session, user):
        return box

    seen = {}

    async def fake_list(box_id, *, session, user):
        seen["box_id"] = box_id
        return {"items": []}

    monkeypatch.setattr(me, "_require_own_box", fake_require_box)
    monkeypatch.setattr(me, "list_box_messages", fake_list)
    out = await me.my_voicemail(session=_Session(), user=_user(extension=_ext()))
    assert seen["box_id"] == "box1" and out == {"items": []}


@pytest.mark.asyncio
async def test_my_voicemail_audio_delegates_with_own_box(monkeypatch):
    box = SimpleNamespace(id="box1")

    async def fake_require_box(session, user):
        return box

    seen = {}

    async def fake_audio(box_id, msg, *, session, user):
        seen["args"] = (box_id, msg)
        return "FILE"

    monkeypatch.setattr(me, "_require_own_box", fake_require_box)
    monkeypatch.setattr(me, "message_audio", fake_audio)
    out = await me.my_voicemail_audio("msg0001", session=_Session(), user=_user(extension=_ext()))
    assert seen["args"] == ("box1", "msg0001") and out == "FILE"


@pytest.mark.asyncio
async def test_my_voicemail_heard_delegates_with_own_box(monkeypatch):
    box = SimpleNamespace(id="box1")

    async def fake_require_box(session, user):
        return box

    seen = {}

    async def fake_heard(box_id, msg, *, session, user, ami):
        seen["args"] = (box_id, msg)

    monkeypatch.setattr(me, "_require_own_box", fake_require_box)
    monkeypatch.setattr(me, "mark_heard", fake_heard)
    await me.my_voicemail_heard("msg0001", session=_Session(), user=_user(extension=_ext()), ami=object())
    assert seen["args"] == ("box1", "msg0001")


@pytest.mark.asyncio
async def test_my_voicemail_delete_delegates_with_own_box(monkeypatch):
    box = SimpleNamespace(id="box1")

    async def fake_require_box(session, user):
        return box

    seen = {}

    async def fake_delete(box_id, msg, *, session, user, ami):
        seen["args"] = (box_id, msg)

    monkeypatch.setattr(me, "_require_own_box", fake_require_box)
    monkeypatch.setattr(me, "delete_message", fake_delete)
    await me.my_voicemail_delete("msg0001", session=_Session(), user=_user(extension=_ext()), ami=object())
    assert seen["args"] == ("box1", "msg0001")


# --------------------------------------------------------------- B2: 2fa (xavfsizlik)
def _totp_user(**kw) -> SimpleNamespace:
    base = dict(totp_enabled_at=None, totp_secret_enc=None, totp_recovery_hashes=[], totp_last_step=None)
    base.update(kw)
    return _user(**base)


@pytest.fixture
def revoke(monkeypatch):
    calls: list = []

    async def fake_revoke(session, user_id):
        calls.append(user_id)

    monkeypatch.setattr(me, "revoke_refresh_tokens", fake_revoke)
    return calls


@pytest.mark.asyncio
async def test_setup_2fa_rejects_when_already_enabled(monkeypatch):
    """CVE-style takeover: hisobni egallab olgan sessiya (masalan o'g'irlangan
    access token) `/me/2fa/setup`ni qayta chaqirib o'z sekretini yozib qo'ya
    olmasligi kerak — buni faqat 2FA'ni avval O'CHIRGAN (kod talab qiladi)
    foydalanuvchi qila oladi."""

    async def boom(*_a, **_kw):  # pragma: no cover -- chaqirilmasligi SHART
        raise AssertionError("sekret 2FA yoqilganida yozilmasligi kerak")

    monkeypatch.setattr(me, "encrypt_secret", boom)
    user = _totp_user(totp_enabled_at=NOW)
    with pytest.raises(ApiError) as exc:
        await me.setup_2fa(session=_Session(), user=user)
    assert exc.value.status_code == 409 and exc.value.code == "already_enabled"


@pytest.mark.asyncio
async def test_setup_2fa_allows_when_not_enabled(monkeypatch):
    monkeypatch.setattr(me, "encrypt_secret", lambda session, secret: _coro("enc-secret"))
    monkeypatch.setattr(me, "generate_secret", lambda: "raw-secret")
    user = _totp_user(username="aziz")
    out = await me.setup_2fa(session=_Session(), user=user)
    assert user.totp_secret_enc == "enc-secret"
    assert out.secret == "raw-secret"


def _coro(value):
    async def _inner():
        return value
    return _inner()


@pytest.mark.asyncio
async def test_verify_2fa_code_or_raise_locked_rejects_without_checking_code(monkeypatch):
    async def boom(*_a, **_kw):  # pragma: no cover -- chaqirilmasligi SHART
        raise AssertionError("qulflangan hisobda kod tekshirilmasligi kerak")

    monkeypatch.setattr(me, "_is_locked", lambda user: True)
    monkeypatch.setattr(me, "verify_user_code", boom)
    with pytest.raises(ApiError) as exc:
        await me._verify_2fa_code_or_raise(_Session(), _totp_user(), "000000")
    assert exc.value.status_code == 423 and exc.value.code == "locked"


@pytest.mark.asyncio
async def test_verify_2fa_code_or_raise_wrong_code_registers_failed_login(monkeypatch):
    """Login TOTP bosqichi bilan BIR XIL himoya qayta ishlatiladi — noto'g'ri
    kod `_register_failed_login` orqali hisoblanadi, cheksiz urinish YO'Q."""
    registered: list = []

    async def fake_register(session, user):
        registered.append(user)

    monkeypatch.setattr(me, "_is_locked", lambda user: False)
    monkeypatch.setattr(me, "verify_user_code", lambda *a, **kw: _coro(False))
    monkeypatch.setattr(me, "_register_failed_login", fake_register)
    user = _totp_user()
    with pytest.raises(ApiError) as exc:
        await me._verify_2fa_code_or_raise(_Session(), user, "000000")
    assert exc.value.status_code == 401 and exc.value.code == "invalid_code"
    assert registered == [user]


@pytest.mark.asyncio
async def test_verify_2fa_code_or_raise_correct_code_passes(monkeypatch):
    monkeypatch.setattr(me, "_is_locked", lambda user: False)
    monkeypatch.setattr(me, "verify_user_code", lambda *a, **kw: _coro(True))
    await me._verify_2fa_code_or_raise(_Session(), _totp_user(), "123456")  # raise bo'lmasligi -- bu test


@pytest.mark.asyncio
async def test_enable_2fa_revokes_refresh_tokens_on_success(audit, revoke, monkeypatch):
    monkeypatch.setattr(me, "decrypt_secret", lambda session, enc: _coro("raw-secret"))
    monkeypatch.setattr(me, "totp_verify", lambda secret, code, now, last_step: 42)
    monkeypatch.setattr(me, "generate_recovery_codes", lambda: ["a-b", "c-d"])
    monkeypatch.setattr(me, "hash_recovery_codes", lambda codes: [f"h({c})" for c in codes])
    from app.schemas_2fa import TotpEnablePayload
    user = _totp_user(totp_secret_enc="enc-secret", id="u1")
    out = await me.enable_2fa(TotpEnablePayload(code="123456"), session=_Session(), user=user)
    assert out.recovery_codes == ["a-b", "c-d"]
    assert user.totp_enabled_at is not None
    assert revoke == ["u1"]


@pytest.mark.asyncio
async def test_disable_2fa_blocked_when_locked(monkeypatch):
    monkeypatch.setattr(me, "_is_locked", lambda user: True)
    from app.schemas_2fa import TotpDisablePayload
    user = _totp_user(totp_enabled_at=NOW)
    with pytest.raises(ApiError) as exc:
        await me.disable_2fa(TotpDisablePayload(code="000000"), session=_Session(), user=user)
    assert exc.value.status_code == 423 and exc.value.code == "locked"
    assert user.totp_enabled_at == NOW  # hech narsa o'chirilmagan


@pytest.mark.asyncio
async def test_disable_2fa_clears_secret_and_revokes_tokens_on_success(audit, revoke, monkeypatch):
    monkeypatch.setattr(me, "_is_locked", lambda user: False)
    monkeypatch.setattr(me, "verify_user_code", lambda *a, **kw: _coro(True))
    from app.schemas_2fa import TotpDisablePayload
    user = _totp_user(totp_enabled_at=NOW, totp_secret_enc="enc", totp_recovery_hashes=["h"], id="u1")
    await me.disable_2fa(TotpDisablePayload(code="123456"), session=_Session(), user=user)
    assert user.totp_enabled_at is None and user.totp_secret_enc is None and user.totp_recovery_hashes == []
    assert revoke == ["u1"]


@pytest.mark.asyncio
async def test_regenerate_recovery_codes_blocked_when_locked(monkeypatch):
    monkeypatch.setattr(me, "_is_locked", lambda user: True)
    from app.schemas_2fa import TotpDisablePayload
    user = _totp_user(totp_enabled_at=NOW)
    with pytest.raises(ApiError) as exc:
        await me.regenerate_recovery_codes(TotpDisablePayload(code="000000"), session=_Session(), user=user)
    assert exc.value.status_code == 423 and exc.value.code == "locked"
