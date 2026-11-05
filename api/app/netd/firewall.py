"""Firewall paneli — m12-contract.md B3: SSH(22)/Web(80,443)/SIP(5060,5061
tcp+udp)/RTP(10000-20000 udp) uchun "hammaga ochiq" yoki CIDR allowlist +
doimiy bloklangan CIDR'lar. FAQAT mustaqil `table inet innova_fw` (asosiy
`table inet innova` va sip_guard `innova-guard.nft`ga HECH QACHON tegilmaydi
— `executor.py::FIREWALL_CONF_PATH`/`_nft_argv_ok` shu yagona faylga
cheklaydi). `nft -c -f` (tekshirish) -> `nft -f` (qo'llash) -> commit-confirm
(tarmoq moduli bilan BIR XIL naqsh, lekin MUSTAQIL pending fayli) ->
tasdiqlanmasa avtomatik tiklanadi. O'zini qulflashdan himoya: joriy admin IP
SSH/Veb ruxsat ro'yxatida bo'lishi SHART (422), aks holda yozilmaydi."""
from __future__ import annotations

import ipaddress
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Callable

from app.netd.errors import NetdError
from app.netd.executor import FIREWALL_CONF_PATH, Executor

STATE_PATH = "/etc/innova/firewall-state.json"
SERVICE_NAMES = ("ssh", "web", "sip", "rtp")
_SERVICE_NAMES_SET = frozenset(SERVICE_NAMES)
MAX_ALLOW_ENTRIES = 50
MAX_BLOCKED_ENTRIES = 100
DEFAULT_TIMEOUT_S = 120
MIN_TIMEOUT_S = 30
MAX_TIMEOUT_S = 600
_SELF_LOCKOUT_SERVICES = ("ssh", "web")
_ROLLBACK_MESSAGES = {
    "timeout": "Vaqt tugadi — firewall avtomatik qaytarildi",
    "manual": "Firewall qo'lda qaytarildi",
    "restart": "netd qayta ishga tushdi — tasdiqlanmagan firewall qaytarildi",
}
# proto -> port(lar): butun son ro'yxati (`{ a, b }`) yoki tayyor diapazon
# satri (`"10000-20000"`, nft `dport` sintaksisi).
_SERVICE_PORTS: dict[str, tuple[tuple[str, tuple[int, ...] | str], ...]] = {
    "ssh": (("tcp", (22,)),),
    "web": (("tcp", (80, 443)),),
    "sip": (("tcp", (5060, 5061)), ("udp", (5060, 5061))),
    "rtp": (("udp", "10000-20000"),),
}


@dataclass(frozen=True)
class FieldError:
    field: str
    message: str


@dataclass
class FirewallValidationResult:
    errors: list[FieldError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class LastResult:
    kind: str  # confirmed | rolled_back
    at: datetime
    message: str | None


@dataclass(frozen=True)
class _Snapshot:
    conf_text: str | None
    state_json: str | None


@dataclass(frozen=True)
class _PendingRecord:
    id: str
    applied_at: datetime
    expires_at: datetime
    summary: list[str]
    snapshot: _Snapshot

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "applied_at": self.applied_at.astimezone(timezone.utc).isoformat(),
            "expires_at": self.expires_at.astimezone(timezone.utc).isoformat(),
            "summary": self.summary,
            "snapshot": {"conf_text": self.snapshot.conf_text, "state_json": self.snapshot.state_json},
        }

    @staticmethod
    def from_dict(d: dict) -> "_PendingRecord":
        return _PendingRecord(
            id=d["id"],
            applied_at=datetime.fromisoformat(d["applied_at"]),
            expires_at=datetime.fromisoformat(d["expires_at"]),
            summary=d["summary"],
            snapshot=_Snapshot(**d["snapshot"]),
        )


def _load_pending(executor: Executor, path: str) -> _PendingRecord | None:
    raw = executor.read_text(path)
    if not raw or not raw.strip():
        return None
    return _PendingRecord.from_dict(json.loads(raw))


