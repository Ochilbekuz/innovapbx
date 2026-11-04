"""`netd` javoblarini (`{"ok": bool, "result"|"error": ...}`) FastAPI `ApiError`
javobiga aylantiruvchi umumiy yordamchi — `system_time.py`, `system_power.py`,
`firewall.py` bir xil naqshni ishlatadi (M12 B1/B2/B3). `network.py` bu
yordamchidan OLDIN yozilgan (1.0.8) va o'z nusxasini saqlaydi — M12 doirasidan
tashqari, qasddan tegilmagan."""
from __future__ import annotations

from typing import Any

from app.core.errors import ApiError
from app.services.netd_client import NetdClient, NetdUnavailableError

DEFAULT_ERROR_STATUS = {
    # `readonly` — M12 B1/B2/B3 shartnomasi (`../../replica/m12-contract.md`
    # §B1: "yozish 409 `readonly`") — 503 EMAS, chunki bu vaqtinchalik emas,
    # ataylab o'chirilgan konfiguratsiya holati (dev server himoyasi).
    "readonly": 409, "pending_exists": 409, "invalid_config": 422, "not_found": 404, "bad_request": 400,
}


def raise_for_netd_error(error: dict[str, Any], error_status: dict[str, int] = DEFAULT_ERROR_STATUS) -> None:
    code = error.get("code", "bad_request")
    fields = error.get("fields") or []
    raise ApiError(error_status.get(code, 400), code, error.get("message", "Xato"),
                    details={"fields": fields} if fields else None)


async def call_netd(
    client: NetdClient, op: str, error_status: dict[str, int] = DEFAULT_ERROR_STATUS, **kwargs: Any,
) -> dict[str, Any]:
    try:
        response = await getattr(client, op)(**kwargs)
    except NetdUnavailableError:
        raise ApiError(503, "helper_unavailable", "netd bilan aloqa yo'q") from None
    if not response.get("ok", False):
        raise_for_netd_error(response.get("error") or {}, error_status)
    return response["result"]
