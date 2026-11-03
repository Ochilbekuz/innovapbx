"""Audio — m1a-contract.md «Audio (S11 — M1a minimal)»."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_access
from app.core.config import settings
from app.core.errors import ApiError
from app.core.lookups import get_tenant_code, get_tenant_scoped_or_404
from app.db.models import AudioFile, Ivr, MohClass, MohClassFile, Tenant, User, VoicemailBox
from app.schemas import AudioCreated, AudioOut, TtsPreviewPayload, TtsSynthesizePayload
from app.services import tts_yandex
from app.services.audio_tools import ALLOWED_UPLOAD_SUFFIXES, AudioConversionError, convert_to_wav_8k_mono
from app.services.audit import record_audit
from app.services.rate_limit import SlidingWindowLimiter

router = APIRouter(prefix="/audio", tags=["audio"])
_tts_preview_limiter = SlidingWindowLimiter()


def _audio_out(audio: AudioFile) -> AudioOut:
    return AudioOut(id=str(audio.id), name=audio.name, duration_ms=audio.duration_ms,
                     format="wav", created_at=audio.created_at)


def _wav_path(tenant_code: str, audio_id: uuid.UUID) -> Path:
    return Path(settings.sounds_dir) / tenant_code / f"{audio_id}.wav"


@router.get("")
async def list_audio(
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> dict:
    items = (await session.execute(
        select(AudioFile).where(AudioFile.tenant_id == user.tenant_id).order_by(AudioFile.name)
    )).scalars().all()
    return {"items": [_audio_out(a) for a in items]}


@router.post("", response_model=AudioCreated, status_code=201)
async def upload_audio(
    name: str = Form(...), file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> AudioCreated:
    tenant_id = str(user.tenant_id)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        raise ApiError(415, "bad_format", "Qo'llab-quvvatlanmaydigan audio format")

    raw = await file.read(settings.audio_max_upload_bytes + 1)
    if len(raw) > settings.audio_max_upload_bytes:
        raise ApiError(413, "too_large", "Audio fayl juda katta")

    # Avval konvertatsiya (duration_ms shu bilan ma'lum bo'ladi), QATOR FAQAT
    # OXIRIDA flush qilinadi — `duration_ms > 0` CHECK cheklovini qanoatlantiradigan
    # haqiqiy qiymat bilan. Avvalgi versiya `duration_ms=0` bilan erta flush
    # qilardi — bu CHECK'ni HAR DOIM buzardi va natijadagi IntegrityError
    # (noto'g'ri) 409 `name_taken` sifatida ko'rsatilardi: audio yuklash
    # jonli bazaga qarshi HECH QACHON muvaffaqiyatli bo'lmagan edi (jonli
    # DB'da topilgan, 2026-10-28). `id` endi bazadan kutilmay Python tomonda
    # generatsiya qilinadi — fayl yo'li uchun oldindan kerak.
    audio_id = str(uuid.uuid4())
    code = await get_tenant_code(session, tenant_id)
    dst = _wav_path(code, audio_id)
    tmp_src = dst.with_suffix(suffix + ".src")
    tmp_src.parent.mkdir(parents=True, exist_ok=True)
    tmp_src.write_bytes(raw)
    try:
        duration_ms = convert_to_wav_8k_mono(tmp_src, dst)
    except AudioConversionError as exc:
        raise ApiError(415, "bad_format", "Audio faylni o'girishda xato") from exc
    finally:
        tmp_src.unlink(missing_ok=True)

    if duration_ms > settings.audio_max_duration_s * 1000:
        dst.unlink(missing_ok=True)
        raise ApiError(422, "too_long", "Audio fayl ruxsat etilgan uzunlikdan oshib ketdi",
                        details={"max_seconds": settings.audio_max_duration_s})

    audio = AudioFile(id=audio_id, tenant_id=tenant_id, name=name, source="upload",
                       storage_path=f"sounds/{code}/{audio_id}", duration_ms=duration_ms)
    session.add(audio)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        dst.unlink(missing_ok=True)
        raise ApiError(409, "name_taken", "Shu nomli audio allaqachon mavjud", field="name") from exc

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="audio.upload",
                        entity="audio", entity_id=str(audio.id), diff={"name": name})
    await session.commit()
    return AudioCreated(item=_audio_out(audio))


# ------------------------------------------------------------ M10 A3: Yandex SpeechKit TTS
async def _tts_config_or_409(session: AsyncSession, tenant_id: str) -> tts_yandex.TtsConfig:
    cfg = await tts_yandex.load_config(session, tenant_id)
    if cfg.provider == "none" or not cfg.api_key:
        raise ApiError(409, "tts_not_configured", "TTS sozlanmagan — avval Sozlamalar > TTS'da to'ldiring")
    return cfg


async def _tenant_language(session: AsyncSession, tenant_id: str) -> str:
    tenant = await session.get(Tenant, tenant_id)
    return tenant.language if tenant else "uz"


async def _synthesize_wav(cfg: tts_yandex.TtsConfig, text: str, language: str, dst: Path) -> int:
    """LPCM'ni oladi, vaqtinchalik faylga yozadi, WAV'ga o'giradi (`dst`ga)."""
    try:
        lpcm = await tts_yandex.synthesize_lpcm(cfg, text, language)
    except tts_yandex.TtsError as exc:
        raise ApiError(502, "tts_failed", f"TTS so'rovi muvaffaqiyatsiz: {exc}"[:500]) from exc
    tmp_src = dst.with_suffix(".lpcm")
    tmp_src.parent.mkdir(parents=True, exist_ok=True)
    tmp_src.write_bytes(lpcm)
    try:
        return convert_to_wav_8k_mono(tmp_src, dst, tts_yandex.lpcm_ffmpeg_args())
    except AudioConversionError as exc:
        raise ApiError(415, "bad_format", "TTS audio oqimini o'girishda xato") from exc
    finally:
        tmp_src.unlink(missing_ok=True)


