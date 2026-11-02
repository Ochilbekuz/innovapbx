"""Qo'ng'iroq yo'nalishini ANIQLASH qoidasi — BITTA joyda (ub-mode DRY):
`calls.py` (`/calls`, tugagan CDR) VA `live_status.py` (`/dashboard`, hozirgi
jonli kanallar) ikkisi ham AYNAN BIR XIL qoidani ishlatadi, aks holda
tarix bilan jonli panel bir xil qo'ng'iroqni boshqacha ko'rsatib qolishi mumkin.

Qoida: manba kanal (`channel`) trunk endpoint bo'lsa — qo'ng'iroq TRUNK'dan
KIRGAN (`in`); aks holda manzil kanal (`dstchannel`) trunk bo'lsa — ICHKI
raqamdan trunk orqali CHIQGAN (`out`); aks holda ikkisi ham ichki — `internal`."""
from __future__ import annotations

from typing import Literal

Direction = Literal["in", "out", "internal"]


def classify_direction(channel: str | None, dstchannel: str | None) -> Direction:
    if channel and "-trunk-" in channel:
        return "in"
    if dstchannel and "-trunk-" in dstchannel:
        return "out"
    return "internal"
