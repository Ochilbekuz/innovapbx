"""M2a §1–§3 dialplan qismlari — SOF funksiyalar (kompilyator shu yerdan oladi).

Realtime (m2a-contract.md §0): DND va yo'naltirish holati dialplan'ga
yozilMAYDI — har qo'ng'iroqda `REALTIME_FIELD(ext_state,...)` bilan PG'dan
o'qiladi (`asterisk_ext_state` view, extconfig `ext_state`), *-kodlar esa
`Set(REALTIME(ext_state,...)=...)` bilan YOZADI (view INSTEAD OF UPDATE
trigger bilan `extensions` jadvalini yangilaydi). Yagona haqiqat manbai —
`extensions` jadvali; AstDB ishlatilmaydi, API'ga CURL yo'q. Yozuvdan keyin
qiymat QAYTA O'QIB tekshiriladi: CHECK buzilsa (masalan noto'g'ri raqam) PG
UPDATE'ni rad etadi, `Set(REALTIME())` esa xatoni dialplan'ga bildirmaydi.

Kontekstlar:
  <code>-ext       — ichki raqamga qo'ng'iroqning YAGONA kirish nuqtasi: raqam
                     parametrlari (ring, javobsiz manzil), noma'lum raqam —
                     chiquvchi marshrutga.
  <code>-ext-call  — umumiy oqim: DND -> forward_always -> Dial(tT) -> BUSY
                     bo'lsa forward_busy -> javobsiz manzil.
  <code>-cf        — *72/*73/*90/*91 yozuvi (raqam `INNOVA_NUM`da).
  <code>-fm        — M5b Follow Me: ichki raqam javob bermasa ro'yxatga (ring_all / sequential).
  <code>-fm-leg    — Follow Me oyog'i (`Local/<raqam>@...`): ichki — to'g'ridan PJSIP (o'z Follow Me'si
                     ishlamaydi, bir pog'ona), tashqi — chiquvchi marshrut (ruxsat/toll egasiniki).
"""
from __future__ import annotations

from collections.abc import Callable

from app.services.dialplan_recording import recorded_dial_lines

EXT_STATE_FAMILY = "ext_state"
BLACKLIST_FAMILY = "blacklist"  # m2a-contract.md §5 — faqat o'qish (API yozadi).
AGENT_STATE_FAMILY = "agent_state"  # m2b-contract.md §0/§1 — navbat login/pauza.

# Park joyi (m2a-contract.md §3): tenant bo'yicha bitta lot, raqamlar band qilingan.
PARK_LOT_NUMBER = "700"
PARK_FIRST_SLOT = 701
PARK_LAST_SLOT = 720
PARK_TIMEOUT_S = 60

# Yo'naltirish zanjiri: boshlang'ich raqam + ko'pi bilan 3 sakrash.
MAX_FORWARD_HOPS = 3

# Transfer (§3): chaqirilgan tomon doim (`t`), chaqiruvchi faqat ICHKI bo'lsa
# (`T`) — trunk'dan kelgan tashqi chaqiruvchi `##` bilan transfer qilib
# chiquvchi marshrutga kira olmasligi uchun (toll fraud).
XFER_OPTIONS = 't${IF($["${INNOVA_FROM_TRUNK}"="1"]?:T)}'


def park_lot_name(code: str) -> str:
    return f"{code}-park"


def realtime_read(_code: str, number_expr: str, column: str) -> str:
    """`_code` endi ishlatilmaydi (imzo o'zgarmasin — chaqiruvchilar ko'p) —
    `asterisk_ext_state.endpoint` endi prefikssiz (`sip_identity.endpoint_id`,
    m-sip-login-plain-number)."""
    return f"${{REALTIME_FIELD({EXT_STATE_FAMILY},endpoint,{number_expr},{column})}}"


