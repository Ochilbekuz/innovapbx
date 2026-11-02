"""Texnik xizmat rejimi — tiklash paytida (m4b-contract.md §0):
"boshqa API so'rovlari 503 `maintenance`, `/healthz` va `/backups/jobs/{id}` ochiq,
fon vazifalari pauza".

Yagona, jarayon darajasidagi ulashiladigan bayroq (`state.enabled`) — HTTP
middleware (`maintenance_middleware`, `app/main.py`da ulanadi) va oddiy
`while True: ... sleep(...)` naqshli fon vazifalar (`vm_notify`/`sip_guard`/
`trunk_monitor`/`recordings`/`integrations.dispatch`/`prov` tozalovchisi) buni
o'qiydi; `restore_job.py` yozadi.

`call_events.py`ning AMI tinglovchisi (uzluksiz ulanish — oddiy daqiqa-siljish
TSIKLI EMAS, `asyncio.gather` bilan tinglovchi/iste'molchi/supurgich) BU YERGA
ULANMAGAN: `pg_restore --single-transaction` allaqachon tiklash tranzaksiyasi
paytida yozilayotgan har qanday jadvalni DB DARAJASIDA bloklaydi (qulf kutish —
xavfsiz, ma'lumot buzilishi EMAS), shu sabab uni to'xtatish ortiqcha murakkablik
qo'shadi, xavfsizlikka hech narsa qo'shmaydi.

Starlette'da `register_exception_handlers` (`ExceptionMiddleware`) har qanday
`app.middleware("http")` qatlamidan ICHKARIDA ishlaydi — shu sabab bu middleware
`ApiError` KO'TARMAYDI (formatlanmagan javob qaytaradi), balki `ApiError.body()`
shakliga mos `JSONResponse`ni TO'G'RIDAN-TO'G'RI quradi."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_JOB_STATUS_RE = re.compile(r"^/api/v1/backups/jobs/[^/]+$")


@dataclass
class MaintenanceState:
    enabled: bool = False


state = MaintenanceState()


def is_open_path(method: str, path: str) -> bool:
    """`/healthz` va `GET /api/v1/backups/jobs/{id}` texnik xizmat rejimida ham
    ishlashi SHART (progress kuzatish, konteyner tayyorlik tekshiruvi)."""
    if method != "GET":
        return False
    return path == "/healthz" or bool(_JOB_STATUS_RE.match(path))


async def maintenance_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if state.enabled and not is_open_path(request.method, request.url.path):
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "maintenance", "message": "Tizim tiklanish jarayonida"}},
        )
    return await call_next(request)
