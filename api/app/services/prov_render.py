"""M4a §0/§2 — config generatori: SOF funksiyalar (`render(vendor, model, ctx) -> (filename, bytes)`), baza/vaqt/tasodifsiz.

Bir xil `ctx` → bayt-ma-bayt bir xil natija (snapshot testlar `tests/test_m4a_render.py`). `config_hash` shu baytlardan olinadi.

Qiymat xavfsizligi (qator in'ektsiyasi):
  * Yealink/Fanvil — matn qatorli format: qiymat ichidagi `\\r`/`\\n` (va boshqa boshqaruv belgilari) generatsiyada OLIB
    TASHLANADI. Saqlash bosqichi (`devices.validate_*`) ularni allaqachon 422 bilan rad etadi — bu ikkinchi qatlam.
  * Grandstream — XML: `&<>"'` escape, XML 1.0 da taqiqlangan boshqaruv belgilari olib tashlanadi.

Vendor kalitlari: shartnomada sanalganlari (Yealink `account.1.*`, `linekey` 16/13, `static.security.user_password`;
Grandstream P271/P47/P35/P36/P34/P3/P270/P2/P33/P64/P246/P30/P1362; Fanvil `SIP1 ...`) — ishlab chiqaruvchi hujjatidagi
nomlar. Izohda «tekshirilmagan» deb belgilanganlari jonli apparatda sinalmagan (docs'da aytiladi, UI'da emas).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone as dt_timezone
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

MASK = "***"
VOICEMAIL_NUMBER = "*97"
TRANSPORT_CODES = {"udp": 0, "tcp": 1, "tls": 2}

# Vaqt zonasi siljishi — determinizm uchun QAT'IY sana bo'yicha (yozgi vaqt yo'q zonalar uchun aniq; bor zonalarda
# qishki siljish — apparatning o'z DST qoidasi alohida, M4a dan tashqari).
_TZ_REFERENCE = datetime(2026, 1, 15, 12, 0, tzinfo=dt_timezone.utc)
_LINE_UNSAFE = re.compile(r"[\x00-\x1f\x7f]")
_XML_UNSAFE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass(frozen=True)
class KeySpec:
    idx: int
    type: str  # blf | speed_dial | line | park | dnd | none
    value: str = ""
    label: str = ""


@dataclass(frozen=True)
class CommonCtx:
    language: str = "uz"
    timezone: str = "Asia/Tashkent"
    ntp_server: str = "pool.ntp.org"


@dataclass(frozen=True)
class DeviceCtx:
    mac: str
    number: str
    display_name: str
    sip_user: str
    password: str
    server_host: str
    server_port: int = 5060
    transport: str = "udp"
    admin_password: str | None = None
    label: str = ""
    common: CommonCtx = field(default_factory=CommonCtx)
    keys: tuple[KeySpec, ...] = ()
    extra: str = ""


def masked(ctx: DeviceCtx) -> DeviceCtx:
    """Admin ko'rinishi uchun: barcha sirlar `***` (`?reveal` YO'Q — sir faqat apparatga)."""
    return replace(ctx, password=MASK, admin_password=MASK if ctx.admin_password else None)


def line_value(value: object) -> str:
    return _LINE_UNSAFE.sub("", str(value)).strip()


def xml_value(value: object) -> str:
    return escape(_XML_UNSAFE.sub("", str(value)), {'"': "&quot;", "'": "&apos;"})


def utc_offset_minutes(tz_name: str) -> int:
    """`Asia/Tashkent` → 300; `Asia/Kolkata` → 330; `America/St_Johns` → -210 (qishki)."""
    return int(ZoneInfo(tz_name).utcoffset(_TZ_REFERENCE).total_seconds() // 60)


def _split_offset(total: int) -> tuple[str, int, int]:
    hours, minutes = divmod(abs(total), 60)
    return ("-" if total < 0 else "+"), hours, minutes


def _offset_text(tz_name: str) -> str:
    """Yealink `local_time.time_zone` shakli: `+5`, `+5:30`, `-3:30`."""
    sign, hours, minutes = _split_offset(utc_offset_minutes(tz_name))
    return f"{sign}{hours}:{minutes:02d}" if minutes else f"{sign}{hours}"


def _posix_tz(tz_name: str) -> str:
    """POSIX TZ (ishorasi teskari): Toshkent `<+05>-5`, Kolkata `<+0530>-5:30`. Grandstream P246 (tekshirilmagan)."""
    total = utc_offset_minutes(tz_name)
    sign, hours, minutes = _split_offset(total)
    name = f"{sign}{hours:02d}{minutes:02d}" if minutes else f"{sign}{hours:02d}"
    offset = f"{hours}:{minutes:02d}" if minutes else f"{hours}"
    return f"<{name}>{'-' if total > 0 else ''}{offset}"


def _extra_lines(extra: str) -> list[str]:
    return [line.rstrip("\r") for line in (extra or "").split("\n") if line.strip()]


# ------------------------------------------------------------------ Yealink
# Tugma turlari: 16 BLF, 13 speed dial — shartnomada; 15 line, 10 call park, 5 DND, 0 N/A — tekshirilmagan.
_YEALINK_KEY_TYPES = {"blf": 16, "speed_dial": 13, "line": 15, "park": 10, "dnd": 5, "none": 0}
# `lang.gui`/`lang.wui` — Yealink o'zbek tilini bilmaydi → English (tekshirilmagan: nomlar ro'yxati firmware'ga bog'liq).
_YEALINK_LANG = {"uz": "English", "ru": "Russian", "en": "English"}


def _kv(pairs: list[tuple[str, object]]) -> list[str]:
    return [f"{key} = {line_value(value)}" for key, value in pairs]


def _yealink_common_pairs(common: CommonCtx) -> list[tuple[str, object]]:
    return [
        ("lang.gui", _YEALINK_LANG.get(common.language, "English")),
        ("lang.wui", _YEALINK_LANG.get(common.language, "English")),
        ("local_time.time_zone", _offset_text(common.timezone)),
        ("local_time.ntp_server1", common.ntp_server),
        ("local_time.summer_time", 0),  # tekshirilmagan
        ("static.auto_provision.power_on", 1),  # tekshirilmagan
    ]


def render_yealink_common(common: CommonCtx) -> bytes:
    """`y000000000000.cfg` — SIRSIZ (token, parol, SIP login yo'q)."""
    lines = ["#!version:1.0.0.1", *_kv(_yealink_common_pairs(common))]
    return ("\n".join(lines) + "\n").encode()


def _yealink_key_pairs(key: KeySpec) -> list[tuple[str, object]]:
    prefix = f"linekey.{key.idx}"
    return [(f"{prefix}.type", _YEALINK_KEY_TYPES.get(key.type, 0)), (f"{prefix}.line", 1),
            (f"{prefix}.value", key.value), (f"{prefix}.label", key.label)]


def _yealink_device(ctx: DeviceCtx) -> bytes:
    acc = "account.1"
    pairs: list[tuple[str, object]] = [
        (f"{acc}.enable", 1),
        (f"{acc}.label", ctx.label or ctx.number),
        (f"{acc}.display_name", ctx.display_name),
        (f"{acc}.auth_name", ctx.sip_user),
        (f"{acc}.user_name", ctx.sip_user),
        (f"{acc}.password", ctx.password),
        (f"{acc}.sip_server.1.address", ctx.server_host),
        (f"{acc}.sip_server.1.port", ctx.server_port),
        (f"{acc}.sip_server.1.transport_type", TRANSPORT_CODES.get(ctx.transport, 0)),
        ("voice_mail.number.1", VOICEMAIL_NUMBER),
    ]
    for key in ctx.keys:
        pairs += _yealink_key_pairs(key)
    if ctx.admin_password:
        pairs.append(("static.security.user_password", f"admin:{ctx.admin_password}"))
    lines = ["#!version:1.0.0.1", *_kv(_yealink_common_pairs(ctx.common)), *_kv(pairs), *_extra_lines(ctx.extra)]
    return ("\n".join(lines) + "\n").encode()


# ------------------------------------------------------------------ Grandstream
# P-kodlar shartnomadan; P130 (transport) va P64=`customize` + P246 POSIX TZ shakli — tekshirilmagan.
# BLF/MPK P-kodlari modelga qarab farq qiladi va jonli apparatda tekshirilmagan — M4a da GENERATSIYA QILINMAYDI.
_GS_LANG = {"uz": "en", "ru": "ru", "en": "en"}


def _gs_extra_pair(line: str) -> tuple[str, str]:
    """`P1234 = qiymat` → (`P1234`, `qiymat`); format saqlashda tekshirilgan (`prov_settings.validate_extra`)."""
    code, _, value = line.partition("=")
    return code.strip(), value.strip()


def _grandstream_device(ctx: DeviceCtx) -> bytes:
    pairs: list[tuple[str, object]] = [
        ("P271", 1), ("P270", ctx.label or ctx.number), ("P47", f"{ctx.server_host}:{ctx.server_port}"),
        ("P35", ctx.sip_user), ("P36", ctx.sip_user), ("P34", ctx.password), ("P3", ctx.display_name),
        ("P33", VOICEMAIL_NUMBER), ("P130", TRANSPORT_CODES.get(ctx.transport, 0)),
        ("P64", "customize"), ("P246", _posix_tz(ctx.common.timezone)), ("P30", ctx.common.ntp_server),
        ("P1362", _GS_LANG.get(ctx.common.language, "en")),
    ]
    if ctx.admin_password:
        pairs.append(("P2", ctx.admin_password))
    pairs += [_gs_extra_pair(line) for line in _extra_lines(ctx.extra)]
    body = "".join(f"    <{code}>{xml_value(value)}</{code}>\n" for code, value in pairs)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<gs_provision version="1">\n'
           f"  <mac>{ctx.mac}</mac>\n  <config version=\"1\">\n{body}  </config>\n</gs_provision>\n")
    return xml.encode()


