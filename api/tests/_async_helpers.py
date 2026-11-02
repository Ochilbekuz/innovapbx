"""Testlar uchun umumiy yordamchi — bir nechta test faylida takrorlanmasin (ub-mode dryer)."""
from __future__ import annotations


def const_async(value):
    """Har doim `value`ni qaytaradigan async funksiya — `monkeypatch.setattr` bilan
    biror async servis funksiyasini soxtalashtirish uchun."""
    async def _inner(*args, **kwargs):
        return value
    return _inner
