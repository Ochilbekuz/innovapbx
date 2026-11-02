"""`app/api/v1/settings_alerts.py` — M2c §4: `/settings/alerts` GET/PATCH,
`/settings/alerts/test` POST. DB/Telegram'siz: soxta sessiya,
`vm_notify.load_config`/`send_telegram` monkeypatch."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import settings_alerts as sa
from app.core.errors import ApiError
from app.schemas_security import UpdateAlertSettingsPayload
from app.services import vm_notify

USER = SimpleNamespace(id="u1", tenant_id="t1")
OLD = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)

_NOTIFY_WITH_TOKEN = vm_notify.NotifyConfig(
    smtp_host=None, smtp_port=587, smtp_tls="starttls", smtp_user=None, smtp_password=None,
    from_email=None, telegram_token="123:ABC", telegram_api_base="https://api.telegram.org",
)
_NOTIFY_NO_TOKEN = vm_notify.NotifyConfig(
    smtp_host=None, smtp_port=587, smtp_tls="starttls", smtp_user=None, smtp_password=None,
    from_email=None, telegram_token=None, telegram_api_base="https://api.telegram.org",
)


class _Session:
    def __init__(self, *, settings_row=None, tenant_row=None):
        self.settings_row = settings_row
        self.tenant_row = tenant_row
        self.added: list = []
        self.flushes = self.commits = self.refreshed = 0

    async def get(self, model, _pk):
        if model.__name__ == "Tenant":
            return self.tenant_row
        return self.settings_row

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1

    async def refresh(self, _obj):
        self.refreshed += 1


def _settings_row(**kw):
    base = dict(tenant_id="t1", telegram={"chat_ids": ["1"], "dedup_s": 600,
                                          "events": {"ip_banned": True, "toll_blocked": True}},
                updated_at=OLD)
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def env(monkeypatch):
    state: dict = {"audit": []}

    async def fake_audit(session, **kw):
        state["audit"].append(kw)

    monkeypatch.setattr(sa, "record_audit", fake_audit)
    return state


@pytest.mark.asyncio
async def test_get_alert_settings_combines_telegram_cfg_and_token(monkeypatch):
    async def fake_load_config(_session, _tenant_id):
        return _NOTIFY_WITH_TOKEN

    monkeypatch.setattr(vm_notify, "load_config", fake_load_config)
    session = _Session(settings_row=_settings_row())
    out = await sa.get_alert_settings(session=session, user=USER)
    assert out.chat_ids == ["1"] and out.has_telegram_token is True


@pytest.mark.asyncio
async def test_get_alert_settings_no_token(monkeypatch):
    async def fake_load_config(_session, _tenant_id):
        return _NOTIFY_NO_TOKEN

    monkeypatch.setattr(vm_notify, "load_config", fake_load_config)
    session = _Session(settings_row=_settings_row())
    out = await sa.get_alert_settings(session=session, user=USER)
    assert out.has_telegram_token is False


@pytest.mark.asyncio
async def test_get_alert_settings_404_when_missing(monkeypatch):
    session = _Session(settings_row=None)
    with pytest.raises(ApiError) as e:
        await sa.get_alert_settings(session=session, user=USER)
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_patch_events_partial_merge_keeps_other_keys(env, monkeypatch):
    async def fake_load_config(_s, _t):
        return _NOTIFY_WITH_TOKEN

    monkeypatch.setattr(vm_notify, "load_config", fake_load_config)
    session = _Session(settings_row=_settings_row())
    payload = UpdateAlertSettingsPayload(events={"ip_banned": False}, updated_at=OLD)
    out = await sa.update_alert_settings(payload, session=session, user=USER)
    assert out.events["ip_banned"] is False
    assert out.events["toll_blocked"] is True  # saqlanib qoldi
    assert session.commits == 1 and session.refreshed == 1


@pytest.mark.asyncio
async def test_patch_rejects_unknown_event_key(env):
    session = _Session(settings_row=_settings_row())
    payload = UpdateAlertSettingsPayload(events={"made_up": True}, updated_at=OLD)
    with pytest.raises(ApiError) as e:
        await sa.update_alert_settings(payload, session=session, user=USER)
    assert (e.value.status_code, e.value.field) == (422, "events")


@pytest.mark.asyncio
async def test_patch_rejects_bad_chat_ids(env):
    session = _Session(settings_row=_settings_row())
    payload = UpdateAlertSettingsPayload(chat_ids=["abc"], updated_at=OLD)
    with pytest.raises(ApiError) as e:
        await sa.update_alert_settings(payload, session=session, user=USER)
    assert e.value.field == "chat_ids"


@pytest.mark.asyncio
async def test_patch_rejects_bad_dedup_s(env):
    session = _Session(settings_row=_settings_row())
    payload = UpdateAlertSettingsPayload(dedup_s=86_401, updated_at=OLD)
    with pytest.raises(ApiError) as e:
        await sa.update_alert_settings(payload, session=session, user=USER)
    assert e.value.field == "dedup_s"


@pytest.mark.asyncio
async def test_patch_stale_raises_409(env):
    session = _Session(settings_row=_settings_row(updated_at=NOW))
    payload = UpdateAlertSettingsPayload(dedup_s=60, updated_at=OLD)
    with pytest.raises(ApiError) as e:
        await sa.update_alert_settings(payload, session=session, user=USER)
    assert e.value.status_code == 409


@pytest.mark.asyncio
async def test_test_alert_no_token_raises_422(monkeypatch):
    async def fake_load_config(_s, _t):
        return _NOTIFY_NO_TOKEN

    monkeypatch.setattr(vm_notify, "load_config", fake_load_config)
    session = _Session(settings_row=_settings_row())
    with pytest.raises(ApiError) as e:
        await sa.test_alert_settings(session=session, user=USER)
    assert (e.value.status_code, e.value.code) == (422, "no_token")
    assert session.added == []


@pytest.mark.asyncio
async def test_test_alert_no_chat_raises_422(monkeypatch):
    async def fake_load_config(_s, _t):
        return _NOTIFY_WITH_TOKEN

    monkeypatch.setattr(vm_notify, "load_config", fake_load_config)
    session = _Session(settings_row=_settings_row(telegram={"chat_ids": [], "dedup_s": 600, "events": {}}))
    with pytest.raises(ApiError) as e:
        await sa.test_alert_settings(session=session, user=USER)
    assert e.value.code == "no_chat"


@pytest.mark.asyncio
async def test_test_alert_success_writes_sent_alert_log(monkeypatch):
    async def fake_load_config(_s, _t):
        return _NOTIFY_WITH_TOKEN

    async def fake_send(cfg, chat_id, caption, audio, *, transport=None):
        return None

    monkeypatch.setattr(vm_notify, "load_config", fake_load_config)
    monkeypatch.setattr(vm_notify, "send_telegram", fake_send)
    session = _Session(settings_row=_settings_row())
    out = await sa.test_alert_settings(session=session, user=USER)
    assert out.sent == 1
    assert session.added[0].status == "sent" and session.added[0].kind == "test"
    assert session.commits == 1


@pytest.mark.asyncio
async def test_test_alert_partial_failure_writes_failed_log_then_raises_502(monkeypatch):
    async def fake_load_config(_s, _t):
        return _NOTIFY_WITH_TOKEN

    async def fake_send(cfg, chat_id, caption, audio, *, transport=None):
        raise vm_notify.NotifyError("Telegram 400")

    monkeypatch.setattr(vm_notify, "load_config", fake_load_config)
    monkeypatch.setattr(vm_notify, "send_telegram", fake_send)
    session = _Session(settings_row=_settings_row())
    with pytest.raises(ApiError) as e:
        await sa.test_alert_settings(session=session, user=USER)
    assert e.value.status_code == 502
    assert session.added[0].status == "failed"
    assert session.commits == 1  # alert_log yozilgan — xatodan OLDIN
