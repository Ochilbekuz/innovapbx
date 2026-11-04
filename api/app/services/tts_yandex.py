"""M10 A3 — Yandex SpeechKit v1 REST klienti.

Baza manzil FAQAT `settings.tts_yandex_base`dan o'qiladi — foydalanuvchi uni
hech qanday maydon orqali bermaydi/o'zgartirmaydi (m10-onlinepbx-contract.md
§A3: "Base URL faqat env'dan — SSRF yo'q"). `POST {base}/speech/v1/tts:synthesize`,
`Authorization: Api-Key <key>` sarlavhasi, `data=` (form-urlencoded) tanasi;
javob TANASI — xom LPCM (16-bit, signed, little-endian, mono) oqimi, JSON EMAS
(`services/audio_tools.convert_to_wav_8k_mono`ga `input_args` bilan beriladi)."""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.db.models import TtsSettings
from app.services.crypto import decrypt_secret

_SAMPLE_RATE = 8000
# Yandex SpeechKit lang kodlari — `voices` lug'ati kalitlari (uz/ru/en) bilan.
_LANG_CODES = {"uz": "uz-UZ", "ru": "ru-RU", "en": "en-US"}
_DEFAULT_VOICES = {"uz": "nigora", "ru": "alena", "en": "john"}


class TtsError(RuntimeError):
    """Yandex xatosi — sabab matnda (API kalit HECH QACHON matnga qo'shilmaydi)."""


@dataclass(frozen=True)
class TtsConfig:
    provider: str
    api_key: str | None
    folder_id: str | None
    voices: dict[str, str]


async def load_config(session, tenant_id: str) -> TtsConfig:  # noqa: ANN001 — AsyncSession, aylanma importdan qochish
    row = await session.get(TtsSettings, tenant_id)
    if row is None:
        return TtsConfig(provider="none", api_key=None, folder_id=None, voices=dict(_DEFAULT_VOICES))
    return TtsConfig(
        provider=row.provider, folder_id=row.folder_id, voices=dict(row.voices or _DEFAULT_VOICES),
        api_key=await decrypt_secret(session, row.api_key_enc) if row.api_key_enc else None,
    )


def voice_for(cfg: TtsConfig, language: str) -> str:
    return cfg.voices.get(language) or cfg.voices.get("uz") or next(iter(cfg.voices.values()), "alena")


async def synthesize_lpcm(cfg: TtsConfig, text: str, language: str, *,
                          transport: httpx.AsyncBaseTransport | None = None) -> bytes:
    """`cfg.provider != "yandex"` yoki kalit yo'q — chaqiruvchi OLDINDAN
    tekshiradi (409 `tts_not_configured`); bu yerda faqat tarmoq/HTTP xatosi."""
    lang = _LANG_CODES.get(language, _LANG_CODES["uz"])
    data = {
        "text": text, "lang": lang, "voice": voice_for(cfg, language),
        "format": "lpcm", "sampleRateHertz": str(_SAMPLE_RATE),
    }
    # folderId yuborilmaydi: Api-Key = xizmat akkaunti, Yandex hujjati «Do not use this field if you make a request
    # on behalf of a service account» — noto'g'ri katalog 401 «does not match with service account folder» berardi.
    headers = {"Authorization": f"Api-Key {cfg.api_key}"}
    url = f"{settings.tts_yandex_base.rstrip('/')}/speech/v1/tts:synthesize"
    try:
        async with httpx.AsyncClient(timeout=settings.tts_http_timeout_s, transport=transport) as client:
            resp = await client.post(url, data=data, headers=headers)
    except httpx.HTTPError as exc:
        raise TtsError(f"{type(exc).__name__}: {exc}"[:300]) from exc
    if resp.status_code != 200:
        raise TtsError(f"Yandex TTS {resp.status_code}: {resp.text[:200]}")
    return resp.content


def lpcm_ffmpeg_args() -> tuple[str, ...]:
    """`convert_to_wav_8k_mono`ning `input_args` — xom LPCM kodlanmagan oqim
    uchun ffmpeg formatini aniq ko'rsatish shart (konteyner/sarlavha yo'q)."""
    return ("-f", "s16le", "-ar", str(_SAMPLE_RATE), "-ac", "1")