# ------------------------------------------------------------ <code>-ext
def ext_entry_lines(code: str, number: str, name: str, ring_seconds: int,
                    noans_dest: str | None, dnd_dest: str | None) -> list[str]:
    """Snapshot'dagi ichki raqam: parametrlar -> umumiy oqim."""
    return [
        f"exten => {number},1,NoOp(Innova: {name} <{number}>)",
        f" same => n,Set(INNOVA_RING={ring_seconds})",
        f" same => n,Set(INNOVA_NOANS={noans_dest or ''})",
        f" same => n,Set(INNOVA_DNDDEST={dnd_dest or ''})",
        f" same => n,Goto({code}-ext-call,${{EXTEN}},1)",
    ]


def ext_generic_lines(code: str) -> list[str]:
    """Snapshot'da yo'q raqam: realtime'da ham yo'q bo'lsa — chiquvchi marshrut."""
    exists = realtime_read(code, "${EXTEN}", "endpoint")
    return [
        f'exten => _X.,1,GotoIf($["{exists}"=""]?{code}-outbound,${{EXTEN}},1)',
        " same => n,Set(INNOVA_RING=20)",
        " same => n,Set(INNOVA_NOANS=)",
        " same => n,Set(INNOVA_DNDDEST=)",
        f" same => n,Goto({code}-ext-call,${{EXTEN}},1)",
    ]


def ext_call_lines(code: str) -> list[str]:
    seen_limit = MAX_FORWARD_HOPS + 1  # FIELDQTY: bosh bo'sh maydon + ko'rilgan raqamlar
    return [
        f"[{code}-ext-call]",
        "exten => _X.,1,NoOp(Innova: ichki raqam ${EXTEN})",
        " same => n,Set(INNOVA_FWD_SEEN=${INNOVA_FWD_SEEN}-${EXTEN})",
        f' same => n,GotoIf($["{realtime_read(code, "${EXTEN}", "dnd")}"="t"]?dnd)',
        f" same => n,Set(INNOVA_FWD={realtime_read(code, '${EXTEN}', 'forward_always')})",
        " same => n,Set(INNOVA_FWD_STOP=dial)",
        ' same => n,GotoIf($["${INNOVA_FWD}"!=""]?fwd)',
        f" same => n(dial),Set(__PICKUPMARK={code}-${{EXTEN}})",
        f" same => n,Set(__TRANSFER_CONTEXT={code}-from-internal)",
        # SIP endpoint id — prefikssiz (`sip_identity.endpoint_id`), ${EXTEN} shu bilan BIR XIL.
        *recorded_dial_lines("PJSIP/${EXTEN}", "${INNOVA_RING}", XFER_OPTIONS),
        ' same => n,GotoIf($["${DIALSTATUS}"!="BUSY"]?noans)',
        f" same => n,Set(INNOVA_FWD={realtime_read(code, '${EXTEN}', 'forward_busy')})",
        " same => n,Set(INNOVA_FWD_STOP=noans)",
        ' same => n,GotoIf($["${INNOVA_FWD}"!=""]?fwd)',
        # M5b: javobsiz / band / mavjud emas → Follow Me (yoqilgan bo'lsa), keyin javobsiz manzil.
        f' same => n(noans),GotoIf($["{realtime_read(code, "${EXTEN}", "fm_enabled")}"!="t"]?noans2)',
        f" same => n,Goto({fm_context(code)},${{EXTEN}},1)",
        ' same => n(noans2),GotoIf($["${INNOVA_NOANS}"=""]?done)',
        " same => n,Goto(${INNOVA_NOANS},s,1)",
        " same => n(done),Hangup()",
        # DND: band holat — ovozli pochta (`b` salomlashuvi) yoki 486.
        " same => n(dnd),Set(DIALSTATUS=BUSY)",
        ' same => n,GotoIf($["${INNOVA_DNDDEST}"=""]?busy)',
        " same => n,Goto(${INNOVA_DNDDEST},s,1)",
        " same => n(busy),Busy(5)",
        " same => n,Hangup(17)",
        # Halqa / uzun zanjir — yo'naltirmasdan o'zi jiringlaydi (yoki javobsiz).
        " same => n(fwd),GotoIf($[${FIELDNUM(INNOVA_FWD_SEEN,-,${INNOVA_FWD})} > 0]?fwdstop)",
        f" same => n,GotoIf($[${{FIELDQTY(INNOVA_FWD_SEEN,-)}} > {seen_limit}]?fwdstop)",
        # Tashqi raqamga chiqishda ruxsatlar YO'NALTIRUVCHI ext'niki (outbound kontekst).
        " same => n,Set(INNOVA_FWD_FROM=${EXTEN})",
        f" same => n,Goto({code}-ext,${{INNOVA_FWD}},1)",
        " same => n(fwdstop),NoOp(Innova: yo'naltirish to'xtatildi ${INNOVA_FWD_SEEN})",
        " same => n,Goto(${INNOVA_FWD_STOP})",
    ]


