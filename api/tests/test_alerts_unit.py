"""`app/services/alerts.py` — M2c §4: sof matn (`alert_text`), navbat qoidasi
(`initial_status`, `_is_duplicate`, `raise_alert`) va fon vazifa (`dispatch_once`).
Bazasiz — soxta sessiya (`app/db/models.py` duck-typing, boshqa testlar bilan
BIR XIL qolip)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import alerts as al
from app.services import vm_notify


def test_alert_text_toll_blocked_per_hour_uz():
    text = al.alert_text("uz", "toll_blocked", number="101", limit=60, reason="per_hour")
    assert "101" in text and "60" in text and "soatiga" in text


def test_alert_text_toll_blocked_international_ru():
    text = al.alert_text("ru", "toll_blocked", number="101", limit=1, reason="international_per_day")
    assert "101" in text and "сутки" in text


def test_alert_text_concurrent_limit_en():
    text = al.alert_text("en", "concurrent_limit", number="101", limit=1)
    assert "101" in text and "1" in text


def test_alert_text_unknown_language_falls_back_to_uz():
    assert al.alert_text("fr", "test", ) == al.alert_text("uz", "test")


def test_alert_text_toll_blocked_defaults_to_per_hour_reason_if_missing():
    text = al.alert_text("uz", "toll_blocked", number="101", limit=60)
    assert "soatiga" in text


# ------------------------------------------------------------ initial_status
def test_initial_status_disabled_event_type():
    cfg = al.AlertConfig(events={"ip_banned": False})
    assert al.initial_status(cfg, "ip_banned", duplicate=False) == "disabled"


def test_initial_status_test_kind_ignores_events_toggle():
    cfg = al.AlertConfig(events={})
    assert al.initial_status(cfg, "test", duplicate=False) == "pending"


def test_initial_status_duplicate_suppressed():
    cfg = al.AlertConfig(events={"toll_blocked": True})
    assert al.initial_status(cfg, "toll_blocked", duplicate=True) == "suppressed"


def test_initial_status_normal_pending():
    cfg = al.AlertConfig(events={"toll_blocked": True})
    assert al.initial_status(cfg, "toll_blocked", duplicate=False) == "pending"


# ------------------------------------------------------------ soxta sessiya
class _Result:
    def __init__(self, rows):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    def __init__(self, *, settings_row=None, tenant_row=None, dup_rows=None, queue=None):
        self.settings_row = settings_row
        self.tenant_row = tenant_row
        self.dup_rows = dup_rows if dup_rows is not None else []
        self.queue = queue if queue is not None else []
        self.added: list = []
        self.committed = 0
        self.flushed = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, model, _pk):
        if model.__name__ == "SystemSettings":
            return self.settings_row
        if model.__name__ == "Tenant":
            return self.tenant_row
        return None

    async def execute(self, _stmt):
        if self.queue:
            return _Result([self.queue.pop(0)])
        return _Result(self.dup_rows)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushed += 1

    async def commit(self):
        self.committed += 1


def _settings_row(**telegram):
    return SimpleNamespace(telegram={"chat_ids": ["1"], "dedup_s": 600,
                                     "events": {"ip_banned": True, "toll_blocked": True}, **telegram})


@pytest.mark.asyncio
async def test_raise_alert_creates_pending_row():
    session = _FakeSession(settings_row=_settings_row())
    row = await al.raise_alert(session, "t1", "toll_blocked", "101", "matn")
    assert row.status == "pending"
    assert session.added == [row]
    assert session.flushed == 1


@pytest.mark.asyncio
async def test_raise_alert_duplicate_suppressed():
    session = _FakeSession(settings_row=_settings_row(), dup_rows=[(1,)])
    row = await al.raise_alert(session, "t1", "toll_blocked", "101", "matn")
    assert row.status == "suppressed"


@pytest.mark.asyncio
async def test_tenant_language_defaults_to_uz_when_missing():
    session = _FakeSession()
    assert await al.tenant_language(session, "t1") == "uz"


@pytest.mark.asyncio
async def test_tenant_language_uses_tenant_row():
    session = _FakeSession(tenant_row=SimpleNamespace(language="ru"))
    assert await al.tenant_language(session, "t1") == "ru"


# ------------------------------------------------------------ dispatch_once
def _alert_row(**kw):
    base = dict(tenant_id="t1", kind="toll_blocked", body="matn", status="pending", error=None, sent_at=None)
    base.update(kw)
    return SimpleNamespace(**base)


_NOTIFY_CFG_WITH_TOKEN = vm_notify.NotifyConfig(
    smtp_host=None, smtp_port=587, smtp_tls="starttls", smtp_user=None, smtp_password=None,
    from_email=None, telegram_token="123:ABC", telegram_api_base="https://api.telegram.org",
)
_NOTIFY_CFG_NO_TOKEN = vm_notify.NotifyConfig(
    smtp_host=None, smtp_port=587, smtp_tls="starttls", smtp_user=None, smtp_password=None,
    from_email=None, telegram_token=None, telegram_api_base="https://api.telegram.org",
)


@pytest.mark.asyncio
async def test_dispatch_once_sends_to_all_chats_and_marks_sent(monkeypatch):
    sent_to = []

    async def fake_send(cfg, chat_id, caption, audio, *, transport=None):
        sent_to.append(chat_id)

    monkeypatch.setattr(vm_notify, "send_telegram", fake_send)

    async def _async_cfg(*_a):
        return al.AlertConfig(chat_ids=("1", "2"))
    async def _async_notify(*_a):
        return _NOTIFY_CFG_WITH_TOKEN
    monkeypatch.setattr(al, "load_alert_config", _async_cfg)
    monkeypatch.setattr(vm_notify, "load_config", _async_notify)

    row = _alert_row()
    queue = [row, None]

    def factory():
        return _FakeSession(queue=queue)

    await al.dispatch_once(factory)
    assert sent_to == ["1", "2"]
    assert row.status == "sent"
    assert row.sent_at is not None


@pytest.mark.asyncio
async def test_dispatch_once_no_token_marks_failed(monkeypatch):
    async def _async_cfg(*_a):
        return al.AlertConfig(chat_ids=("1",))
    async def _async_notify(*_a):
        return _NOTIFY_CFG_NO_TOKEN
    monkeypatch.setattr(al, "load_alert_config", _async_cfg)
    monkeypatch.setattr(vm_notify, "load_config", _async_notify)

    row = _alert_row()
    queue = [row, None]
    await al.dispatch_once(lambda: _FakeSession(queue=queue))
    assert row.status == "failed"
    assert row.error == "no_token"


@pytest.mark.asyncio
async def test_dispatch_once_no_chat_marks_failed(monkeypatch):
    async def _async_cfg(*_a):
        return al.AlertConfig(chat_ids=())
    async def _async_notify(*_a):
        return _NOTIFY_CFG_WITH_TOKEN
    monkeypatch.setattr(al, "load_alert_config", _async_cfg)
    monkeypatch.setattr(vm_notify, "load_config", _async_notify)

    row = _alert_row()
    queue = [row, None]
    await al.dispatch_once(lambda: _FakeSession(queue=queue))
    assert row.status == "failed"
    assert row.error == "no_chat"


@pytest.mark.asyncio
async def test_dispatch_once_telegram_error_marks_failed_with_reason(monkeypatch):
    async def fake_send(cfg, chat_id, caption, audio, *, transport=None):
        raise vm_notify.NotifyError("Telegram 400: bad chat")

    async def _async_cfg(*_a):
        return al.AlertConfig(chat_ids=("1",))
    async def _async_notify(*_a):
        return _NOTIFY_CFG_WITH_TOKEN
    monkeypatch.setattr(al, "load_alert_config", _async_cfg)
    monkeypatch.setattr(vm_notify, "load_config", _async_notify)
    monkeypatch.setattr(vm_notify, "send_telegram", fake_send)

    row = _alert_row()
    queue = [row, None]
    await al.dispatch_once(lambda: _FakeSession(queue=queue))
    assert row.status == "failed"
    assert "bad chat" in row.error


@pytest.mark.asyncio
async def test_dispatch_once_stops_when_queue_empty():
    session = _FakeSession(queue=[None])
    await al.dispatch_once(lambda: session)
    assert session.committed == 0


@pytest.mark.asyncio
async def test_run_forever_cancels_cleanly(monkeypatch):
    import asyncio

    calls = {"n": 0}

    async def fake_dispatch_once(_factory):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise asyncio.CancelledError()

    monkeypatch.setattr(al, "dispatch_once", fake_dispatch_once)
    with pytest.raises(asyncio.CancelledError):
        await al.run_forever(lambda: None, 0.001)
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_dispatch_once_network_error_marks_failed_without_token(monkeypatch):
    """Telegram'ga ulanib bo'lmasa (httpx xatosi — `NotifyError` EMAS) qator `pending`da
    qolib ketmasin: aks holda u har aylanishda birinchi bo'lib olinib, keyingi barcha
    ogohlantirishlarni to'sib qo'yadi. Xato matnida bot token bo'lmasin."""
    import httpx

    async def fake_send(cfg, chat_id, caption, audio, *, transport=None):
        raise httpx.ConnectError(f"https://api.telegram.org/bot{cfg.telegram_token}/sendMessage ulanmadi")

    async def _async_cfg(*_a):
        return al.AlertConfig(chat_ids=("1",))
    async def _async_notify(*_a):
        return _NOTIFY_CFG_WITH_TOKEN
    monkeypatch.setattr(al, "load_alert_config", _async_cfg)
    monkeypatch.setattr(vm_notify, "load_config", _async_notify)
    monkeypatch.setattr(vm_notify, "send_telegram", fake_send)

    row = _alert_row()
    queue = [row, None]
    await al.dispatch_once(lambda: _FakeSession(queue=queue))
    assert row.status == "failed"
    assert "ConnectError" in row.error
    assert "123:ABC" not in row.error
