"""Ichki raqam media qarori — WebRTC rejimi va kodeklar (m3a-contract.md §2). Sof funksiya,
YAGONA joy: admin `POST`/`PATCH /extensions` shu orqali o'tadi.

- `codecs` kirishda tekshiriladi (ps_endpoints view'da `array_to_string(codecs, ',')` — `allow`
  satri; vergul/bo'sh nom o'tib ketmasin).
- WebRTC raqamda kodeklar ⊂ brauzer to'plami (DTLS-SRTP/Opus) va kamida bitta → aks holda 422
  `webrtc_codec`.
- WebRTC yoqilayotganda `codecs` berilmasa → `WEBRTC_DEFAULT_CODECS` (Opus birinchi)."""
from __future__ import annotations

import re

from app.core.errors import ApiError

WEBRTC_CODECS = frozenset({"opus", "g722", "ulaw", "alaw"})
WEBRTC_DEFAULT_CODECS = ("opus", "ulaw", "alaw")
_CODEC_RE = re.compile(r"^[a-z0-9_]{2,16}$")


def _validated(requested: list[str], *, webrtc: bool) -> list[str]:
    codecs = list(dict.fromkeys(requested))
    if webrtc and (not codecs or not set(codecs) <= WEBRTC_CODECS):
        raise ApiError(422, "webrtc_codec", "WebRTC raqam kodeklari: opus, g722, ulaw, alaw (kamida bitta)",
                       field="codecs")
    if not codecs or not all(_CODEC_RE.fullmatch(c) for c in codecs):
        raise ApiError(422, "bad_codec", "Kodek nomi noto'g'ri (a-z, 0-9, _; kamida bitta)", field="codecs")
    return codecs


def resolve_codecs(*, webrtc: bool, requested: list[str] | None, current: list[str] | None,
                   switching_on: bool) -> list[str] | None:
    """Saqlanadigan kodeklar ro'yxati; `None` — o'zgarmaydi (yaratishda — DB standarti).
    `webrtc` — natijaviy rejim; `switching_on` — rejim shu so'rovda yoqilmoqda (yaratish ham)."""
    if requested is not None:
        return _validated(requested, webrtc=webrtc)
    if webrtc and switching_on:
        return list(WEBRTC_DEFAULT_CODECS)
    return current
