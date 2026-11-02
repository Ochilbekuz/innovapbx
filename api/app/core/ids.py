"""UUID yo'l parametrlarini tekshirish — noto'g'ri shakl 500 emas, aniq 404/422
bilan qaytishi kerak (boundary discipline: ma'lumot kirish nuqtasida tekshiriladi)."""
from __future__ import annotations

import uuid

from app.core.errors import ApiError


def parse_uuid(value: str, *, not_found_message: str = "Topilmadi") -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ApiError(404, "not_found", not_found_message) from exc