# ------------------------------------------------------------ Follow Me (M5b §1)
def fm_context(code: str) -> str:
    return f"{code}-fm"


def fm_leg_context(code: str) -> str:
    return f"{code}-fm-leg"


def fm_context_lines(code: str) -> list[str]:
    """`fm_dial` (view) — ring_all uchun tayyor `Local/...&...` (include_extension bo'lsa egasi birinchi);
    sequential — `fm_numbers` bo'yicha birma-bir. Oyoqlar egasi/tasdiq/trunk belgisini `__` merosdan oladi
    (`Local` kanaliga oddiy o'zgaruvchi o'tmaydi). Keyin — `ext-call` ning javobsiz manzili (`noans2`)."""
    def rt(column: str) -> str:
        return realtime_read(code, "${EXTEN}", column)

    leg = f"Local/${{INNOVA_FM_LEG}}@{fm_leg_context(code)}/n"
    return [
        f"[{fm_context(code)}]",
        "exten => _X.,1,NoOp(Innova: Follow Me ${EXTEN})",
        " same => n,Set(__INNOVA_FM_OWNER=${EXTEN})",
        f" same => n,Set(__INNOVA_FM_CONF={rt('fm_confirm')})",
        " same => n,Set(__INNOVA_FM_TRUNK=${INNOVA_FROM_TRUNK})",
        f" same => n,Set(INNOVA_FM_RING={rt('fm_ring')})",
        f' same => n,GotoIf($["{rt("fm_strategy")}"="sequential"]?seq)',
        f" same => n,Set(INNOVA_FM_DIAL={rt('fm_dial')})",
        ' same => n,GotoIf($["${INNOVA_FM_DIAL}"=""]?after)',
        # Tashqi Dial transfer opsiyasiz: `t`/`T` ichki oyoqda (`fm-leg`), ikki marta tutilmasin.
        *recorded_dial_lines("${INNOVA_FM_DIAL}", "${INNOVA_FM_RING}"),
        " same => n,Goto(after)",
        f" same => n(seq),Set(INNOVA_FM_LIST={rt('fm_numbers')})",
        " same => n,Set(INNOVA_FM_I=0)",
        " same => n(next),Set(INNOVA_FM_I=$[${INNOVA_FM_I}+1])",
        " same => n,Set(INNOVA_FM_LEG=${CUT(INNOVA_FM_LIST,&,${INNOVA_FM_I})})",
        ' same => n,GotoIf($["${INNOVA_FM_LEG}"=""]?after)',
        *recorded_dial_lines(leg, "${INNOVA_FM_RING}"),
        " same => n,Goto(next)",
        f" same => n(after),Goto({code}-ext-call,${{EXTEN}},noans2)",
    ]