def _save_pending(executor: Executor, path: str, record: _PendingRecord) -> None:
    executor.write_text_atomic(path, json.dumps(record.to_dict(), indent=2) + "\n", mode=0o600)


def _clear_pending(executor: Executor, path: str) -> None:
    # `pending.py::clear_pending` singari `os.unlink` ISHLATMAYMIZ — testdagi
    # xotiradagi soxta `Executor` haqiqiy fayl yo'liga ega emas; "pending
    # yo'q" holati bo'sh satr yozish bilan ifodalanadi (`_load_pending` buni
    # `None` deb o'qiydi).
    executor.write_text_atomic(path, "", mode=0o600)


# --------------------------------------------------------------------- validatsiya

def is_valid_cidr(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        ipaddress.IPv4Interface(value)
        return True
    except ValueError:
        return False


def _ipv4_network(value: str) -> ipaddress.IPv4Network | None:
    try:
        return ipaddress.IPv4Interface(value).network
    except ValueError:
        return None


def _ipv4_address(value: str) -> ipaddress.IPv4Address | None:
    try:
        return ipaddress.IPv4Address(value)
    except ValueError:
        return None


def _ip_in_any_cidr(ip: str, cidrs: list[str]) -> bool:
    addr = _ipv4_address(ip)
    if addr is None:
        return False
    return any((net := _ipv4_network(cidr)) is not None and addr in net for cidr in cidrs)


def _validate_allow_list(idx: int, allow: list[str], errors: list[FieldError]) -> None:
    if not allow:
        errors.append(FieldError(f"services[{idx}].allow", "allowlist rejimida kamida bitta CIDR kerak"))
        return
    if len(allow) > MAX_ALLOW_ENTRIES:
        errors.append(FieldError(f"services[{idx}].allow", f"Ko'pi bilan {MAX_ALLOW_ENTRIES} ta CIDR bo'lishi mumkin"))
        return
    for j, cidr in enumerate(allow):
        if not is_valid_cidr(cidr):
            errors.append(FieldError(f"services[{idx}].allow[{j}]", f"Yaroqsiz IPv4 CIDR: {cidr!r}"))


def _validate_service(idx: int, svc: Any, names_seen: set[str], errors: list[FieldError]) -> None:
    name = getattr(svc, "name", None)
    if name not in _SERVICE_NAMES_SET:
        errors.append(FieldError(f"services[{idx}].name", f"Noma'lum xizmat: {name!r}"))
        return
    if name in names_seen:
        errors.append(FieldError(f"services[{idx}].name", f"Xizmat takrorlangan: {name}"))
        return
    names_seen.add(name)
    mode = getattr(svc, "mode", None)
    if mode not in ("all", "allowlist"):
        errors.append(FieldError(f"services[{idx}].mode", "mode \"all\" yoki \"allowlist\" bo'lishi kerak"))
        return
    if mode == "allowlist":
        _validate_allow_list(idx, getattr(svc, "allow", None) or [], errors)


def _validate_blocked_cidrs(blocked: list[Any], errors: list[FieldError]) -> None:
    if len(blocked) > MAX_BLOCKED_ENTRIES:
        errors.append(FieldError("blocked_cidrs", f"Ko'pi bilan {MAX_BLOCKED_ENTRIES} ta bloklangan CIDR bo'lishi mumkin"))
        return
    for idx, cidr in enumerate(blocked):
        if not is_valid_cidr(cidr):
            errors.append(FieldError(f"blocked_cidrs[{idx}]", f"Yaroqsiz IPv4 CIDR: {cidr!r}"))
        elif _ipv4_network(cidr) == ipaddress.IPv4Network("0.0.0.0/0"):
            errors.append(FieldError(f"blocked_cidrs[{idx}]", "0.0.0.0/0 ni bloklash taqiqlangan — butun tarmoqni uzadi"))


def validate_firewall_config(cfg: Any) -> FirewallValidationResult:
    errors: list[FieldError] = []
    names_seen: set[str] = set()
    for idx, svc in enumerate(getattr(cfg, "services", None) or []):
        _validate_service(idx, svc, names_seen, errors)
    for name in sorted(_SERVICE_NAMES_SET - names_seen):
        errors.append(FieldError("services", f"Xizmat ko'rsatilmagan: {name}"))
    _validate_blocked_cidrs(getattr(cfg, "blocked_cidrs", None) or [], errors)
    timeout = getattr(cfg, "timeout_s", None)
    if timeout is not None and not (isinstance(timeout, int) and not isinstance(timeout, bool)
                                     and MIN_TIMEOUT_S <= timeout <= MAX_TIMEOUT_S):
        errors.append(FieldError("timeout_s", f"{MIN_TIMEOUT_S}..{MAX_TIMEOUT_S} oralig'ida butun son bo'lishi kerak"))
    return FirewallValidationResult(errors)


def _check_service_self_lockout(svc_by_name: dict, name: str, request_host: str, errors: list[FieldError]) -> None:
    svc = svc_by_name.get(name)
    if svc is None or getattr(svc, "mode", None) != "allowlist":
        return
    if _ip_in_any_cidr(request_host, getattr(svc, "allow", None) or []):
        return
    errors.append(FieldError(f"services.{name}.allow",
                              f"Joriy admin IP ({request_host}) {name} ruxsat ro'yxatida emas — o'zini qulflash oldini olinadi"))


def _check_blocked_cidrs_self_lockout(cfg: Any, request_host: str, errors: list[FieldError]) -> None:
    if not _ip_in_any_cidr(request_host, getattr(cfg, "blocked_cidrs", None) or []):
        return
    errors.append(FieldError("blocked_cidrs",
                              f"Joriy admin IP ({request_host}) bloklangan CIDR qatoriga tushadi — o'zini qulflash oldini olinadi"))


def check_self_lockout(cfg: Any, request_host: str | None, errors: list[FieldError]) -> None:
    """m12-contract.md B3 — joriy admin IP SSH/Veb ruxsatida qolishi SHART,
    aks holda 422 (`request_host` noma'lum/IPv6 bo'lsa tekshirib bo'lmaydi —
    bu holda O'TKAZIB YUBORILADI, chunki netd IPv4-only)."""
    if not request_host or _ipv4_address(request_host) is None:
        return
    svc_by_name = {getattr(s, "name", None): s for s in getattr(cfg, "services", None) or []}
    for name in _SELF_LOCKOUT_SERVICES:
        _check_service_self_lockout(svc_by_name, name, request_host, errors)
    _check_blocked_cidrs_self_lockout(cfg, request_host, errors)


# --------------------------------------------------------------------- render/state

def default_config() -> SimpleNamespace:
    return SimpleNamespace(
        services=[SimpleNamespace(name=n, mode="all", allow=[]) for n in SERVICE_NAMES],
        blocked_cidrs=[],
    )


def _format_cidr_set(cidrs: list[str]) -> str:
    return "{ " + ", ".join(cidrs) + " }"


def _format_ports(portspec: tuple[int, ...] | str) -> str:
    if isinstance(portspec, str):
        return portspec
    return "{ " + ", ".join(str(p) for p in portspec) + " }"


def _effective_ports(name: str, ports: dict[str, list[int]] | None) -> tuple[tuple[str, tuple[int, ...] | str], ...]:
    """`ssh`/`web` portlari `access.py`dagi JORIY (PENDING paytida ikkalasi
    ham) qiymatdan olinadi; `sip`/`rtp` doim statik (`access` ularni
    boshqarmaydi)."""
    if ports is not None and name in ports:
        return (("tcp", tuple(sorted(set(ports[name])))),)
    return _SERVICE_PORTS[name]


def _render_forward_chain(web_svc: Any, blocked: list[str], web_ports: tuple) -> list[str]:
    """Docker'ning `web` portlarini (80/443) NAT/DNAT qilib forward qilishi
    — paket host'ning `input` emas, `forward` ilmog'idan o'tadi (manzil
    DNAT'dan keyin KONTEYNER IP'si, mahalliy emas). Shu sabab `input`
    zanjiridagi veb qoida Docker-published portlarga ta'sir qilmaydi — DALIL
    uchun hisobotga qarang. Tuzatish: `ct original proto-dst` (DNAT'DAN
    OLDINGI so'ralgan port) bo'yicha mos keladigan alohida `forward` ilmog'i."""
    web_portspec = web_ports[0][1]
    lines = []
    if blocked:
        lines.append(f"        ip saddr {_format_cidr_set(blocked)} "
                      f"ct original proto-dst {_format_ports(web_portspec)} drop")
    if web_svc is not None and web_svc.mode == "allowlist":
        allow = list(web_svc.allow or [])
        lines.append(f"        ip saddr != {_format_cidr_set(allow)} "
                      f"ct original proto-dst {_format_ports(web_portspec)} drop")
    if not lines:
        return []
    return ["    chain forward {", "        type filter hook forward priority filter - 5; policy accept;",
            *lines, "    }"]


def render_nft(cfg: Any, *, ports: dict[str, list[int]] | None = None) -> str:
    svc_by_name = {s.name: s for s in cfg.services}
    lines = [
        "table inet innova_fw {",
        "    chain input {",
        "        type filter hook input priority filter - 5; policy accept;",
    ]
    blocked = list(getattr(cfg, "blocked_cidrs", None) or [])
    if blocked:
        lines.append(f"        ip saddr {_format_cidr_set(blocked)} drop")
    for name in SERVICE_NAMES:
        svc = svc_by_name.get(name)
        if svc is None or svc.mode != "allowlist":
            continue
        allow = list(svc.allow or [])
        for proto, portspec in _effective_ports(name, ports):
            lines.append(f"        ip saddr != {_format_cidr_set(allow)} {proto} dport {_format_ports(portspec)} drop")
    lines.append("    }")
    lines.extend(_render_forward_chain(svc_by_name.get("web"), blocked, _effective_ports("web", ports)))
    lines.append("}")
    return "\n".join(lines) + "\n"


def config_to_dict(cfg: Any) -> dict:
    return {
        "services": [{"name": s.name, "mode": s.mode, "allow": list(s.allow or [])} for s in cfg.services],
        "blocked_cidrs": list(getattr(cfg, "blocked_cidrs", None) or []),
    }


def _service_diff_line(old_by_name: dict, svc: Any) -> str | None:
    prev = old_by_name.get(svc.name, {"mode": "all", "allow": []})
    new_allow = list(svc.allow or [])
    if prev.get("mode") == svc.mode and list(prev.get("allow") or []) == new_allow:
        return None
    if svc.mode == "all":
        return f"{svc.name}: hammaga ochiq bo'ladi"
    return f"{svc.name}: faqat {len(new_allow)} ta CIDR uchun ochiq bo'ladi"


def _blocked_cidrs_diff_line(old: dict, cfg: Any) -> str | None:
    if list(old.get("blocked_cidrs") or []) == list(getattr(cfg, "blocked_cidrs", None) or []):
        return None
    return f"bloklangan CIDR ro'yxati o'zgaradi ({len(cfg.blocked_cidrs or [])} ta)"


def diff_summary(old: dict, cfg: Any) -> list[str]:
    old_by_name = {s["name"]: s for s in old["services"]}
    lines = [line for svc in cfg.services if (line := _service_diff_line(old_by_name, svc)) is not None]
    blocked_line = _blocked_cidrs_diff_line(old, cfg)
    if blocked_line is not None:
        lines.append(blocked_line)
    return lines


class FirewallService:
    """`m12-contract.md` B3 — tarmoq moduli (`service.py`) bilan BIR XIL
    commit-confirm naqsh, lekin MUSTAQIL holat (`pending_path`,
    `STATE_PATH`) — tarmoq rollback/pending'iga HECH QANDAY bog'liqligi yo'q."""

    def __init__(self, executor: Executor, *, readonly: bool, pending_path: str,
                 now_fn: Callable[[], datetime], other_pending: Callable[[], bool] = lambda: False,
                 ports_provider: Callable[[], Any] | None = None) -> None:
        self.executor = executor
        self.readonly = readonly
        self.pending_path = pending_path
        self._now = now_fn
        self._other_pending = other_pending
        # Kirish (access) moduli — `ssh`/`web` JORIY portlarini beradi
        # (`AccessService.current_ports`, async); `None` bo'lsa statik
        # `_SERVICE_PORTS` ishlatiladi (test/standalone ishlatish uchun).
        self._ports_provider = ports_provider
        self.pending: _PendingRecord | None = _load_pending(executor, pending_path)
        self.last_result: LastResult | None = None

    # ----------------------------------------------------------------- public ops
    async def state(self) -> dict[str, Any]:
        await self._maybe_expire()
        current = self._load_state_dict()
        return {
            "services": current["services"],
            "blocked_cidrs": current["blocked_cidrs"],
            "readonly_reason": self._readonly_reason(),
            "pending": self._pending_out(),
            "last_result": self._last_result_out(),
        }

    async def validate(self, config: Any, *, request_host: str | None = None) -> dict[str, Any]:
        result = validate_firewall_config(config)
        check_self_lockout(config, request_host, result.errors)
        errors = [{"field": e.field, "message": e.message} for e in result.errors]
        if not result.ok:
            return {"ok": False, "errors": errors, "warnings": [], "diff": []}
        return {"ok": True, "errors": [], "warnings": [], "diff": diff_summary(self._load_state_dict(), config)}

    async def apply(self, config: Any, *, request_host: str | None = None) -> dict[str, Any]:
        await self._maybe_expire()
        self._guard_writable()
        result = validate_firewall_config(config)
        check_self_lockout(config, request_host, result.errors)
        if not result.ok:
            raise NetdError("invalid_config", "Firewall konfiguratsiyasi yaroqsiz",
                             [{"field": e.field, "message": e.message} for e in result.errors])
        timeout = self._clamp_timeout(getattr(config, "timeout_s", None))
        summary = diff_summary(self._load_state_dict(), config)
        old_conf = self.executor.read_text(FIREWALL_CONF_PATH)
        old_state_json = self.executor.read_text(STATE_PATH)
        await self._write_and_apply(render_nft(config, ports=await self._current_ports()))
        self.executor.write_text_atomic(STATE_PATH, json.dumps(config_to_dict(config)) + "\n", mode=0o600)
        self._open_pending(timeout, summary, _Snapshot(old_conf, old_state_json))
        return await self.state()

    async def confirm(self, pending_id: str) -> dict[str, Any]:
        await self._maybe_expire()
        self._require_pending(pending_id)
        self._close_pending(LastResult("confirmed", self._now(), None))
        return await self.state()

    async def rollback(self, pending_id: str) -> dict[str, Any]:
        self._require_pending(pending_id)
        await self._do_rollback(reason="manual")
        return await self.state()

    async def startup_recover(self) -> None:
        if self.pending is not None:
            await self._do_rollback(reason="restart")

    # ----------------------------------------------------------------- nft apply/rollback
    async def _write_and_apply(self, new_conf: str) -> None:
        old_conf = self.executor.read_text(FIREWALL_CONF_PATH)
        self.executor.write_text_atomic(FIREWALL_CONF_PATH, new_conf)
        check = await self.executor.run(["nft", "-c", "-f", FIREWALL_CONF_PATH], timeout=5.0)
        if not check.ok:
            self._restore_conf_file(old_conf)
            raise NetdError("invalid_config", f"nft sintaksisi xato: {check.stderr.strip()}")
        applied = await self.executor.run(["nft", "-f", FIREWALL_CONF_PATH], timeout=5.0)
        if not applied.ok:
            await self._reapply_conf(old_conf)
            raise NetdError("apply_failed", f"nft qo'llash xato: {applied.stderr.strip()}")

    def _restore_conf_file(self, old_conf: str | None) -> None:
        self.executor.write_text_atomic(FIREWALL_CONF_PATH, old_conf if old_conf is not None else render_nft(default_config()))

    async def _reapply_conf(self, old_conf: str | None) -> None:
        self._restore_conf_file(old_conf)
        await self.executor.run(["nft", "-f", FIREWALL_CONF_PATH], timeout=5.0)

    async def _do_rollback(self, *, reason: str) -> None:
        record = self.pending
        if record is None:
            return
        await self._reapply_conf(record.snapshot.conf_text)
        old_state = record.snapshot.state_json
        self.executor.write_text_atomic(STATE_PATH, old_state if old_state is not None else "")
        self._close_pending(LastResult("rolled_back", self._now(), _ROLLBACK_MESSAGES[reason]))

    # ----------------------------------------------------------------- guards
    def _readonly_reason(self) -> str | None:
        if self.readonly:
            return "Bu serverda firewall qoidalarini tahrirlash o'chirilgan (NETD_READONLY)"
        return None

    def _guard_writable(self) -> None:
        if self.readonly:
            # `self.readonly` True bo'lganda `_readonly_reason()` doim xabar qaytaradi.
            raise NetdError("readonly", self._readonly_reason())
        if self.pending is not None:
            raise NetdError("pending_exists", "Tasdiqlanmagan firewall o'zgarishi allaqachon mavjud (409)")
        if self._other_pending():
            raise NetdError("pending_exists", "Kirish (SSH/Veb) o'zgarishi kutilmoqda — avval uni yakunlang (409)")

    async def _current_ports(self) -> dict[str, list[int]] | None:
        if self._ports_provider is None:
            return None
        return await self._ports_provider()

    def _require_pending(self, pending_id: str) -> None:
        if self.pending is None or self.pending.id != pending_id:
            raise NetdError("not_found", "Kutilayotgan firewall o'zgarishi topilmadi")

    async def _maybe_expire(self) -> None:
        if self.pending is not None and self.pending.is_expired(self._now()):
            await self._do_rollback(reason="timeout")

    @staticmethod
    def _clamp_timeout(timeout_s: int | None) -> int:
        value = DEFAULT_TIMEOUT_S if timeout_s is None else timeout_s
        return max(MIN_TIMEOUT_S, min(MAX_TIMEOUT_S, value))

    # ----------------------------------------------------------------- state/pending io
    def _load_state_dict(self) -> dict:
        raw = self.executor.read_text(STATE_PATH)
        if not raw or not raw.strip():
            return config_to_dict(default_config())
        return json.loads(raw)

    def _open_pending(self, timeout_s: int, summary: list[str], snapshot: _Snapshot) -> None:
        now = self._now()
        record = _PendingRecord(id=uuid.uuid4().hex, applied_at=now, expires_at=now + timedelta(seconds=timeout_s),
                                 summary=summary, snapshot=snapshot)
        self.pending = record
        _save_pending(self.executor, self.pending_path, record)

    def _close_pending(self, result: LastResult) -> None:
        self.last_result = result
        self.pending = None
        _clear_pending(self.executor, self.pending_path)

    def _pending_out(self) -> dict | None:
        if self.pending is None:
            return None
        return {"id": self.pending.id, "applied_at": self.pending.applied_at.isoformat(),
                "expires_at": self.pending.expires_at.isoformat(), "summary": self.pending.summary}

    def _last_result_out(self) -> dict | None:
        if self.last_result is None:
            return None
        return {"kind": self.last_result.kind, "at": self.last_result.at.isoformat(),
                "message": self.last_result.message}
