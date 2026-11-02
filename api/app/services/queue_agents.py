"""Navbat agent holati — BITTA yozish yo'li (m2b-contract.md §0/§1).

Admin endpointlari (`api/v1/queues.py`) VA kelajakdagi `/me/queues` portal
endpointlari (§4, keyingi agentning ishi) shu funksiyalarni QAYTA ISHLATADI —
ikkinchi mustaqil yozish mantiqi YO'Q (dryer).

Yagona haqiqat manbai — `queue_members` jadvali (PG). Bu yerdagi to'g'ridan-
to'g'ri ORM yozuvi telefon *45/*46'ning `Set(REALTIME(agent_state,...))`
yozuvi BILAN TENG KUCHGA EGA (ikkisi ham oxir-oqibat `queue_members`ga tegadi,
0015_m2b_agent_state.sql). AstDB/AMI `QueueAdd`/`QueueRemove` ISHLATILMAYDI —
bu yerda AMI FAQAT jonli "turtki" (pauza holati allaqachon yozilgandan keyin
Asterisk xotirasini sinxronlash, m2b-contract.md §0: "≤ 3 s").

Manba belgisi (`agent_events.source`) — tranzaksiya-lokal GUC orqali
(`queue_members_log_agent_event` trigger o'qiydi). ORM autoflush tartib
saboq (M2a): `set_config(...)` har doim ATTRIBUT o'zgarishidan OLDIN
bajariladi, aks holda trigger yozuvdan OLDINGI (sukut "phone") qiymatni ko'radi."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.db.models import QueueMember
from app.services.apply import AmiLike

Source = str  # "admin" | "portal" — "phone" faqat dialplan *-kod yo'li uchun.


async def set_agent_event_source(session: AsyncSession, source: Source) -> None:
    await session.execute(text("select set_config('innova.agent_event_source', :s, true)"), {"s": source})


def _require_dynamic(member: QueueMember) -> None:
    if not member.dynamic:
        raise ApiError(409, "not_dynamic", "A'zo dinamik emas — login/logout faqat dinamik a'zoga tegishli",
                        field="extension_id")


async def _set_logged_in(session: AsyncSession, member: QueueMember, *, source: Source, value: bool) -> None:
    """`login_member`/`logout_member` — BITTA yo'l (dryer): ikkisi ham shu
    yagona o'tishni chaqiradi, farqi faqat `value`."""
    _require_dynamic(member)
    await set_agent_event_source(session, source)
    member.logged_in = value


async def login_member(session: AsyncSession, member: QueueMember, *, source: Source) -> None:
    await _set_logged_in(session, member, source=source, value=True)


async def logout_member(session: AsyncSession, member: QueueMember, *, source: Source) -> None:
    await _set_logged_in(session, member, source=source, value=False)


async def _set_paused(
    session: AsyncSession, member: QueueMember, *, source: Source, value: bool, reason: str | None,
) -> None:
    """`pause_member`/`unpause_member` — BITTA yo'l (dryer)."""
    await set_agent_event_source(session, source)
    member.paused = value
    member.pause_reason = reason if value else None


async def pause_member(session: AsyncSession, member: QueueMember, *, source: Source, reason: str | None) -> None:
    await _set_paused(session, member, source=source, value=True, reason=reason)


async def unpause_member(session: AsyncSession, member: QueueMember, *, source: Source) -> None:
    await _set_paused(session, member, source=source, value=False, reason=None)


def queue_interface(tenant_code: str, number: str) -> str:
    return f"PJSIP/{tenant_code}-{number}"


def queue_asterisk_name(tenant_code: str, queue_id: str) -> str:
    return f"{tenant_code}-q-{queue_id}"


async def nudge_pause_state(
    ami: AmiLike, *, tenant_code: str, number: str, queue_id: str, paused: bool, reason: str | None,
) -> None:
    """PG yozilgandan KEYIN chaqiriladi — Asterisk xotirasidagi navbat holatini
    darhol sinxronlaydi (m2b-contract.md §0: kutayotgan qo'ng'iroq uchun ≤ 3 s).
    AMI mavjud bo'lmasa/xato — jim o'tkazib yuboriladi (PG allaqachon haqiqiy
    holat yozib qo'ygan, bu FAQAT tezlashtiruvchi turtki, funksional emas)."""
    try:
        await ami.ensure_connected()
        await ami.action(
            "QueuePause", Interface=queue_interface(tenant_code, number),
            Paused="true" if paused else "false", Queue=queue_asterisk_name(tenant_code, queue_id),
            Reason=reason,
        )
    except Exception:  # noqa: BLE001 — qasddan keng: bu faqat tezlashtiruvchi turtki
        pass
