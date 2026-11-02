"""`/voicemail-boxes` va `/settings/notify` marshrut funksiyalari — DB/AMI'siz
(soxta sessiya, tashqi qadamlar monkeypatch). To'liq oqim jonli testda
(`test_voicemail_live.py`) va `scripts/m1c-proof.sh` da."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from app.api.v1 import notify_settings as ns
from app.api.v1 import voicemail_boxes as vb
from app.core.errors import ApiError
from app.schemas_voicemail import CreateVoicemailBoxPayload, UpdateNotifySettingsPayload, UpdateVoicemailBoxPayload

USER = SimpleNamespace(id="u1", tenant_id="t1")
NOW = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)


class _Session:
    def __init__(self, *, get=None, flush_error: Exception | None = None):
        self.added: list = []
        self.deleted: list = []
        self.commits = self.rollbacks = 0
        self._get = get or {}
        self._flush_error = flush_error

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()
        if self._flush_error and len(self.added) > 1:
            raise self._flush_error

    async def rollback(self):
        self.rollbacks += 1

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        obj.updated_at = NOW

    async def delete(self, obj):
        self.deleted.append(obj)

    async def get(self, model, key):
        return self._get.get(str(key))


@pytest.fixture
def audit(monkeypatch):
    rows: list = []

    async def fake_audit(session, **kw):
        rows.append(kw)

    monkeypatch.setattr(vb, "record_audit", fake_audit)
    monkeypatch.setattr(ns, "record_audit", fake_audit)
    return rows


@pytest.fixture
def stub_apply(monkeypatch):
    applied: list = []

    async def fake_apply(session, tenant_id, user, ami):
        applied.append(tenant_id)
        return "APPLY"

    async def fake_code(session, tenant_id):
        return "t1"

    async def fake_get(session, tenant_id, box_id, *, fresh=False):
        return SimpleNamespace(id=box_id, fresh=fresh)

    async def no_greeting(session, tenant_id, audio_id):
        return None

    monkeypatch.setattr(vb, "apply_dialplan_and_voicemail", fake_apply)
    monkeypatch.setattr(vb, "get_tenant_code", fake_code)
    monkeypatch.setattr(vb, "_get_box_or_404", fake_get)
    monkeypatch.setattr(vb, "_check_greeting", no_greeting)
    monkeypatch.setattr(vb, "_box_out", lambda box, code: {"id": str(box.id), "code": code})
    monkeypatch.setattr(vb, "VoicemailBoxMutated", lambda item, apply: SimpleNamespace(item=item, apply=apply))
    return applied


def _owner(monkeypatch, ext):
    async def fake_owner(session, tenant_id, payload):
        return ext, ext.number if ext else payload.mailbox

    monkeypatch.setattr(vb, "_resolve_owner", fake_owner)


# ------------------------------------------------------------ _resolve_owner (1.0.4 §2: umumiy
# quti raqami ext/navbat/guruh/IVR raqami bilan to'qnashmasin — `numbers.ensure_number_free`
# BIR XIL umumiy yordamchi orqali, va teskarisi).
async def test_resolve_owner_shared_mailbox_checks_common_number_helper(monkeypatch):
    calls: list = []

    async def fake_ensure(session, tenant_id, number, *, field):
        calls.append((tenant_id, number, field))

    monkeypatch.setattr(vb, "ensure_number_free", fake_ensure)
    ext, mailbox = await vb._resolve_owner(_Session(), "t1", CreateVoicemailBoxPayload(mailbox="601", pin="1234"))
    assert ext is None and mailbox == "601"
    assert calls == [("t1", "601", "mailbox")]


async def test_resolve_owner_shared_mailbox_taken_by_other_entity_is_409(monkeypatch):
    async def fake_ensure(session, tenant_id, number, *, field):
        raise ApiError(409, "number_taken", "Bu raqam band", field=field)

    monkeypatch.setattr(vb, "ensure_number_free", fake_ensure)
    with pytest.raises(ApiError) as exc:
        await vb._resolve_owner(_Session(), "t1", CreateVoicemailBoxPayload(mailbox="601", pin="1234"))
    assert (exc.value.status_code, exc.value.code, exc.value.field) == (409, "number_taken", "mailbox")


async def test_resolve_owner_by_extension_skips_number_check(monkeypatch):
    called = False

    async def fake_ensure(*a, **kw):
        nonlocal called
        called = True

    async def fake_get(session, model, tenant_id, ext_id, *, not_found_message, field=None, options=()):
        return SimpleNamespace(id=ext_id, number="201")

    monkeypatch.setattr(vb, "ensure_number_free", fake_ensure)
    monkeypatch.setattr(vb, "get_tenant_scoped_or_404", fake_get)
    ext, mailbox = await vb._resolve_owner(_Session(), "t1",
                                           CreateVoicemailBoxPayload(extension_id="e1", pin="1234"))
    assert (ext.number, mailbox, called) == ("201", "201", False)


# ------------------------------------------------------------ create
async def test_create_for_extension_sets_no_answer_and_masks_pin_in_audit(monkeypatch, audit, stub_apply):
    ext = SimpleNamespace(id=uuid.uuid4(), number="201", no_answer_target_id=None)
    _owner(monkeypatch, ext)
    s = _Session()
    payload = CreateVoicemailBoxPayload(extension_id=str(ext.id), pin="1234", email="a@b.uz", email_notify=True)
    out = await vb.create_box(payload, s, USER, ami=None)
    target, box = s.added
    assert (target.kind, target.label) == ("voicemail", "Ovozli pochta · 201")
    assert (box.mailbox, box.extension_id, box.email, box.email_notify) == ("201", ext.id, "a@b.uz", True)
    assert box.pin_hash and box.pin_hash != "1234"
    assert ext.no_answer_target_id == target.id
    assert audit[0]["diff"] == {"mailbox": "201", "pin": "1234", "email": "a@b.uz", "email_notify": True}
    assert audit[0]["action"] == "voicemail.create"
    assert stub_apply == ["t1"] and s.commits == 1
    assert out.apply == "APPLY" and out.item["id"] == str(box.id)


async def test_create_keeps_existing_no_answer(monkeypatch, audit, stub_apply):
    keep = uuid.uuid4()
    ext = SimpleNamespace(id=uuid.uuid4(), number="202", no_answer_target_id=keep)
    _owner(monkeypatch, ext)
    await vb.create_box(CreateVoicemailBoxPayload(extension_id=str(ext.id), pin="1234"), _Session(), USER, ami=None)
    assert ext.no_answer_target_id == keep


@pytest.mark.parametrize("ext,field", [(None, "mailbox"), (SimpleNamespace(id=uuid.uuid4(), number="203",
                                                                            no_answer_target_id=None), "extension_id")])
async def test_create_duplicate_mailbox_is_409_with_field(monkeypatch, audit, stub_apply, ext, field):
    _owner(monkeypatch, ext)
    s = _Session(flush_error=IntegrityError("x", {}, Exception("dup")))
    payload = CreateVoicemailBoxPayload(pin="1234", **({"extension_id": "e"} if ext else {"mailbox": "700"}))
    with pytest.raises(ApiError) as exc:
        await vb.create_box(payload, s, USER, ami=None)
    assert (exc.value.status_code, exc.value.code, exc.value.field) == (409, "mailbox_taken", field)
    assert s.rollbacks == 1 and s.commits == 0 and audit == [] and stub_apply == []


# ------------------------------------------------------------ update
async def test_update_only_given_fields_pin_rehashed(monkeypatch, audit, stub_apply):
    box = SimpleNamespace(id="b1", updated_at=NOW, email="old@x.uz", email_notify=False, pin_hash="H",
                          greeting_audio_id="g0")

    async def fake_get(session, tenant_id, box_id, *, fresh=False):
        return box

    monkeypatch.setattr(vb, "_get_box_or_404", fake_get)
    payload = UpdateVoicemailBoxPayload(email=None, pin="5678", updated_at=NOW)
    await vb.update_box("b1", payload, _Session(), USER, ami=None)
    assert box.email is None and box.email_notify is False and box.greeting_audio_id == "g0"
    assert box.pin_hash != "H"
    assert audit[0]["diff"] == {"email": None, "pin": "5678"}


async def test_update_greeting_checked_and_cleared(monkeypatch, audit, stub_apply):
    box = SimpleNamespace(id="b1", updated_at=NOW, greeting_audio_id="g0", pin_hash="H")
    checked: list = []

    async def fake_get(session, tenant_id, box_id, *, fresh=False):
        return box

    async def fake_check(session, tenant_id, audio_id):
        checked.append(audio_id)

    monkeypatch.setattr(vb, "_get_box_or_404", fake_get)
    monkeypatch.setattr(vb, "_check_greeting", fake_check)
    await vb.update_box("b1", UpdateVoicemailBoxPayload(greeting_audio_id=None, updated_at=NOW), _Session(),
                        USER, ami=None)
    assert checked == [None] and box.greeting_audio_id is None and box.pin_hash == "H"
    assert audit[0]["diff"] == {"greeting_audio_id": None}


async def test_update_stale_is_409(monkeypatch, audit, stub_apply):
    async def fake_get(session, tenant_id, box_id, *, fresh=False):
        return SimpleNamespace(id="b1", updated_at=NOW)

    monkeypatch.setattr(vb, "_get_box_or_404", fake_get)
    with pytest.raises(ApiError) as exc:
        await vb.update_box("b1", UpdateVoicemailBoxPayload(updated_at=datetime(2020, 1, 1, tzinfo=timezone.utc)),
                            _Session(), USER, ami=None)
    assert exc.value.status_code == 409 and audit == []


# ------------------------------------------------------------ delete
def _box(ext_target=None, own_target=None):
    target_id = own_target or uuid.uuid4()
    ext = SimpleNamespace(id=uuid.uuid4(), no_answer_target_id=ext_target if ext_target is not None else target_id)
    return SimpleNamespace(target_id=target_id, extension_id=ext.id, extension=ext, mailbox="201"), ext


def _usages(monkeypatch, usages):
    async def fake(session, tenant_id, target_id):
        return usages

    monkeypatch.setattr(vb, "usages_for_target", fake)


async def test_delete_ignores_own_extension_usage_and_clears_no_answer(monkeypatch):
    box, ext = _box()
    _usages(monkeypatch, [{"kind": "extension", "id": str(ext.id), "field": "no_answer"}])
    target = SimpleNamespace(id=box.target_id)
    s = _Session(get={str(box.target_id): target})
    await vb.delete_box_and_target(s, "t1", box)
    assert ext.no_answer_target_id is None
    assert s.deleted == [box, target]


async def test_delete_keeps_other_no_answer_and_tolerates_missing_target(monkeypatch):
    other = uuid.uuid4()
    box, ext = _box(ext_target=other)
    _usages(monkeypatch, [])
    s = _Session()
    await vb.delete_box_and_target(s, "t1", box)
    assert ext.no_answer_target_id == other and s.deleted == [box]


async def test_delete_shared_box_without_extension(monkeypatch):
    box = SimpleNamespace(target_id=uuid.uuid4(), extension_id=None, extension=None, mailbox="700")
    _usages(monkeypatch, [])
    s = _Session()
    await vb.delete_box_and_target(s, "t1", box)
    assert s.deleted == [box]


async def test_delete_in_use_by_other_is_409_with_usages(monkeypatch):
    box, ext = _box()
    other_ext = {"kind": "extension", "id": "someone-else", "field": "no_answer"}
    route = {"kind": "inbound_route", "id": "r1"}
    _usages(monkeypatch, [{"kind": "extension", "id": str(ext.id)}, other_ext, route])
    s = _Session()
    with pytest.raises(ApiError) as exc:
        await vb.delete_box_and_target(s, "t1", box)
    assert (exc.value.status_code, exc.value.code) == (409, "in_use")
    assert exc.value.details == {"usages": [other_ext, route]}
    assert s.deleted == [] and ext.no_answer_target_id == box.target_id


# ------------------------------------------------------------ /settings/notify
@pytest.fixture
def fake_encrypt(monkeypatch):
    async def enc(session, value):
        return f"enc:{value}"

    monkeypatch.setattr(ns, "encrypt_secret", enc)


def test_plain_changes_nullable_vs_required():
    p = UpdateNotifySettingsPayload(smtp_host=None, smtp_port=None, smtp_tls="tls", from_email="a@b.uz")
    assert ns._plain_changes(p) == {"smtp_host": None, "from_email": "a@b.uz", "smtp_tls": "tls"}


async def test_apply_secrets_set_clear_and_skip(fake_encrypt):
    row = SimpleNamespace(smtp_password_enc="old", telegram_token_enc="old")
    diff: dict = {}
    await ns._apply_secrets(None, row, UpdateNotifySettingsPayload(smtp_password="p", telegram_token=""), diff)
    assert (row.smtp_password_enc, row.telegram_token_enc) == ("enc:p", None)
    assert diff == {"smtp_password": "p", "telegram_token": ""}  # record_audit -> "***"
    row2 = SimpleNamespace(smtp_password_enc="keep", telegram_token_enc="keep")
    diff2: dict = {}
    await ns._apply_secrets(None, row2, UpdateNotifySettingsPayload(), diff2)
    assert (row2.smtp_password_enc, row2.telegram_token_enc, diff2) == ("keep", "keep", {})


async def test_update_creates_row_with_defaults(audit, fake_encrypt):
    s = _Session()
    out = await ns.update_notify_settings(UpdateNotifySettingsPayload(smtp_host="mail", telegram_token="T"), s, USER)
    (row,) = s.added
    assert (row.tenant_id, row.smtp_host, row.smtp_port, row.smtp_tls) == ("t1", "mail", 587, "starttls")
    assert row.telegram_token_enc == "enc:T"
    assert out.has_telegram_token and not out.has_smtp_password and out.updated_at == NOW
    assert audit[0]["diff"] == {"smtp_host": "mail", "telegram_token": "T"} and s.commits == 1


async def test_update_existing_row_checks_stale_only_when_given(audit, fake_encrypt):
    row = SimpleNamespace(tenant_id="t1", smtp_host="h", smtp_port=25, smtp_tls="none", smtp_user=None,
                          smtp_password_enc=None, from_email=None, telegram_token_enc=None,
                          telegram_api_base="https://api.telegram.org", updated_at=NOW)
    s = _Session(get={"t1": row})
    await ns.update_notify_settings(UpdateNotifySettingsPayload(smtp_port=2525), s, USER)
    assert row.smtp_port == 2525 and s.added == []
    with pytest.raises(ApiError) as exc:
        await ns.update_notify_settings(
            UpdateNotifySettingsPayload(smtp_port=1, updated_at=datetime(2020, 1, 1, tzinfo=timezone.utc)), s, USER)
    assert exc.value.status_code == 409 and row.smtp_port == 2525


async def test_get_without_row_returns_defaults():
    out = await ns.get_notify_settings(_Session(), USER)
    assert (out.smtp_port, out.smtp_tls, out.telegram_api_base, out.updated_at) == (
        587, "starttls", "https://api.telegram.org", None)
    assert not out.has_smtp_password and not out.has_telegram_token


async def test_notify_test_ok_and_502(monkeypatch):
    async def cfg(session, tenant_id):
        return "CFG"

    sent: list = []

    async def send(c, channel, to):
        sent.append((c, channel, to))
        if to == "bad":
            raise ns.vm_notify.NotifyError("Telegram 400: chat not found")

    monkeypatch.setattr(ns.vm_notify, "load_config", cfg)
    monkeypatch.setattr(ns.vm_notify, "send_test", send)
    ok = await ns.test_notify(ns.NotifyTestPayload(channel="telegram", to="42"), None, USER)
    assert ok.ok is True and sent == [("CFG", "telegram", "42")]
    with pytest.raises(ApiError) as exc:
        await ns.test_notify(ns.NotifyTestPayload(channel="telegram", to="bad"), None, USER)
    assert (exc.value.status_code, exc.value.code) == (502, "notify_failed")
    assert exc.value.details == {"reason": "Telegram 400: chat not found"}
