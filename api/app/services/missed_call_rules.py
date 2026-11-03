"""M10 A2 — o'tkazib yuborilgan qo'ng'iroq bildirishnomasi: SOF (bazasiz) qoidalar.
Bazaga tegadigan qism — `app/services/missed_call_notify.py`.

Manba — `integration_events` outbox (`type='call.ended'`, `payload.call.status='missed'`,
`app/services/integrations/events.py::ended_call`). Qoida moslashtirish — `scope_kind`:
`any` (hammasi), `did` (`call.did`), `queue` (`call.queue.id`), `extension` (`call.extension`
raqami), `ring_group` (guruh a'zolari raqamlaridan BIRI `call.extension`ga mos kelsa —
a'zolar ro'yxati DB'dan, `missed_call_notify.py::_ring_group_numbers`)."""
from __future__ import annotations

SCOPE_KINDS = ("any", "did", "queue", "ring_group", "extension")


def rule_matches(scope_kind: str, scope_value: str | None, call: dict, *,
                 ring_group_numbers: frozenset[str] = frozenset()) -> bool:
    if scope_kind == "any":
        return True
    if not scope_value:
        return False
    if scope_kind == "did":
        return call.get("did") == scope_value
    if scope_kind == "queue":
        queue = call.get("queue") or {}
        return queue.get("id") == scope_value
    if scope_kind == "extension":
        return call.get("extension") == scope_value
    if scope_kind == "ring_group":
        return bool(call.get("extension")) and call["extension"] in ring_group_numbers
    return False


def is_missed(call: dict) -> bool:
    return (call.get("status") or "") == "missed"


_TEXTS: dict[str, str] = {
    "uz": "📵 O'tkazib yuborilgan qo'ng'iroq\nKimdan: {from_}\nQayerga: {to}\nVaqt: {started_at}",
    "ru": "📵 Пропущенный звонок\nОт: {from_}\nНа: {to}\nВремя: {started_at}",
    "en": "📵 Missed call\nFrom: {from_}\nTo: {to}\nTime: {started_at}",
}


def missed_call_text(language: str | None, call: dict) -> str:
    lang = language if language in _TEXTS else "uz"
    return _TEXTS[lang].format(
        from_=call.get("from") or "noma'lum", to=call.get("to") or call.get("did") or "-",
        started_at=call.get("started_at") or "-",
    )


def rule_included(include_internal: bool, direction: str) -> bool:
    """Ichki (extension->extension) qo'ng'iroq — faqat `include_internal=true` bo'lsa."""
    return include_internal or direction != "internal"
