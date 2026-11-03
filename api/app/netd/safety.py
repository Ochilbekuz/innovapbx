"""Render qatlami uchun so'nggi himoya chizig'i (m8-network-contract.md
xavfsizlik eslatmasi: CRLF/NUL in'eksiyasi). `netd` API'dan kelgan hech
narsaga ishonmaydi — `validate.py` struktura qoidalarini tekshiradi, bu
modul esa HAR qanday render qilingan qatorni, qaysi maydondan kelganidan
qat'i nazar, `/etc/network/interfaces`/`resolv.conf`/`hostname`/`hosts`ga
yozilishidan OLDIN yana bir bor tekshiradi (ikkinchi, mustaqil chiziq)."""
from __future__ import annotations

_FORBIDDEN_CHARS = ("\r", "\n", "\x00")


class UnsafeRenderError(ValueError):
    """Render qilinadigan qatorda taqiqlangan boshqaruv belgisi topildi."""


def assert_renderable(raw: str) -> None:
    """`raw` konfiguratsiya fayliga/buyruqqa shu ko'rinishda yoziladi —
    ichida qator ko'chirish (`\\r`/`\\n`) yoki NUL bo'lsa in'eksiya imkoni
    tug'iladi (masalan yangi `pre-up`/`up` qatori)."""
    if any(ch in raw for ch in _FORBIDDEN_CHARS):
        raise UnsafeRenderError(f"xavfli boshqaruv belgisi aniqlandi: {raw!r}")