def fm_leg_lines(code: str) -> list[str]:
    exists = realtime_read(code, "${EXTEN}", "endpoint")
    return [
        f"[{fm_leg_context(code)}]",
        "exten => _X.,1,NoOp(Innova: Follow Me oyog'i ${EXTEN} (egasi ${INNOVA_FM_OWNER}))",
        # Trunk'dan kelgan chaqiruvchiga `T` (transfer) berilmasin — belgi `Local` orqali tiklanadi.
        " same => n,Set(INNOVA_FROM_TRUNK=${INNOVA_FM_TRUNK})",
        f' same => n,GotoIf($["{exists}"=""]?external)',
        f' same => n,GotoIf($["{realtime_read(code, "${EXTEN}", "dnd")}"="t"]?skip)',
        f" same => n,Set(__PICKUPMARK={code}-${{EXTEN}})",
        f" same => n,Set(__TRANSFER_CONTEXT={code}-from-internal)",
        # SIP endpoint id — prefikssiz (`sip_identity.endpoint_id`), ${EXTEN} shu bilan BIR XIL.
        *recorded_dial_lines("PJSIP/${EXTEN}", "", XFER_OPTIONS),
        " same => n,Hangup()",
        " same => n(skip),Hangup(17)",
        # Tashqi: ruxsat/toll — Follow Me EGASINIKI (`INNOVA_FWD_FROM`, yo'naltirish kabi);
        # javob bergan trunk kanalida `innova-rec` tasdiq so'raydi (`__INNOVA_FM_CONFIRM` meros).
        " same => n(external),Set(INNOVA_FWD_FROM=${INNOVA_FM_OWNER})",
        " same => n,Set(__INNOVA_FM_CONFIRM=${INNOVA_FM_CONF})",
        f" same => n,Goto({code}-outbound,${{EXTEN}},1)",
    ]


# ------------------------------------------------------------ outbound manba
def outbound_source_lines(blocked_expr: str | None) -> list[str]:
    """`INNOVA_SRC_EXT` — ruxsatlari tekshiriladigan ichki raqam:
    yo'naltiruvchi ext > blind transfer qilgan ext > chaqiruvchining o'zi.
    *-kodlar holatni `CHANNEL(endpoint)` bo'yicha yozadi (CALLERID emas — trunk
    CLI'si soxtalashtirilsa ham boshqa ext'ning yo'naltirishini o'zgartira olmaydi).
    Trunk'dan kelgan kanal na yo'naltirish, na transfer bilan kelmagan bo'lsa
    (masalan IVR to'g'ridan-to'g'ri terish) — chiquvchi marshrutga KIRMAYDI."""
    lines = [
        " same => n,Set(INNOVA_SRC_EXT=${CALLERID(num)})",
        ' same => n,ExecIf($["${BLINDTRANSFER}"!=""]?Set(INNOVA_SRC_EXT=${CUT(BLINDTRANSFER,-,2)}))',
        ' same => n,ExecIf($["${INNOVA_FWD_FROM}"!=""]?Set(INNOVA_SRC_EXT=${INNOVA_FWD_FROM}))',
        ' same => n,GotoIf($["${INNOVA_FROM_TRUNK}${INNOVA_FWD_FROM}${BLINDTRANSFER}"="1"]?outbound_blocked)',
        # Transfer qilgan tomon trunk bo'lsa (`PJSIP/<code>-trunk-...`) — rad.
        ' same => n,GotoIf($["${INNOVA_SRC_EXT}"="trunk"]?outbound_blocked)',
    ]
    if blocked_expr:
        # outbound_allowed=false — chiquvchi marshrutga UMUMAN kirmaydi
        lines.append(f" same => n,GotoIf({blocked_expr}?outbound_blocked)")
    return lines


def outbound_blocked_lines() -> list[str]:
    return [" same => n(outbound_blocked),NoOp(Innova: chiquvchi qo'ng'iroq taqiqlangan ${INNOVA_SRC_EXT})",
            " same => n,Congestion()",
            " same => n,Hangup()"]


