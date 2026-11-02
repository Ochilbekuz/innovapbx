"""`GET /live` / `POST /live/spy` marshrut funksiyalari — DB/AMI'siz (soxta
sessiya + monkeypatch), `test_voicemail_routes_unit.py` namunasi bo'yicha.
To'liq orkestratsiya (`build_live_status`) jonli testda (`scripts/m2b-proof.sh`,
ssenariy 5/6, Postgres+Asterisk kerak)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import live as lv
from app.core.errors import ApiError
from app.schemas import LiveSpyPayload

NOW = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)
USER = SimpleNamespace(id="u1", tenant_id="t1", extension_id="e1", tenant=SimpleNamespace(code="t1", timezone="UTC"))


class _Session:
    def __init__(self, *, get=None) -> None:
        self.commits = 0
        self._get = get

    async def get(self, model, key):
        return self._get

    async def commit(self) -> None:
        self.commits += 1


@pytest.fixture
def audit(monkeypatch):
    rows: list = []

    async def fake_audit(session, **kw):
        rows.append(kw)

    monkeypatch.setattr(lv, "record_audit", fake_audit)
    return rows


# ------------------------------------------------------------------- GET /live
@pytest.mark.asyncio
async def test_get_live_passes_tenant_code_and_timezone_and_wraps_result(monkeypatch):
    seen = {}
    canned = {"at": NOW, "calls": [], "queues": [], "extensions": [], "asterisk": "up"}

    async def fake_build(session, ami, *, tenant_id, tenant_code, tenant_tz):
        seen.update(tenant_id=tenant_id, tenant_code=tenant_code, tenant_tz=tenant_tz)
        return canned

    monkeypatch.setattr(lv, "build_live_status", fake_build)
    out = await lv.get_live(session=_Session(), user=USER, ami=object())
    assert seen == {"tenant_id": "t1", "tenant_code": "t1", "tenant_tz": "UTC"}
    assert out.asterisk == "up"


# ------------------------------------------------------------------- POST /live/spy
@pytest.mark.asyncio
async def test_spy_without_extension_raises_409():
    user = SimpleNamespace(id="u1", tenant_id="t1", extension_id=None, tenant=SimpleNamespace(code="t1"))
    with pytest.raises(ApiError) as exc:
        await lv.spy(LiveSpyPayload(channel="X"), session=_Session(), user=user, ami=object())
    assert exc.value.status_code == 409
    assert exc.value.code == "no_extension"


@pytest.mark.asyncio
async def test_spy_channel_not_found_raises_404(monkeypatch):
    async def no_channels(ami):
        return []

    monkeypatch.setattr(lv, "active_channels", no_channels)
    session = _Session(get=SimpleNamespace(id="e1", number="201"))
    with pytest.raises(ApiError) as exc:
        await lv.spy(LiveSpyPayload(channel="PJSIP/t1-999-1"), session=session, user=USER, ami=object())
    assert exc.value.status_code == 404
    assert exc.value.code == "not_found"
    assert exc.value.field == "channel"


@pytest.mark.asyncio
async def test_spy_success_originates_to_own_extension_and_audits(audit, monkeypatch):
    channels = [{"Channel": "PJSIP/t1-999-00000001"}]

    async def fake_channels(ami):
        return channels

    originated: dict = {}

    async def fake_originate(ami, *, tenant_code, number, target_channel, mode):
        originated.update(tenant_code=tenant_code, number=number, target_channel=target_channel, mode=mode)

    monkeypatch.setattr(lv, "active_channels", fake_channels)
    monkeypatch.setattr(lv, "_originate_spy", fake_originate)
    session = _Session(get=SimpleNamespace(id="e1", number="201"))
    payload = LiveSpyPayload(channel="PJSIP/t1-999-00000001", mode="whisper")
    out = await lv.spy(payload, session=session, user=USER, ami=object())
    # ChanSpy FAQAT so'rovchining O'Z ichki raqamiga (201) Originate qilinadi — boshqa birov EMAS.
    assert originated == {"tenant_code": "t1", "number": "201", "target_channel": "PJSIP/t1-999-00000001",
                           "mode": "whisper"}
    assert out.status == "calling"
    assert session.commits == 1
    assert audit[0]["action"] == "live.spy"
    assert audit[0]["diff"] == {"call_id": None, "channel": "PJSIP/t1-999-00000001", "mode": "whisper"}


@pytest.mark.asyncio
async def test_originate_spy_raises_ami_error_on_exception():
    class _FailAmi:
        async def ensure_connected(self):
            raise ConnectionError("yo'q")

    with pytest.raises(ApiError) as exc:
        await lv._originate_spy(_FailAmi(), tenant_code="t1", number="201", target_channel="X", mode="listen")
    assert exc.value.status_code == 502
    assert exc.value.code == "ami_error"


@pytest.mark.asyncio
async def test_originate_spy_raises_when_response_not_success():
    class _RejectAmi:
        async def ensure_connected(self):
            return None

        async def action(self, action, **fields):
            return {"Response": "Error", "Message": "rad etildi"}

    with pytest.raises(ApiError) as exc:
        await lv._originate_spy(_RejectAmi(), tenant_code="t1", number="201", target_channel="X", mode="listen")
    assert exc.value.status_code == 502
    assert exc.value.code == "ami_error"