@router.post("/tts", response_model=AudioCreated, status_code=201)
async def synthesize_audio(
    payload: TtsSynthesizePayload, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> AudioCreated:
    tenant_id = str(user.tenant_id)
    cfg = await _tts_config_or_409(session, tenant_id)
    language = await _tenant_language(session, tenant_id)

    audio_id = str(uuid.uuid4())
    code = await get_tenant_code(session, tenant_id)
    dst = _wav_path(code, audio_id)
    duration_ms = await _synthesize_wav(cfg, payload.text, language, dst)

    audio = AudioFile(id=audio_id, tenant_id=tenant_id, name=payload.name, language=language, source="tts",
                      tts_text=payload.text, storage_path=f"sounds/{code}/{audio_id}", duration_ms=duration_ms)
    session.add(audio)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        dst.unlink(missing_ok=True)
        raise ApiError(409, "name_taken", "Shu nomli audio allaqachon mavjud", field="name") from exc

    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="audio.tts",
                       entity="audio", entity_id=str(audio.id), diff={"name": payload.name})
    await session.commit()
    return AudioCreated(item=_audio_out(audio))


@router.post("/tts/preview")
async def preview_tts(
    payload: TtsPreviewPayload, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> Response:
    if not _tts_preview_limiter.allow(str(user.id), limit=settings.tts_preview_rate_limit_per_min):
        raise ApiError(429, "rate_limited", "Juda ko'p so'rov — birozdan keyin qayta urining")
    tenant_id = str(user.tenant_id)
    cfg = await _tts_config_or_409(session, tenant_id)
    language = await _tenant_language(session, tenant_id)

    tmp_dst = Path(settings.sounds_dir) / f".tts-preview-{uuid.uuid4()}.wav"
    tmp_dst.parent.mkdir(parents=True, exist_ok=True)
    await _synthesize_wav(cfg, payload.text, language, tmp_dst)
    try:
        wav_bytes = tmp_dst.read_bytes()
    finally:
        tmp_dst.unlink(missing_ok=True)
    return Response(content=wav_bytes, media_type="audio/wav")


@router.get("/{audio_id}/stream")
async def stream_audio(
    audio_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> FileResponse:
    audio = await get_tenant_scoped_or_404(
        session, AudioFile, str(user.tenant_id), audio_id, not_found_message="Audio topilmadi",
    )
    code = await get_tenant_code(session, str(user.tenant_id))
    path = _wav_path(code, audio.id)
    if not path.exists():
        raise ApiError(404, "not_found", "Audio fayli diskda topilmadi")
    return FileResponse(path, media_type="audio/wav", filename=f"{audio.name}.wav")


@router.delete("/{audio_id}", status_code=204, response_model=None)
async def delete_audio(
    audio_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(require_access),
) -> None:
    tenant_id = str(user.tenant_id)
    audio = await get_tenant_scoped_or_404(
        session, AudioFile, tenant_id, audio_id, not_found_message="Audio topilmadi",
    )
    usages = (await session.execute(
        select(Ivr).where(Ivr.tenant_id == tenant_id,
                           (Ivr.greeting_audio_id == audio.id) | (Ivr.invalid_audio_id == audio.id))
    )).scalars().all()
    moh_usages = (await session.execute(
        select(MohClass).join(MohClassFile, MohClassFile.moh_class_id == MohClass.id)
        .where(MohClass.tenant_id == tenant_id, MohClassFile.audio_file_id == audio.id)
    )).scalars().all()
    vm_usages = (await session.execute(
        select(VoicemailBox).where(VoicemailBox.tenant_id == tenant_id, VoicemailBox.greeting_audio_id == audio.id)
    )).scalars().all()
    if usages or moh_usages or vm_usages:
        # `moh_classes.audio_file_id` FK `ondelete="RESTRICT"` — ushbu
        # tekshiruv bo'lmasa, Postgres xatosi (500) chiqardi (M1b MOH
        # haqiqiy Asterisk sinxronidan oldin bu hol hech qachon amalda
        # sinab ko'rilmagan edi — isbot skriptida topilgan).
        raise ApiError(409, "in_use", "Audio ishlatilmoqda", details={
            "usages": [{"kind": "ivr", "id": str(i.id), "label": i.name,
                        "field": "greeting" if i.greeting_audio_id == audio.id else "invalid_audio"}
                       for i in usages] + [
                {"kind": "moh_class", "id": str(m.id), "label": m.name, "field": "file_ids"}
                for m in moh_usages
            ] + [
                {"kind": "voicemail", "id": str(b.id), "label": b.mailbox, "field": "greeting_audio_id"}
                for b in vm_usages
            ],
        })

    code = await get_tenant_code(session, tenant_id)
    path = _wav_path(code, audio.id)
    await session.delete(audio)
    await record_audit(session, tenant_id=tenant_id, user_id=str(user.id), action="audio.delete",
                        entity="audio", entity_id=str(audio_id))
    await session.commit()
    path.unlink(missing_ok=True)
