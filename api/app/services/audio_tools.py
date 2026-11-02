"""Audio fayllar — yuklangan (wav/mp3/ogg/webm — oxirgi ikkisi brauzer
`MediaRecorder`idan, m1b-contract.md bo'lim 8) ffmpeg bilan 8 kHz mono wav'ga
o'giriladi; tizim ovozi esa sof Python bilan generatsiya qilinadi
(Asterisk/FreePBX ovoz fayllari NUSXALANMAYDI — m1a-contract.md S11)."""
from __future__ import annotations

import math
import struct
import subprocess
import wave
from collections.abc import Sequence
from pathlib import Path

ALLOWED_UPLOAD_SUFFIXES = {".wav", ".mp3", ".ogg", ".webm"}


class AudioConversionError(Exception):
    pass


def convert_to_wav_8k_mono(src_path: Path, dst_path: Path, input_args: Sequence[str] = ()) -> int:
    """ffmpeg bilan 8 kHz, mono, 16-bit PCM wav'ga o'giradi. Davomiylikni (ms) qaytaradi.
    `input_args` — sarlavhasiz (raw) manba formatlari uchun ffmpeg kirish bayroqlari
    (masalan FreePBX `.ulaw` -> `-f mulaw -ar 8000 -ac 1`, M5a import)."""
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["ffmpeg", "-y", *input_args, "-i", str(src_path), "-ar", "8000", "-ac", "1", "-sample_fmt", "s16",
         "-f", "wav", str(dst_path)],
        capture_output=True, timeout=30, check=False,
    )
    if result.returncode != 0 or not dst_path.exists():
        raise AudioConversionError(result.stderr.decode("utf-8", "ignore")[-500:])
    return _wav_duration_ms(dst_path)


def _wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate() or 8000
    return max(1, int(frames / rate * 1000))


def synth_tone_wav(
    dst_path: Path, *, freq_hz: float = 440.0, duration_ms: int = 600, sample_rate: int = 8000,
) -> int:
    """Sof-Python sinusoidal ohang — tizim «salomlashuv» namunasi. Oxiri asta
    pasayadi (xirillash bo'lmasin). Davomiylikni (ms) qaytaradi."""
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    n_samples = int(sample_rate * duration_ms / 1000)
    amplitude = 12000
    fade_samples = max(1, int(sample_rate * 0.05))
    frames = bytearray()
    for i in range(n_samples):
        fade = min(1.0, (n_samples - i) / fade_samples)
        sample = int(amplitude * fade * math.sin(2 * math.pi * freq_hz * i / sample_rate))
        frames += struct.pack("<h", sample)
    with wave.open(str(dst_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))
    return duration_ms
