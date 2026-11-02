"""`app/services/vm_notify.py` — sof qismlar (xat/izoh qurish, kanal
tanlash) va yuborish adapterlari (soxta SMTP/HTTP bilan)."""
from __future__ import annotations

import json

import httpx
import pytest

from app.services import vm_notify as vn
from app.services.vm_notify import NotifyConfig, PendingMessage, build_email, channels_for, telegram_caption

_CFG = NotifyConfig(smtp_host="mail", smtp_port=1025, smtp_tls="none", smtp_user=None, smtp_password=None,
                    from_email="pbx@innova.uz", telegram_token="123:ABC", telegram_api_base="http://tg:8080")


def _msg(tmp_path, **kw) -> PendingMessage:
    wav = tmp_path / "msg0000.wav"
    wav.write_bytes(b"RIFFdata")
    defaults = dict(tenant_id="t", box_id="b", mailbox="201", msg_id="m-1", callerid='"Ali" <998901112233>',
                    duration_s=7, received_at="2026-10-28T10:00:00Z", wav=wav, email="a@b.uz",
                    email_notify=True, telegram_notify=True, telegram_chat_id="42", attach_audio=True)
    defaults.update(kw)
    return PendingMessage(**defaults)


def test_caption_has_caller_box_and_duration(tmp_path):
    text = telegram_caption(_msg(tmp_path))
    assert "201" in text
    assert '"Ali" <998901112233>' in text
    assert "7 s" in text
    assert "2026-10-28T10:00:00Z" in text


def test_email_with_wav_attachment(tmp_path):
    em = build_email(_CFG, _msg(tmp_path))
    assert em["To"] == "a@b.uz"
    assert em["From"] == "pbx@innova.uz"
    assert "201" in em["Subject"]
    atts = list(em.iter_attachments())
    assert len(atts) == 1
    assert atts[0].get_content_type() == "audio/wav"
    assert atts[0].get_filename() == "201-msg0000.wav"
    assert atts[0].get_content() == b"RIFFdata"


def test_email_without_attachment_when_disabled(tmp_path):
    em = build_email(_CFG, _msg(tmp_path, attach_audio=False))
    assert list(em.iter_attachments()) == []
    assert "201" in em.get_body().get_content()


def test_email_override_recipient(tmp_path):
    em = build_email(_CFG, _msg(tmp_path), to="x@y.uz")
    assert em["To"] == "x@y.uz"


@pytest.mark.parametrize("kw,cfg_kw,expected", [
    ({}, {}, ["email", "telegram"]),
    ({"email_notify": False}, {}, ["telegram"]),
    ({"email": None}, {}, ["telegram"]),
    ({"telegram_notify": False}, {}, ["email"]),
    ({"telegram_chat_id": None}, {}, ["email"]),
    ({}, {"smtp_host": None}, ["telegram"]),
    ({}, {"from_email": None}, ["telegram"]),
    ({}, {"telegram_token": None}, ["email"]),
])
def test_channels_require_both_box_and_settings(tmp_path, kw, cfg_kw, expected):
    cfg = NotifyConfig(**{**_CFG.__dict__, **cfg_kw})
    assert channels_for(cfg, _msg(tmp_path, **kw)) == expected


# ------------------------------------------------------------ Telegram
def _tg_transport(calls: list, status: int = 200, body: dict | None = None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, json=body if body is not None else {"ok": True})
    return httpx.MockTransport(handler)


async def test_telegram_send_audio_multipart(tmp_path):
    calls: list[httpx.Request] = []
    await vn.send_telegram(_CFG, "42", telegram_caption(_msg(tmp_path)), _msg(tmp_path).wav,
                           transport=_tg_transport(calls))
    assert len(calls) == 1
    req = calls[0]
    assert str(req.url) == "http://tg:8080/bot123:ABC/sendAudio"
    body = req.content
    assert b'name="chat_id"' in body and b"42" in body
    assert b'name="audio"; filename="msg0000.wav"' in body
    assert b"RIFFdata" in body


async def test_telegram_send_message_without_audio(tmp_path):
    calls: list[httpx.Request] = []
    await vn.send_telegram(_CFG, "42", "salom", None, transport=_tg_transport(calls))
    assert str(calls[0].url) == "http://tg:8080/bot123:ABC/sendMessage"
    assert json.loads(calls[0].content) == {"chat_id": "42", "text": "salom"}


async def test_telegram_error_raises_with_description(tmp_path):
    calls: list = []
    with pytest.raises(vn.NotifyError, match="chat not found"):
        await vn.send_telegram(_CFG, "42", "x", None,
                               transport=_tg_transport(calls, 400, {"ok": False, "description": "chat not found"}))


async def test_telegram_without_token_raises():
    cfg = NotifyConfig(**{**_CFG.__dict__, "telegram_token": None})
    with pytest.raises(vn.NotifyError, match="token"):
        await vn.send_telegram(cfg, "42", "x", None)


# ------------------------------------------------------------ SMTP
class _FakeSmtp:
    instances: list[_FakeSmtp] = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.timeout = host, port, timeout
        self.ssl = context is not None
        self.log: list = []
        _FakeSmtp.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        self.log.append("starttls")

    def login(self, user, password):
        self.log.append(("login", user, password))

    def send_message(self, msg):
        self.log.append(("send", msg["To"]))


