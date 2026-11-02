"""Asterisk/DB «sog'lik» tekshiruvi — BITTA joyda (ub-mode DRY):
`GET /system/health` VA `GET /dashboard` ikkisi ham AYNAN BIR XIL qoidani
ishlatadi (m0-contract.md «Tizim», m1b-contract.md bo'lim 5)."""
from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import AsteriskHealth
from app.services.live_status import run_command

_UPTIME_RE = re.compile(r"System uptime:\s*(.+)")
_VERSION_RE = re.compile(r"Asterisk\s+(\S+)")


async def db_up(session: AsyncSession) -> bool:
    try:
        await session.execute(text("select 1"))
    except SQLAlchemyError:
        return False
    return True


async def asterisk_health(ami) -> AsteriskHealth:
    output = await run_command(ami, "core show uptime")
    if output is None:
        return AsteriskHealth(up=False, version=None, uptime_s=None)
    version_output = await run_command(ami, "core show version")
    version = None
    if version_output:
        m = _VERSION_RE.search(version_output)
        version = m.group(1) if m else None
    return AsteriskHealth(up=True, version=version, uptime_s=_parse_uptime_seconds(output))


def _parse_uptime_seconds(output: str) -> int | None:
    m = _UPTIME_RE.search(output)
    if not m:
        return None
    text_value = m.group(1).strip()
    days = re.search(r"(\d+)\s+day", text_value)
    hours = re.search(r"(\d+)\s+hour", text_value)
    minutes = re.search(r"(\d+)\s+minute", text_value)
    seconds = re.search(r"(\d+)\s+second", text_value)
    total = 0
    if days:
        total += int(days.group(1)) * 86400
    if hours:
        total += int(hours.group(1)) * 3600
    if minutes:
        total += int(minutes.group(1)) * 60
    if seconds:
        total += int(seconds.group(1))
    return total