# ------------------------------------------------------------------ Fanvil
# `SIP1 ...` kalitlari shartnomadan. `SIP1 Transport`, `<GLOBAL CONFIG MODULE>` vaqt kalitlari, `<DSS CONFIG MODULE>`
# `Fkey<N> Type/Value/Title` (BLF qiymati `<raqam>@1/b`), `<WEB CONFIG MODULE>` `Web Server Password`,
# `Language` qiymatlari — tekshirilmagan.
_FANVIL_KEY_TYPES = {"blf": 1, "speed_dial": 1, "line": 2, "park": 1, "dnd": 4, "none": 0}
_FANVIL_KEY_SUFFIX = {"blf": "/b", "speed_dial": "/f", "park": "/f"}
_FANVIL_LANG = {"uz": "en", "ru": "ru", "en": "en"}


def _fanvil_section(title: str, pairs: list[tuple[str, object]]) -> list[str]:
    return [f"<{title}>", *(f"{name:<24}:{line_value(value)}" for name, value in pairs), ""]


def _fanvil_key_pairs(key: KeySpec) -> list[tuple[str, object]]:
    suffix = _FANVIL_KEY_SUFFIX.get(key.type)
    value = f"{key.value}@1{suffix}" if suffix and key.value else key.value
    name = f"Fkey{key.idx}"
    return [(f"{name} Type", _FANVIL_KEY_TYPES.get(key.type, 0)), (f"{name} Value", value), (f"{name} Title", key.label)]


