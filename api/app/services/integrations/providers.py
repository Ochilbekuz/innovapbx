"""Yetkazuvchilar reyestri — outbox dispetcheri FAQAT shu interfeys orqali gaplashadi.

Yangi yetkazuvchi (masalan `bitrix24.py`) qo'shish:

    from app.services.integrations.providers import DeliveryResult, register_provider

    class Bitrix24Provider:
        async def deliver(self, ctx: DeliveryContext) -> DeliveryResult: ...

    register_provider("bitrix24", Bitrix24Provider())

va modulni `app/services/integrations/registry.py` dagi `load_providers()` ga import qiling.
`kind` `integration_subscriptions.kind` CHECK ro'yxatida bo'lishi shart (0018 migratsiya).

`DeliveryResult` semantikasi (VoxBridge ADR-003 saboqlari):
  ok=True                 → `delivered`.
  retry_after_s=N         → rate-limit: N s dan keyin qayta, urinish SANALMAYDI.
  permanent=True          → darhol `dead` (masalan 400 noto'g'ri so'rov, SSRF taqiq).
  aks holda               → vaqtinchalik xato: urinish sanaladi, jadval bo'yicha qayta (oxiri `dead`).
`error` — admin ko'radigan qisqa matn (sirlar `***` bilan niqoblangan bo'lishi SHART).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class DeliveryResult:
    ok: bool
    status_code: int | None = None
    retry_after_s: float | None = None
    error: str | None = None
    permanent: bool = False
    response_body: str | None = None


@dataclass(frozen=True)
class SubscriptionView:
    """Obuna — yetkazuvchiga beriladigan ko'rinish (`secret` ochilgan, faqat xotirada)."""
    id: str
    tenant_id: str
    kind: str
    name: str
    config: dict[str, Any] = field(default_factory=dict)
    secret: str | None = None


@dataclass(frozen=True)
class EventView:
    """`integration_events` qatori: `payload` — §2 yagona model (`id`, `type`, `occurred_at`, `call`)."""
    id: str
    type: str
    call_id: str | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class DeliveryContext:
    """Bitta yetkazish: `session` — CRM yetkazuvchilari o'z jadvallari (`crm_call_links`,
    foydalanuvchi xaritasi) uchun ishlatadi; tranzaksiyani dispetcher yakunlaydi (commit qilmang)."""
    delivery_id: str
    attempt: int
    subscription: SubscriptionView
    event: EventView
    session: AsyncSession


class Provider(Protocol):
    async def deliver(self, ctx: DeliveryContext) -> DeliveryResult: ...


_REGISTRY: dict[str, Provider] = {}


def register_provider(kind: str, provider: Provider) -> None:
    _REGISTRY[kind] = provider


def get_provider(kind: str) -> Provider | None:
    return _REGISTRY.get(kind)


async def deliver(kind: str, ctx: DeliveryContext) -> DeliveryResult:
    """Reyestr orqali yetkazish; noma'lum `kind` — doimiy xato (navbatni to'smaydi)."""
    provider = get_provider(kind)
    if provider is None:
        return DeliveryResult(ok=False, error=f"provider_not_registered:{kind}", permanent=True)
    return await provider.deliver(ctx)
