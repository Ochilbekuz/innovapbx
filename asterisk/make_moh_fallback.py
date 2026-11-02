#!/usr/bin/env python3
"""Build vaqtida ishga tushadi (Dockerfile RUN) — doimiy, HAR DOIM ishlaydigan
fallback MOH fayli (`/var/lib/asterisk/moh-fallback/tone.wav`) generatsiya
qiladi, SOF Python (`wave`, hech qanday ffmpeg/sox shart emas — asterisk
image'da ular yo'q).

NEGA kerak (haqiqiy topilgan Asterisk xatosi, 2026-10-28): `res_musiconhold`
birinchi marta NOLTA (0) ishlaydigan sinf bilan yuklansa (katalogda birorta
ham o'ynaladigan fayl yo'q), modul butunlay "disabled" holatiga o'tadi va
SHU HOLATDAN keyingi `moh reload`/AMI `Command: moh reload` ham chiqa
OLMAYDI (faqat to'liq `module unload`+`load`, bu esa AMI'dan taqiqlangan/
xavfli). Demak agar Asterisk birinchi marta ishga tushganda (API hali hech
qanday MOH sinfini yaratmagan bo'lsa ham) musiconhold.conf'da KAMIDA bitta
HAQIQIY faylli sinf bo'lmasa — `app/services/moh.py` `apply_moh()`dagi AMI
`moh reload` keyinchalik HECH QACHON muvaffaqiyatli bo'lmaydi (m1b-proof.sh
orqali topilgan)."""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

DEST = Path("/var/lib/asterisk/moh-fallback/tone.wav")
SAMPLE_RATE = 8000
DURATION_S = 2.0
FREQ_HZ = 440.0
AMPLITUDE = 8000


def main() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    n_samples = int(SAMPLE_RATE * DURATION_S)
    fade_samples = max(1, int(SAMPLE_RATE * 0.05))
    frames = bytearray()
    for i in range(n_samples):
        fade = min(1.0, (n_samples - i) / fade_samples, i / fade_samples + 0.001)
        sample = int(AMPLITUDE * fade * math.sin(2 * math.pi * FREQ_HZ * i / SAMPLE_RATE))
        frames += struct.pack("<h", sample)
    with wave.open(str(DEST), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(bytes(frames))


if __name__ == "__main__":
    main()
