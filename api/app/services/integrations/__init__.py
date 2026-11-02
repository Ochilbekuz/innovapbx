"""M3b — integratsiyalar: hodisalar outbox'i va yetkazuvchilar (replica/m3b-contract.md §0–§4).

Oqim: `events.py` (sof payload) → `outbox.py` (hodisa + har obuna uchun yetkazish qatori,
bitta tranzaksiyada) → `dispatch.py` (fon vazifa, `FOR UPDATE SKIP LOCKED`) →
`providers.py` reyestri (`webhook.py`; CRM muhandisi `bitrix24.py`/`amocrm.py` qo'shadi).
"""
