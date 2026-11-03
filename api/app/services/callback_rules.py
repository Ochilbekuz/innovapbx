"""M10 A1 — qayta chaqirish vidjeti: sof qoidalar (bazasiz). m10-onlinepbx-contract.md §A1.

Ikki bosqichli terish (`app/services/dialplan_callback.py` kontekstlari bilan birga o'qiladi):
1) AMI Originate `Local/s@<code>-callback-dial/n`, `Context=<code>-callback-answer` — ;2 operatorni
   teradi (`INNOVA_CB_DESTCTX`), ;1 operator javob bergandan keyin ishga tushadi va mijozni teradi.
2) Operator javob BERMASA — `<code>-callback-ophang` (;2 hangup handler) `operator_result()` orqali
   qayta urinish/bekor qilinadi. Operator javob BERSA — operator tomon o'zgarish qilmaydi (`None`),
   chunki mijoz terish davom etmoqda; yakuniy natija — mijoz tomondan (`customer_result()`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.services.campaign_rules import classify_dial_status

OPERATOR_RING_S = 30
# AMI `Variable:` qiymatlari — faqat shu belgilar (CR/LF/`,`/`;`/`@` in'ektsiya xavfi).
_AMI_SAFE = re.compile(r"[A-Za-z0-9/_.\-]*")


def _safe(value: str) -> str:
    if not _AMI_SAFE.fullmatch(value):
        raise ValueError(f"AMI uchun xavfli qiymat: {value!r}")
    return value


@dataclass(frozen=True)
class CallbackDialRequest:
    code: str
    request_id: str
    dest_ctx: str  # `<code>-dest-<target_id>` — operator manzili (mavjud umumiy kontekst)
    phone: str
    callerid_prefix: str | None = None


def originate_fields(req: CallbackDialRequest) -> dict[str, str]:
    """Local kanal `<code>-callback-dial` (;2 — operator, darhol teriladi) javob bersa
    `<code>-callback-answer` (;1 — mijozni teradi). `Timeout` — FAQAT operator qo'ng'irog'iga
    tegishli (mijoz oyoq Dial() marshrutning o'z vaqt chegarasidan foydalanadi)."""
    variables = {
        "INNOVA_CB_REQUEST": req.request_id,
        "INNOVA_CB_DESTCTX": req.dest_ctx,
        "INNOVA_CB_PHONE": req.phone,
        "INNOVA_CB_CID": req.callerid_prefix or "",
    }
    return {
        "Channel": f"Local/s@{_safe(req.code)}-callback-dial/n",
        "Context": f"{req.code}-callback-answer",
        "Exten": "s",
        "Priority": "1",
        "Timeout": str(OPERATOR_RING_S * 1000),
        "Async": "true",
        "Variable": ",".join(f"{k}={_safe(v)}" for k, v in variables.items()),
    }


@dataclass(frozen=True)
class RetryDecision:
    status: str  # "connected" | "pending" | "failed"
    next_attempt_at: datetime | None
    last_error: str | None


def _retry_decision(tag: str, attempts: int, max_attempts: int, now: datetime,
                    retry_interval_s: int) -> RetryDecision:
    if attempts >= max_attempts:
        return RetryDecision("failed", None, tag)
    return RetryDecision("pending", now + timedelta(seconds=retry_interval_s), tag)


def operator_result(raw_status: str, attempts: int, max_attempts: int, now: datetime,
                    retry_interval_s: int) -> RetryDecision | None:
    """`<code>-callback-ophang`. Operator JAVOB BERDI — `None` (o'zgarish yo'q, mijoz terish
    davom etadi/etgan — yakuniy natijani `customer_result()` belgilaydi, idempotentlik shu
    yerda: chaqiruvchi so'rov allaqachon yopilgan bo'lsa ham bu holatni e'tiborsiz qoldiradi)."""
    status = classify_dial_status(raw_status)
    if status == "ANSWER":
        return None
    return _retry_decision(f"operator_{status}", attempts, max_attempts, now, retry_interval_s)


def lost_result(attempts: int, max_attempts: int, now: datetime, retry_interval_s: int) -> RetryDecision:
    """`callback_dialer.sweep_lost` — AMI uzilib hangup handler kelmagan eski `dialing` so'rov."""
    return _retry_decision("lost", attempts, max_attempts, now, retry_interval_s)


def customer_result(raw_status: str, attempts: int, max_attempts: int, now: datetime,
                    retry_interval_s: int) -> RetryDecision:
    """`<code>-callback-custhang` — faqat operator javob bergandan keyin BIR MARTA ishga tushadi,
    shu sabab doim yakuniy (connected yoki qayta urinish/failed)."""
    status = classify_dial_status(raw_status)
    if status == "ANSWER":
        return RetryDecision("connected", None, None)
    return _retry_decision(f"customer_{status}", attempts, max_attempts, now, retry_interval_s)
