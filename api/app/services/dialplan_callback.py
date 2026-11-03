"""M10 A1 — qayta chaqirish vidjeti dialplan kontekstlari (har tenant uchun statik;
vidjet qo'shilganda ham o'zgarmaydi — operator manzili allaqachon umumiy `<code>-dest-<target_id>`
orqali ishlaydi, shu sabab `compiler.py` bu kontekstlarni har tenant uchun BIR MARTA yozadi,
`campaigns`/`dialplan_campaign.py` bilan bir xil shablon).

- `<code>-callback-dial`    — Local ;2: operator hangup handler ulanadi, so'ng ${INNOVA_CB_DESTCTX}
                              (operatorning umumiy manzil konteksti) ga o'tadi.
- `<code>-callback-ophang`  — ;2 tugaganda (operator DIALSTATUS) -> `/internal/callback/result`.
- `<code>-callback-answer`  — operator javob bergach (;1): mijoz hangup handler, so'ng mijozni
                              `<code>-outbound-rg` orqali teradi.
- `<code>-callback-custhang`— ;1 tugaganda (mijoz DIALSTATUS) -> `/internal/callback/result`.

Kanal o'zgaruvchilari (`INNOVA_CB_*`) — `callback_rules.originate_fields` (oq ro'yxat belgilari)."""
from __future__ import annotations


def _curl_lines(var: str, url: str) -> list[str]:
    return [
        " same => n,Set(CURLOPT(conntimeout)=2)",
        " same => n,Set(CURLOPT(httptimeout)=3)",
        f" same => n,Set({var}=${{CURL({url})}})",
    ]


def callback_context_lines(code: str, base_url: str, token: str) -> list[str]:
    op_url = (f"{base_url}/internal/callback/result?token={token}&request=${{INNOVA_CB_REQUEST}}"
              "&stage=operator&status=${DIALSTATUS}")
    # DIQQAT (mahsulot xatosi, TUZATILDI): yalang'och `${LINKEDID}` o'zgaruvchisi
    # Asterisk 22'da to'ldirilmaydi (bo'sh qatorga aylanadi) — to'g'ri shakl
    # `${CHANNEL(linkedid)}` funksiyasi (BU FAYLDAGI boshqa joyda, yozib olish
    # uchun `dialplan_recording.py`da ALLAQACHON to'g'ri ishlatilgan — xuddi shu
    # qolip bilan mos qilindi).
    cust_url = (f"{base_url}/internal/callback/result?token={token}&request=${{INNOVA_CB_REQUEST}}"
                "&stage=customer&status=${DIALSTATUS}&linkedid=${CHANNEL(linkedid)}")
    return [
        f"[{code}-callback-dial]",
        "exten => s,1,NoOp(Innova: qayta chaqirish ${INNOVA_CB_REQUEST} -> operator)",
        f" same => n,Set(CHANNEL(hangup_handler_push)={code}-callback-ophang,s,1)",
        " same => n,Goto(${INNOVA_CB_DESTCTX},s,1)",
        "",
        f"[{code}-callback-ophang]",
        "exten => s,1,NoOp(Innova: qayta chaqirish ${INNOVA_CB_REQUEST} operator natija ${DIALSTATUS})",
        *_curl_lines("INNOVA_CB_RES", op_url),
        " same => n,Return()",
        "",
        f"[{code}-callback-answer]",
        "exten => s,1,NoOp(Innova: qayta chaqirish ${INNOVA_CB_REQUEST} operator javob berdi -> mijoz)",
        f" same => n,Set(CHANNEL(hangup_handler_push)={code}-callback-custhang,s,1)",
        " same => n,Answer()",
        " same => n,Wait(1)",
        ' same => n,ExecIf($["${INNOVA_CB_CID}"!=""]?Set(CALLERID(num)=${INNOVA_CB_CID}))',
        f" same => n,Goto({code}-outbound-rg,${{INNOVA_CB_PHONE}},1)",
        "",
        f"[{code}-callback-custhang]",
        "exten => s,1,NoOp(Innova: qayta chaqirish ${INNOVA_CB_REQUEST} mijoz natija ${DIALSTATUS})",
        *_curl_lines("INNOVA_CB_RES", cust_url),
        " same => n,Return()",
    ]
