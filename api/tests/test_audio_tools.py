"""Audio vositalari — tizim ohangi (sof Python) va ffmpeg o'girish (ffmpeg
mavjud bo'lsa, aks holda `skip`)."""
from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from app.services.audio_tools import ALLOWED_UPLOAD_SUFFIXES, AudioConversionError, convert_to_wav_8k_mono, synth_tone_wav

requires_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg o'rnatilmagan")


def test_allowed_upload_suffixes_includes_browser_recorded_formats():
    """m1b-contract.md bo'lim 8: `POST /audio` brauzerda yozilgan ovoz
    (MediaRecorder) uchun `webm`/`ogg` (opus) qo'shimcha formatlarni
    qabul qilishi SHART."""
    assert ".webm" in ALLOWED_UPLOAD_SUFFIXES
    assert ".ogg" in ALLOWED_UPLOAD_SUFFIXES


def _encode_opus(src_wav: Path, dst: Path, container: str) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src_wav), "-c:a", "libopus", "-f", container, str(dst)],
        check=True, capture_output=True,
    )


@requires_ffmpeg
@pytest.mark.parametrize("suffix,container", [(".ogg", "ogg"), (".webm", "webm")])
def test_convert_to_wav_8k_mono_accepts_opus_encoded_upload(tmp_path: Path, suffix: str, container: str):
    """Regressiya (m1b-contract.md bo'lim 8): brauzer MediaRecorder odatda
    `webm`/`ogg` konteynerida opus kodek bilan yozadi — bu haqiqiy opus
    oqimini (faqat kengaytmani emas) qabul qilishni tasdiqlaydi."""
    src_wav = tmp_path / "src.wav"
    synth_tone_wav(src_wav, duration_ms=500, sample_rate=48000)
    opus_src = tmp_path / f"voice{suffix}"
    _encode_opus(src_wav, opus_src, container)

    dst = tmp_path / "out.wav"
    duration_ms = convert_to_wav_8k_mono(opus_src, dst)
    assert dst.exists()
    assert duration_ms > 0
    with wave.open(str(dst), "rb") as wf:
        assert wf.getframerate() == 8000
        assert wf.getnchannels() == 1


def test_synth_tone_wav_creates_valid_8khz_mono_file(tmp_path: Path):
    dst = tmp_path / "greeting.wav"
    duration = synth_tone_wav(dst, duration_ms=500)
    assert dst.exists()
    assert duration == 500
    with wave.open(str(dst), "rb") as wf:
        assert wf.getframerate() == 8000
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2


def test_synth_tone_wav_duration_matches_frame_count(tmp_path: Path):
    dst = tmp_path / "tone.wav"
    synth_tone_wav(dst, duration_ms=1000, sample_rate=8000)
    with wave.open(str(dst), "rb") as wf:
        assert wf.getnframes() == 8000


@requires_ffmpeg
def test_convert_to_wav_8k_mono_from_higher_rate_source(tmp_path: Path):
    src = tmp_path / "src.wav"
    synth_tone_wav(src, duration_ms=300, sample_rate=44100)
    dst = tmp_path / "out.wav"
    duration_ms = convert_to_wav_8k_mono(src, dst)
    assert dst.exists()
    assert duration_ms > 0
    with wave.open(str(dst), "rb") as wf:
        assert wf.getframerate() == 8000
        assert wf.getnchannels() == 1


@requires_ffmpeg
def test_convert_to_wav_8k_mono_raises_on_bad_input(tmp_path: Path):
    src = tmp_path / "bad.wav"
    src.write_bytes(b"not an audio file at all")
    dst = tmp_path / "out.wav"
    with pytest.raises(AudioConversionError):
        convert_to_wav_8k_mono(src, dst)
