"""M3b §1/M3c §1 — qo'ng'iroq yozuvi dialplan'i (SOF funksiyalar).

BITTA yordamchi (`recorded_dial_lines` / navbat uchun `recorded_queue_lines`) BARCHA dial nuqtalarida:
to'g'ridan ichki raqam va forward (`<code>-ext-call`), qo'ng'iroq guruhi, navbat (javob bergan a'zo),
chiquvchi trunk; transfer ham shu nuqtalardan qayta o'tadi (`TRANSFER_CONTEXT=<code>-from-internal`).

  * `innova-rec-prep` — Dial/Queue'dan OLDIN chaqiruvchi (A) kanalida: `__INNOVA_REC_A=<endpoint>`
    (B'ga meros), A'ning `recording_out` `on_demand` bo'lsa A'ga `*1` (`DYNAMIC_FEATURES=innova-rec`).
  * `innova-rec` — javob bergan B kanalida (`Dial(U())`, `Queue(...,gosub)`), bridge'dan OLDIN:
    `app/services/recording_policy.decide` qoidasining Asterisk'dagi aynan nusxasi (A'ning
    `recording_out`, B'ning `recording_in`).
  * `innova-rec-start` — `MixMonitor` (fayl `innova/YYYY/MM/DD/<linkedid>-<uniqueid>.wav`, UTC; `a` —
    `*1` bilan qayta yoqilsa o'sha faylga qo'shiladi), `CDR(recordingfile)` nisbiy yo'l.
  * `innova-rec-toggle` — `*1` (features.conf `applicationmap`, `self`): yoqish/o'chirish.

Siyosat realtime'dan (`ext_state` → `asterisk_ext_state` view: `recording` — KIRUVCHI,
`recording_out` — CHIQUVCHI, `rec_external_only`) — raqam siyosati o'zgarsa dialplan
qayta kompilyatsiya shart emas.
"""
from __future__ import annotations

# `dialplan_features` shu moduldan import qiladi — sikl bo'lmasin, oila nomi shu yerda (test tenglikni tekshiradi).
EXT_STATE_FAMILY = "ext_state"

SUBROUTINE = "innova-rec"
FEATURE_NAME = "innova-rec"
PREP = "innova-rec-prep"
START = "innova-rec-start"
TOGGLE = "innova-rec-toggle"


def _field(endpoint_expr: str, column: str) -> str:
    return f"${{REALTIME_FIELD({EXT_STATE_FAMILY},endpoint,{endpoint_expr},{column})}}"


# ------------------------------------------------------------ dial nuqtalari
def prep_line() -> str:
    return f" same => n,Gosub({PREP},s,1)"


def recorded_dial_lines(target: str, timeout: str, options: str = "") -> list[str]:
    """Har bir `Dial()` — shu yerdan (to'g'ridan ichki, RG, forward, trunk)."""
    return [prep_line(), f" same => n,Dial({target},{timeout},{options}U({SUBROUTINE}))"]


def recorded_queue_lines(queue_name: str, max_wait: int, *, queue_id: str) -> list[str]:
    """Asterisk 22 `Queue(name,options,URL,announce,timeout,AGI,gosub,...)` — gosub 7-argument."""
    return [
        f" same => n,Set(__INNOVA_QUEUE={queue_id})",
        prep_line(),
        f" same => n,Queue({queue_name},,,,{max_wait},,{SUBROUTINE})",
    ]


# ------------------------------------------------------------ umumiy kontekstlar
def _prep_context() -> list[str]:
    return [
        f"[{PREP}]",
        'exten => s,1,GotoIf($["${CHANNEL(channeltype)}"!="PJSIP"]?done)',
        " same => n,Set(__INNOVA_REC_A=${CHANNEL(endpoint)})",
        # M3c §1: A o'z chiquvchi qo'ng'irog'ini boshlayapti — `recording_out` tekshiriladi.
        f' same => n,ExecIf($["{_field("${INNOVA_REC_A}", "recording_out")}"="on_demand"]?Set(DYNAMIC_FEATURES={FEATURE_NAME}))',
        " same => n(done),Return()",
    ]


