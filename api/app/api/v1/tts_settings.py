"""M10 A3 — TTS sozlamalari (Yandex SpeechKit), faqat admin (`apps:edit`).
`GET/PATCH /settings/tts` + `POST /settings/tts/test` — `notify_settings.py`
BILAN BIR XIL qolip (create-or-update + optimistik qulf, sir hech qachon
qaytarilmaydi, PATCH'da berilmagan maydon o'zgarmaydi, `api_key=""` — o'chirish)."""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_access
from app.core.errors import ApiError
from app.core.optimistic import check_not_stale
from app.db.models import TtsSettings, User
from app.schemas import TtsSettingsMutated, TtsSettingsOut, TtsTestResult, UpdateTtsSettingsPayload
from app.services import tts_yandex
from app.services.audit import record_audit
from app.services.crypto import encrypt_secret

router = APIRouter(prefix="/settings/tts", tags=["settings"])

_DEFAULTS = SimpleNamespace(provider="none", api_key_enc=None, folder_id=None,
                            voices={"uz": "nigora", "ru": "alena", "en": "john"})


def _out(row: TtsSettings | None) -> TtsSettingsOut:
    src = row or _DEFAULTS
    return TtsSettingsOut(provider=src.provider, has_api_key=bool(src.api_key_enc), folder_id=src.folder_id,
                          voices=src.voices, updated_at=row.updated_at if row else None)


@router.get("", response_model=TtsSettingsOut)
async def get_tts_settings(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> TtsSettingsOut:
    return _out(await session.get(TtsSettings, str(user.tenant_id)))


@router.patch("", response_model=TtsSettingsMutated)
async def update_tts_settings(
    payload: UpdateTtsSettingsPayload, session: AsyncSession = Depends(get_session),
    user: User = Depends(require_access),
) -> TtsSettingsMutated:
    tenant_id = str(user.tenant_id)
    row = await session.get(TtsSettings, tenant_id)
    if row is None:
        row = TtsSettings(tenant_id=tenant_id)
        session.add(row)
    elif payload.updated_at is not None:
        check_not_stale(row.updated_at, payload.updated_at)

    diff: dict = {}
    if payload.provider is not None:
        row.provider, diff["provider"] = payload.provider, payload.provider
    if payload.folder_id is not None:
        row.folder_id, diff["folder_id"] = payload.folder_id, payload.folder_id
    if payload.voices is not None:
        row.voices, diff["voices"] = payload.voices, payload.voices
    if payload.api_key is not None:
        row.api_key_enc = await encrypt_secret(session, payload.api_key) if payload.api_key else None
        diff["api_key"] = payload.api_key  # record_audit -> "***"

    await session.flush()
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="tts_settings.update",
                       entity="tts_settings", entity_id=tenant_id, diff=diff)
    await session.commit()
    await session.refresh(row)
    return TtsSettingsMutated(item=_out(row))


@router.post("/test", response_model=TtsTestResult)
async def test_tts_settings(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> TtsTestResult:
    cfg = await tts_yandex.load_config(session, str(user.tenant_id))
    if cfg.provider == "none" or not cfg.api_key:
        raise ApiError(409, "tts_not_configured", "TTS sozlanmagan")
    try:
        await tts_yandex.synthesize_lpcm(cfg, "Salom, bu sinov xabari", "uz")
    except tts_yandex.TtsError as exc:
        raise ApiError(502, "tts_failed", f"TTS so'rovi muvaffaqiyatsiz: {exc}"[:500]) from exc
    return TtsTestResult(ok=True, message="Muvaffaqiyatli")