@pytest.fixture
def fake_smtp(monkeypatch):
    _FakeSmtp.instances = []
    monkeypatch.setattr(vn.smtplib, "SMTP", _FakeSmtp)
    monkeypatch.setattr(vn.smtplib, "SMTP_SSL", _FakeSmtp)
    return _FakeSmtp


@pytest.mark.parametrize("tls,expected_log_head,ssl", [
    ("none", [], False),
    ("starttls", ["starttls"], False),
    ("tls", [], True),
])
def test_smtp_modes(tmp_path, fake_smtp, tls, expected_log_head, ssl):
    cfg = NotifyConfig(**{**_CFG.__dict__, "smtp_tls": tls})
    vn.send_email_sync(cfg, build_email(cfg, _msg(tmp_path)))
    smtp = fake_smtp.instances[0]
    assert (smtp.host, smtp.port, smtp.ssl) == ("mail", 1025, ssl)
    assert smtp.log == expected_log_head + [("send", "a@b.uz")]


def test_smtp_login_when_user_given(tmp_path, fake_smtp):
    cfg = NotifyConfig(**{**_CFG.__dict__, "smtp_user": "u", "smtp_password": "p"})
    vn.send_email_sync(cfg, build_email(cfg, _msg(tmp_path)))
    assert ("login", "u", "p") in fake_smtp.instances[0].log


def test_smtp_without_host_raises(tmp_path):
    cfg = NotifyConfig(**{**_CFG.__dict__, "smtp_host": None})
    with pytest.raises(vn.NotifyError, match="SMTP"):
        vn.send_email_sync(cfg, build_email(_CFG, _msg(tmp_path)))


# ------------------------------------------------------------ yuborish dispetcheri
async def test_deliver_dispatches_and_wraps_errors(tmp_path, monkeypatch):
    sent: list = []

    async def fake_tg(cfg, chat_id, text, audio, transport=None):
        sent.append(("telegram", chat_id, audio is not None))

    def fake_email(cfg, message):
        sent.append(("email", message["To"]))

    monkeypatch.setattr(vn, "send_telegram", fake_tg)
    monkeypatch.setattr(vn, "send_email_sync", fake_email)
    await vn.deliver(_CFG, _msg(tmp_path), "telegram")
    await vn.deliver(_CFG, _msg(tmp_path, attach_audio=False), "telegram")
    await vn.deliver(_CFG, _msg(tmp_path), "email")
    assert sent == [("telegram", "42", True), ("telegram", "42", False), ("email", "a@b.uz")]


async def test_deliver_wraps_unexpected_errors(tmp_path, monkeypatch):
    def boom(cfg, message):
        raise OSError("connection refused")

    monkeypatch.setattr(vn, "send_email_sync", boom)
    with pytest.raises(vn.NotifyError, match="connection refused"):
        await vn.deliver(_CFG, _msg(tmp_path), "email")


# ------------------------------------------------------------ DB qatlami (soxta sessiya)
class _Result:
    def __init__(self, first=None, rows=None):
        self._first, self._rows = first, rows or []

    def first(self):
        return self._first

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, results=(), get=None):
        self.results = list(results)
        self.executed: list = []
        self.commits = 0
        self._get = get

    async def execute(self, stmt, params=None):
        self.executed.append(params)
        return self.results.pop(0) if self.results else _Result()

    async def commit(self):
        self.commits += 1

    async def get(self, model, key):
        return self._get

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


async def test_claim_returns_id_and_commits_immediately(tmp_path):
    s = _FakeSession([_Result(first=(7,))])
    assert await vn._claim(s, _msg(tmp_path), "email") == 7
    assert s.commits == 1
    assert s.executed[0]["channel"] == "email" and s.executed[0]["msg_id"] == "m-1"
    assert s.executed[0]["max_attempts"] == vn.settings.vm_notify_max_attempts


async def test_claim_already_taken_returns_none(tmp_path):
    s = _FakeSession([_Result(first=None)])
    assert await vn._claim(s, _msg(tmp_path), "telegram") is None


async def test_notify_message_marks_sent_failed_and_skips_claimed(tmp_path, monkeypatch):
    claims = {"email": 1, "telegram": None}

    async def fake_claim(session, msg, channel):
        return claims[channel]

    async def fake_deliver(cfg, msg, channel):
        raise vn.NotifyError("smtp down")

    monkeypatch.setattr(vn, "_claim", fake_claim)
    monkeypatch.setattr(vn, "deliver", fake_deliver)
    s = _FakeSession()
    await vn._notify_message(s, _CFG, _msg(tmp_path))
    assert s.executed == [{"status": "failed", "error": "smtp down", "id": 1}]  # telegram egallanmagan -> yuborilmaydi
    assert s.commits == 1

    async def ok_deliver(cfg, msg, channel):
        return None

    monkeypatch.setattr(vn, "deliver", ok_deliver)
    s = _FakeSession()
    await vn._notify_message(s, _CFG, _msg(tmp_path))
    assert s.executed == [{"status": "sent", "error": None, "id": 1}]


