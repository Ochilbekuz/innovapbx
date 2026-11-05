"""Umumiy test himoyasi.

2026-11-04: netd testi `systemctl reboot` / `timedatectl set-ntp` ni HAQIQIY bajarib, pytest
yurgan dev/bot serverini 3 marta qayta yuklagan. Shu sababli testlarda host holatini
o'zgartiradigan binarlarni ishga tushirish butunlay taqiqlangan — kerak bo'lsa test
`app.netd.executor.asyncio.create_subprocess_exec` ni o'zi soxtalashtiradi.
"""
from __future__ import annotations

import asyncio

import pytest

# `ping` host holatini o'zgartirmaydi, lekin testda tashqi tarmoqqa chiqmasin (soxta executor bilan sinaladi).
_HOSTNI_OZGARTIRADI = frozenset(
    {"systemctl", "timedatectl", "nft", "ifup", "ifdown", "reboot", "poweroff", "shutdown", "ping"})


@pytest.fixture(autouse=True)
def _xavfli_buyruqlarni_taqiqlash(monkeypatch):
    haqiqiy = asyncio.create_subprocess_exec

    async def _qoriqchi(*argv, **kwargs):
        if _HOSTNI_OZGARTIRADI.intersection(str(a) for a in argv):
            raise RuntimeError(f"Testda host buyrug'i taqiqlangan: {argv!r}")
        return await haqiqiy(*argv, **kwargs)

    monkeypatch.setattr("app.netd.executor.asyncio.create_subprocess_exec", _qoriqchi)
