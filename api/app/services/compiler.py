"""Dialplan kompilyatori — SOF funksiya: `DialplanSnapshot` (bazadan o'qilgan
ko'rinish) kiradi, `extensions_innova.conf` matni chiqadi. IO yo'q, tasodif
yo'q — bir xil kirish doim bir xil chiqish beradi (sha256 solishtirish shuni
talab qiladi).

Kontekstlar (architecture.md «Kontekstlar» bo'limi):
  <code>-from-internal  — ro'yxatdan o'tgan ichki raqamlar shu yerdan qo'ng'iroq qiladi
  <code>-from-trunk     — IP-trunk'dan kiruvchi qo'ng'iroqlar (identify bo'yicha)
  <code>-dest-<target_id> — har manzil uchun alohida kichik kontekst (bitta joy — bitta ma'no)
  <code>-outbound       — M1b: `from-internal`da mos ichki raqam topilmagan terilgan
                           raqam shu yerga tushadi (CALLERID(num) = terayotgan ichki
                           raqamning o'zi — `ps_endpoints` buni allaqachon shunday
                           o'rnatadi, pastdagi izohga qarang).
  <code>-outbound-rg    — M1b: qo'ng'iroq guruhidagi TASHQI a'zoga `Local/<raqam>@...`
                           orqali kirish — ichki raqam ruxsati TEKSHIRILMAYDI (m1b-contract.md
                           bo'lim 3), lekin xalqaro qoida amal qiladi.

M1b CallerID aniqlash (m1b-contract.md 31-32-qator, `app/services/outbound_rules.
resolve_callerid` bilan BIR XIL ustunlik tartibi, lekin mantiq runtime'da dialplan
o'zgaruvchilari bilan takrorlanadi — Python funksiyasi o'zi dialplan ichida
chaqirilmaydi, chunki Asterisk Python'ni chaqira olmaydi):
  INNOVA_SRC_EXT — qo'ng'iroq qiluvchi ichki raqamning NOMERI (`${CALLERID(num)}`,
  ps_endpoints realtime view extensions.number'ni comment sifatida o'rnatadi).
  INNOVA_EXT_CID — shu raqamga mos `extensions.outbound_callerid` (compile-time
  ma'lum, cheklangan ro'yxat — har bir extension uchun bitta `Set(...)` qatori).
  Ustunlik: (A) `override_extension_callerid` + `route.callerid` — FIKS qiymat;
  (B) `route.callerid` BOR (override yo'q) — ext_cid BO'LSA ustun, aks holda route;
  (C) `route.callerid` YO'Q — ext_cid BO'LSA ustun, aks holda HAR BIR trunk urinishida
  o'zining `trunk.outbound_callerid`'i (agar bor bo'lsa) ishlatiladi.

PIN tekshiruvi — Asterisk dialplan bcrypt solishtira olmaydi (`outbound_routes.pin_hash`).
`CURL()` dialplan funksiyasi (tasdiqlangan: `res_curl`/`func_curl` yuklangan,
build-log.md) ichki `/internal/outbound-routes/{id}/pin-check` endpoint'iga
murojaat qiladi — parol ochiq matnda dialplan faylida (0644) SAQLANMAYDI.

DID CDR'da ko'rinishi uchun `Set(CDR(userfield)=${EXTEN})` ishlatiladi (dst/konteksti
Goto bilan o'zgaradi, userfield — DID'ni saqlaydigan barqaror joy).

M1a (replica/m1a-contract.md) — manzil turlari kengaytirildi: time_condition
(ish vaqti), ivr, ring_group, queue, hangup, busy. Halqa tekshiruvi endi
umumiy grafik ustida ishlaydi (`_build_edges`): faqat "avtomatik" qirralar
(timeout/invalid/no_answer/open/closed) hisobga olinadi — IVR tugma (digit)
qirralari ATAYLAB chiqarib tashlanadi (m1a-contract.md: «Tugma orqali
halqa — ruxsat»).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from app.services import dialplan_features as feat
from app.services import dialplan_recording as rec
from app.services import outbound_rules as rules
from app.services.dialplan_campaign import campaign_context_lines

_WEEKDAY_NAMES = {1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat", 7: "sun"}


class CompileError(Exception):
    """Kompilyatsiya qila olmaydigan holat — halqa, noma'lum manzil turi.

    `code`/`details` — `app/services/apply.py` orqali API xato formatiga
    o'tadi (m1a-contract.md: halqa uchun 422 `loop` + `details.path`)."""

    def __init__(self, message: str, *, code: str = "compile_error", details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class ExtensionSnapshot:
    id: str
    number: str
    name: str
    ring_seconds: int
    target_id: str
    no_answer_target_id: str | None = None


@dataclass(frozen=True)
class TargetSnapshot:
    id: str
    kind: str
    label: str


@dataclass(frozen=True)
class InboundRouteSnapshot:
    id: str
    did: str
    callerid_pattern: str
    target_id: str
    enabled: bool = True


@dataclass(frozen=True)
class DialNumberSnapshot:
    number: str
    target_id: str


@dataclass(frozen=True)
class TimeRangeSnapshot:
    weekdays: tuple[int, ...]
    start: str  # "HH:MM"
    end: str    # "HH:MM"


@dataclass(frozen=True)
class TimeConditionSnapshot:
    id: str
    target_id: str
    name: str
    ranges: tuple[TimeRangeSnapshot, ...]
    honor_holidays: bool
    override: str  # auto|force_open|force_closed
    open_target_id: str
    closed_target_id: str
    toggle_code: str | None = None


@dataclass(frozen=True)
class IvrOptionSnapshot:
    digit: str
    target_id: str


@dataclass(frozen=True)
class IvrSnapshot:
    id: str
    target_id: str
    name: str
    greeting_audio_id: str
    invalid_audio_id: str | None
    timeout_seconds: int
    repeats: int
    direct_dial: bool
    timeout_target_id: str
    invalid_target_id: str
    options: tuple[IvrOptionSnapshot, ...] = ()


@dataclass(frozen=True)
class RingGroupMemberSnapshot:
    position: int
    extension_number: str | None
    is_external: bool = False


@dataclass(frozen=True)
class RingGroupSnapshot:
    id: str
    target_id: str
    name: str
    strategy: str  # ringall|hunt|memoryhunt
    ring_seconds: int
    no_answer_target_id: str
    members: tuple[RingGroupMemberSnapshot, ...] = ()


# -------------------------------------------------------------- M1b: chiquvchi
@dataclass(frozen=True)
class OutboundPatternSnapshot:
    strip_prefix: str
    pattern: str
    add_prefix: str


@dataclass(frozen=True)
class OutboundTrunkSnapshot:
    position: int
    id: str
    name: str
    outbound_callerid: str | None = None


@dataclass(frozen=True)
class OutboundRouteSnapshot:
    id: str
    name: str
    priority: int
    enabled: bool
    international: bool
    patterns: tuple[OutboundPatternSnapshot, ...]
    trunks: tuple[OutboundTrunkSnapshot, ...]
    callerid: str | None = None
    override_extension_callerid: bool = False
    has_pin: bool = False
    allowed_extension_numbers: tuple[str, ...] | None = None  # None = "all"


@dataclass(frozen=True)
class ExtensionCallerIdSnapshot:
    number: str
    outbound_callerid: str


@dataclass(frozen=True)
class QueueSnapshot:
    id: str
    target_id: str
    name: str
    max_wait_seconds: int
    timeout_target_id: str


@dataclass(frozen=True)
class VoicemailBoxSnapshot:
    """Ovozli pochta qutisi (m1c-contract.md §2) — Asterisk konteksti = tenant `code`."""
    target_id: str
    mailbox: str


@dataclass(frozen=True)
class ConferenceSnapshot:
    """Konferensiya (m2a-contract.md §4). PIN'ning o'zi (hash) BU YERDA YO'Q —
    dialplan hech qachon hashni solishtirmaydi, ichki CURL() endpoint'ga
    murojaat qiladi (`has_pin`/`has_admin_pin` — faqat so'rash kerakligini
    bilish uchun), xuddi `OutboundRouteSnapshot.has_pin` kabi."""
    id: str
    target_id: str
    name: str
    has_pin: bool
    has_admin_pin: bool


@dataclass(frozen=True)
class DialplanSnapshot:
    tenant_code: str
    extensions: list[ExtensionSnapshot] = field(default_factory=list)
    targets: dict[str, TargetSnapshot] = field(default_factory=dict)
    inbound_routes: list[InboundRouteSnapshot] = field(default_factory=list)
    dial_numbers: list[DialNumberSnapshot] = field(default_factory=list)
    time_conditions: list[TimeConditionSnapshot] = field(default_factory=list)
    ivrs: list[IvrSnapshot] = field(default_factory=list)
    ring_groups: list[RingGroupSnapshot] = field(default_factory=list)
    queues: list[QueueSnapshot] = field(default_factory=list)
    holidays_mmdd: tuple[tuple[int, int], ...] = ()
    audio_paths: dict[str, str] = field(default_factory=dict)
    outbound_routes: list[OutboundRouteSnapshot] = field(default_factory=list)
    extension_callerids: tuple[ExtensionCallerIdSnapshot, ...] = ()
    internal_api_base_url: str = ""
    internal_api_token: str = ""
    # `Extension.outbound_allowed=false` raqamlari -- avval faqat
    # /outbound-routes/simulate'da tekshirilardi, haqiqiy dialplan'da
    # (`[t1-from-internal]`) hech qachon emas (ishlab chiqarish xatosi,
    # m1b-contract.md bo'lim 9 ssenariy 3). Shu yerda saqlab, chiquvchi
    # kontekstga o'tishdan OLDIN CALLERID(num) bo'yicha bloklaymiz.
    outbound_blocked_extension_numbers: tuple[str, ...] = ()
    voicemail_boxes: list[VoicemailBoxSnapshot] = field(default_factory=list)
    # M2a §2: yoqilgan funksiya kodlari, feature -> kod (`feature_codes` jadvali).
    feature_codes: dict[str, str] = field(default_factory=dict)
    # M2a §4: konferensiyalar (`dest-<target_id>` — PIN so'rash + ConfBridge()).
    conferences: list[ConferenceSnapshot] = field(default_factory=list)
    # M2c §3 — toll-fraud: `system_settings.toll_fraud.max_concurrent_outbound`
    # (0 = cheksiz -> GROUP() qatorlari umuman chiqmaydi, m2c-contract.md §3).
    toll_max_concurrent_outbound: int = 0


def dialplan_sha256(dialplan_text: str) -> str:
    return hashlib.sha256(dialplan_text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------- halqa
def _build_edges(snapshot: DialplanSnapshot) -> dict[str, list[str]]:
    """Faqat "avtomatik" (foydalanuvchi tanlovisiz yurilgan) qirralar —
    IVR tugma (digit) tanlovlari ATAYLAB kiritilmagan (ruxsat etilgan halqa)."""
    edges: dict[str, list[str]] = {}

    def add(src: str | None, dst: str | None) -> None:
        if src and dst:
            edges.setdefault(src, []).append(dst)

    for ext in snapshot.extensions:
        add(ext.target_id, ext.no_answer_target_id)
    for tc in snapshot.time_conditions:
        add(tc.target_id, tc.open_target_id)
        add(tc.target_id, tc.closed_target_id)
    for ivr in snapshot.ivrs:
        add(ivr.target_id, ivr.timeout_target_id)
        add(ivr.target_id, ivr.invalid_target_id)
    for rg in snapshot.ring_groups:
        add(rg.target_id, rg.no_answer_target_id)
    for q in snapshot.queues:
        add(q.target_id, q.timeout_target_id)
    return edges


def _label(snapshot: DialplanSnapshot, target_id: str) -> str:
    target = snapshot.targets.get(target_id)
    return target.label if target is not None else target_id


def _detect_target_cycle(snapshot: DialplanSnapshot) -> None:
    """IVR/navbat/guruh/ish-vaqti zanjirida timeout/invalid/no_answer/open/closed
    yo'lida chiqishsiz halqa bo'lsa — `CompileError(code="loop")` (m1a-contract.md)."""
    edges = _build_edges(snapshot)
    visited: set[str] = set()

    def dfs(node: str, stack: list[str]) -> None:
        if node in stack:
            cycle = stack[stack.index(node):] + [node]
            path = [_label(snapshot, n) for n in cycle]
            raise CompileError(
                "Qo'ng'iroq oqimida chiqishsiz halqa topildi: " + " -> ".join(path),
                code="loop", details={"path": path},
            )
        if node in visited:
            return
        visited.add(node)
        stack.append(node)
        for nxt in edges.get(node, []):
            dfs(nxt, stack)
        stack.pop()

    for start in list(edges):
        if start not in visited:
            dfs(start, [])


# ------------------------------------------------------------- yordamchilar
def _extension_by_target(snapshot: DialplanSnapshot) -> dict[str, ExtensionSnapshot]:
    return {e.target_id: e for e in snapshot.extensions}


# ----------------------------------------------------------- dest-<target>
def _extension_dest_lines(code: str, ext: ExtensionSnapshot) -> list[str]:
    """M2a: ichki raqamga har qanday yo'l (DID, IVR, guruh javobsiz manzili) —
    yagona `<code>-ext` oqimi (DND/yo'naltirish/transfer bir joyda)."""
    return [f"exten => s,1,NoOp(Innova: {ext.name} <{ext.number}>)",
            f" same => n,Goto({code}-ext,{ext.number},1)"]


def _time_condition_dest_lines(code: str, tc: TimeConditionSnapshot, holidays: tuple) -> list[str]:
    lines = [f"exten => s,1,NoOp(Innova: ish vaqti {tc.name})"]
    if tc.override == "force_open":
        lines.append(f" same => n,Goto({code}-dest-{tc.open_target_id},s,1)")
        return lines
    if tc.override == "force_closed":
        lines.append(f" same => n,Goto({code}-dest-{tc.closed_target_id},s,1)")
        return lines
    if tc.honor_holidays:
        for month, day in holidays:
            lines.append(f" same => n,GotoIfTime(*,*,{day},{month}?closed)")
    for rng in tc.ranges:
        days = ",".join(_WEEKDAY_NAMES[d] for d in sorted(rng.weekdays))
        lines.append(f" same => n,GotoIfTime({rng.start}-{rng.end},{days},*,*?open)")
    lines.append(" same => n,Goto(closed)")
    lines.append(f" same => n(open),Goto({code}-dest-{tc.open_target_id},s,1)")
    lines.append(f" same => n(closed),Goto({code}-dest-{tc.closed_target_id},s,1)")
    return lines


def _ivr_dest_lines(code: str, ivr: IvrSnapshot, audio_paths: dict[str, str]) -> list[str]:
    # `Answer()` SHART (sinovda topilgan): `Background()` javob berilmagan
    # kanalda ovoz chiqarmaydi, `WaitExten()` esa SIP INFO orqali DTMF
    # qabul qilish uchun o'rnatilgan (javob berilgan) dialog talab qiladi.
    # Idempotent — kanal allaqachon javob berilgan bo'lsa, no-op.
    greeting = audio_paths.get(ivr.greeting_audio_id, "")
    lines = [
        f"exten => s,1,NoOp(Innova: IVR {ivr.name})",
        " same => n,Answer()",
        " same => n,Set(IVR_REPEAT=0)",
        f" same => n(menu),Background({greeting})",
        f" same => n,WaitExten({ivr.timeout_seconds})",
    ]
    for opt in sorted(ivr.options, key=lambda o: o.digit):
        lines.append(f"exten => {opt.digit},1,Goto({code}-dest-{opt.target_id},s,1)")
    if ivr.direct_dial:
        lines.append(f"exten => _X.,1,Goto({code}-from-internal,${{EXTEN}},1)")
    lines.append("exten => t,1,Set(IVR_REPEAT=$[${IVR_REPEAT} + 1])")
    lines.append(f" same => n,GotoIf($[${{IVR_REPEAT}} <= {ivr.repeats}]?s,menu)")
    lines.append(f" same => n,Goto({code}-dest-{ivr.timeout_target_id},s,1)")
    lines.append("exten => i,1,NoOp(Innova: IVR noto'g'ri tanlov)")
    if ivr.invalid_audio_id:
        lines.append(f" same => n,Background({audio_paths.get(ivr.invalid_audio_id, '')})")
    lines.append(f" same => n,Goto({code}-dest-{ivr.invalid_target_id},s,1)")
    return lines


def _ring_group_dest_lines(code: str, rg: RingGroupSnapshot) -> list[str]:
    lines = [f"exten => s,1,NoOp(Innova: qo'ng'iroq guruhi {rg.name})"]
    members = [m for m in sorted(rg.members, key=lambda m: m.position) if m.extension_number]
    if not members:
        lines.append(" same => n,NoOp(Innova: guruhda a'zo yo'q)")
        lines.append(f" same => n,Goto({code}-dest-{rg.no_answer_target_id},s,1)")
        return lines
    lines.append(f" same => n,Set(__TRANSFER_CONTEXT={code}-from-internal)")
    pairs = [(m.extension_number, m.is_external) for m in members]
    for idx, dial_set in enumerate(_rg_dial_sets(rg.strategy, pairs), start=1):
        lines += feat.ring_group_set_lines(code, idx, dial_set, rg.ring_seconds)
    lines.append(f" same => n,Goto({code}-dest-{rg.no_answer_target_id},s,1)")
    return lines


def _rg_dial_sets(strategy: str, endpoints: list) -> list[list]:
    """Har `Dial()` bir vaqtda jiringlaydigan to'plam: ringall — hammasi birdan; hunt — bittadan;
    memoryhunt — yig'ilib boradi (1, 1+2, 1+2+3 …), holat saqlash shart emas."""
    if strategy == "ringall":
        return [endpoints]
    if strategy == "memoryhunt":
        return [endpoints[:i] for i in range(1, len(endpoints) + 1)]
    return [[endpoint] for endpoint in endpoints]


def _or_expr(var: str, values: tuple[str, ...]) -> str:
    """`$["VAR"="a"] | $["VAR"="b"] ...` — ko'p qiymatli solishtirish (ext ro'yxati)."""
    parts = [f'$["${{{var}}}"="{v}"]' for v in values]
    return parts[0] if len(parts) == 1 else "$[ " + " | ".join(parts) + " ]"


def _route_extension_filter_lines(idx: int, route: OutboundRouteSnapshot, next_label: str) -> list[str]:
    if route.allowed_extension_numbers is None:
        return []
    expr = _or_expr("INNOVA_SRC_EXT", route.allowed_extension_numbers)
    return [f" same => n,GotoIf({expr}?r{idx}_intl:{next_label})"]


def _route_international_lines(idx: int, route: OutboundRouteSnapshot, next_label: str) -> list[str]:
    """`app/services/outbound_rules.international_blocked` bilan BIR XIL
    mantiq: `00`/`+` xalqaro prefiksi OLIB TASHLANGANDAN KEYIN `998` bilan
    boshlanmasa — bloklanadi (`00998...`/`+998...` — O'zbekistonga xalqaro
    format, bloklanMAYDI)."""
    if route.international:
        return []
    return [
        f' same => n,GotoIf($["${{EXTEN:0:2}}"="00"]?r{idx}_intl00)',
        f' same => n,GotoIf($["${{EXTEN:0:1}}"="+"]?r{idx}_intlplus)',
        f" same => n,Goto(r{idx}_patterns)",
        f' same => n(r{idx}_intl00),GotoIf($["${{EXTEN:2:3}}"="998"]?r{idx}_patterns)',
        f" same => n,Goto({next_label})",
        f' same => n(r{idx}_intlplus),GotoIf($["${{EXTEN:1:3}}"="998"]?r{idx}_patterns)',
        f" same => n,Goto({next_label})",
    ]


def _route_pattern_lines(idx: int, route: OutboundRouteSnapshot, next_label: str) -> list[str]:
    lines: list[str] = []
    for pidx, pat in enumerate(route.patterns, start=1):
        strip_len = len(pat.strip_prefix)
        stripped = "${EXTEN}" if not strip_len else f"${{EXTEN:{strip_len}}}"
        lines.append(f" same => n,Set(INNOVA_STRIPPED={stripped})")
        body = rules.pattern_to_regex_body(pat.pattern)
        # MUHIM (ishlab chiqarish xatosi, jonli SIP isbotida topildi):
        # Asterisk'ning `REGEX()` funksiyasi (`funcs/func_strings.c`,
        # `AST_NONSTANDARD_APP_ARGS(args, parse, '"')`) yopiq qo'shtirnoqdan
        # keyin FAQAT bo'shliq/tab'ni tashlab yuboradi, VERGULNI EMAS. Vergul
        # qo'ysak `args.str` = ",${INNOVA_STRIPPED}" bo'lib qoladi -- boshi
        # "," bilan boshlanadi, shuning uchun `^` langar HECH QACHON mos
        # kelmaydi (langarsiz naqshlar esa tasodifan mos kelgandek ko'rinadi
        # -- yashiringan xato). Shu sabab BO'SHLIQ ishlatiladi, vergul emas.
        lines.append(
            f' same => n,GotoIf($[${{REGEX("^{body}$" ${{INNOVA_STRIPPED}})}} = 1]?r{idx}_p{pidx}_matched)')
    lines.append(f" same => n,Goto({next_label})")
    for pidx, pat in enumerate(route.patterns, start=1):
        lines.append(f" same => n(r{idx}_p{pidx}_matched),Set(INNOVA_DIALED={pat.add_prefix}${{INNOVA_STRIPPED}})")
        lines.append(f" same => n,Goto(r{idx}_proceed)")
    return lines


def _route_pin_lines(idx: int, route: OutboundRouteSnapshot, base_url: str, token: str) -> list[str]:
    if not route.has_pin:
        return []
    url = f"{base_url}/internal/outbound-routes/{route.id}/pin-check?token={token}&pin=${{INNOVA_PIN}}"
    return [
        # MUHIM (ishlab chiqarish xatosi, jonli SIP isbotida topildi, 2026-10-28):
        # ILGARI ikkinchi argument sifatida "beep" FAYL NOMI berilgan edi.
        # Ushbu Asterisk o'rnatishida (va umuman core-sounds paketi
        # o'rnatilmagan har qanday muhitda) "beep" nomli tovush fayli YO'Q.
        # `ast_app_getdata_terminator()` (main/app.c) fayl topilmasa
        # `ast_streamfile()`dan manfiy natija bilan DARHOL qaytadi va
        # RAQAM TERISH TSIKLIGA HECH QACHON KIRMAYDI -- `app_read.c` buni
        # "User disconnected" deb talqin qiladi (READSTATUS har doim
        # boshlang'ich "ERROR" qiymatida qolib ketadi). Natijada PIN
        # himoyalangan marshrut ORQALI chaqiruv qilish MUTLAQO ISHLAMAYDI
        # (haqiqiy PIN kiritilsa ham, chunki raqamlar hech qachon
        # o'qilmaydi). Fayl nomi O'RNIGA BO'SH qoldiriladi -- Read() ovozli
        # signalsiz, to'g'ridan-to'g'ri raqam kutishga o'tadi (xavfsiz,
        # hech qanday tovush faylga bog'liq emas).
        " same => n,Read(INNOVA_PIN,,8)",
        f' same => n,Set(INNOVA_PIN_OK=${{CURL({url})}})',
        f' same => n,GotoIf($["${{INNOVA_PIN_OK}}"="1"]?r{idx}_cid)',
        " same => n,Congestion()",
        " same => n,Hangup()",
    ]


def _route_callerid_lines(idx: int, route: OutboundRouteSnapshot) -> list[str]:
    """m1b-contract.md 31-32-qator ustunligi — `app/services/outbound_rules.
    resolve_callerid` bilan BIR XIL tartib (A>B>C), runtime o'zgaruvchilari bilan.
    CallerID aniqlangandan keyin har doim `r{idx}_toll1`ga o'tadi — bu toll-fraud
    tekshiruvi (M2c §3, pastda) uchun ANIQ KIRISH NUQTASI, trunk Dial zanjiridan
    OLDIN (zanjirning o'zi `r{idx}_dial1`dan o'zgarmagan boshlanadi)."""
    if route.override_extension_callerid and route.callerid:
        return [
            f" same => n(r{idx}_cid),Set(CALLERID(num)={route.callerid})",
            " same => n,Set(INNOVA_CID_DONE=1)",
            f" same => n,Goto(r{idx}_toll1)",
        ]
    if route.callerid:
        return [
            f' same => n(r{idx}_cid),GotoIf($["${{INNOVA_EXT_CID}}"!=""]?r{idx}_cid_ext:r{idx}_cid_route)',
            f" same => n(r{idx}_cid_ext),Set(CALLERID(num)=${{INNOVA_EXT_CID}})",
            " same => n,Set(INNOVA_CID_DONE=1)",
            f" same => n,Goto(r{idx}_toll1)",
            f" same => n(r{idx}_cid_route),Set(CALLERID(num)={route.callerid})",
            " same => n,Set(INNOVA_CID_DONE=1)",
            f" same => n,Goto(r{idx}_toll1)",
        ]
    return [
        f' same => n(r{idx}_cid),GotoIf($["${{INNOVA_EXT_CID}}"!=""]?r{idx}_cid_ext2:r{idx}_toll1)',
        f" same => n(r{idx}_cid_ext2),Set(CALLERID(num)=${{INNOVA_EXT_CID}})",
        " same => n,Set(INNOVA_CID_DONE=1)",
        f" same => n,Goto(r{idx}_toll1)",
    ]


# ------------------------------------------------------------- M2c §3: toll-fraud
def _toll_intl_detect_lines() -> list[str]:
    """`INNOVA_TOLL_INTL` — joriy `${EXTEN}` haqiqatan xalqaro bo'lsa `1`
    (`app/services/outbound_rules.international_blocked` BILAN BIR XIL
    `00`/`+` prefiks + `998` mantiqi, lekin bloklamaydi — faqat belgi
    o'rnatadi, `/internal/toll/check`ga `intl=` sifatida yuboriladi)."""
    return [
        " same => n,Set(INNOVA_TOLL_INTL=0)",
        ' same => n,GotoIf($["${EXTEN:0:2}"="00"]?toll_intl00)',
        ' same => n,GotoIf($["${EXTEN:0:1}"="+"]?toll_intlplus)',
        " same => n,Goto(toll_intl_done)",
        ' same => n(toll_intl00),GotoIf($["${EXTEN:2:3}"="998"]?toll_intl_done)',
        " same => n,Set(INNOVA_TOLL_INTL=1)",
        " same => n,Goto(toll_intl_done)",
        ' same => n(toll_intlplus),GotoIf($["${EXTEN:1:3}"="998"]?toll_intl_done)',
        " same => n,Set(INNOVA_TOLL_INTL=1)",
        " same => n(toll_intl_done),NoOp(Innova: xalqaro aniqlash tugadi)",
    ]


def _toll_concurrent_lines(idx: int, max_concurrent: int, base_url: str, token: str, tenant_code: str) -> list[str]:
    """`max_concurrent <= 0` -> bu qatorlar UMUMAN chiqmaydi (m2c-contract.md §3).
    Aks holda: `GROUP()` bilan belgilanadi, `GROUP_COUNT()` limitdan oshsa
    `/internal/toll/event` (javob e'tiborsiz) + `Congestion()`."""
    if max_concurrent <= 0:
        return []
    url = (f"{base_url}/internal/toll/event?token={token}&tenant={tenant_code}"
           f"&kind=concurrent_limit&ext=${{URIENCODE(${{INNOVA_SRC_EXT}})}}")
    return [
        " same => n,Set(GROUP(innova_out)=all)",
        f' same => n,GotoIf($[${{GROUP_COUNT(all@innova_out)}} > {max_concurrent}]?r{idx}_toll_conc)',
        f" same => n,Goto(r{idx}_toll_conc_ok)",
        f" same => n(r{idx}_toll_conc),NoOp(Innova: bir vaqtdagi chiquvchi limit {max_concurrent})",
        " same => n,Set(CURLOPT(conntimeout)=2)",
        " same => n,Set(CURLOPT(httptimeout)=3)",
        f' same => n,Set(INNOVA_TOLL_EVT=${{CURL({url})}})',
        " same => n,Congestion()",
        " same => n,Hangup()",
        f" same => n(r{idx}_toll_conc_ok),NoOp(Innova: bir vaqtdagi limit OK)",
    ]


def _toll_ext_check_lines(idx: int, base_url: str, token: str, tenant_code: str) -> list[str]:
    """Ichki raqam limiti — `/internal/toll/check` javobi: `"1"` davom,
    `"0"` rad, bo'sh (API ishlamayapti) — mahalliyga ruxsat, xalqaroga rad
    (fail-closed faqat xalqaro uchun, m2c-contract.md §3).

    MUHIM (jonli isbotda topilgan haqiqiy xato, 2026-10-28): bloklangan
    yo'nalishda `Playback()` ISHLATILMAYDI — kanal hali javob BERILMAGAN
    (unanswered) holatda, `Playback()` kabi media-ilovalar Asterisk'da
    kanalni ICHKI ravishda avtomatik `Answer()` qiladi, shu sabab chaqiruvchi
    tomon HAQIQATAN "200 OK" ko'rib qoladi (keyin tezda Hangup(21) bo'lsa
    ham) — toll-fraud bloki amalda ISHLAMAGANDAY ko'rinadi. `Congestion()`
    (`dialplan_features.outbound_blocked_lines` BILAN BIR XIL qolip) kanalni
    javobsiz holda rad etadi — dryer: shu qolipni takrorlaymiz."""
    url = (f"{base_url}/internal/toll/check?token={token}&tenant={tenant_code}&ext=${{URIENCODE(${{INNOVA_SRC_EXT}})}}"
           f"&number=${{URIENCODE(${{INNOVA_DIALED}})}}&intl=${{INNOVA_TOLL_INTL}}")
    return [
        " same => n,Set(CURLOPT(conntimeout)=2)",
        " same => n,Set(CURLOPT(httptimeout)=3)",
        f' same => n,Set(INNOVA_TOLL_OK=${{CURL({url})}})',
        f' same => n,GotoIf($["${{INNOVA_TOLL_OK}}"="0"]?r{idx}_toll_blocked)',
        f' same => n,GotoIf($["${{INNOVA_TOLL_OK}}"="1"]?r{idx}_toll_ok)',
        f' same => n,GotoIf($["${{INNOVA_TOLL_INTL}}"="1"]?r{idx}_toll_blocked)',
        f" same => n,Goto(r{idx}_toll_ok)",
        f" same => n(r{idx}_toll_blocked),Congestion()",
        " same => n,Hangup()",
        f" same => n(r{idx}_toll_ok),NoOp(Innova: toll tekshiruvi OK)",
    ]


def _route_trunk_dial_lines(code: str, idx: int, route: OutboundRouteSnapshot) -> list[str]:
    """Trunklar pozitsiya tartibida — `DIALSTATUS` CHANUNAVAIL/CONGESTION bo'lsa
    KEYINGI trunk (m1b-contract.md 33-qator), BUSY/NOANSWER — failover YO'Q."""
    lines: list[str] = []
    trunks = sorted(route.trunks, key=lambda t: t.position)
    for t_i, trunk in enumerate(trunks, start=1):
        is_last = t_i == len(trunks)
        fail_label = f"r{idx}_all_failed" if is_last else f"r{idx}_dial{t_i + 1}"
        lines.append(f' same => n(r{idx}_dial{t_i}),GotoIf($["${{INNOVA_CID_DONE}}"="1"]?r{idx}_dial{t_i}_go)')
        if trunk.outbound_callerid:
            lines.append(f" same => n,Set(CALLERID(num)={trunk.outbound_callerid})")
        lines.append(f" same => n(r{idx}_dial{t_i}_go),Set(CDR(userfield)={trunk.name})")
        lines += rec.recorded_dial_lines(f"PJSIP/${{INNOVA_DIALED}}@{code}-trunk-{trunk.id}", "30")
        lines.append(f' same => n,GotoIf($["${{DIALSTATUS}}"="CHANUNAVAIL"]?{fail_label})')
        lines.append(f' same => n,GotoIf($["${{DIALSTATUS}}"="CONGESTION"]?{fail_label})')
        lines.append(" same => n,Hangup()")
    lines.append(f" same => n(r{idx}_all_failed),Congestion()")
    lines.append(" same => n,Hangup()")
    return lines


def _outbound_route_block(
    code: str, idx: int, route: OutboundRouteSnapshot, next_label: str,
    *, base_url: str, token: str, toll_max_concurrent: int, toll_ext_check: bool,
) -> list[str]:
    """Bitta marshrut — tekshiruv (ext ruxsat, xalqaro, naqsh) -> PIN -> CallerID ->
    toll-fraud (M2c §3) -> trunk Dial zanjiri. `next_label` — bu marshrut mos
    kelmasa KEYINGI marshrut (yoki `no_route`). CallerID bloki har doim
    `r{idx}_toll1`ga o'tadi — toll-fraud tekshiruvlari (bo'sh bo'lsa ham, NoOp
    sifatida) har doim shu nuqtada, trunk Dial zanjiridan (`r{idx}_dial1`,
    o'zgarmagan) OLDIN turadi."""
    lines = [f" same => n(r{idx}_start),NoOp(Innova: marshrut {route.name})"]
    lines += _route_extension_filter_lines(idx, route, next_label)
    lines.append(f" same => n(r{idx}_intl),NoOp(Innova: xalqaro tekshiruv)")
    lines += _route_international_lines(idx, route, next_label)
    lines.append(f" same => n(r{idx}_patterns),NoOp(Innova: naqsh tekshiruvi)")
    lines += _route_pattern_lines(idx, route, next_label)
    lines.append(f" same => n(r{idx}_proceed),Set(INNOVA_CID_DONE=0)")
    lines += _route_pin_lines(idx, route, base_url, token)
    lines += _route_callerid_lines(idx, route)
    lines.append(f" same => n(r{idx}_toll1),NoOp(Innova: toll-fraud tekshiruvi)")
    lines += _toll_concurrent_lines(idx, toll_max_concurrent, base_url, token, code)
    if toll_ext_check:
        lines += _toll_ext_check_lines(idx, base_url, token, code)
    lines += _route_trunk_dial_lines(code, idx, route)
    return lines


def _ext_callerid_lookup_lines(extension_callerids: tuple[ExtensionCallerIdSnapshot, ...]) -> list[str]:
    """`INNOVA_EXT_CID` — chaqiruvchi ichki raqamning `outbound_callerid`'i,
    compile-time ma'lum (cheklangan ro'yxat, `ps_endpoints` CALLERID(num)'ni
    doim raqamning o'ziga o'rnatadi — build-log.md «REGISTER digest auth»
    izohi yonidagi comment, 596-qator atrofi)."""
    lines = []
    for ext in extension_callerids:
        lines.append(
            f' same => n,Set(INNOVA_EXT_CID=${{IF($["${{INNOVA_SRC_EXT}}"="{ext.number}"'
            f'?"{ext.outbound_callerid}":${{INNOVA_EXT_CID}})}})')
    return lines


def _outbound_context_lines(
    code: str, context_name: str, routes: list[OutboundRouteSnapshot],
    *, enforce_extension_filter: bool, extension_callerids: tuple[ExtensionCallerIdSnapshot, ...],
    base_url: str, token: str, blocked_numbers: tuple[str, ...] = (), toll_max_concurrent: int = 0,
) -> list[str]:
    enabled = sorted((r for r in routes if r.enabled), key=lambda r: r.priority)
    lines = [f"[{context_name}]", "exten => _X.,1,NoOp(Innova: chiquvchi qo'ng'iroq ${EXTEN})"]
    if enforce_extension_filter:
        blocked = _or_expr("INNOVA_SRC_EXT", blocked_numbers) if blocked_numbers else None
        lines += feat.outbound_source_lines(blocked)
        lines.append(f" same => n,Set(__INNOVA_REC_SRC={code}-${{INNOVA_SRC_EXT}})")
        lines.append(" same => n,Set(INNOVA_EXT_CID=)")
        lines += _ext_callerid_lookup_lines(extension_callerids)
        lines += _toll_intl_detect_lines()
    else:
        lines.append(" same => n,Set(INNOVA_EXT_CID=)")
    first_label = f"r1_start" if enabled else "no_route"
    lines.append(f" same => n,Goto({first_label})")
    for idx, route in enumerate(enabled, start=1):
        is_last = idx == len(enabled)
        next_label = "no_route" if is_last else f"r{idx + 1}_start"
        lines += _outbound_route_block(
            code, idx,
            route if enforce_extension_filter else _without_extension_filter(route),
            next_label, base_url=base_url, token=token,
            toll_max_concurrent=toll_max_concurrent, toll_ext_check=enforce_extension_filter,
        )
    lines.append(" same => n(no_route),NoOp(Innova: chiquvchi marshrut yo'q)")
    lines.append(" same => n,Congestion()")
    lines.append(" same => n,Hangup()")
    if enforce_extension_filter:
        lines += feat.outbound_blocked_lines()
    return lines


def _without_extension_filter(route: OutboundRouteSnapshot) -> OutboundRouteSnapshot:
    """`<code>-outbound-rg` — ichki raqam ruxsati TEKSHIRILMAYDI (m1b-contract.md
    bo'lim 3) — shuning uchun shart emas maydonni vaqtincha olib tashlaymiz."""
    if route.allowed_extension_numbers is None:
        return route
    return OutboundRouteSnapshot(
        id=route.id, name=route.name, priority=route.priority, enabled=route.enabled,
        international=route.international, patterns=route.patterns, trunks=route.trunks,
        callerid=route.callerid, override_extension_callerid=route.override_extension_callerid,
        has_pin=route.has_pin, allowed_extension_numbers=None,
    )


def _queue_dest_lines(code: str, q: QueueSnapshot) -> list[str]:
    # `Answer()` SHART — Asterisk `Queue()` dokumentatsiyasi: kanal
    # OLDINDAN javob berilgan deb FARZ qiladi, aks holda qo'ng'iroq
    # qiluvchi hech qanday kutish ovozini (MOH) eshitmaydi. Idempotent.
    queue_name = f"{code}-q-{q.id}"
    return [
        f"exten => s,1,NoOp(Innova: navbat {q.name})",
        " same => n,Answer()",
        *rec.recorded_queue_lines(queue_name, q.max_wait_seconds, queue_id=q.id),
        f" same => n,Goto({code}-dest-{q.timeout_target_id},s,1)",
    ]


def _terminal_dest_lines(kind: str) -> list[str]:
    action = "Hangup()" if kind == "hangup" else "Busy()"
    return [f"exten => s,1,NoOp(Innova: {kind})", f" same => n,{action}"]


def _voicemail_dest_lines(code: str, box: VoicemailBoxSnapshot) -> list[str]:
    """m1c-contract.md §2: javob bo'lmasa `u` (unavailable), band bo'lsa `b`.
    `DIALSTATUS` oldingi `Dial()` dan (ichki raqam `dest` konteksti) qoladi —
    to'g'ridan-to'g'ri (marshrut/IVR) kelganda bo'sh, ya'ni `u`."""
    mailbox = f"{box.mailbox}@{code}"
    return [
        f"exten => s,1,NoOp(Innova: ovozli pochta {box.mailbox})",
        ' same => n,GotoIf($["${DIALSTATUS}"="BUSY"]?busy)',
        f" same => n,VoiceMail({mailbox},u)",
        " same => n,Hangup()",
        f" same => n(busy),VoiceMail({mailbox},b)",
        " same => n,Hangup()",
    ]


def _conference_dest_lines(code: str, conf: ConferenceSnapshot, snapshot: DialplanSnapshot) -> list[str]:
    """m2a-contract.md §4: PIN bo'lsa ko'pi bilan `CONF_PIN_ATTEMPTS` marta so'raydi
    (tekshiruv — ichki CURL(), PIN hech qachon faylda/dialplan'da ochiq emas);
    admin PIN mos kelsa admin profili (mark/mute boshqaruvi). PIN yo'q bo'lsa
    to'g'ridan-to'g'ri oddiy a'zo profili bilan qo'shiladi. Xona to'lib ketgan
    holat — Asterisk o'zi (`max_members`, confbridge.conf) e'lon qilib uzadi."""
    room = feat.conf_room(code, conf.id)
    bridge = feat.conf_bridge_profile(code, conf.id)
    user = feat.conf_user_profile(code, conf.id)
    admin = feat.conf_admin_profile(code, conf.id)
    lines = [f"exten => s,1,NoOp(Innova: konferensiya {conf.name})", " same => n,Answer()"]
    if not conf.has_pin and not conf.has_admin_pin:
        lines.append(f" same => n,ConfBridge({room},{bridge},{user},{feat.CONF_MENU})")
        lines.append(" same => n,Hangup()")
        return lines

    url = (f"{snapshot.internal_api_base_url}/internal/conferences/{conf.id}/pin-check"
           f"?token={snapshot.internal_api_token}&pin=${{INNOVA_PIN}}")
    lines += [
        " same => n,Set(INNOVA_CONF_TRY=0)",
        " same => n(pin),Set(INNOVA_CONF_TRY=$[${INNOVA_CONF_TRY} + 1])",
        " same => n,Read(INNOVA_PIN,,8)",
        f" same => n,Set(INNOVA_CONF_ROLE=${{CURL({url})}})",
        ' same => n,GotoIf($["${INNOVA_CONF_ROLE}"="admin"]?join_admin)',
        ' same => n,GotoIf($["${INNOVA_CONF_ROLE}"="user"]?join_user)',
        f' same => n,GotoIf($[${{INNOVA_CONF_TRY}} < {feat.CONF_PIN_ATTEMPTS}]?pin)',
        " same => n,Hangup()",
        f" same => n(join_admin),ConfBridge({room},{bridge},{admin},{feat.CONF_MENU})",
        " same => n,Hangup()",
        f" same => n(join_user),ConfBridge({room},{bridge},{user},{feat.CONF_MENU})",
        " same => n,Hangup()",
    ]
    return lines


# Satellit manzil turlari: tur -> (snapshot ro'yxati, target_id -> qatorlar quruvchi).
_SATELLITE_BUILDERS = {
    "time_condition": lambda code, item, snap: _time_condition_dest_lines(code, item, snap.holidays_mmdd),
    "ivr": lambda code, item, snap: _ivr_dest_lines(code, item, snap.audio_paths),
    "ring_group": lambda code, item, snap: _ring_group_dest_lines(code, item),
    "queue": lambda code, item, snap: _queue_dest_lines(code, item),
    "voicemail": lambda code, item, snap: _voicemail_dest_lines(code, item),
    "conference": lambda code, item, snap: _conference_dest_lines(code, item, snap),
}


def _satellite_index(snapshot: DialplanSnapshot) -> dict[str, dict[str, object]]:
    """Har satellit tur uchun `target_id -> snapshot` (bir marta quriladi)."""
    sources = {
        "time_condition": snapshot.time_conditions,
        "ivr": snapshot.ivrs,
        "ring_group": snapshot.ring_groups,
        "queue": snapshot.queues,
        "voicemail": snapshot.voicemail_boxes,
        "conference": snapshot.conferences,
    }
    return {kind: {item.target_id: item for item in items} for kind, items in sources.items()}


def _dest_body_lines(
    target: TargetSnapshot, snapshot: DialplanSnapshot, by_target: dict[str, ExtensionSnapshot],
    satellites: dict[str, dict[str, object]],
) -> list[str]:
    code = snapshot.tenant_code
    if target.kind == "extension":
        ext = by_target.get(target.id)
        if ext is None:
            return [f"exten => s,1,NoOp(Innova: ichki raqam yozuvi yo'q {target.id})", " same => n,Hangup(1)"]
        return _extension_dest_lines(code, ext)
    item = satellites.get(target.kind, {}).get(target.id)
    if item is not None:
        return _SATELLITE_BUILDERS[target.kind](code, item, snapshot)
    if target.kind in ("hangup", "busy"):
        return _terminal_dest_lines(target.kind)
    return [f"exten => s,1,NoOp(Innova: qo'llab-quvvatlanmagan manzil turi {target.kind})",
            " same => n,Hangup(34)"]


def _dest_context_lines(
    target_id: str, snapshot: DialplanSnapshot, by_target: dict[str, ExtensionSnapshot],
    satellites: dict[str, dict[str, object]],
) -> list[str]:
    header = [f"[{snapshot.tenant_code}-dest-{target_id}]"]
    target = snapshot.targets.get(target_id)
    if target is None:
        return header + [f"exten => s,1,NoOp(Innova: manzil topilmadi {target_id})", " same => n,Hangup(1)"]
    return header + _dest_body_lines(target, snapshot, by_target, satellites)


# ------------------------------------------------------------ ovozli pochta
def _extensions_with_no_answer(snapshot: DialplanSnapshot) -> list[ExtensionSnapshot]:
    return sorted((e for e in snapshot.extensions if e.no_answer_target_id), key=lambda e: e.number)


def _vm_main_lines(snapshot: DialplanSnapshot) -> list[str]:
    """PIN — M1b chiquvchi marshrut PIN'i bilan BIR XIL qolip: dialplan bcrypt
    solishtira olmaydi, `CURL()` ichki endpoint'ga so'raydi (fayl 0644 — PIN
    unda yo'q). Bitta urinish; xato bo'lsa uziladi. `VoiceMailMain(...,s)` —
    Asterisk o'z parol so'rovini o'tkazib yuboradi (fayldagi parol yaroqsiz)."""
    code = snapshot.tenant_code
    url = (f"{snapshot.internal_api_base_url}/internal/voicemail/pin-check?token={snapshot.internal_api_token}"
           f"&context={code}&mailbox=${{INNOVA_VM_BOX}}&pin=${{INNOVA_PIN}}")
    return [
        f"[{code}-vm-main]",
        "exten => s,1,NoOp(Innova: ovozli pochta ${INNOVA_VM_BOX})",
        " same => n,Answer()",
        " same => n,Read(INNOVA_PIN,vm-password,8)",
        f" same => n,Set(INNOVA_PIN_OK=${{CURL({url})}})",
        ' same => n,GotoIf($["${INNOVA_PIN_OK}"="1"]?ok)',
        " same => n,Playback(vm-incorrect)",
        " same => n,Hangup()",
        f" same => n(ok),VoiceMailMain(${{INNOVA_VM_BOX}}@{code},s)",
        " same => n,Hangup()",
    ]


# ------------------------------------------------------------ kontekstlar
def _from_internal_lines(snapshot: DialplanSnapshot) -> list[str]:
    """Ichki raqamlar ro'yxatiga BOG'LIQ EMAS (raqam qo'shish — `<code>-ext`da).
    `dial_numbers`dagi manzillar (navbat/guruh/IVR/ish vaqti raqami), funksiya
    kodlari va park raqamlari — aniq moslik `_X.` dan ustun (Asterisk naqsh tanlovi)."""
    code = snapshot.tenant_code
    lines = [f"[{code}-from-internal]"]
    for dn in sorted(snapshot.dial_numbers, key=lambda d: d.number):
        lines.append(f"exten => {dn.number},1,Goto({code}-dest-{dn.target_id},s,1)")
    lines += feat.feature_code_lines(code, snapshot.feature_codes)
    lines += feat.park_lines(code)
    for tc in snapshot.time_conditions:
        if tc.toggle_code:
            lines.append(f"exten => {tc.toggle_code},1,NoOp(Innova: {tc.name} rejim almashtirish — "
                         "faqat API orqali, M1a'da dialplan write-back yo'q)")
            lines.append(" same => n,Hangup()")
    lines += [
        "exten => _X.,1,NoOp(Innova: ichki qo'ng'iroq ${EXTEN})",
        f" same => n,Set(CDR(accountcode)={code})",
        " same => n,Set(INNOVA_FWD_SEEN=)",
        " same => n,Set(INNOVA_FWD_FROM=)",
        f" same => n,Goto({code}-ext,${{EXTEN}},1)",
    ]
    return lines


def _dnd_dest(snapshot: DialplanSnapshot, ext: ExtensionSnapshot) -> str | None:
    """DND — javobsiz manzil ovozli pochta bo'lsa o'sha (`b`), aks holda 486."""
    target = snapshot.targets.get(ext.no_answer_target_id or "")
    if target is not None and target.kind == "voicemail":
        return f"{snapshot.tenant_code}-dest-{target.id}"
    return None


def _ext_context_lines(snapshot: DialplanSnapshot) -> list[str]:
    code = snapshot.tenant_code
    lines = [f"[{code}-ext]"]
    for ext in sorted(snapshot.extensions, key=lambda e: e.number):
        noans = f"{code}-dest-{ext.no_answer_target_id}" if ext.no_answer_target_id else None
        lines += feat.ext_entry_lines(code, ext.number, ext.name, ext.ring_seconds, noans,
                                      _dnd_dest(snapshot, ext))
    return lines + feat.ext_generic_lines(code)


def _inbound_route_lines(snapshot: DialplanSnapshot) -> list[str]:
    code = snapshot.tenant_code
    lines = [f"[{code}-from-trunk]"]
    routes = [r for r in snapshot.inbound_routes if r.enabled]
    routes.sort(key=lambda r: (r.did, r.callerid_pattern, r.id))
    for route in routes:
        exten = route.did if route.did else "_."
        lines.append(f"exten => {exten},1,NoOp(Innova: kiruvchi {route.did or 'har qanday'})")
        lines.append(f" same => n,Set(CDR(accountcode)={code})")
        lines.append(" same => n,Set(CDR(userfield)=${EXTEN})")
        lines.append(" same => n,Set(__INNOVA_DID=${EXTEN})")
        lines.append(" same => n,Set(INNOVA_FROM_TRUNK=1)")
        # §5: qora ro'yxat — marshrutlashdan OLDIN (realtime, reload shart emas).
        lines.append(f" same => n,Gosub({code}-blacklist-check,s,1)")
        if route.callerid_pattern:
            lines.append(
                f' same => n,GotoIf($["${{CALLERID(num)}}"="{route.callerid_pattern}"]?matched)')
            lines.append(" same => n,Hangup(21)")
            lines.append(" same => n(matched),NoOp(Innova: callerid mos keldi)")
        lines.append(f" same => n,Goto({code}-dest-{route.target_id},s,1)")
    lines.append("exten => _.,1,NoOp(Innova: mos marshrut topilmadi)")
    lines.append(" same => n,Hangup(1)")
    return lines


def _all_dest_ids(snapshot: DialplanSnapshot) -> list[str]:
    ids: set[str] = {r.target_id for r in snapshot.inbound_routes if r.enabled}
    ids |= {dn.target_id for dn in snapshot.dial_numbers}
    for ext in _extensions_with_no_answer(snapshot):
        ids |= {ext.target_id, ext.no_answer_target_id}
    for tc in snapshot.time_conditions:
        ids |= {tc.open_target_id, tc.closed_target_id}
    for ivr in snapshot.ivrs:
        ids |= {ivr.timeout_target_id, ivr.invalid_target_id}
        ids |= {opt.target_id for opt in ivr.options}
    for rg in snapshot.ring_groups:
        ids.add(rg.no_answer_target_id)
    for q in snapshot.queues:
        ids.add(q.timeout_target_id)
    return sorted(ids)


def compile_dialplan(snapshot: DialplanSnapshot) -> str:
    """Bazadan o'qilgan snapshot -> `extensions_innova.conf` matni. Sof funksiya."""
    _detect_target_cycle(snapshot)
    by_target = _extension_by_target(snapshot)
    satellites = _satellite_index(snapshot)

    dest_ids = _all_dest_ids(snapshot)

    parts: list[str] = [
        "; Innova PBX — avtomatik yaratilgan fayl. QO'LDA TAHRIRLAMANG.",
        f"; tenant={snapshot.tenant_code}",
        "",
    ]
    parts += rec.recording_context_lines()
    parts += _from_internal_lines(snapshot)
    parts.append("")
    parts += _ext_context_lines(snapshot)
    parts.append("")
    parts += feat.ext_call_lines(snapshot.tenant_code)
    parts.append("")
    parts += feat.cf_context_lines(snapshot.tenant_code)
    parts.append("")
    parts += feat.fm_context_lines(snapshot.tenant_code)
    parts.append("")
    parts += feat.fm_leg_lines(snapshot.tenant_code)
    parts.append("")
    parts += feat.blacklist_check_lines(snapshot.tenant_code)
    parts.append("")
    parts += _inbound_route_lines(snapshot)
    parts.append("")
    for target_id in dest_ids:
        parts += _dest_context_lines(target_id, snapshot, by_target, satellites)
        parts.append("")
    parts += _vm_main_lines(snapshot)
    parts.append("")
    parts += _outbound_context_lines(
        snapshot.tenant_code, f"{snapshot.tenant_code}-outbound", snapshot.outbound_routes,
        enforce_extension_filter=True, extension_callerids=snapshot.extension_callerids,
        base_url=snapshot.internal_api_base_url, token=snapshot.internal_api_token,
        blocked_numbers=snapshot.outbound_blocked_extension_numbers,
        toll_max_concurrent=snapshot.toll_max_concurrent_outbound,
    )
    parts.append("")
    parts += _outbound_context_lines(
        snapshot.tenant_code, f"{snapshot.tenant_code}-outbound-rg", snapshot.outbound_routes,
        enforce_extension_filter=False, extension_callerids=snapshot.extension_callerids,
        base_url=snapshot.internal_api_base_url, token=snapshot.internal_api_token,
        toll_max_concurrent=snapshot.toll_max_concurrent_outbound,
    )
    parts.append("")
    parts += rec.originate_context_lines(snapshot.tenant_code)
    parts.append("")
    parts += campaign_context_lines(snapshot.tenant_code, snapshot.internal_api_base_url,
                                    snapshot.internal_api_token)
    return "\n".join(parts) + "\n"
