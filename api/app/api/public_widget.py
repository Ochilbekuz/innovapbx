"""M10 A1 — qayta chaqirish vidjeti: ommaviy (JWT'siz) endpoint'lar, uchinchi tomon
saytlaridan chaqiriladi. `web-nginx.conf`: `/widget/` -> shu router, `/api/public/widget/`
— mavjud `/api/` proksi orqali avtomatik (ustun prefiks).

`app/main.py`da `CORSMiddleware(allow_origins=["*"])` BUTUN ilova uchun o'rnatilgan
(brauzer darajasida o'qish ruxsati — `credentials` YO'Q, shu sabab xavfsiz: boshqa
API'lar JWT/Bearer talab qiladi, begona sayt uni bilmaydi/yubora olmaydi). Shu
sabab bu yerda Origin UCHUN maxsus CORS sarlavha/OPTIONS kodi KERAK EMAS — faqat
dastur darajasidagi RUXSAT tekshiruvi (`allowed_origins`, 403) qoladi haqiqiy
xavfsizlik chegarasi sifatida.

Xavfsizlik qatlamlari (m10-onlinepbx-contract.md §A1):
- Origin: `allowed_origins` bo'sh = cheklov yo'q; bo'sh bo'lmasa — mos kelmasa 403
  (dastur darajasida — CORSMiddleware bundan qat'i nazar `*` sarlavha qo'yadi).
- Honeypot (`hp`): to'lgan bo'lsa bot — yozuv yaratilMAYdi, lekin javob muvaffaqiyat
  ko'rinishida (botga signal bermaslik, `services/blacklist.py` sabab bilan BIR XIL fikr).
- Tezlik cheklovi: IP/telefon/vidjet (`SlidingWindowLimiter` — `api/public.py` BILAN
  BIR XIL asbob).
- Telefon: `originate.validate_to` (AMI oq ro'yxati, `api/public.py` BILAN BIR XIL) +
  `outbound_rules.international_blocked` (xalqaro, `+`/`00` yo'qolishidan OLDIN tekshiriladi)
  + `blacklist.get_entry` (qora ro'yxat).
- Ish vaqti: `offhours_mode="reject"` — FAQAT shu yerda (qabul vaqtida) tekshiriladi;
  `schedule` — qabul qilinadi, keyinga suriladi (`services/callback_dialer.is_open`).
- Dublikat: bir xil telefon uchun ochiq (`pending`/`dialing`) so'rov bor bo'lsa — qayta
  yozilmaydi, "navbatdasiz" deb javob beriladi (tugmani ikki marta bosish himoyasi).

`PublicCallbackAccepted(accepted, message)` — BARCHA "yumshoq" holatlar (honeypot,
tezlik, xalqaro, qora ro'yxat, ish vaqti, dublikat) shu bilan 200 qaytaradi (botga/UI
aniq signal bermaslik va bir xil shakl); FAQAT tuzilma darajasidagi xato (telefon
formati, vidjet topilmadi/o'chirilgan, Origin mos kelmadi) ApiError bilan rad etiladi.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.errors import ApiError
from app.db.models import CallbackRequest, CallbackWidget, Tenant
from app.schemas import PublicCallbackAccepted, PublicCallbackPayload, PublicWidgetConfig
from app.services import callback_dialer, originate
from app.services.blacklist import get_entry
from app.services.outbound_rules import international_blocked
from app.services.rate_limit import SlidingWindowLimiter

router = APIRouter(tags=["public-widget"])
_limiter = SlidingWindowLimiter()
IP_LIMIT_PER_MIN = 5
WIDGET_LIMIT_PER_MIN = 30
PHONE_LIMIT_PER_HOUR = 3
DEDUP_OPEN_STATUSES = ("pending", "dialing")

_WIDGET_JS = """\
(() => {
  const s = document.currentScript;
  const m = (s && s.src || "").match(/\\/widget\\/([^/]+)\\.js/);
  const key = m && m[1];
  if (!key) return;
  const api = new URL(s.src).origin;
  const root = document.createElement("div");
  root.id = "innova-callback-widget";
  const shadow = root.attachShadow({mode: "open"});
  document.currentScript.insertAdjacentElement("afterend", root);

  async function cfg() {
    const r = await fetch(`${api}/api/public/widget/${key}/config`);
    if (!r.ok) return null;
    return r.json();
  }

  function render(c) {
    const btn = document.createElement("button");
    btn.textContent = (c && c.name) || "Qayta aloqa";
    btn.style.cssText = "position:fixed;right:16px;bottom:16px;z-index:999999;padding:10px 16px;" +
      "border-radius:8px;border:none;background:#2563eb;color:#fff;cursor:pointer;font-size:14px";
    const panel = document.createElement("div");
    panel.style.cssText = "display:none;position:fixed;right:16px;bottom:64px;z-index:999999;" +
      "background:#fff;color:#111;border-radius:8px;padding:16px;box-shadow:0 4px 24px rgba(0,0,0,.2);" +
      "width:260px;font-family:sans-serif";
    panel.innerHTML = '<input type="text" placeholder="+998 90 123 45 67" style="width:100%;' +
      'box-sizing:border-box;padding:8px;margin-bottom:8px;border:1px solid #ccc;border-radius:6px">' +
      '<input type="text" style="position:absolute;left:-9999px" tabindex="-1" autocomplete="off">' +
      '<button type="button" style="width:100%;padding:8px;border:none;border-radius:6px;' +
      'background:#2563eb;color:#fff;cursor:pointer">Yuborish</button>' +
      '<div class="msg" style="margin-top:8px;font-size:13px"></div>';
    shadow.append(btn, panel);
    const [phoneEl, hpEl] = panel.querySelectorAll("input");
    const sendBtn = panel.querySelector("button");
    const msgEl = panel.querySelector(".msg");
    btn.onclick = () => { panel.style.display = panel.style.display === "none" ? "block" : "none"; };
    sendBtn.onclick = async () => {
      sendBtn.disabled = true;
      try {
        const r = await fetch(`${api}/api/public/widget/${key}/callback`, {
          method: "POST", headers: {"Content-Type": "application/json"},
          body: JSON.stringify({phone: phoneEl.value, hp: hpEl.value}),
        });
        const data = await r.json().catch(() => ({accepted: false, message: "Xatolik"}));
        msgEl.textContent = data.message || "";
        if (data.accepted) phoneEl.value = "";
      } catch (e) {
        msgEl.textContent = "Tarmoq xatosi, qayta urining";
      } finally {
        sendBtn.disabled = false;
      }
    };
  }

  cfg().then((c) => { if (c) render(c); });
})();
"""


def _origin_allowed(widget: CallbackWidget, origin: str | None) -> bool:
    return not widget.allowed_origins or origin in widget.allowed_origins


async def _widget_or_404(session: AsyncSession, public_key: str) -> CallbackWidget:
    widget = (await session.execute(
        select(CallbackWidget).where(CallbackWidget.public_key == public_key))).scalar_one_or_none()
    if widget is None or not widget.enabled:
        raise ApiError(404, "not_found", "Vidjet topilmadi")
    return widget


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/widget/{public_key}.js")
async def widget_script(public_key: str, session: AsyncSession = Depends(get_session)) -> Response:
    await _widget_or_404(session, public_key)
    return Response(content=_WIDGET_JS, media_type="application/javascript",
                    headers={"Cache-Control": "public, max-age=300"})


@router.get("/api/public/widget/{public_key}/config", response_model=PublicWidgetConfig)
async def widget_config(public_key: str, request: Request,
                        session: AsyncSession = Depends(get_session)) -> PublicWidgetConfig:
    widget = await _widget_or_404(session, public_key)
    origin = request.headers.get("origin")
    if origin and not _origin_allowed(widget, origin):
        raise ApiError(403, "origin_not_allowed", "Bu sayt uchun vidjet ruxsat etilmagan")
    return PublicWidgetConfig(name=widget.name, appearance=widget.appearance,
                              allow_international=widget.allow_international)


async def _validated_phone(raw: str, *, allow_international: bool) -> str:
    try:
        dialed = originate.validate_to(raw)
    except originate.InvalidNumber as exc:
        raise ApiError(422, "invalid_number", "Telefon raqami formati noto'g'ri", field="phone") from exc
    check = raw.strip().replace(" ", "").replace("-", "")
    if international_blocked(check, international=allow_international):
        raise ApiError(422, "international_blocked", "Xalqaro raqamlarga xizmat ko'rsatilmaydi", field="phone")
    return dialed


async def _already_queued(session: AsyncSession, widget_id: str, phone: str) -> bool:
    row = (await session.execute(select(CallbackRequest.id).where(
        CallbackRequest.widget_id == widget_id, CallbackRequest.phone == phone,
        CallbackRequest.status.in_(DEDUP_OPEN_STATUSES)).limit(1))).scalar_one_or_none()
    return row is not None


def _result(accepted: bool, message: str) -> PublicCallbackAccepted:
    return PublicCallbackAccepted(accepted=accepted, message=message)


@router.post("/api/public/widget/{public_key}/callback", response_model=PublicCallbackAccepted)
async def widget_callback(
    public_key: str, payload: PublicCallbackPayload, request: Request,
    session: AsyncSession = Depends(get_session),
) -> PublicCallbackAccepted:
    widget = await _widget_or_404(session, public_key)
    origin = request.headers.get("origin")
    if origin and not _origin_allowed(widget, origin):
        raise ApiError(403, "origin_not_allowed", "Bu sayt uchun vidjet ruxsat etilmagan")

    if payload.hp.strip():  # honeypot — botga jim "muvaffaqiyat"
        return _result(True, "Qabul qilindi, tez orada bog'lanamiz")

    ip = _client_ip(request)
    if not _limiter.allow(f"ip:{ip}", limit=IP_LIMIT_PER_MIN, window_s=60):
        return _result(False, "Juda ko'p so'rov — birozdan keyin urining")
    if not _limiter.allow(f"widget:{widget.id}", limit=WIDGET_LIMIT_PER_MIN, window_s=60):
        return _result(False, "Juda ko'p so'rov — birozdan keyin urining")

    dialed = await _validated_phone(payload.phone, allow_international=widget.allow_international)

    if not _limiter.allow(f"phone:{dialed}", limit=PHONE_LIMIT_PER_HOUR, window_s=3600):
        return _result(False, "Juda ko'p so'rov — birozdan keyin urining")
    if await get_entry(session, str(widget.tenant_id), dialed) is not None:
        return _result(False, "Hozircha xizmat ko'rsata olmaymiz")
    if await _already_queued(session, str(widget.id), dialed):
        return _result(True, "Siz allaqachon navbatdasiz")

    tenant = await session.get(Tenant, widget.tenant_id)
    if widget.offhours_mode == "reject" and tenant is not None and not await callback_dialer.is_open(
        session, tenant, widget,
    ):
        return _result(False, "Hozir ish vaqti emas")

    page_url = (request.headers.get("referer") or "")[:512] or None
    session.add(CallbackRequest(tenant_id=widget.tenant_id, widget_id=widget.id, phone=dialed,
                                page_url=page_url, ip=ip if ip != "unknown" else None,
                                next_attempt_at=None))
    await session.commit()
    return _result(True, "Qabul qilindi, tez orada bog'lanamiz")
