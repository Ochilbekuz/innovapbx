"""Yetkazuvchi modullarini yuklash — har modul import paytida `register_provider(kind, ...)` chaqiradi.

CRM muhandisi: `bitrix24.py`/`amocrm.py` yaratilgach shu ro'yxatga qo'shing (yo'q modul — e'tiborsiz).
"""
from __future__ import annotations

import importlib
import logging

log = logging.getLogger(__name__)

PROVIDER_MODULES = (
    "app.services.integrations.webhook",
    "app.services.integrations.bitrix24",
    "app.services.integrations.amocrm",
)


def load_providers() -> list[str]:
    loaded = []
    for name in PROVIDER_MODULES:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError as exc:
            if exc.name != name:
                raise
            continue
        loaded.append(name)
    log.info("integratsiya yetkazuvchilari: %s", ", ".join(loaded))
    return loaded
