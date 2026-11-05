"""Bitrix24 OAuth (bitrix-oauth-shartnoma.md) birlik testlari — broker mijozi (`bitrix_broker.py`),
umumlashtirilgan mijoz (`bitrix24.make_client`/`BitrixClient` OAuth rejimi), ulash oqimi
(`bitrix_oauth_flow.py`: `connect`/`poll`/`run_setup`/`disconnect`/`license_info`) va public hook
autentifikatsiyasi (`public_crm.hook_auth_ok`). Faqat `httpx.MockTransport` — real tarmoq YO'Q."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.api import public_crm
from app.core.config import settings
from app.services import bitrix_oauth_flow as flow
from app.services import crm_settings
from app.services.integrations import bitrix24, bitrix_broker, crm, ssrf
from app.services.integrations.crm import CrmCallError
from tests.test_m3b_crm_unit import NOW, CrmSession, FakeCrm, NoWait, _sub

ULANISH_ID = "ul-1"
ULANISH_SIR = "sir-1"
ENDPOINT = "http://b24.example.com/rest/"


@pytest.fixture(autouse=True)
def _no_leftover_cache():
    bitrix_broker.reset_token_cache()
    flow.reset_license_cache()
    yield
    bitrix_broker.reset_token_cache()
    flow.reset_license_cache()


@pytest.fixture
def plain_crypto(monkeypatch):
    """`crm_settings` ICHIDA ishlatiladigan nom bo'yicha ulanadigan sirlash — PLYUS
    `bitrix_oauth_flow`ning o'z nom-fazosiga TO'G'RIDAN-TO'G'RI import qilingan `encrypt_secret`
    (shu sabab `crm_settings.encrypt_secret`ni patch qilish yetarli EMAS)."""
    async def decrypt(session, value):
        return value

    async def encrypt(session, value):
        return value

    monkeypatch.setattr(crm_settings, "decrypt_secret", decrypt)
    monkeypatch.setattr(crm_settings, "encrypt_secret", encrypt)
    monkeypatch.setattr(flow, "encrypt_secret", encrypt)


def _broker_transport(responses=None, fail=()):
    return httpx.MockTransport(FakeCrm(responses=responses, fail=fail))


@pytest.fixture
def oauth_provider(monkeypatch):
    """`bitrix_oauth_flow.run_setup`/`disconnect` haqiqiy Bitrix REST so'rovlarini
    MODUL DARAJASIDAGI `bitrix24.PROVIDER` orqali yuboradi (sukut holatda haqiqiy
    tarmoq, `transport=None`) — shu sabab test shu yerda `bitrix24.PROVIDER`ni
    berilgan soxta transport bilan ALMASHTIRADI (`test_m3b_crm_unit.py` bilan BIR XIL qolip)."""
    def _patch(handler):
        monkeypatch.setattr(bitrix24, "PROVIDER", bitrix24.Bitrix24Provider(
            url_check=lambda url: None, transport=httpx.MockTransport(handler)))
    return _patch


def _token_body(**kw):
    body = {"access_token": "tok-1", "client_endpoint": ENDPOINT,
            "expires_at": (NOW + timedelta(hours=1)).isoformat(), "member_id": "m1", "domain": "a.bitrix24.ru"}
    body.update(kw)
    return body


def _oauth_sub(**config_kw):
    secrets = {"ulanish_id": ULANISH_ID, "ulanish_sir": ULANISH_SIR}
    config = {**crm_settings.default_config("bitrix24"), "auth_mode": "oauth", "domain": "a.bitrix24.ru",
              **config_kw}
    return _sub(config=config, secret_enc=crm.dump_secrets(secrets))


# ============================================================== A. BitrixClient / make_client
class TestMakeClient:
    def test_webhook_mode_calls_configured_url(self):
        fake = FakeCrm(responses={"/user.get.json": (200, {"result": [], "next": None})})
        settings_ = bitrix24.BitrixSettings(webhook_url="http://10.0.0.7/rest/1/abc/", create_lead=True,
                                            popup_max_delay_s=20, default_user_id=None)
        client = bitrix24.make_client("s1", settings_, limiter=NoWait(), transport=httpx.MockTransport(fake),
                                      url_check=lambda url: None)
        import asyncio
        asyncio.run(client.users())
        assert fake.requests[0][0].endswith("/user.get.json")

    def test_webhook_mode_ssrf_forbidden_raises_permanent(self):
        settings_ = bitrix24.BitrixSettings(webhook_url="http://169.254.169.254/rest/1/abc/", create_lead=True,
                                            popup_max_delay_s=20, default_user_id=None)

        def deny(url):
            raise ssrf.UrlForbidden("private_ip")

        with pytest.raises(CrmCallError) as exc:
            bitrix24.make_client("s1", settings_, limiter=NoWait(), url_check=deny)
        assert exc.value.result.permanent and "url_forbidden" in exc.value.result.error

    def test_oauth_mode_injects_auth_and_dynamic_endpoint(self):
        fake = FakeCrm(responses={"/token": (200, _token_body()), "/app.info.json": (200, {"result": {"ID": "9"}})})
        settings_ = bitrix24.BitrixSettings(webhook_url="", create_lead=True, popup_max_delay_s=20,
                                            default_user_id=None, auth_mode="oauth", ulanish_id=ULANISH_ID,
                                            ulanish_sir=ULANISH_SIR)
        client = bitrix24.make_client("s1", settings_, limiter=NoWait(), transport=httpx.MockTransport(fake),
                                      url_check=lambda url: None)
        import asyncio
        result = asyncio.run(client.call("app.info", {}))
        assert result == {"ID": "9"}
        method_path, body = fake.requests[-1]
        assert method_path.startswith("/rest/app.info") and body["auth"] == "tok-1"

    def test_oauth_dynamic_endpoint_ssrf_forbidden(self):
        fake = FakeCrm(responses={"/token": (200, _token_body(client_endpoint="http://169.254.169.254/rest/"))})
        settings_ = bitrix24.BitrixSettings(webhook_url="", create_lead=True, popup_max_delay_s=20,
                                            default_user_id=None, auth_mode="oauth", ulanish_id=ULANISH_ID,
                                            ulanish_sir=ULANISH_SIR)

        def deny(url):
            raise ssrf.UrlForbidden("private_ip")

        client = bitrix24.make_client("s1", settings_, limiter=NoWait(), transport=httpx.MockTransport(fake),
                                      url_check=deny)
        import asyncio
        with pytest.raises(CrmCallError) as exc:
            asyncio.run(client.call("app.info", {}))
        assert exc.value.result.permanent and "url_forbidden" in exc.value.result.error

    def test_oauth_expired_token_forces_single_refresh_then_succeeds(self):
        calls = {"n": 0}
        fake = FakeCrm()

        def transport(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/v1/bitrix/token":
                calls["n"] += 1
                return httpx.Response(200, json=_token_body(access_token=f"tok-{calls['n']}"))
            if request.url.path.endswith("/app.info.json"):
                if "tok-1" in request.content.decode():
                    return httpx.Response(401, json={"error": "EXPIRED_TOKEN"})
                return httpx.Response(200, json={"result": {"ID": "7"}})
            raise AssertionError(request.url.path)

        settings_ = bitrix24.BitrixSettings(webhook_url="", create_lead=True, popup_max_delay_s=20,
                                            default_user_id=None, auth_mode="oauth", ulanish_id=ULANISH_ID,
                                            ulanish_sir=ULANISH_SIR)
        client = bitrix24.make_client("s1", settings_, limiter=NoWait(), transport=httpx.MockTransport(transport),
                                      url_check=lambda url: None)
        import asyncio
        result = asyncio.run(client.call("app.info", {}))
        assert result == {"ID": "7"} and calls["n"] == 2

    def test_oauth_expired_token_second_failure_raises(self):
        def transport(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/v1/bitrix/token":
                return httpx.Response(200, json=_token_body())
            return httpx.Response(401, json={"error": "EXPIRED_TOKEN"})

        settings_ = bitrix24.BitrixSettings(webhook_url="", create_lead=True, popup_max_delay_s=20,
                                            default_user_id=None, auth_mode="oauth", ulanish_id=ULANISH_ID,
                                            ulanish_sir=ULANISH_SIR)
        client = bitrix24.make_client("s1", settings_, limiter=NoWait(), transport=httpx.MockTransport(transport),
                                      url_check=lambda url: None)
        import asyncio
        with pytest.raises(CrmCallError):
            asyncio.run(client.call("app.info", {}))


# ============================================================== B. bitrix_broker
class TestBroker:
    @pytest.mark.asyncio
    async def test_get_token_caches_until_margin_then_refreshes(self):
        calls = {"n": 0}

        def transport(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, json=_token_body(access_token=f"t{calls['n']}"))

        clock_now = NOW

        async def first():
            return await bitrix_broker.get_token(ULANISH_ID, ULANISH_SIR, transport=httpx.MockTransport(transport),
                                                 clock=lambda: clock_now)

        t1 = await first()
        t2 = await bitrix_broker.get_token(ULANISH_ID, ULANISH_SIR, transport=httpx.MockTransport(transport),
                                           clock=lambda: clock_now)
        assert t1.access_token == t2.access_token and calls["n"] == 1

    @pytest.mark.asyncio
    async def test_get_token_force_refresh_bypasses_cache(self):
        calls = {"n": 0}

        def transport(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, json=_token_body(access_token=f"t{calls['n']}"))

        await bitrix_broker.get_token(ULANISH_ID, ULANISH_SIR, transport=httpx.MockTransport(transport),
                                      clock=lambda: NOW)
        refreshed = await bitrix_broker.get_token(ULANISH_ID, ULANISH_SIR, transport=httpx.MockTransport(transport),
                                                  force=True, clock=lambda: NOW)
        assert refreshed.access_token == "t2" and calls["n"] == 2

    @pytest.mark.asyncio
    async def test_get_token_402_maps_to_license_expired(self):
        transport = httpx.MockTransport(lambda r: httpx.Response(402, json={"xato": "lic", "xabar": "tugagan"}))
        with pytest.raises(bitrix_broker.BrokerError) as exc:
            await bitrix_broker.get_token(ULANISH_ID, ULANISH_SIR, transport=transport)
        failure = bitrix_broker.to_crm_failure(exc.value)
        assert failure.result.permanent and failure.result.error == "license_expired"

    @pytest.mark.asyncio
    async def test_broker_unreachable_maps_to_transient(self):
        def boom(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route")

        with pytest.raises(bitrix_broker.BrokerError) as exc:
            await bitrix_broker.get_token(ULANISH_ID, ULANISH_SIR, transport=httpx.MockTransport(boom))
        failure = bitrix_broker.to_crm_failure(exc.value)
        assert not failure.result.permanent and failure.result.retry_after_s is not None

    @pytest.mark.asyncio
    async def test_boshla_returns_session_and_authorize_url(self, monkeypatch):
        monkeypatch.setattr(settings, "innova_id", "innova-1")
        transport = httpx.MockTransport(lambda r: httpx.Response(
            200, json={"sessiya": "sess-1", "authorize_url": "https://lic.uzmik.uz/auth/sess-1"}))
        result = await bitrix_broker.boshla("a.bitrix24.ru", transport=transport)
        assert result.sessiya == "sess-1" and result.authorize_url.endswith("sess-1")

    @pytest.mark.asyncio
    async def test_boshla_without_innova_id_raises_misconfigured(self, monkeypatch):
        monkeypatch.setattr(settings, "innova_id", "")
        with pytest.raises(bitrix_broker.BrokerError) as exc:
            await bitrix_broker.boshla("a.bitrix24.ru", transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json={})))
        assert exc.value.code == "broker_misconfigured"

    @pytest.mark.asyncio
    async def test_boshla_non_200_raises_broker_error_with_body_fields(self, monkeypatch):
        monkeypatch.setattr(settings, "innova_id", "innova-1")
        transport = httpx.MockTransport(lambda r: httpx.Response(
            500, json={"xato": "ichki_xato", "xabar": "Server tushundi yo'q"}))
        with pytest.raises(bitrix_broker.BrokerError) as exc:
            await bitrix_broker.boshla("a.bitrix24.ru", transport=transport)
        assert exc.value.code == "ichki_xato" and exc.value.message == "Server tushundi yo'q"
        assert exc.value.status == 500

    @pytest.mark.asyncio
    async def test_litsenziya_non_200_raises_broker_error_with_body_fields(self):
        transport = httpx.MockTransport(lambda r: httpx.Response(
            500, json={"xato": "ichki_xato", "xabar": "Litsenziya topilmadi"}))
        with pytest.raises(bitrix_broker.BrokerError) as exc:
            await bitrix_broker.litsenziya(ULANISH_ID, ULANISH_SIR, transport=transport)
        assert exc.value.code == "ichki_xato" and exc.value.message == "Litsenziya topilmadi"

    def test_to_crm_failure_generic_status_maps_to_permanent(self):
        error = bitrix_broker.BrokerError("boom", "nimadir xato", status=500)
        failure = bitrix_broker.to_crm_failure(error)
        assert failure.result.permanent and failure.result.error == "broker:boom"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("holat", ["kutilmoqda", "olingan"])
    async def test_natija_passthrough_holat_without_secrets(self, holat):
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"holat": holat}))
        result = await bitrix_broker.natija("sess-1", transport=transport)
        assert result.holat == holat and result.ulanish_id is None

    @pytest.mark.asyncio
    async def test_natija_tayyor_fills_secrets(self):
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json={
            "holat": "tayyor", "ulanish_id": ULANISH_ID, "ulanish_sir": ULANISH_SIR, "member_id": "m1",
            "domain": "a.bitrix24.ru", "application_token": "app-tok"}))
        result = await bitrix_broker.natija("sess-1", transport=transport)
        assert result.holat == "tayyor" and result.ulanish_id == ULANISH_ID and result.application_token == "app-tok"

    @pytest.mark.asyncio
    async def test_natija_404_maps_to_sessiya_yoq(self):
        transport = httpx.MockTransport(lambda r: httpx.Response(404, json={}))
        result = await bitrix_broker.natija("sess-1", transport=transport)
        assert result.holat == "xato" and result.xato == "sessiya_yoq"

    @pytest.mark.asyncio
    async def test_uzish_best_effort_true_on_success(self):
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"ok": True}))
        assert await bitrix_broker.uzish(ULANISH_ID, ULANISH_SIR, transport=transport) is True

    @pytest.mark.asyncio
    async def test_uzish_best_effort_false_on_broker_error_never_raises(self):
        def boom(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("down")

        assert await bitrix_broker.uzish(ULANISH_ID, ULANISH_SIR, transport=httpx.MockTransport(boom)) is False


# ============================================================== C. bitrix_oauth_flow.connect / poll
class TestConnect:
    @pytest.mark.asyncio
    async def test_connect_saves_pending_session_and_audits(self, plain_crypto, monkeypatch):
        monkeypatch.setattr(settings, "innova_id", "innova-1")
        session = CrmSession()
        sub = _sub()
        transport = httpx.MockTransport(lambda r: httpx.Response(
            200, json={"sessiya": "sess-1", "authorize_url": "https://lic.uzmik.uz/auth/sess-1"}))
        url = await flow.connect(session, sub, "a.bitrix24.ru", user_id="u1", transport=transport)
        assert url.endswith("sess-1") and sub.config["domain"] == "a.bitrix24.ru"
        secrets = crm.load_secrets(sub.secret_enc)
        assert secrets["pending_sessiya"] == "sess-1"
        assert session.added and session.added[0].entity == "crm" and session.added[0].entity_id == "bitrix24"
        assert session.added[0].diff == {"domain": "a.bitrix24.ru"}

    @pytest.mark.parametrize("status,code", [(400, "invalid_domain"), (404, "app_not_installed"),
                                             (500, "broker_unreachable"), (None, "broker_unreachable")])
    def test_connect_error_detail_maps_broker_status(self, status, code):
        error = bitrix_broker.BrokerError("x", "xato", status=status)
        http_status, mapped_code, _ = flow.connect_error_detail(error)
        assert mapped_code == code


class TestPoll:
    @pytest.mark.asyncio
    async def test_poll_without_pending_session_is_error(self, plain_crypto):
        session = CrmSession()
        sub = _sub()
        result = await flow.poll(session, sub, user_id="u1")
        assert result.status == "error" and result.code == "no_session"

    @pytest.mark.asyncio
    async def test_poll_pending(self, plain_crypto):
        session = CrmSession()
        sub = _sub(secret_enc=crm.dump_secrets({"pending_sessiya": "sess-1"}))
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"holat": "kutilmoqda"}))
        result = await flow.poll(session, sub, user_id="u1", transport=transport)
        assert result.status == "pending"

    @pytest.mark.asyncio
    async def test_poll_olingan_is_error_already_taken(self, plain_crypto):
        session = CrmSession()
        sub = _sub(secret_enc=crm.dump_secrets({"pending_sessiya": "sess-1"}))
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"holat": "olingan"}))
        result = await flow.poll(session, sub, user_id="u1", transport=transport)
        assert result.status == "error" and result.code == "already_taken"

    @pytest.mark.asyncio
    async def test_poll_xato_passes_through_code_and_message(self, plain_crypto):
        session = CrmSession()
        sub = _sub(secret_enc=crm.dump_secrets({"pending_sessiya": "sess-1"}))
        transport = httpx.MockTransport(lambda r: httpx.Response(
            200, json={"holat": "xato", "xato": "rad_etildi", "xabar": "Foydalanuvchi rad etdi"}))
        result = await flow.poll(session, sub, user_id="u1", transport=transport)
        assert result.status == "error" and result.code == "rad_etildi" and result.message == "Foydalanuvchi rad etdi"

    @pytest.mark.asyncio
    async def test_poll_tayyor_saves_secrets_and_runs_setup(self, plain_crypto, oauth_provider):
        session = CrmSession([])
        sub = _sub(secret_enc=crm.dump_secrets({"pending_sessiya": "sess-1"}))

        def transport(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path == "/api/v1/bitrix/natija":
                return httpx.Response(200, json={"holat": "tayyor", "ulanish_id": ULANISH_ID,
                                                 "ulanish_sir": ULANISH_SIR, "member_id": "m1",
                                                 "domain": "a.bitrix24.ru", "application_token": "app-tok"})
            if path == "/api/v1/bitrix/token":
                return httpx.Response(200, json=_token_body())
            if path.endswith("/app.info.json"):
                return httpx.Response(200, json={"result": {"ID": "9"}})
            if path.endswith("/telephony.externalLine.get.json"):
                return httpx.Response(200, json={"result": []})
            if path.endswith("/voximplant.line.outgoing.set.json"):
                return httpx.Response(200, json={"result": True})
            if path.endswith("/voximplant.line.outgoing.get.json"):
                return httpx.Response(200, json={"result": "REST_APP:9"})
            if path.endswith("/event.bind.json"):
                return httpx.Response(200, json={"result": True})
            if path.endswith("/user.get.json"):
                return httpx.Response(200, json={"result": [], "next": None})
            raise AssertionError(path)

        oauth_provider(transport)
        result = await flow.poll(session, sub, user_id="u1", transport=httpx.MockTransport(transport),
                                 public_base_url="https://pbx.example.com")
        assert result.status == "connected"
        assert result.setup.default_line is True and result.setup.event_bound is True
        secrets = crm.load_secrets(sub.secret_enc)
        assert secrets["ulanish_id"] == ULANISH_ID and "pending_sessiya" not in secrets
        assert sub.config["auth_mode"] == "oauth" and sub.config["member_id"] == "m1"


# ============================================================== D. run_setup (har qadam alohida)
class TestRunSetup:
    def _dids_session(self, dids=()):
        """`_sync_lines` (tenant_dids select) va `_sync_users` (store_users delete + refresh_auto_map
        select*2 + delete) uchun navbat; 0 foydalanuvchi — faqat shu execute'lar chaqiriladi."""
        return CrmSession(list(dids), [], [])

    @pytest.mark.asyncio
    async def test_run_setup_not_oauth_raises_permanent(self, plain_crypto):
        session = CrmSession()
        sub = _sub()  # auth_mode default webhook
        with pytest.raises(CrmCallError) as exc:
            await flow.run_setup(session, sub, user_id="u1")
        assert exc.value.result.permanent

    @pytest.mark.asyncio
    async def test_run_setup_token_failure_aborts_entirely(self, plain_crypto):
        session = self._dids_session()
        sub = _oauth_sub()
        transport = httpx.MockTransport(lambda r: httpx.Response(402, json={"xato": "lic", "xabar": "tugagan"}))
        with pytest.raises(CrmCallError) as exc:
            await flow.run_setup(session, sub, user_id="u1", transport=transport)
        assert exc.value.result.error == "license_expired"
        assert not session.added  # audit ham yozilmagan — hech narsa boshlanmagan

    @pytest.mark.asyncio
    async def test_run_setup_happy_path_no_warnings(self, plain_crypto, oauth_provider):
        session = self._dids_session()
        sub = _oauth_sub()

        def transport(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path == "/api/v1/bitrix/token":
                return httpx.Response(200, json=_token_body())
            if path.endswith("/app.info.json"):
                return httpx.Response(200, json={"result": {"ID": "9"}})
            if path.endswith("/telephony.externalLine.get.json"):
                return httpx.Response(200, json={"result": []})
            if path.endswith("/voximplant.line.outgoing.set.json"):
                return httpx.Response(200, json={"result": True})
            if path.endswith("/voximplant.line.outgoing.get.json"):
                return httpx.Response(200, json={"result": "REST_APP:9"})
            if path.endswith("/event.bind.json"):
                return httpx.Response(200, json={"result": True})
            if path.endswith("/user.get.json"):
                return httpx.Response(200, json={"result": [], "next": None})
            raise AssertionError(path)

        oauth_provider(transport)
        result = await flow.run_setup(session, sub, user_id="u1", transport=httpx.MockTransport(transport),
                                      public_base_url="https://pbx.example.com")
        assert result.warnings == [] and result.default_line is True and result.event_bound is True
        audit = session.added[-1]
        assert audit.entity == "crm" and audit.diff["warnings"] == []

    @pytest.mark.asyncio
    async def test_run_setup_saves_application_token_from_broker(self, plain_crypto, oauth_provider):
        """Lokal ilovada ONAPPINSTALL «Переустановить»dan keyin keladi — application_token
        `natija`da yo'q, keyinroq `/token` javobida paydo bo'ladi va saqlanishi shart."""
        session = self._dids_session()
        sub = _oauth_sub()

        def transport(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/v1/bitrix/token":
                return httpx.Response(200, json=_token_body(application_token="apt-1"))
            return httpx.Response(200, json={"error": "X", "error_description": "o'tkazib yuborildi"})

        oauth_provider(transport)
        await flow.run_setup(session, sub, user_id="u1", transport=httpx.MockTransport(transport))
        assert crm.load_secrets(sub.secret_enc)["application_token"] == "apt-1"

    @pytest.mark.asyncio
    async def test_run_setup_public_url_missing_warns_not_aborts(self, plain_crypto, oauth_provider):
        session = self._dids_session()
        sub = _oauth_sub()

        def transport(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path == "/api/v1/bitrix/token":
                return httpx.Response(200, json=_token_body())
            if path.endswith("/app.info.json"):
                return httpx.Response(200, json={"result": {"ID": "9"}})
            if path.endswith("/telephony.externalLine.get.json"):
                return httpx.Response(200, json={"result": []})
            if path.endswith("/voximplant.line.outgoing.set.json"):
                return httpx.Response(200, json={"result": True})
            if path.endswith("/voximplant.line.outgoing.get.json"):
                return httpx.Response(200, json={"result": "REST_APP:9"})
            if path.endswith("/user.get.json"):
                return httpx.Response(200, json={"result": [], "next": None})
            raise AssertionError(path)

        oauth_provider(transport)
        result = await flow.run_setup(session, sub, user_id="u1", transport=httpx.MockTransport(transport),
                                      public_base_url=None)
        assert result.warnings == ["public_url_missing"] and result.event_bound is False

    @pytest.mark.asyncio
    async def test_run_setup_event_already_binded_counts_as_bound(self, plain_crypto, oauth_provider):
        session = self._dids_session()
        sub = _oauth_sub()

        def transport(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path == "/api/v1/bitrix/token":
                return httpx.Response(200, json=_token_body())
            if path.endswith("/app.info.json"):
                return httpx.Response(200, json={"result": {"ID": "9"}})
            if path.endswith("/telephony.externalLine.get.json"):
                return httpx.Response(200, json={"result": []})
            if path.endswith("/voximplant.line.outgoing.set.json"):
                return httpx.Response(200, json={"result": True})
            if path.endswith("/voximplant.line.outgoing.get.json"):
                return httpx.Response(200, json={"result": "REST_APP:9"})
            if path.endswith("/event.bind.json"):
                return httpx.Response(200, json={"error": "ERROR_CORE", "error_description": "Handler already binded"})
            if path.endswith("/user.get.json"):
                return httpx.Response(200, json={"result": [], "next": None})
            raise AssertionError(path)

        oauth_provider(transport)
        result = await flow.run_setup(session, sub, user_id="u1", transport=httpx.MockTransport(transport),
                                      public_base_url="https://pbx.example.com")
        assert result.event_bound is True and "event_bind_failed" not in result.warnings

    @pytest.mark.asyncio
    async def test_run_setup_event_bind_other_error_warns(self, plain_crypto, oauth_provider):
        session = self._dids_session()
        sub = _oauth_sub()

        def transport(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path == "/api/v1/bitrix/token":
                return httpx.Response(200, json=_token_body())
            if path.endswith("/app.info.json"):
                return httpx.Response(200, json={"result": {"ID": "9"}})
            if path.endswith("/telephony.externalLine.get.json"):
                return httpx.Response(200, json={"result": []})
            if path.endswith("/voximplant.line.outgoing.set.json"):
                return httpx.Response(200, json={"result": True})
            if path.endswith("/voximplant.line.outgoing.get.json"):
                return httpx.Response(200, json={"result": "REST_APP:9"})
            if path.endswith("/event.bind.json"):
                return httpx.Response(400, json={"error": "BAD_REQUEST", "error_description": "boom"})
            if path.endswith("/user.get.json"):
                return httpx.Response(200, json={"result": [], "next": None})
            raise AssertionError(path)

        oauth_provider(transport)
        result = await flow.run_setup(session, sub, user_id="u1", transport=httpx.MockTransport(transport),
                                      public_base_url="https://pbx.example.com")
        assert result.warnings == ["event_bind_failed"]

    @pytest.mark.asyncio
    async def test_run_setup_default_line_failed_warns(self, plain_crypto, oauth_provider):
        session = self._dids_session()
        sub = _oauth_sub()

        def transport(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path == "/api/v1/bitrix/token":
                return httpx.Response(200, json=_token_body())
            if path.endswith("/app.info.json"):
                return httpx.Response(200, json={"result": {"ID": "9"}})
            if path.endswith("/telephony.externalLine.get.json"):
                return httpx.Response(200, json={"result": []})
            if path.endswith("/voximplant.line.outgoing.set.json"):
                return httpx.Response(400, json={"error": "BAD_REQUEST", "error_description": "boom"})
            if path.endswith("/event.bind.json"):
                return httpx.Response(200, json={"result": True})
            if path.endswith("/user.get.json"):
                return httpx.Response(200, json={"result": [], "next": None})
            raise AssertionError(path)

        oauth_provider(transport)
        result = await flow.run_setup(session, sub, user_id="u1", transport=httpx.MockTransport(transport),
                                      public_base_url="https://pbx.example.com")
        assert result.warnings == ["default_line_failed"] and result.default_line is False

    @pytest.mark.asyncio
    async def test_run_setup_lines_failed_warns_and_continues(self, plain_crypto, oauth_provider):
        """`tenant_dids` (faqat BIRINCHI `session.execute`) yiqilsa — `_sync_lines`
        `Exception`ni yutib `lines_failed` qo'shadi, qolgan qadamlar (foydalanuvchi
        sinxroni ham) davom etadi (liniyalar MUHIM EMAS)."""
        class FailFirstSession(CrmSession):
            async def execute(self, stmt, params=None):
                if not self.executed:
                    self.executed.append(stmt)
                    raise RuntimeError("db down")
                return await super().execute(stmt, params)

        session = FailFirstSession()
        sub = _oauth_sub()

        def transport(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path == "/api/v1/bitrix/token":
                return httpx.Response(200, json=_token_body())
            if path.endswith("/app.info.json"):
                return httpx.Response(200, json={"result": {"ID": "9"}})
            if path.endswith("/voximplant.line.outgoing.set.json"):
                return httpx.Response(200, json={"result": True})
            if path.endswith("/voximplant.line.outgoing.get.json"):
                return httpx.Response(200, json={"result": "REST_APP:9"})
            if path.endswith("/event.bind.json"):
                return httpx.Response(200, json={"result": True})
            if path.endswith("/user.get.json"):
                return httpx.Response(200, json={"result": [], "next": None})
            raise AssertionError(path)

        oauth_provider(transport)
        result = await flow.run_setup(session, sub, user_id="u1", transport=httpx.MockTransport(transport),
                                      public_base_url="https://pbx.example.com")
        assert result.warnings == ["lines_failed"] and result.lines == 0

    @pytest.mark.asyncio
    async def test_run_setup_users_failed_warns(self, plain_crypto, oauth_provider):
        session = self._dids_session()
        sub = _oauth_sub()

        def transport(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path == "/api/v1/bitrix/token":
                return httpx.Response(200, json=_token_body())
            if path.endswith("/app.info.json"):
                return httpx.Response(200, json={"result": {"ID": "9"}})
            if path.endswith("/telephony.externalLine.get.json"):
                return httpx.Response(200, json={"result": []})
            if path.endswith("/voximplant.line.outgoing.set.json"):
                return httpx.Response(200, json={"result": True})
            if path.endswith("/voximplant.line.outgoing.get.json"):
                return httpx.Response(200, json={"result": "REST_APP:9"})
            if path.endswith("/event.bind.json"):
                return httpx.Response(200, json={"result": True})
            if path.endswith("/user.get.json"):
                return httpx.Response(400, json={"error": "BAD_REQUEST", "error_description": "boom"})
            raise AssertionError(path)

        oauth_provider(transport)
        result = await flow.run_setup(session, sub, user_id="u1", transport=httpx.MockTransport(transport),
                                      public_base_url="https://pbx.example.com")
        assert result.warnings == ["users_failed"] and result.users_synced == 0


# ============================================================== E. disconnect
class TestDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_noop_when_not_oauth(self, plain_crypto):
        session = CrmSession()
        sub = _sub()
        await flow.disconnect(session, sub, user_id="u1")
        assert not session.added

    @pytest.mark.asyncio
    async def test_disconnect_clears_secrets_and_audits_even_if_unbind_fails(self, plain_crypto, oauth_provider):
        session = CrmSession()
        sub = _oauth_sub()

        def transport(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/v1/bitrix/token":
                return httpx.Response(200, json=_token_body())
            if request.url.path.endswith("/event.unbind.json"):
                return httpx.Response(400, json={"error": "BAD_REQUEST", "error_description": "boom"})
            if request.url.path == "/api/v1/bitrix/uzish":
                return httpx.Response(200, json={"ok": True})
            raise AssertionError(request.url.path)

        oauth_provider(transport)
        await flow.disconnect(session, sub, user_id="u1", transport=httpx.MockTransport(transport),
                              public_base_url="https://pbx.example.com")
        secrets = crm.load_secrets(sub.secret_enc)
        assert "ulanish_id" not in secrets and sub.config["auth_mode"] is None
        assert session.added[-1].entity == "crm" and session.added[-1].diff["auth_mode"] is None

    @pytest.mark.asyncio
    async def test_disconnect_without_public_base_url_skips_unbind(self, plain_crypto):
        session = CrmSession()
        sub = _oauth_sub()
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"ok": True}))
        await flow.disconnect(session, sub, user_id="u1", transport=transport, public_base_url=None)
        secrets = crm.load_secrets(sub.secret_enc)
        assert "ulanish_id" not in secrets


# ============================================================== F. license_info
class TestLicenseInfo:
    @pytest.mark.asyncio
    async def test_license_info_not_connected_without_ulanish_id(self, plain_crypto):
        session = CrmSession()
        sub = _sub()
        info = await flow.license_info(session, sub)
        assert info == {"connected": False, "license": None, "error": None}

    @pytest.mark.asyncio
    async def test_license_info_fetches_and_caches(self, plain_crypto):
        session = CrmSession()
        sub = _oauth_sub()
        calls = {"n": 0}

        def transport(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(200, json={"plan": "pro", "limit": 10})

        clock = {"t": 1000.0}
        info1 = await flow.license_info(session, sub, transport=httpx.MockTransport(transport),
                                         clock=lambda: clock["t"])
        info2 = await flow.license_info(session, sub, transport=httpx.MockTransport(transport),
                                         clock=lambda: clock["t"] + 10)
        assert info1["license"] == {"plan": "pro", "limit": 10} and calls["n"] == 1
        assert info2["license"] == info1["license"]

    @pytest.mark.asyncio
    async def test_license_info_broker_error_reports_connected_with_error(self, plain_crypto):
        session = CrmSession()
        sub = _oauth_sub()

        def boom(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("down")

        info = await flow.license_info(session, sub, transport=httpx.MockTransport(boom), clock=lambda: 1.0)
        assert info["connected"] is True and info["license"] is None and info["error"]


# ============================================================== G. public_crm hook auth
class TestHookAuth:
    def test_member_matches_requires_exact_nonblank_match(self):
        assert public_crm.member_matches("m1", "m1") is True
        assert public_crm.member_matches("m1", "m2") is False
        assert public_crm.member_matches(None, None) is False
        assert public_crm.member_matches("", "") is False

    def test_hook_auth_ok_webhook_mode_unchanged(self):
        secrets = {"application_token": "app-tok"}
        form_ok = {"auth[application_token]": "app-tok"}
        form_bad = {"auth[application_token]": "wrong"}
        assert public_crm.hook_auth_ok("", {}, secrets, form_ok) is True
        assert public_crm.hook_auth_ok("webhook", {}, secrets, form_bad) is False

    def test_hook_auth_ok_oauth_requires_member_id(self):
        config = {"member_id": "m1"}
        secrets: dict[str, str] = {}
        assert public_crm.hook_auth_ok("oauth", config, secrets, {"auth[member_id]": "m1"}) is True
        assert public_crm.hook_auth_ok("oauth", config, secrets, {"auth[member_id]": "other"}) is False
        assert public_crm.hook_auth_ok("oauth", config, secrets, {}) is False

    def test_hook_auth_ok_oauth_also_checks_application_token_when_stored(self):
        config = {"member_id": "m1"}
        secrets = {"application_token": "app-tok"}
        ok_form = {"auth[member_id]": "m1", "auth[application_token]": "app-tok"}
        bad_form = {"auth[member_id]": "m1", "auth[application_token]": "wrong"}
        assert public_crm.hook_auth_ok("oauth", config, secrets, ok_form) is True
        assert public_crm.hook_auth_ok("oauth", config, secrets, bad_form) is False


class TestSetupRoute:
    """`POST .../bitrix24/setup` javobi shartnoma §2 bo'yicha `{setup:{...}}` (web `res.setup` o'qiydi)."""

    async def test_setup_route_wraps_result_in_setup_key(self, monkeypatch):
        from app.api.v1 import crm as crm_api

        class _Session:
            async def commit(self):
                return None

        async def _sub_stub(session, user, provider):
            return object()

        async def _url_stub(session, tenant_id):
            return "https://pbx.example.uz"

        async def _setup_stub(session, sub, *, user_id, public_base_url):
            return flow.SetupResult(lines=2, default_line=True, event_bound=True, users_synced=5,
                                    warnings=["users_failed"])

        monkeypatch.setattr(crm_api, "_subscription", _sub_stub)
        monkeypatch.setattr(crm_api, "_public_base_url", _url_stub)
        monkeypatch.setattr(crm_api.bitrix_oauth_flow, "run_setup", _setup_stub)
        user = type("U", (), {"id": "u1", "tenant_id": "t1"})()
        out = await crm_api.bitrix_setup(session=_Session(), user=user)
        assert out.model_dump() == {"setup": {"lines": 2, "default_line": True, "event_bound": True,
                                              "users_synced": 5, "warnings": ["users_failed"]}}