# ------------------------------------------------------------ qo'ng'iroq guruhi
def ring_group_set_lines(code: str, idx: int, members: list[tuple[str, bool]], ring_seconds: int) -> list[str]:
    """Bitta `Dial()` to'plami runtime'da yig'iladi: DND yoqilgan ichki a'zo
    tashlab ketiladi, tashqi a'zo (`Local/...@<code>-outbound-rg`) doim kiradi."""
    lines = [" same => n,Set(INNOVA_RG=)"]
    for number, is_external in members:
        if is_external:
            lines.append(f" same => n,Set(INNOVA_RG=${{INNOVA_RG}}&Local/{number}@{code}-outbound-rg)")
            continue
        dnd = realtime_read(code, number, "dnd")
        # SIP endpoint id — prefikssiz (`sip_identity.endpoint_id`), `number` shu bilan BIR XIL.
        lines.append(f' same => n,ExecIf($["{dnd}"!="t"]?Set(INNOVA_RG=${{INNOVA_RG}}&PJSIP/{number}))')
    lines += [
        f' same => n,GotoIf($["${{INNOVA_RG}}"=""]?rg{idx}_skip)',
        *recorded_dial_lines("${INNOVA_RG:1}", str(ring_seconds), XFER_OPTIONS),
        f" same => n(rg{idx}_skip),NoOp(Innova: guruh to'plami {idx} tugadi)",
    ]
    return lines


# ------------------------------------------------------------ funksiya kodlari
def _vm_own(code: str, fc: str) -> list[str]:
    return [f"exten => {fc},1,NoOp(Innova: o'z ovozli pochtasi)",
            " same => n,Set(INNOVA_VM_BOX=${CALLERID(num)})",
            f" same => n,Goto({code}-vm-main,s,1)"]


def _vm_other(code: str, fc: str) -> list[str]:
    return [f"exten => {fc},1,NoOp(Innova: istalgan ovozli pochta)",
            " same => n,Answer()",
            " same => n,Read(INNOVA_VM_BOX,vm-login,10)",
            f" same => n,Goto({code}-vm-main,s,1)"]


def _toggle_realtime_lines(
    fc: str, *, noop: str, family: str, column: str, after_write: list[str], success_playback: str,
) -> list[str]:
    """Umumiy "o'qi -> teskarisini yoz -> qayta o'qib tasdiqla" skeleti —
    `_dnd_toggle`/`_queue_login`/`_queue_pause` BIR XIL qolipdan (dryar):
    farqi faqat ustun nomi, yozuvdan KEYINGI qo'shimcha qatorlar (`after_write`
    — masalan DND ovozi yoki Pause/UnpauseQueueMember turtkisi) va muvaffaqiyat
    ovozi (`success_playback`, `"<yoqilgan>:<o'chirilgan>"` shaklida)."""
    ep = "${INNOVA_EP}"
    read = f"${{REALTIME_FIELD({family},endpoint,{ep},{column})}}"
    return [
        f"exten => {fc},1,NoOp(Innova: {noop})",
        " same => n,Answer()",
        " same => n,Set(INNOVA_EP=${CHANNEL(endpoint)})",
        f' same => n,Set(INNOVA_NEW=${{IF($["{read}"="t"]?f:t)}})',
        f" same => n,Set(REALTIME({family},endpoint,{ep},{column})=${{INNOVA_NEW}})",
        f' same => n,GotoIf($["{read}"!="${{INNOVA_NEW}}"]?err)',
        *after_write,
        f' same => n,Playback(${{IF($["${{INNOVA_NEW}}"="t"]?{success_playback})}})',
        " same => n,Hangup()",
        " same => n(err),Playback(invalid)",
        " same => n,Hangup()",
    ]


def _dnd_toggle(code: str, fc: str) -> list[str]:
    return _toggle_realtime_lines(
        fc, noop="DND almashtirish", family=EXT_STATE_FAMILY, column="dnd",
        after_write=[" same => n,Playback(do-not-disturb)"], success_playback="activated:de-activated",
    )


