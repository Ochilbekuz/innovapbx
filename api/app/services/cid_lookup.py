"""M9 B2 — CID Lookup manbalari: `phonebook` (ichki telefon kitobi), `http`
(tashqi HTTP manba, SSRF tekshiruvi bilan) va `crm` (M-CRM §3 — Bitrix24
`searchCrmEntities` orqali, `crm_route.py`) dispetcherlashtirish + natija
tozalash + jarayon ichidagi TTL keshi (`cache_ttl_s` — manba sozlamasi).

`crm` turi `app.services.crm_route`ni KECHIKTIRILGAN import qiladi (aylanma
import yo'q — `crm_route` bu modulni import qilmaydi, lekin ehtiyot chorasi)."""
from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CidLookupSource, PhonebookContact, PhonebookNumber
from app.services.integrations import ssrf
from app.services.number_normalize import normalize_number

_MAX_NAME_LEN = 40
_STRIP_CHARS = str.maketrans("", "", '";,\n\r')


def sanitize_name(raw: str) -> str:
    """Dialplan `CALLERID(name)`ga xavfsiz: tirnoq/vergul/nokta-vergul/qator
    ko'chirish olib tashlanadi, uzunlik `_MAX_NAME_LEN`gacha kesiladi."""
    return raw.translate(_STRIP_CHARS).strip()[:_MAX_NAME_LEN]


class TTLCache:
    """Jarayon ichidagi oddiy TTL kesh — `cache_ttl_s=0` keshlanmaydi degani."""

    def __init__(self, clock: Callable[[], float] = time.monotonic, *, max_items: int = 10_000) -> None:
        self._clock = clock
        self._max_items = max_items
        self._store: OrderedDict[tuple[str, str], tuple[float, str | None]] = OrderedDict()

    def get(self, key: tuple[str, str]) -> tuple[bool, str | None]:
        entry = self._store.get(key)
        if entry is None:
            return False, None
        expires_at, value = entry
        if self._clock() >= expires_at:
            del self._store[key]
            return False, None
        return True, value

    def set(self, key: tuple[str, str], value: str | None, ttl_s: int) -> None:
        if ttl_s <= 0:
            return
        self._store[key] = (self._clock() + ttl_s, value)
        self._store.move_to_end(key)
        while len(self._store) > self._max_items:
            self._store.popitem(last=False)


cache = TTLCache()


def _extract_json_path(data: object, path: str) -> object:
    """`"data.name"` kabi nuqta bilan ajratilgan yo'l; ro'yxat elementi uchun
    butun indeks ham qo'llab-quvvatlanadi (`"items.0.name"`). Topilmasa `None`."""
    current = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.lstrip("-").isdigit():
            idx = int(part)
            current = current[idx] if -len(current) <= idx < len(current) else None
        else:
            return None
    return current


async def _lookup_phonebook(session: AsyncSession, tenant_id: str, num: str) -> str | None:
    norm = normalize_number(num)
    if not norm:
        return None
    row = (await session.execute(
        select(PhonebookContact.name)
        .join(PhonebookNumber, PhonebookNumber.contact_id == PhonebookContact.id)
        .where(PhonebookNumber.tenant_id == tenant_id, PhonebookNumber.number_norm == norm)
        .limit(1)
    )).first()
    return sanitize_name(row[0]) if row else None


async def _lookup_http_detailed(
    source: CidLookupSource, num: str, *, transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[str | None, str | None]:
    """`(name, error)` — `/cid-sources/{id}/test` sababni ko'rsatishi uchun;
    `_lookup_http` (dialplan yo'li) xatoni jim yutadi (shu funksiyani chaqiradi, dryer)."""
    if not source.http_url:
        return None, "no_url"
    url = source.http_url.replace("{number}", num)
    try:
        ssrf.check_url_default(url)
    except ssrf.UrlForbidden as exc:
        return None, f"forbidden_url:{exc.reason}"
    timeout_s = max(source.timeout_ms, 1) / 1000.0
    try:
        async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=False, transport=transport) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            return None, f"http_{resp.status_code}"
        data = resp.json()
    except httpx.TimeoutException:
        return None, "timeout"
    except (httpx.HTTPError, ValueError) as exc:
        return None, f"http_error:{exc}"
    value = _extract_json_path(data, source.http_json_path) if source.http_json_path else data
    if not value:
        return None, "not_found"
    return sanitize_name(str(value)), None


async def _lookup_http(
    source: CidLookupSource, num: str, *, transport: httpx.AsyncBaseTransport | None = None,
) -> str | None:
    name, _error = await _lookup_http_detailed(source, num, transport=transport)
    return name


async def _lookup_crm(
    session: AsyncSession, tenant_id: str, num: str, *, transport: httpx.AsyncBaseTransport | None = None,
) -> str | None:
    """M-CRM §3: tenant'ning YOQILGAN bitrix24 obunasi orqali — obuna/webhook
    yo'q bo'lsa `None` (fail-open, `crm_route.py` o'zi ham fail-open)."""
    from app.services import crm_route, crm_settings  # kechiktirilgan — aylanma importsiz
    from app.services.crm_settings import read_secrets
    from app.services.integrations.bitrix24 import BitrixSettings

    sub = await crm_route.enabled_subscription(session, tenant_id)
    if sub is None:
        return None
    secrets = await read_secrets(session, sub)
    if not crm_settings.is_configured(sub.kind, sub.config or {}, secrets):
        return None
    settings = BitrixSettings.parse(sub.config or {}, secrets)
    result = await crm_route.route_for_number(session, sub, settings, num, transport=transport)
    return result.name


async def lookup_name(
    session: AsyncSession, tenant_id: str, source: CidLookupSource, num: str,
    *, transport: httpx.AsyncBaseTransport | None = None,
) -> str | None:
    """Manba turiga qarab dispetcherlaydi (`phonebook`/`http`/`crm`); noma'lum tur — `None`."""
    if not source.enabled:
        return None
    key = (str(source.id), num)
    hit, cached = cache.get(key)
    if hit:
        return cached

    if source.kind == "phonebook":
        name = await _lookup_phonebook(session, tenant_id, num)
    elif source.kind == "http":
        name = await _lookup_http(source, num, transport=transport)
    elif source.kind == "crm":
        name = await _lookup_crm(session, tenant_id, num, transport=transport)
    else:
        name = None

    cache.set(key, name, source.cache_ttl_s)
    return name


async def test_lookup(
    session: AsyncSession, tenant_id: str, source: CidLookupSource, num: str,
    *, transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[str | None, int, str | None]:
    """`/cid-sources/{id}/test {number}` — jonli chaqiruv, TTL keshni CHETLAB o'tadi,
    `(name, ms, error)` qaytaradi (`lookup_name` esa dialplan uchun sababsiz `None`)."""
    started = time.monotonic()
    if source.kind == "phonebook":
        name = await _lookup_phonebook(session, tenant_id, num)
        error = None if name else "not_found"
    elif source.kind == "http":
        name, error = await _lookup_http_detailed(source, num, transport=transport)
    elif source.kind == "crm":
        name = await _lookup_crm(session, tenant_id, num, transport=transport)
        error = None if name else "not_found"
    else:
        name, error = None, "unknown_kind"
    ms = int((time.monotonic() - started) * 1000)
    return name, ms, error
