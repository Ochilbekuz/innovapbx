"""M6 §3 — kampaniya dialplan kontekstlari (har tenant uchun statik; kampaniya qo'shilganda apply SHART EMAS).

- `<code>-campaign-dial`   — Local ;2: hangup handler + CallerID → `<code>-outbound-rg` (mavjud marshrut/trunk).
- `<code>-campaign-hangup` — ;2 tugaganda DIALSTATUS/ANSWEREDTIME → `/internal/campaigns/result`.
- `<code>-campaign-answer` — mijoz javob bergach (;1): audio / DTMF menyu / operatorga ulash.

Kanal o'zgaruvchilari (`INNOVA_CAMP_*`) — `campaign_rules.originate_fields` (oq ro'yxat belgilari)."""
from __future__ import annotations


def _curl_lines(var: str, url: str) -> list[str]:
    return [
        " same => n,Set(CURLOPT(conntimeout)=2)",
        " same => n,Set(CURLOPT(httptimeout)=3)",
        f" same => n,Set({var}=${{CURL({url})}})",
    ]


def campaign_context_lines(code: str, base_url: str, token: str) -> list[str]:
    result_url = (f"{base_url}/internal/campaigns/result?token={token}&attempt=${{INNOVA_CAMP_ATTEMPT}}"
                  "&status=${DIALSTATUS}&answered=${ANSWEREDTIME}")
    key_url = (f"{base_url}/internal/campaigns/key?token={token}&attempt=${{INNOVA_CAMP_ATTEMPT}}"
               "&key=${URIENCODE(${INNOVA_CAMP_KEY})}")
    return [
        f"[{code}-campaign-dial]",
        "exten => _X.,1,NoOp(Innova: kampaniya ${INNOVA_CAMP_ID} urinish ${INNOVA_CAMP_ATTEMPT} -> ${EXTEN})",
        f" same => n,Set(CHANNEL(hangup_handler_push)={code}-campaign-hangup,s,1)",
        ' same => n,ExecIf($["${INNOVA_CAMP_CID}"!=""]?Set(CALLERID(num)=${INNOVA_CAMP_CID}))',
        f" same => n,Goto({code}-outbound-rg,${{EXTEN}},1)",
        "",
        f"[{code}-campaign-hangup]",
        "exten => s,1,NoOp(Innova: kampaniya natija ${DIALSTATUS} ${ANSWEREDTIME})",
        *_curl_lines("INNOVA_CAMP_RES", result_url),
        " same => n,Return()",
        "",
        f"[{code}-campaign-answer]",
        "exten => s,1,NoOp(Innova: kampaniya javob ${INNOVA_CAMP_NUM})",
        " same => n,Answer()",
        " same => n,Wait(1)",
        " same => n,Set(CALLERID(num)=${INNOVA_CAMP_NUM})",
        " same => n,Set(CALLERID(name)=)",
        ' same => n,GotoIf($["${INNOVA_CAMP_AUDIO}"=""]?connect)',
        ' same => n,GotoIf($["${INNOVA_CAMP_DTMF}"="1"]?menu)',
        " same => n,Playback(${INNOVA_CAMP_AUDIO})",
        ' same => n,GotoIf($["${INNOVA_CAMP_MODE}"="connect"]?connect)',
        " same => n,Hangup()",
        " same => n(menu),Read(INNOVA_CAMP_KEY,${INNOVA_CAMP_AUDIO},1,,2,6)",
        ' same => n,GotoIf($["${INNOVA_CAMP_KEY}"=""]?done)',
        *_curl_lines("INNOVA_CAMP_ACT", key_url),
        ' same => n,GotoIf($["${INNOVA_CAMP_ACT}"="connect"]?connect)',
        ' same => n,GotoIf($["${INNOVA_CAMP_ACT}"="optout"]?optout)',
        " same => n(done),Hangup()",
        " same => n(optout),Playback(vm-goodbye)",
        " same => n,Hangup()",
        f" same => n(connect),Goto({code}-from-internal,${{INNOVA_CAMP_TO}},1)",
    ]
