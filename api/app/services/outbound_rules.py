"""Chiquvchi marshrut qoidalari — SOF (IO'siz) funksiyalar.

m1b-contract.md bo'lim 2: "`POST /outbound-routes/simulate` ... dialplan bilan
BIR XIL qoidalar (bitta Python funksiya kompilyator va simulyatorda umumiy
bo'lsin)". Shu sabab BARCHA qaror mantiqi (naqsh tekshirish, strip/add,
xalqaro bloklash, marshrut/trunk tanlash) shu yerda — `app/api/v1/outbound_routes.py`
(`/simulate`) VA `app/services/compiler.py` (dialplan generatsiyasi, `REGEX()`
orqali) ikkisi ham `pattern_to_asterisk_regex`/`strip_number`/`international_blocked`
dan foydalanadi.

Naqsh sintaksisi (m1b-contract.md 25-qator): raqamlar, `X` (0-9), `Z` (1-9),
`N` (2-9), `.`/`!` (oxirida — qolgan BARCHA raqamlar), `[1-5]` kabi diapazon,
`*`/`#`/`+` harflama belgilar sifatida.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_ALLOWED_CHARS_RE = re.compile(r"^[0-9XZN.!\[\]*#+\-]+$")
_CLASS_RE = re.compile(r"^\[(\d)-(\d)\]$")


@dataclass(frozen=True)
class PatternCheckResult:
    ok: bool
    reason: str | None = None


def validate_pattern(pattern: str) -> PatternCheckResult:
    """Naqsh sintaksisini tekshiradi — xato bo'lsa `reason` qaytaradi
    (`app/api/v1/outbound_routes.py`: 422 `bad_pattern` + `details.reason`)."""
    if not pattern:
        return PatternCheckResult(False, "Naqsh bo'sh bo'lmasin")
    if not _ALLOWED_CHARS_RE.match(pattern):
        return PatternCheckResult(False, "Naqshda ruxsat etilmagan belgi bor")
    for idx, ch in enumerate(pattern):
        if ch == "." and idx != len(pattern) - 1:
            return PatternCheckResult(False, "'.' faqat naqsh oxirida bo'lishi mumkin")
        if ch == "!" and idx != len(pattern) - 1:
            return PatternCheckResult(False, "'!' faqat naqsh oxirida bo'lishi mumkin")
    for group in re.findall(r"\[[^\]]*\]", pattern):
        m = _CLASS_RE.match(group)
        if not m:
            return PatternCheckResult(False, f"Diapazon noto'g'ri: {group}")
        lo, hi = int(m.group(1)), int(m.group(2))
        if lo > hi:
            return PatternCheckResult(False, f"Diapazon tartibsiz: {group}")
    return PatternCheckResult(True)


_SIMPLE_CLASS_MAP = {"X": "[0-9]", "Z": "[1-9]", "N": "[2-9]"}
_LITERAL_ESCAPE = set("+*#")


def pattern_to_regex_body(pattern: str) -> str:
    """Asterisk naqshini Python/POSIX ERE bilan mos keluvchi regex tanasiga
    o'giradi (anchorsiz — chaqiruvchi `^`/`$` qo'yadi). Compiler buni
    `REGEX()` dialplan funksiyasi uchun, simulyator `re.fullmatch` uchun
    ishlatadi — ikkisi BIR XIL natija berishi uchun."""
    out: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if ch == "[":
            end = pattern.index("]", i)
            out.append(pattern[i:end + 1])
            i = end + 1
            continue
        if ch in _SIMPLE_CLASS_MAP:
            out.append(_SIMPLE_CLASS_MAP[ch])
        elif ch == ".":
            out.append(".+")
        elif ch == "!":
            out.append(".*")
        elif ch in _LITERAL_ESCAPE:
            out.append("\\" + ch)
        elif ch.isdigit():
            out.append(ch)
        else:
            out.append(re.escape(ch))
        i += 1
    return "".join(out)


def pattern_matches(pattern: str, number: str) -> bool:
    body = pattern_to_regex_body(pattern)
    return re.fullmatch(body, number) is not None


def strip_number(strip_prefix: str, dialed: str) -> str:
    """`strip_prefix` UZUNLIGICHA dialed boshidan olib tashlanadi (Asterisk
    `${EXTEN:N}` bilan bir xil — belgilarga qarab emas, SONIGA qarab,
    m1b-contract.md misoli: strip_prefix='0', dialed='0901234567' ->
    '901234567')."""
    n = len(strip_prefix)
    return dialed[n:] if n else dialed


def international_blocked(dialed: str, *, international: bool) -> bool:
    """`international=false` bo'lsa va raqam `00`/`+` bilan boshlanib (xalqaro
    prefiks OLIB TASHLANGANDAN KEYIN) `998` bilan boshlanMAsa — bloklanadi
    (toll-fraud, m1b-contract.md 27-qator). `00998...`/`+998...` — O'zbekistonga
    xalqaro formatda qo'ng'iroq, bloklanMAYDI (faqat chet davlat kodlari bloklanadi)."""
    if international:
        return False
    if dialed.startswith("00"):
        rest = dialed[2:]
    elif dialed.startswith("+"):
        rest = dialed[1:]
    else:
        return False
    return not rest.startswith("998")


@dataclass(frozen=True)
class PatternRule:
    strip_prefix: str
    pattern: str
    add_prefix: str
    callerid_match: str = ""


@dataclass(frozen=True)
class TrunkRef:
    id: str
    name: str
    health_state: str = "unknown"


@dataclass(frozen=True)
class RouteRule:
    id: str
    name: str
    priority: int
    enabled: bool
    international: bool
    patterns: tuple[PatternRule, ...]
    trunks: tuple[TrunkRef, ...]
    callerid: str | None = None
    override_extension_callerid: bool = False
    has_pin: bool = False
    allowed_extension_ids: tuple[str, ...] | None = None  # None = "all"


@dataclass(frozen=True)
class RouteMatch:
    route: RouteRule
    dialed: str
    pattern: PatternRule


@dataclass(frozen=True)
class SimulateStep:
    route: str
    result: str  # match|no_pattern|ext_not_allowed|international_blocked|disabled
    detail: str


def _extension_allowed(route: RouteRule, extension_id: str | None) -> bool:
    if route.allowed_extension_ids is None:
        return True
    return extension_id is not None and extension_id in route.allowed_extension_ids


def match_number_against_route(
    route: RouteRule, number: str, *, extension_id: str | None,
) -> tuple[RouteMatch | None, SimulateStep]:
    """Bitta marshrutni bitta raqamga qarshi tekshiradi — natija VA izoh
    qadami (`simulate` javobidagi `steps[]`) birgalikda qaytariladi."""
    if not route.enabled:
        return None, SimulateStep(route.name, "disabled", "Marshrut o'chirilgan")
    if not _extension_allowed(route, extension_id):
        return None, SimulateStep(route.name, "ext_not_allowed", "Bu ichki raqamga ruxsat yo'q")
    if international_blocked(number, international=route.international):
        return None, SimulateStep(route.name, "international_blocked",
                                    "Xalqaro raqam — marshrut xalqaro emas")
    for pat in route.patterns:
        stripped = strip_number(pat.strip_prefix, number)
        if pattern_matches(pat.pattern, stripped):
            dialed = pat.add_prefix + stripped
            return RouteMatch(route=route, dialed=dialed, pattern=pat), SimulateStep(
                route.name, "match", f"Naqshga mos keldi -> {dialed}")
    return None, SimulateStep(route.name, "no_pattern", "Hech bir naqshga mos kelmadi")


@dataclass(frozen=True)
class SimulateOutcome:
    allowed: bool
    route: RouteRule | None
    dialed: str | None
    trunks: tuple[TrunkRef, ...]
    steps: tuple[SimulateStep, ...]
    reason: str | None


def resolve_route(
    routes: list[RouteRule], number: str, *, extension_id: str | None,
) -> SimulateOutcome:
    """Priority tartibida (kichik raqam = birinchi) marshrutlarni tekshiradi,
    BIRINCHI mos kelganini qaytaradi — dialplan xuddi shu tartibda GotoIf
    zanjiri bilan ishlaydi (`app/services/compiler.py: _outbound_lines`)."""
    steps: list[SimulateStep] = []
    for route in sorted(routes, key=lambda r: r.priority):
        match, step = match_number_against_route(route, number, extension_id=extension_id)
        steps.append(step)
        if match is not None:
            return SimulateOutcome(
                allowed=True, route=match.route, dialed=match.dialed,
                trunks=match.route.trunks, steps=tuple(steps), reason=None,
            )
    return SimulateOutcome(
        allowed=False, route=None, dialed=None, trunks=(), steps=tuple(steps),
        reason="Hech bir chiquvchi marshrut mos kelmadi",
    )


def resolve_callerid(
    *, route_callerid: str | None, override_extension_callerid: bool,
    extension_outbound_callerid: str | None, trunk_outbound_callerid: str | None,
) -> str | None:
    """m1b-contract.md 31-32-qator: CallerID tanlov tartibi —
    (1) agar `override_extension_callerid` True bo'lsa route.callerid ustun;
    (2) aks holda ichki raqamning o'zi (`outbound_callerid`);
    (3) aks holda route.callerid;
    (4) aks holda trunk.outbound_callerid."""
    if override_extension_callerid and route_callerid:
        return route_callerid
    if extension_outbound_callerid:
        return extension_outbound_callerid
    if route_callerid:
        return route_callerid
    return trunk_outbound_callerid
