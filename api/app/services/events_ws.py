"""M10 Bo'lak B3 — tashqi WebSocket hodisalar, sof qoidalar.

`ConnectionLimiter` va `event_matches`/`validate_subscribe`/`clamp_since_seq`
tarmoqsiz, DB'siz — ulanish registri va poll tsikli (`app/api/public_events_ws.py`)
shu funksiyalarni chaqiradi. Chegaralar shartnoma bo'yicha: 5 ulanish/kalit,
50/tenant, `since_seq` replay ko'pi bilan 1000 hodisa/24 soat."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

MAX_REPLAY_EVENTS = 1000
MAX_REPLAY_AGE = timedelta(hours=24)
MAX_CONNECTIONS_PER_KEY = 5
MAX_CONNECTIONS_PER_TENANT = 50

CLOSE_TOO_MANY_CONNECTIONS = 4429
CLOSE_FORBIDDEN_SCOPE = 4403
CLOSE_UNAUTHORIZED = 4401


def event_matches(subscribed_types: tuple[str, ...], event_type: str) -> bool:
    """`["*"]` — hammasi; aks holda ro'yxatda bo'lishi kerak."""
    return "*" in subscribed_types or event_type in subscribed_types


def wants_ws_event(subscribed_types: tuple[str, ...], include_internal: bool, event_type: str,
                   *, internal: bool) -> bool:
    """`outbox.wants_event()` bilan BIR XIL ichki-hodisa qoidasi (faqat
    `include_internal` so'ralsa yetkaziladi), CRM istisnosiz — WS'da faqat
    bitta obunachi turi bor."""
    if internal and not include_internal:
        return False
    return event_matches(subscribed_types, event_type)


def validate_subscribe(types: list[str] | None) -> tuple[str, ...] | None:
    """Mijoz yuborgan obuna ro'yxatini tekshiradi. Bo'sh/`None` -> hammasi
    (`("*",)`). Noto'g'ri (bo'sh satr) kirsa -> `None` (xato)."""
    if not types:
        return ("*",)
    cleaned = [t.strip() for t in types]
    if any(not t for t in cleaned):
        return None
    return tuple(cleaned)


def clamp_since_seq(since_seq: int | None, latest_seq: int) -> int | None:
    """`since_seq`ni 1000 hodisadan ko'p bo'lmasligi uchun qisqartiradi
    (quyi chegara bilan) — `None` bo'lsa replay yo'q."""
    if since_seq is None:
        return None
    floor = max(0, latest_seq - MAX_REPLAY_EVENTS)
    return max(since_seq, floor)


def replay_cutoff(now: datetime) -> datetime:
    return now.astimezone(timezone.utc) - MAX_REPLAY_AGE


@dataclass
class ConnectionLimiter:
    """Xotiradagi ulanishlar hisobi (bir-process, 1 Uvicorn worker). Faqat
    hisoblash — WS obyektlarini saqlamaydi (chaqiruvchi registrda saqlaydi)."""

    per_key: dict[str, int] = field(default_factory=dict)
    per_tenant: dict[str, int] = field(default_factory=dict)

    def can_connect(self, *, key_id: str, tenant_id: str) -> bool:
        return (self.per_key.get(key_id, 0) < MAX_CONNECTIONS_PER_KEY
                and self.per_tenant.get(tenant_id, 0) < MAX_CONNECTIONS_PER_TENANT)

    def register(self, *, key_id: str, tenant_id: str) -> None:
        self.per_key[key_id] = self.per_key.get(key_id, 0) + 1
        self.per_tenant[tenant_id] = self.per_tenant.get(tenant_id, 0) + 1

    def release(self, *, key_id: str, tenant_id: str) -> None:
        if key_id in self.per_key:
            self.per_key[key_id] = max(0, self.per_key[key_id] - 1)
            if self.per_key[key_id] == 0:
                del self.per_key[key_id]
        if tenant_id in self.per_tenant:
            self.per_tenant[tenant_id] = max(0, self.per_tenant[tenant_id] - 1)
            if self.per_tenant[tenant_id] == 0:
                del self.per_tenant[tenant_id]