def _queue_login(code: str, fc: str) -> list[str]:
    """*45 — navbat login/logout ALMASHTIRISH (m2b-contract.md §1): ext'ning
    BARCHA navbatlaridagi DINAMIK a'zoliklariga ta'sir qiladi (`asterisk_agent_state`
    view INSTEAD OF UPDATE trigger, 0015_m2b_agent_state.sql)."""
    return _toggle_realtime_lines(
        fc, noop="navbat login/logout almashtirish", family=AGENT_STATE_FAMILY, column="logged_in",
        after_write=[], success_playback="agent-loginok:agent-loggedoff",
    )


def _queue_pause(code: str, fc: str) -> list[str]:
    """*46 — pauza ALMASHTIRISH (m2b-contract.md §1): ext'ning BARCHA
    a'zoliklariga (statik ham, dinamik ham) ta'sir qiladi. PG yozilgandan
    keyin `PauseQueueMember`/`UnpauseQueueMember` (bo'sh navbat nomi = BARCHA
    navbatlar) — Asterisk xotirasidagi holatni darhol sinxronlaydi (≤ 3 s
    talabi, m2b-contract.md §0); bu IKKINCHI MANBA EMAS — PG allaqachon
    yozilgan, bu faqat kutayotgan qo'ng'iroq uchun jonli turtki."""
    return _toggle_realtime_lines(
        fc, noop="navbat pauza almashtirish", family=AGENT_STATE_FAMILY, column="paused",
        after_write=[
            ' same => n,ExecIf($["${INNOVA_NEW}"="t"]?PauseQueueMember(,PJSIP/${INNOVA_EP}))',
            ' same => n,ExecIf($["${INNOVA_NEW}"="f"]?UnpauseQueueMember(,PJSIP/${INNOVA_EP}))',
        ],
        success_playback="activated:de-activated",
    )


def _followme_toggle(code: str, fc: str) -> list[str]:
    """*21 — Follow Me yoqish/o'chirish (M5b). Ro'yxat bo'sh bo'lsa CHECK yoqishni rad etadi →
    qayta o'qish farq qiladi → `invalid` (skelet o'zi)."""
    return _toggle_realtime_lines(
        fc, noop="Follow Me almashtirish", family=EXT_STATE_FAMILY, column="fm_enabled",
        after_write=[], success_playback="activated:de-activated",
    )


_CF_PROMPTS = {"forward_always": "call-fwd-unconditional", "forward_busy": "call-fwd-on-busy"}


def _cf_on(column: str) -> Callable[[str, str], list[str]]:
    def build(code: str, fc: str) -> list[str]:
        return [
            f"exten => _{fc}X.,1,NoOp(Innova: yo'naltirish {column} -> ${{EXTEN:{len(fc)}}})",
            f" same => n,Set(INNOVA_NUM=${{EXTEN:{len(fc)}}})",
            " same => n,Set(INNOVA_CF_ON=1)",
            f" same => n,Goto({code}-cf,{column},1)",
            f"exten => {fc},1,NoOp(Innova: yo'naltirish {column} — raqam so'raladi)",
            " same => n,Answer()",
            f" same => n,Read(INNOVA_NUM,{_CF_PROMPTS[column]},15,,1,10)",
            " same => n,Set(INNOVA_CF_ON=1)",
            f" same => n,Goto({code}-cf,{column},1)",
        ]
    return build


def _cf_off(column: str) -> Callable[[str, str], list[str]]:
    def build(code: str, fc: str) -> list[str]:
        return [f"exten => {fc},1,NoOp(Innova: yo'naltirish {column} o'chiriladi)",
                " same => n,Set(INNOVA_NUM=)",
                " same => n,Set(INNOVA_CF_ON=)",
                f" same => n,Goto({code}-cf,{column},1)"]
    return build


