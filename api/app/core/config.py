"""Ilova sozlamalari — barcha maxfiy qiymatlar faqat muhit o'zgaruvchilaridan olinadi.

Manba: callcenter/backend/app/core/config.py namunasi (soddalashtirilgan — M0
uchun fayl-fallback kalit kerak emas, sir yo'q bo'lsa aniq xato beramiz).
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # --- Baza ---
    database_url: str = Field(
        default="postgresql+asyncpg://innova:innova@postgres:5432/innova"
    )
    # pgp_sym_encrypt/decrypt kaliti — Asterisk realtime view'lar va API bir xil qiymatni
    # ishlatadi (`current_setting('innova.key')`). ALTER DATABASE orqali o'rnatiladi.
    innova_db_key: str = Field(default="")

    # --- JWT ---
    secret_key: str = Field(default="")
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 30

    # --- Login bloklash ---
    login_max_attempts: int = 5
    login_lock_minutes: int = 15

    # --- Parol siyosati ---
    password_min_length: int = 10

    # --- AMI ---
    ami_host: str = "asterisk"
    ami_port: int = 5038
    ami_username: str = "innova"
    ami_password: str = ""

    # --- Dialplan kompilyatori ---
    dialplan_dir: str = "/srv/dialplan"
    dialplan_filename: str = "extensions_innova.conf"
    # Kutish musiqasi (MOH, M1b) — xuddi shu umumiy `dialplan` hajmiga yoziladi
    # (musiconhold.conf uni #include qiladi) — app/services/moh.py.
    musiconhold_filename: str = "musiconhold_innova.conf"
    # SIP/RTP (S32) — pjsip.conf va rtp.conf #include qiladi — app/services/sip_transport.py.
    pjsip_transports_filename: str = "pjsip_transports_innova.conf"
    rtp_filename: str = "rtp_innova.conf"

    # --- Tenant sehrgari uchun standart ---
    default_tenant_code: str = "t1"

    # --- Audio (M1a) --- Asterisk ham o'qiydigan umumiy hajm.
    sounds_dir: str = "/var/lib/innova/sounds"
    audio_max_upload_bytes: int = 20 * 1024 * 1024
    audio_max_duration_s: int = 300

    # --- SIP TLS sertifikati (M1c, S32 davomi) --- Asterisk FAQAT o'qiydigan
    # umumiy hajm (app/services/tls_cert.py). Kalit (`tls_key_filename`)
    # dunyoga ochiq EMAS — faqat egasi (API, root) va `tls_cert.ASTERISK_GID`
    # guruhi o'qiy oladi.
    certs_dir: str = "/etc/innova/certs"
    tls_cert_filename: str = "innova.crt"
    tls_key_filename: str = "innova.key"

    # --- 1.0.4: veb (nginx 443) HTTPS sertifikati (app/services/web_tls_cert.py) ---
    # BIR MARTA (birinchi ishga tushishda) generatsiya qilinadi, keyin
    # YANGILANMAYDI (xuddi shu `certs_dir` hajmida — yangilashlarda saqlanadi).
    # SAN = `web_tls_hostname` + `web_tls_san_ips` (vergul bilan, install.sh/
    # innova-start.sh server IP'larini aniqlab beradi).
    web_tls_cert_filename: str = "web.crt"
    web_tls_key_filename: str = "web.key"
    web_tls_hostname: str = "innova-pbx"
    web_tls_san_ips: str = ""
    web_tls_validity_days: int = 3650

    # --- Ovozli pochta (M1c §2) --- `voicemail` umumiy hajm (asterisk + api);
    # konfiguratsiya `dialplan` hajmiga (voicemail.conf #include) —
    # app/services/voicemail.py. Bildirishnoma fon vazifasi — app/services/vm_notify.py.
    voicemail_spool_dir: str = "/var/spool/asterisk/voicemail"
    voicemail_filename: str = "voicemail_innova.conf"
    # --- Park (M2a §3) --- lot fayli (`res_parking.conf` #include), app/services/parking.py.
    parking_filename: str = "res_parking_innova.conf"
    # --- Konferensiya (M2a §4) --- profillar fayli (`confbridge.conf` #include),
    # app/services/conference.py.
    confbridge_filename: str = "confbridge_innova.conf"
    vm_notify_enabled: bool = True
    vm_notify_interval_s: float = 5.0
    # 1.0.4 §3: kamida-bir-marta qayta urinish — `integrations`dagi outbox qolipi
    # bilan BIR XIL (`app/services/integrations/outbox.py` `parse_schedule`/`transition`),
    # urinishlar tugagach qator `dead` bo'ladi (`vm_notify_max_attempts` o'rnini bosadi).
    vm_notify_retry_schedule_s: str = "30,120,600,1800,3600"

    # --- Chiquvchi marshrut PIN tekshiruvi (M1b) --- dialplan `CURL()` shu
    # ichki endpoint'ga PIN'ni tekshirish uchun murojaat qiladi; parolni
    # dialplan matni ichida saqlamaslik uchun (0644, dunyo o'qiy oladi).
    internal_api_token: str = Field(default="")
    internal_api_base_url: str = "http://api:8000"

    # --- M2c §4: ogohlantirish yuborish fon vazifasi (`app/services/alerts.py`
    # `run_forever`) — `vm_notify_enabled`/`vm_notify_interval_s` BILAN BIR XIL qolip.
    alert_dispatch_enabled: bool = True
    alert_dispatch_interval_s: float = 2.0

    # --- M2c §2: SIP hujum himoyasi — PJSIP ACL fayli (`dialplan` umumiy
    # hajmiga, `pjsip.conf` #include qiladi) va Asterisk `security` logger
    # kanali fayli (yangi `astlog` hajm — Asterisk rw, API ro, §0).
    sip_acl_filename: str = "pjsip_acl_innova.conf"
    security_log_path: str = "/var/log/asterisk/innova/security.log"
    sip_guard_task_enabled: bool = True
    sip_guard_interval_s: float = 5.0

    # --- M2c §5: trunk monitoringi fon vazifasi — `vm_notify_enabled` BILAN BIR XIL qolip.
    trunk_monitor_enabled: bool = True
    trunk_monitor_interval_s: float = 30.0

    # --- M6 §3: kampaniya dialer (avtoinformator / avtoterish).
    campaign_dialer_enabled: bool = True
    campaign_dialer_interval_s: float = 2.0

    # --- M3a §0/§2: brauzer softfoni — WS ticket muddati va `/me/softphone` chastota chegarasi.
    softphone_ticket_ttl_s: int = 600
    softphone_rate_limit_per_min: int = 30

    # --- M3b §1: qo'ng'iroq yozuvlari — `recordings` umumiy hajm (asterisk rw, api rw).
    recordings_dir: str = "/var/spool/asterisk/monitor"
    recording_purge_enabled: bool = True
    recording_purge_interval_s: float = 86400.0
    # --- M4a §1: provizioning so'rovlari jurnali (`provision_requests`) 30 kunlik tozalovchi.
    provision_purge_enabled: bool = True
    provision_purge_interval_s: float = 86400.0
    # --- M3b §0/§3: hodisalar (AMI event-ulanish + CDR supurgich) va outbox yetkazuvchisi.
    call_events_enabled: bool = True
    call_events_sweep_interval_s: float = 30.0
    call_events_settle_s: float = 2.0  # oxirgi kanal yopilgach CDR yozilishini kutish
    integration_dispatch_enabled: bool = True
    integration_dispatch_interval_s: float = 1.0
    # Vergul bilan sekundlar: "30,120,600,1800,3600,10800,21600,43200" (8 qayta urinish).
    integration_retry_schedule_s: str = "30,120,600,1800,3600,10800,21600,43200"
    integration_disable_after_s: int = 86400
    integration_http_timeout_s: float = 10.0
    # SSRF: PBX'ning o'z xizmatlari (nomlari + resolve qilingan IP'lari) — webhook URL'i bo'la olmaydi.
    integration_blocked_hosts: str = "api,postgres,asterisk,web,migrate,localhost,innova-pbx"
    # --- M3b §4: ochiq API kalitlari.
    api_key_rate_limit_per_min: int = 120

    # --- M4b §0/§1: zaxira va tiklash — lokal nusxa hajmi (`backups` volume), fon jadvali
    # (`backup_scheduler.run_forever`, `vm_notify_enabled` BILAN BIR XIL qolip).
    backups_dir: str = "/var/lib/innova/backups"
    backup_scheduler_enabled: bool = True
    # Ishga tushishda qotib qolgan zaxira/tiklash/ko'chirish yozuvlarini `failed` qilish (`stale_jobs.py`).
    stale_job_recovery_enabled: bool = True
    # m-sip-login-plain-number §5: ishga tushishda dialplan/navbat a'zosi/hint'ni qayta qo'llash
    # (migratsiya endpoint nomlashni o'zgartirganda eski kompilyatsiya fayli eskirmasin).
    startup_dialplan_regen_enabled: bool = True
    backup_scheduler_interval_s: float = 60.0
    # Masofaviy nishonlarni sinash/yuklash uchun umumiy vaqt chegarasi (S3/SFTP tarmog'i osilib qolmasin).
    backup_target_timeout_s: float = 60.0

    # --- M5a: FreePBX'dan ko'chirish — yuklangan to'plamlar hajmi (`migrations` volume).
    migrations_dir: str = "/var/lib/innova/migrations"
    migration_upload_max_bytes: int = 20 * 1024 * 1024 * 1024

    # --- 1.0.4: o'rnatish kodi (Jenkins uslubi) — `install.sh` generatsiya qiladi,
    # faqat root o'qiydigan `.env`da saqlanadi. Bo'sh = eski/allaqachon o'rnatilgan
    # serverlar uchun tekshiruv o'chirilgan (orqaga moslik).
    setup_code: str = Field(default="")

    # --- Bitrix24 OAuth: markaziy broker (lic.uzmik.uz, `bitrix-oauth-shartnoma.md`).
    # `client_secret` FAQAT brokerda — bu yerda faqat broker manzili va `boshla`
    # so'rovidagi o'rnatish identifikatori (bu PBX nusxasini brokerga tanitadi).
    bitrix_broker_url: str = Field(default="https://lic.uzmik.uz")
    innova_id: str = Field(default="")

    # --- M10 A1: qayta chaqirish vidjeti (S17) — fon dialer `vm_notify_enabled`
    # BILAN BIR XIL qolip; `public_base_url` — admin `Widget.embed_snippet`
    # qurish uchun (bo'sh = UI'da ogohlantirish, 409 EMAS).
    callback_dialer_enabled: bool = True
    callback_dialer_interval_s: float = 2.0
    public_base_url: str = Field(default="")

    # --- M10 A2: o'tkazib yuborilgan qo'ng'iroq bildirishnomasi — `vm_notify_enabled`
    # BILAN BIR XIL qolip; 3 marta qayta urinish jadvali.
    missed_notify_enabled: bool = True
    missed_notify_interval_s: float = 5.0
    missed_notify_retry_schedule_s: str = "30,120,600"

    # --- M-CRM §1: Bitrix24 foydalanuvchi sinxroni fon ishi — `auto_sync_users=true`
    # bo'lgan yoqilgan obunalar uchun (bitta xato boshqalarni to'xtatmaydi).
    crm_users_sync_enabled: bool = True
    crm_users_sync_interval_s: float = 600.0

    # --- M10 A3: Yandex SpeechKit TTS — baza manzili FAQAT muhitdan (foydalanuvchi
    # kiritmaydi — SSRF yo'q, m10-onlinepbx-contract.md §A3).
    tts_yandex_base: str = "https://tts.api.cloud.yandex.net"
    tts_http_timeout_s: float = 20.0
    tts_preview_rate_limit_per_min: int = 20

    # --- M8: tarmoq sozlamalari — `netd` bilan unix-soket orqali gaplashish
    # (m8-network-contract.md bo'lim 1). Soket api/netd konteynerlari orasida
    # umumiy `netd-sock` volume orqali ulashiladi.
    netd_socket_path: str = "/run/innova-netd/netd.sock"
    netd_timeout_s: float = 10.0

    # --- M10 B3: tashqi WS hodisalar (`/api/public/v1/events/ws`) — `integration_events`
    # jadvalini so'rovchi fon tarqatuvchi (`vm_notify_enabled` BILAN BIR XIL qolip);
    # ulanish 25 soniyada bir `ping` oladi (`events_ws_ping_interval_s`).
    events_ws_broadcast_enabled: bool = True
    events_ws_broadcast_interval_s: float = 1.0
    events_ws_ping_interval_s: float = 25.0

    # --- m11-update-contract.md: paneldan yangilash — host agenti (`innova-update
    # --agent`) shu papkaga yozadi, API faqat o'qiydi/so'rov qoldiradi. `innova_version`
    # — joriy o'rnatilgan versiya (install.sh/docker-compose INNOVA_VERSION beradi;
    # bo'sh bo'lsa noma'lum, operator/dev muhitida kutilgan holat).
    update_dir: str = "/var/lib/innova/update"
    innova_version: str | None = Field(default=None)

    @field_validator("innova_version", mode="before")
    @classmethod
    def _empty_version_is_none(cls, value: object) -> object:
        return None if value == "" else value

    def require_internal_api_token(self) -> str:
        return self._require(self.internal_api_token, "INTERNAL_API_TOKEN")

    @staticmethod
    def _require(value: str, env_name: str) -> str:
        """`secret_key`/`innova_db_key` uchun bir xil "bo'lmasa — aniq xato"
        qolipi takrorlangan edi (dryer: 1.00 o'xshashlik) — shu yerga chiqarildi."""
        if not value:
            raise RuntimeError(f"{env_name} muhit o'zgaruvchisi berilmagan")
        return value

    def require_secret_key(self) -> str:
        return self._require(self.secret_key, "SECRET_KEY")

    def require_db_key(self) -> str:
        return self._require(self.innova_db_key, "INNOVA_DB_KEY")


_WEAK_SECRETS = {"change-me", "changeme", "secret", "password", "innova", "default"}
_MIN_SECRET_LENGTH = 32


def _reject_weak_secret(value: str, env_name: str, *, min_length: int = _MIN_SECRET_LENGTH) -> None:
    """Item 6b (LOW): `SECRET_KEY`/`INTERNAL_API_TOKEN` BO'SH bo'lsa jim o'tkaziladi
    (sozlanmaganlik `_require`/`require_*` orqali ALOHIDA, foydalanish vaqtida
    tekshiriladi — ko'p test shu maydonlarga qisqa soxta qiymat (`monkeypatch`)
    qo'yadi, bu yerga tegmaydi). Faqat HAQIQIY (bo'sh bo'lmagan) qiymat
    `.env`dagi odatiy/zaif placeholder BO'LSA yoki juda qisqa bo'lsa — ishga
    tushishda (`get_settings()`, BIR MARTA) darhol to'xtatiladi."""
    if not value:
        return
    if value.lower() in _WEAK_SECRETS or len(value) < min_length:
        raise RuntimeError(
            f"{env_name} juda zaif/qisqa — kamida {min_length} belgili tasodifiy qiymat kerak"
            " (masalan: `openssl rand -hex 32`)"
        )


@lru_cache
def get_settings() -> Settings:
    loaded = Settings()
    _reject_weak_secret(loaded.secret_key, "SECRET_KEY")
    _reject_weak_secret(loaded.internal_api_token, "INTERNAL_API_TOKEN")
    return loaded


settings = get_settings()
