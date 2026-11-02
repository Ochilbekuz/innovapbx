"""M2a §2: xususiyat kodlarini tekshirish (sof funksiyalar, DB'siz).

Kod `^\\*[0-9*#]{1,6}$`. To'qnashuv: boshqa xususiyat kodi bilan teng yoki biri
ikkinchisining PREFIKSI (`*7` va `*72`) — 409 `code_taken`. Vaqt sharti almashtirish
kodlari (`toggle_code`) — faqat tenglik (ular aniq exten, pattern emas)."""
from __future__ import annotations

import re
from collections.abc import Iterable

from app.core.errors import ApiError

CODE_RE = re.compile(r"^\*[0-9*#]{1,6}$")


def _prefix_clash(code: str, other: str) -> bool:
    return code.startswith(other) or other.startswith(code)


def validate_feature_code(code: str, other_feature_codes: Iterable[str], toggle_codes: Iterable[str] = ()) -> None:
    if not CODE_RE.fullmatch(code):
        raise ApiError(422, "bad_code", "Kod `*` bilan boshlanadi: *, # va raqamlar, 2–7 belgi", field="code")
    clash = next((o for o in other_feature_codes if _prefix_clash(code, o)), None)
    if clash is None:
        clash = next((t for t in toggle_codes if t == code), None)
    if clash is not None:
        raise ApiError(409, "code_taken", "Bu kod boshqa funksiya bilan to'qnashadi", field="code",
                       details={"conflict": clash})
