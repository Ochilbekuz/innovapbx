"""Umumiy netd xato turi — `service.py`/`systemtime.py`/`power.py`/`firewall.py`
orasida AYLANMA IMPORT bo'lmasligi uchun alohida, mustaqil modul (hech narsa
import qilmaydi)."""
from __future__ import annotations


class NetdError(Exception):
    def __init__(self, code: str, message: str, fields: list[dict] | None = None) -> None:
        self.code = code
        self.message = message
        self.fields = fields or []
        super().__init__(message)