async def test_scan_once_loads_config_once_per_tenant(tmp_path, monkeypatch):
    class Box:
        def __init__(self, tenant):
            self.tenant_id = tenant

    rows = [(Box("t-a"), "a"), (Box("t-a"), "a"), (Box("t-b"), "b")]
    loaded: list = []
    notified: list = []

    async def fake_load(session, tenant_id):
        loaded.append(tenant_id)
        return tenant_id

    async def fake_notify(session, cfg, msg):
        notified.append((cfg, msg))

    monkeypatch.setattr(vn, "load_config", fake_load)
    monkeypatch.setattr(vn, "_inbox_messages", lambda box, code: [f"{code}-msg"])
    monkeypatch.setattr(vn, "_notify_message", fake_notify)
    await vn.scan_once(lambda: _FakeSession([_Result(rows=rows)]))
    assert loaded == ["t-a", "t-b"]
    assert notified == [("t-a", "a-msg"), ("t-a", "a-msg"), ("t-b", "b-msg")]


async def test_run_forever_survives_errors_and_stops_on_cancel(monkeypatch):
    import asyncio
    calls: list = []

    async def fake_scan(factory):
        calls.append(len(calls))
        if len(calls) == 1:
            raise RuntimeError("db down")
        raise asyncio.CancelledError

    sleeps: list = []

    async def fake_sleep(s):
        sleeps.append(s)

    monkeypatch.setattr(vn, "scan_once", fake_scan)
    monkeypatch.setattr(vn.asyncio, "sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        await vn.run_forever(object(), 2.5)
    assert calls == [0, 1] and sleeps == [2.5]


async def test_run_forever_skips_scan_during_maintenance(monkeypatch):
    import asyncio

    from app.services import maintenance

    async def fail_scan(_factory):
        raise AssertionError("texnik xizmat paytida scan_once chaqirilmasin")

    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)
        raise asyncio.CancelledError

    monkeypatch.setattr(vn, "scan_once", fail_scan)
    monkeypatch.setattr(vn.asyncio, "sleep", fake_sleep)
    maintenance.state.enabled = True
    try:
        with pytest.raises(asyncio.CancelledError):
            await vn.run_forever(object(), 2.5)
    finally:
        maintenance.state.enabled = False
    assert sleeps == [2.5]


async def test_load_config_defaults_without_row():
    cfg = await vn.load_config(_FakeSession(get=None), "t")
    assert cfg == NotifyConfig(None, 587, "starttls", None, None, None, None, "https://api.telegram.org")


async def test_load_config_decrypts_only_present_secrets(monkeypatch):
    from types import SimpleNamespace

    async def fake_decrypt(session, enc):
        return f"plain:{enc}"

    monkeypatch.setattr(vn, "decrypt_secret", fake_decrypt)
    row = SimpleNamespace(smtp_host="h", smtp_port=25, smtp_tls="none", smtp_user="u", smtp_password_enc="E1",
                          from_email="f@x.uz", telegram_token_enc=None, telegram_api_base="http://tg")
    cfg = await vn.load_config(_FakeSession(get=row), "t")
    assert (cfg.smtp_password, cfg.telegram_token, cfg.smtp_port, cfg.telegram_api_base) == ("plain:E1", None, 25, "http://tg")


def test_inbox_messages_only_inbox_with_msg_id(tmp_path, monkeypatch):
    from types import SimpleNamespace
    box_dir = tmp_path / "201"
    monkeypatch.setattr(vn.vm, "box_dir", lambda code, mailbox: box_dir)
    monkeypatch.setattr(vn.vm, "list_messages", lambda folder: [
        {"id": "INBOX/msg0000", "folder": "inbox", "msg_id": "a", "callerid": "c", "duration_s": 3, "received_at": "r"},
        {"id": "INBOX/msg0001", "folder": "inbox", "msg_id": "", "callerid": "c", "duration_s": 3, "received_at": "r"},
        {"id": "Old/msg0000", "folder": "old", "msg_id": "b", "callerid": "c", "duration_s": 3, "received_at": "r"},
    ])
    box = SimpleNamespace(tenant_id="t", id="b1", mailbox="201", email="e@x.uz", email_notify=True,
                          telegram_notify=False, telegram_chat_id=None, attach_audio=True)
    msgs = vn._inbox_messages(box, "t1")
    assert [(m.msg_id, m.wav, m.box_id, m.email) for m in msgs] == [("a", box_dir / "INBOX/msg0000.wav", "b1", "e@x.uz")]


async def test_send_test_probe_targets_given_recipient_without_audio(monkeypatch):
    got: list = []

    async def fake_deliver(cfg, msg, channel):
        got.append((channel, msg.email, msg.telegram_chat_id, msg.attach_audio, msg.wav, msg.email_notify,
                    msg.telegram_notify, msg.callerid))

    monkeypatch.setattr(vn, "deliver", fake_deliver)
    await vn.send_test(_CFG, "telegram", "42")
    assert got == [("telegram", "42", "42", False, None, True, True, "Innova PBX")]