def _simple(*apps: str) -> Callable[[str, str], list[str]]:
    """Ilovalar ketma-ketligi; `{code}`/`{rest}` — tenant va kod ortidagi raqam."""
    def build(code: str, fc: str) -> list[str]:
        exten = f"_{fc}X." if any("{rest}" in a for a in apps) else fc
        rest = f"${{EXTEN:{len(fc)}}}"
        body = [a.format(code=code, rest=rest) for a in apps]
        return [f"exten => {exten},1,{body[0]}"] + [f" same => n,{a}" for a in body[1:]]
    return build


FEATURE_BUILDERS: dict[str, Callable[[str, str], list[str]]] = {
    "voicemail": _vm_own,
    "voicemail_other": _vm_other,
    "dnd_toggle": _dnd_toggle,
    "cf_always_on": _cf_on("forward_always"),
    "cf_always_off": _cf_off("forward_always"),
    "cf_busy_on": _cf_on("forward_busy"),
    "cf_busy_off": _cf_off("forward_busy"),
    "pickup_group": _simple("Pickup()", "Hangup()"),
    "pickup_direct": _simple("Pickup({code}-{rest}@PICKUPMARK)", "Hangup()"),
    "park": _simple("Park({code}-park)", "Hangup()"),
    "echo_test": _simple("Answer()", "Playback(demo-echotest)", "Echo()", "Hangup()"),
    "speaking_clock": _simple("Answer()", "SayUnixTime()", "Hangup()"),
    "queue_login": _queue_login,
    "queue_pause": _queue_pause,
    "followme_toggle": _followme_toggle,
}

# API'da ko'rsatiladigan va dialplan'ga yoziladigan tartib (m2a-contract.md §2).
FEATURE_ORDER = tuple(FEATURE_BUILDERS)


def feature_code_lines(code: str, codes: dict[str, str]) -> list[str]:
    lines: list[str] = []
    for feature in FEATURE_ORDER:
        if feature in codes:
            lines += FEATURE_BUILDERS[feature](code, codes[feature])
    return lines


def cf_context_lines(code: str) -> list[str]:
    """Yozuv + qayta o'qib tekshirish. Bo'sh `INNOVA_NUM` (o'chirish) — NULL
    (view trigger'i `nullif`). Yoqishda bo'sh raqam yoki o'ziga yo'naltirish — xato."""
    lines = [f"[{code}-cf]"]
    ep = "${INNOVA_EP}"
    for column, prompt in _CF_PROMPTS.items():
        read = f"${{REALTIME_FIELD({EXT_STATE_FAMILY},endpoint,{ep},{column})}}"
        lines += [
            f"exten => {column},1,NoOp(Innova: {column}=${{INNOVA_NUM}})",
            " same => n,Answer()",
            " same => n,Set(INNOVA_EP=${CHANNEL(endpoint)})",
            ' same => n,GotoIf($["${INNOVA_CF_ON}${INNOVA_NUM}"="1"]?err)',
            ' same => n,GotoIf($["${INNOVA_NUM}"="${CALLERID(num)}"]?err)',
            f" same => n,Set(REALTIME({EXT_STATE_FAMILY},endpoint,{ep},{column})=${{INNOVA_NUM}})",
            f' same => n,GotoIf($["{read}"!="${{INNOVA_NUM}}"]?err)',
            f" same => n,Playback({prompt})",
            ' same => n,GotoIf($["${INNOVA_NUM}"=""]?off)',
            " same => n,SayDigits(${INNOVA_NUM})",
            " same => n,Playback(activated)",
            " same => n,Hangup()",
            " same => n(off),Playback(de-activated)",
            " same => n,Hangup()",
            " same => n(err),Playback(invalid)",
            " same => n,Hangup()",
        ]
    return lines