def _policy_context() -> list[str]:
    """B — trunk: manba (forward/transfer qilgan) ichki raqamning CHIQUVCHISI yoki A'ning
    CHIQUVCHISI. B — ichki, A — ichki emas: B'ning KIRUVCHISI. Ikkalasi ichki: A'ning
    CHIQUVCHISI va B'ning KIRUVCHISI — external_only → yo'q; never ustun; always → yozish."""
    on_demand_b = f' same => n,ExecIf($["${{INNOVA_REC_RB}}"="on_demand"]?Set(DYNAMIC_FEATURES={FEATURE_NAME}))'
    return [
        f"[{SUBROUTINE}]",
        # M9 B1 (0032): PIN to'plami yorlig'i (`CDR(pin_label)`)
        # `recordingfile` BILAN BIR XIL naqshda (DRY) AYNAN SHU YERDA (B —
        # javob bergan kanalda, bridge'dan OLDIN) yoziladi — custom CDR
        # maydonlari uchun izchil, xavfsiz andoza (tafsilot — compiler.py
        # `_route_pin_set_lines()` izohida: jonli isbotda shu yerga
        # ko'chirishga turtki bo'lgan haqiqiy sabab `cdr_pgsql` modulining
        # ESKI ustun keshi edi, A/B kanal farqi EMAS). `INNOVA_PINSET_LABEL`
        # — A kanalida `__INNOVA_PINSET_LABEL` (meros qoluvchi) sifatida
        # o'rnatiladi, shu sabab bu yerda (B kanalda) pastki chiziqsiz
        # ko'rinadi; bo'sh bo'lsa (PIN to'plami ishlatilmagan yoki
        # yorlig'i yo'q) hech narsa yozilmaydi.
        'exten => s,1,ExecIf($["${INNOVA_PINSET_LABEL}"!=""]?Set(CDR(pin_label)=${INNOVA_PINSET_LABEL}))',
        ' same => n,GotoIf($["${CHANNEL(channeltype)}"!="PJSIP"]?done)',
        # RB — B'ning KIRUVCHI siyosati (`recording`, nomi o'zgarmaydi).
        f" same => n,Set(INNOVA_REC_RB={_field('${CHANNEL(endpoint)}', 'recording')})",
        " same => n,Set(INNOVA_REC_RA=)",
        # RA — A'ning CHIQUVCHI siyosati (`recording_out`).
        f' same => n,ExecIf($["${{INNOVA_REC_A}}"!=""]?Set(INNOVA_REC_RA={_field("${INNOVA_REC_A}", "recording_out")}))',
        ' same => n,GotoIf($["${INNOVA_REC_RB}"=""]?trunk)',
        ' same => n,GotoIf($["${INNOVA_REC_RA}"=""]?extb)',
        f' same => n,GotoIf($["{_field("${CHANNEL(endpoint)}", "rec_external_only")}"="t"]?done)',
        on_demand_b,
        ' same => n,GotoIf($["${INNOVA_REC_RA}"="never"|"${INNOVA_REC_RB}"="never"]?done)',
        ' same => n,GotoIf($["${INNOVA_REC_RA}"="always"|"${INNOVA_REC_RB}"="always"]?start:done)',
        on_demand_b.replace("n,ExecIf", "n(extb),ExecIf"),
        ' same => n,GotoIf($["${INNOVA_REC_RB}"="always"]?start:done)',
        # M5b: Follow Me tashqi oyog'i — «qabul qilish uchun 1» (mobil ovozli pochtasi qo'ng'iroqni yemasin).
        # Rad/javobsiz → faqat SHU oyoq uziladi (`GOSUB_RESULT=ABORT`), boshqalari jiringlashda davom etadi.
        ' same => n(trunk),GotoIf($["${INNOVA_FM_CONFIRM}"!="t"]?trunkrec)',
        " same => n,Read(INNOVA_FM_KEY,followme/options,1,,2,5)",
        ' same => n,GotoIf($["${INNOVA_FM_KEY}"="1"]?trunkrec)',
        " same => n,Set(GOSUB_RESULT=ABORT)",
        " same => n,Return()",
        " same => n(trunkrec),Set(INNOVA_REC_P=${IF($[\"${INNOVA_REC_SRC}\"!=\"\"]?${INNOVA_REC_SRC}:${INNOVA_REC_A})})",
        ' same => n,GotoIf($["${INNOVA_REC_P}"=""]?done)',
        # Manba (SRC) yoki A — har ikkisi ham CHIQUVCHI tomon (`recording_out`).
        f' same => n,GotoIf($["{_field("${INNOVA_REC_P}", "recording_out")}"="always"]?start:done)',
        f" same => n(start),Gosub({START},s,1)",
        " same => n(done),Return()",
    ]


def _start_context() -> list[str]:
    return [
        f"[{START}]",
        "exten => s,1,Set(INNOVA_REC_FILE=innova/${STRFTIME(${EPOCH},UTC,%Y/%m/%d)}/${CHANNEL(linkedid)}-${UNIQUEID}.wav)",
        " same => n,MixMonitor(${INNOVA_REC_FILE},ai(INNOVA_REC_ID))",
        " same => n,Set(CDR(recordingfile)=${INNOVA_REC_FILE})",
        " same => n,Return()",
    ]


def _toggle_context() -> list[str]:
    return [
        f"[{TOGGLE}]",
        'exten => s,1,GotoIf($["${INNOVA_REC_ID}"=""]?on)',
        " same => n,StopMixMonitor(${INNOVA_REC_ID})",
        " same => n,Set(INNOVA_REC_ID=)",
        " same => n,Return()",
        f" same => n(on),Gosub({START},s,1)",
        " same => n,Return()",
    ]


def recording_context_lines() -> list[str]:
    lines: list[str] = []
    for block in (_prep_context(), _policy_context(), _start_context(), _toggle_context()):
        lines += block + [""]
    return lines


# ------------------------------------------------------------ API originate (§4)
def originate_context_lines(code: str) -> list[str]:
    """AMI Originate: ichki raqam (A) javob bergach `to` oddiy marshrutlar bilan teriladi,
    CallerID — ichki raqam. Funksiya kodlari (`*`/`#`) — rad (API kaliti forward'ni o'zgartira olmasin)."""
    return [
        f"[{code}-originate]",
        "exten => _X!,1,NoOp(Innova: API originate ${INNOVA_ORIG_EXT} -> ${EXTEN})",
        " same => n,Set(CALLERID(num)=${INNOVA_ORIG_EXT})",
        " same => n,Set(CALLERID(name)=)",
        f" same => n,Goto({code}-from-internal,${{EXTEN}},1)",
        "exten => _[*#]!,1,NoOp(Innova: API originate funksiya kodiga ruxsat yo'q)",
        " same => n,Hangup(21)",
    ]