def _fanvil_device(ctx: DeviceCtx) -> bytes:
    lines = ["<<VOIP CONFIG FILE>>Version:2.0000000000", ""]
    lines += _fanvil_section("GLOBAL CONFIG MODULE", [
        ("Enable SNTP", 1), ("SNTP Server", ctx.common.ntp_server), ("Time Zone", utc_offset_minutes(ctx.common.timezone)),
        ("Language", _FANVIL_LANG.get(ctx.common.language, "en"))])
    lines += _fanvil_section("SIP CONFIG MODULE", [
        ("SIP1 Phone Number", ctx.sip_user), ("SIP1 Display Name", ctx.display_name),
        ("SIP1 Register Addr", ctx.server_host), ("SIP1 Register Port", ctx.server_port),
        ("SIP1 Register User", ctx.sip_user), ("SIP1 Register Pswd", ctx.password),
        ("SIP1 Transport", TRANSPORT_CODES.get(ctx.transport, 0)), ("SIP1 Enable Reg", 1),
        ("SIP1 VoiceMail Number", VOICEMAIL_NUMBER)])
    if ctx.keys:
        lines += _fanvil_section("DSS CONFIG MODULE", [pair for key in ctx.keys for pair in _fanvil_key_pairs(key)])
    if ctx.admin_password:
        lines += _fanvil_section("WEB CONFIG MODULE", [("Web Server Password", ctx.admin_password)])
    lines += _extra_lines(ctx.extra)
    return ("\n".join(lines).rstrip("\n") + "\n").encode()


# ------------------------------------------------------------------ umumiy kirish
_DEVICE_RENDERERS = {"yealink": _yealink_device, "grandstream": _grandstream_device, "fanvil": _fanvil_device}


def device_filename(vendor: str, mac: str) -> str:
    return f"cfg{mac}.xml" if vendor == "grandstream" else f"{mac}.cfg"


def content_type(vendor: str) -> str:
    return "application/xml" if vendor == "grandstream" else "text/plain"


def render(vendor: str, model: str, ctx: DeviceCtx) -> tuple[str, bytes]:
    """Apparat (MAC) fayli. `model` hozircha formatga ta'sir qilmaydi (tugmalar soni saqlashda tekshiriladi) —
    imzo shartnomadagidek, modelga xos farq kerak bo'lganda shu yerda tarmoqlanadi."""
    del model
    return device_filename(vendor, ctx.mac), _DEVICE_RENDERERS[vendor](ctx)