# ------------------------------------------------------------ park
def park_lines(code: str) -> list[str]:
    """Lot raqami 700 — priority 1 da `Park()` SHART: `##700` blind transfer'ni
    res_parking aynan shu bo'yicha park deb taniydi. 701–720 — qaytarib olish."""
    lot = park_lot_name(code)
    lines = [f"exten => {PARK_LOT_NUMBER},1,Park({lot})", " same => n,Hangup()"]
    for slot in range(PARK_FIRST_SLOT, PARK_LAST_SLOT + 1):
        lines.append(f"exten => {slot},1,ParkedCall({lot},{slot})")
        lines.append(" same => n,Hangup()")
    return lines


def parking_conf_text(code: str) -> str:
    """`res_parking.conf` #include qiladigan lot fayli (`/srv/dialplan`)."""
    return (
        "; Innova PBX — avtomatik yaratilgan fayl. QO'LDA TAHRIRLAMANG.\n"
        f"[{park_lot_name(code)}]\n"
        f"parkpos => {PARK_FIRST_SLOT}-{PARK_LAST_SLOT}\n"
        f"context => {code}-parkedcalls\n"
        f"parkingtime => {PARK_TIMEOUT_S}\n"
        "comebacktoorigin => yes\n"
        "parkedcalltransfers => both\n"
        "findslot => first\n"
    )


PARK_NUMBERS = frozenset({PARK_LOT_NUMBER} | {str(s) for s in range(PARK_FIRST_SLOT, PARK_LAST_SLOT + 1)})


def is_park_number(number: str) -> bool:
    return number in PARK_NUMBERS


# ------------------------------------------------------------ konferensiya (§4)
CONF_MENU = "innova-conf-menu"  # statik `confbridge.conf`da (har tenant/konferensiya uchun BIR XIL).
CONF_PIN_ATTEMPTS = 3


def conf_room(code: str, conf_id: str) -> str:
    """Bitta joy (dryer): `compiler.py` (dialplan) va `services/conference.py`
    (confbridge.conf profillari) BIR XIL nom ishlatadi."""
    return f"{code}-conf-{conf_id}"


def conf_bridge_profile(code: str, conf_id: str) -> str:
    return f"{conf_room(code, conf_id)}-bridge"


def conf_user_profile(code: str, conf_id: str) -> str:
    return f"{conf_room(code, conf_id)}-user"


def conf_admin_profile(code: str, conf_id: str) -> str:
    return f"{conf_room(code, conf_id)}-admin"


# ------------------------------------------------------------ qora ro'yxat (§5)
def blacklist_check_lines(code: str) -> list[str]:
    """`[<code>-blacklist-check]` — `Gosub()` bilan chaqiriladigan BITTA umumiy
    bo'lim (DRY: har `exten`da takrorlanmaydi). `FILTER(0-9,...)` — Python
    `number_normalize.normalize_number()` bilan BIR XIL natija (bo'sh/`+`/
    bo'shliq/`-`/`()` — hammasi olib tashlanadi); bo'sh CallerID — `anonymous`.
    Mos qator topilsa (`asterisk_blacklist` view, `reason` hech qachon bo'sh
    emas — `coalesce(...,'blocked')`, 0014 migratsiya) — CDR belgilanadi va
    uziladi; aks holda chaqiruvchi o'z yo'liga (`Return()`)."""
    return [
        f"[{code}-blacklist-check]",
        "exten => s,1,Set(INNOVA_BL_NUM=${FILTER(0-9,${CALLERID(num)})})",
        ' same => n,Set(INNOVA_BL_NUM=${IF($["${INNOVA_BL_NUM}"=""]?anonymous:${INNOVA_BL_NUM})})',
        f" same => n,Set(INNOVA_BL_REASON=${{REALTIME_FIELD({BLACKLIST_FAMILY},endpoint,"
        f"{code}-${{INNOVA_BL_NUM}},reason)}})",
        ' same => n,GotoIf($["${INNOVA_BL_REASON}"=""]?s-return)',
        " same => n,Set(CDR(userfield)=blacklisted)",
        " same => n,Hangup(21)",
        " same => n(s-return),Return()",
    ]
