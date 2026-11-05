"""Host kirish — SSH va Veb portlarini boshqarish (`firewall.py`dagi
commit-confirm naqshning AYNI o'zi, lekin MUSTAQIL holat/pending fayli).

SSH port o'zgarishi: `/etc/ssh/sshd_config.d/10-innova-port.conf` drop-in
(Debian'ning standart `Include .../sshd_config.d/*.conf`siga tayanadi —
bo'lmasa `unsupported` xatosi bilan rad etiladi), `sshd -t` bilan tekshirish,
keyin `sshd -T` orqali SAMARALI natijani tasdiqlash (asosiy `sshd_config`da
ustun `Port` bo'lsa — buni aniq TOPADI, taxmin qilmaydi). Debian 13'da
`ssh.socket` faol bo'lsa (socket-aktivatsiya) — alohida `ssh.socket.d`
drop-in + `daemon-reload`/`restart ssh.socket`, aks holda `reload ssh`.
PENDING davomida ikkala port (eski+yangi) bir vaqtda tinglanadi — confirm
faqat YANGI portni qoldiradi, rollback/timeout faqat ESKI portni.

Veb port o'zgarishi: `.env`dagi `WEB_HOST_PORT`/`WEB_HTTPS_PORT`ni yangilab,
FAQAT `web` konteynerini qayta yaratadi (`docker compose ... up -d --no-deps
web`) — chaqiruvlarga (asterisk/api) TEGMAYDI. Tasdiqlash YANGI origin'dan
keladi (localStorage token yo'q) — shu sabab `AccessService.confirm()`
`kind` bo'yicha cheklab berilishi mumkin (ochiq API endpoint uchun)."""
from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.netd.errors import NetdError
from app.netd.executor import COMPOSE_WEB_ARGV, Executor, NFTABLES_CONF_PATH

SSHD_MAIN_CONFIG_PATH = "/etc/ssh/sshd_config"
SSHD_DROPIN_PATH = "/etc/ssh/sshd_config.d/10-innova-port.conf"
SSH_SOCKET_DROPIN_PATH = "/etc/systemd/system/ssh.socket.d/10-innova-port.conf"
PORTS_NFT_PATH = "/etc/innova/ports.nft"
ENV_PATH = "/opt/innova/deploy/.env"

SSH_DEFAULT_TIMEOUT_S = 180
WEB_DEFAULT_TIMEOUT_S = 300
MIN_TIMEOUT_S = 30
MAX_TIMEOUT_S = 600

RESERVED_PORTS = frozenset({5060, 5061, 5038, 8088, 5432, 8710, 8711, 8712})
RTP_RANGE = (10000, 20000)

_NOLOGIN_SHELLS = frozenset({"/usr/sbin/nologin", "/sbin/nologin", "/bin/false"})
_NFTABLES_INNOVA_SIGNATURE = "Innova PBX host firewall"
_INCLUDE_RE = re.compile(r"^\s*Include\s+.*sshd_config\.d", re.IGNORECASE | re.MULTILINE)

_ROLLBACK_MESSAGES = {
    "timeout": "Vaqt tugadi — kirish sozlamasi avtomatik qaytarildi",
    "manual": "Kirish sozlamasi qo'lda qaytarildi",
    "restart": "netd qayta ishga tushdi — tasdiqlanmagan kirish o'zgarishi qaytarildi",
}


@dataclass(frozen=True)
class FieldError:
    field: str
    message: str


@dataclass(frozen=True)
class LastResult:
    kind: str  # confirmed | rolled_back
    at: datetime
    message: str | None


# --------------------------------------------------------------------- validatsiya

def is_valid_port(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 65535


def _in_rtp_range(port: int) -> bool:
    return RTP_RANGE[0] <= port <= RTP_RANGE[1]


def _common_port_errors(field_name: str, port: int) -> list[FieldError]:
    errors = []
    if port in RESERVED_PORTS:
        errors.append(FieldError(field_name, f"Tizim xizmati porti band: {port}"))
    if _in_rtp_range(port):
        errors.append(FieldError(field_name, "RTP diapazoniga (10000-20000) tushadi"))
    return errors


def validate_ssh_port(port: object, *, web_ports: tuple[int, int]) -> list[FieldError]:
    if not is_valid_port(port):
        return [FieldError("port", "1..65535 oralig'ida butun son bo'lishi kerak")]
    errors = _common_port_errors("port", port)
    if port in web_ports:
        errors.append(FieldError("port", "Veb port bilan to'qnashadi"))
    return errors


def _validate_one_web_port(field_name: str, port: object, *, ssh_port: int) -> list[FieldError]:
    if not is_valid_port(port):
        return [FieldError(field_name, "1..65535 oralig'ida butun son bo'lishi kerak")]
    errors = _common_port_errors(field_name, port)
    if port == ssh_port:
        errors.append(FieldError(field_name, "SSH porti bilan to'qnashadi"))
    return errors


def validate_web_ports(http_port: object, https_port: object, *, ssh_port: int) -> list[FieldError]:
    errors = _validate_one_web_port("http_port", http_port, ssh_port=ssh_port)
    errors += _validate_one_web_port("https_port", https_port, ssh_port=ssh_port)
    if is_valid_port(http_port) and is_valid_port(https_port) and http_port == https_port:
        errors.append(FieldError("https_port", "http va https porti bir xil bo'lishi mumkin emas"))
    return errors


def _ssh_apply_errors(port: int, current_port: int, web_ports: tuple[int, int],
                       listening_ports: list[int]) -> list[FieldError]:
    """`ssh_apply` validatsiyasi — sof funksiya (CRAP: `ssh_apply`dan ajratilgan)."""
    errors = validate_ssh_port(port, web_ports=web_ports)
    if not errors and port != current_port and port in listening_ports:
        errors.append(FieldError("port", f"{port} portda boshqa jarayon allaqachon tinglayapti"))
    if not errors and port == current_port:
        errors.append(FieldError("port", "Yangi port joriy porti bilan bir xil"))
    return errors


# --------------------------------------------------------------------- parsing

def parse_ss_listen_ports(text: str) -> list[int]:
    """`ss -Hltn` chiqishi — har qatorning 4-ustuni `Local Address:Port`."""
    ports: set[int] = set()
    for line in text.splitlines():
        cols = line.split()
        if len(cols) < 4:
            continue
        _, _, port_str = cols[3].rpartition(":")
        if port_str.isdigit():
            ports.add(int(port_str))
    return sorted(ports)


def parse_sshd_dash_t(text: str) -> dict[str, Any]:
    """`sshd -T` — har qatorda kichik harfdagi `kalit qiymat`; `port` bir
    necha marta qaytarilishi mumkin (bir nechta samarali `Port`)."""
    ports: list[int] = []
    password_auth: bool | None = None
    root_login: str | None = None
    for line in text.splitlines():
        key, _, value = line.strip().partition(" ")
        key, value = key.lower(), value.strip()
        if key == "port" and value.isdigit():
            ports.append(int(value))
        elif key == "passwordauthentication":
            password_auth = value.lower() == "yes"
        elif key == "permitrootlogin":
            root_login = value.lower()
    return {"ports": sorted(set(ports)) or [22], "password_auth": password_auth, "root_login": root_login}


def _directive_values(text: str, name: str) -> list[str]:
    return re.findall(rf"^\s*{name}\s+(\S+)", text, re.IGNORECASE | re.MULTILINE)


def parse_sshd_config_fallback(main_text: str, dropin_text: str) -> dict[str, Any]:
    """`sshd -T` ishlamagan holatlar uchun zaxira — drop-in'dagi `Port`
    asosiy fayldan USTUN turadi (xuddi haqiqiy `Include` tartibi kabi)."""
    port_values = _directive_values(dropin_text, "Port") or _directive_values(main_text, "Port")
    ports = sorted({int(v) for v in port_values if v.isdigit()}) or [22]
    password_values = _directive_values(main_text, "PasswordAuthentication")
    root_values = _directive_values(main_text, "PermitRootLogin")
    password_auth = password_values[0].lower() == "yes" if password_values else None
    root_login = root_values[0].lower() if root_values else None
    return {"ports": ports, "password_auth": password_auth, "root_login": root_login}


def parse_passwd_login_users(text: str) -> list[str]:
    """`/etc/passwd` — UID >= 1000 va shell `nologin`/`false` bo'lmagan
    foydalanuvchilar (preseed: faqat `innova`, root kirishi o'chirilgan)."""
    users = []
    for line in text.splitlines():
        fields = line.split(":")
        if len(fields) < 7 or not fields[2].isdigit():
            continue
        if int(fields[2]) >= 1000 and fields[6].strip() not in _NOLOGIN_SHELLS:
            users.append(fields[0])
    return sorted(users)


def nftables_conf_is_innova(text: str | None) -> bool:
    return text is not None and _NFTABLES_INNOVA_SIGNATURE in text


def has_sshd_config_d_include(text: str) -> bool:
    return bool(_INCLUDE_RE.search(text))


# --------------------------------------------------------------------- render

def render_sshd_port_dropin(ports: list[int]) -> str:
    lines = ["# Innova PBX — netd avtomatik yaratadi, qo'lda tahrir qilinmasin."]
    lines += [f"Port {p}" for p in sorted(set(ports))]
    return "\n".join(lines) + "\n"


def render_ssh_socket_dropin(ports: list[int]) -> str:
    lines = ["[Socket]", "ListenStream="] + [f"ListenStream={p}" for p in sorted(set(ports))]
    return "\n".join(lines) + "\n"


def render_ports_nft(ports: list[int]) -> str:
    joined = ", ".join(str(p) for p in sorted(set(ports)))
    return ("# Innova PBX — netd avtomatik yaratadi, qo'lda tahrir qilinmasin.\n"
            f"define INNOVA_SSH_PORTS = {{ {joined} }}\n")


def parse_env(text: str) -> dict[str, str]:
    env = {}
    for line in text.splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def set_env_vars(text: str, updates: dict[str, str]) -> str:
    """Mavjud kalitlar YANGILANADI (qolgan tartib/izohlar saqlanadi); yo'q
    kalit oxiriga qo'shiladi."""
    remaining = dict(updates)
    out_lines = []
    for line in text.splitlines():
        key = line.partition("=")[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in remaining:
            out_lines.append(f"{key}={remaining.pop(key)}")
        else:
            out_lines.append(line)
    for key, value in remaining.items():
        out_lines.append(f"{key}={value}")
    return "\n".join(out_lines) + "\n"


# --------------------------------------------------------------------- pending

@dataclass(frozen=True)
class _Snapshot:
    files: dict[str, str | None]


@dataclass(frozen=True)
class _PendingRecord:
    id: str
    kind: str  # ssh | web
    applied_at: datetime
    expires_at: datetime
    old_ports: list[int]
    new_ports: list[int]
    snapshot: _Snapshot

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def to_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind,
            "applied_at": self.applied_at.astimezone(timezone.utc).isoformat(),
            "expires_at": self.expires_at.astimezone(timezone.utc).isoformat(),
            "old_ports": self.old_ports, "new_ports": self.new_ports,
            "snapshot": {"files": self.snapshot.files},
        }

    @staticmethod
    def from_dict(d: dict) -> "_PendingRecord":
        return _PendingRecord(
            id=d["id"], kind=d["kind"],
            applied_at=datetime.fromisoformat(d["applied_at"]),
            expires_at=datetime.fromisoformat(d["expires_at"]),
            old_ports=d["old_ports"], new_ports=d["new_ports"],
            snapshot=_Snapshot(files=d["snapshot"]["files"]),
        )


def _load_pending(executor: Executor, path: str) -> _PendingRecord | None:
    raw = executor.read_text(path)
    if not raw or not raw.strip():
        return None
    return _PendingRecord.from_dict(json.loads(raw))


def _save_pending(executor: Executor, path: str, record: _PendingRecord) -> None:
    executor.write_text_atomic(path, json.dumps(record.to_dict(), indent=2) + "\n", mode=0o600)


def _clear_pending(executor: Executor, path: str) -> None:
    # `firewall.py::_clear_pending` bilan BIR XIL sabab — soxta `Executor`
    # haqiqiy fayl yo'liga ega emas, shu sabab o'chirish o'rniga bo'sh yozamiz.
    executor.write_text_atomic(path, "", mode=0o600)


class AccessService:
    def __init__(self, executor: Executor, *, readonly: bool, pending_path: str,
                 now_fn: Callable[[], datetime], other_pending: Callable[[], bool] = lambda: False) -> None:
        self.executor = executor
        self.readonly = readonly
        self.pending_path = pending_path
        self._now = now_fn
        self._other_pending = other_pending
        self.pending: _PendingRecord | None = _load_pending(executor, pending_path)
        self.last_result: LastResult | None = None

    # ----------------------------------------------------------------- public ops
    async def state(self) -> dict[str, Any]:
        await self._maybe_expire()
        return {
            "ssh": await self._ssh_state(), "web": self._web_state(),
            "readonly_reason": self._readonly_reason(),
            "pending": self._pending_out(), "last_result": self._last_result_out(),
        }

    async def current_ports(self) -> dict[str, list[int]]:
        """`firewall.py`ning dinamik `ssh`/`web` port ro'yxati uchun — PENDING
        paytida SSHD haqiqatda ikkala portni ham tinglaydi, shu sabab alohida
        holat kerak emas, joriy samarali konfiguratsiya YETARLI."""
        ssh_ports = (await self._sshd_effective())["ports"]
        web = self._web_state()
        return {"ssh": ssh_ports, "web": [web["http_port"], web["https_port"]]}

    async def _write_ssh_with_rollback(self, current_port: int, port: int, use_socket: bool,
                                        snapshot: _Snapshot) -> str | None:
        try:
            await self._write_ssh_ports([current_port, port], use_socket=use_socket)
            return await self._update_host_firewall_ssh_ports([current_port, port])
        except NetdError:
            await self._rollback_ssh(snapshot)
            raise

    async def ssh_apply(self, port: int, *, timeout_s: int | None = None) -> dict[str, Any]:
        await self._maybe_expire()
        self._guard_writable()
        web = self._web_state()
        current = await self._ssh_state()
        errors = _ssh_apply_errors(port, current["port"], (web["http_port"], web["https_port"]),
                                    await self._listening_ports())
        if errors:
            raise NetdError("invalid_config", "SSH port sozlamasi yaroqsiz",
                             [{"field": e.field, "message": e.message} for e in errors])
        main_cfg = self.executor.read_text(SSHD_MAIN_CONFIG_PATH) or ""
        if not has_sshd_config_d_include(main_cfg):
            raise NetdError("unsupported", "sshd_config'da `Include .../sshd_config.d/*.conf` "
                                            "topilmadi — port avtomatik o'zgartirib bo'lmaydi")
        timeout = self._clamp_timeout(timeout_s, SSH_DEFAULT_TIMEOUT_S)
        snapshot = self._ssh_snapshot()
        use_socket = await self._ssh_socket_active()
        warning = await self._write_ssh_with_rollback(current["port"], port, use_socket, snapshot)
        self._open_pending("ssh", [current["port"]], [port], timeout, snapshot)
        return self._apply_out([warning] if warning else [])

    async def web_apply(self, http_port: int, https_port: int, *, timeout_s: int | None = None) -> dict[str, Any]:
        await self._maybe_expire()
        self._guard_writable()
        ssh_port = (await self._ssh_state())["port"]
        errors = validate_web_ports(http_port, https_port, ssh_port=ssh_port)
        current = self._web_state()
        if not errors and (http_port, https_port) == (current["http_port"], current["https_port"]):
            errors.append(FieldError("http_port", "Yangi portlar joriy portlar bilan bir xil"))
        if errors:
            raise NetdError("invalid_config", "Veb port sozlamasi yaroqsiz",
                             [{"field": e.field, "message": e.message} for e in errors])
        timeout = self._clamp_timeout(timeout_s, WEB_DEFAULT_TIMEOUT_S)
        old_env = self.executor.read_text(ENV_PATH) or ""
        snapshot = _Snapshot(files={ENV_PATH: old_env})
        new_env = set_env_vars(old_env, {"WEB_HOST_PORT": str(http_port), "WEB_HTTPS_PORT": str(https_port)})
        self.executor.write_text_atomic(ENV_PATH, new_env)
        try:
            await self._must_run(list(COMPOSE_WEB_ARGV))
        except NetdError:
            self.executor.write_text_atomic(ENV_PATH, old_env)
            await self._safe_run(list(COMPOSE_WEB_ARGV))
            raise
        self._open_pending("web", [current["http_port"], current["https_port"]], [http_port, https_port],
                            timeout, snapshot)
        return self._apply_out([])

    async def confirm(self, pending_id: str, *, kind: str | None = None) -> dict[str, Any]:
        await self._maybe_expire()
        record = self._require_pending(pending_id, kind)
        if record.kind == "ssh":
            await self._confirm_ssh(record)
        self._close_pending(LastResult("confirmed", self._now(), None))
        return await self.state()

    async def rollback(self, pending_id: str) -> dict[str, Any]:
        self._require_pending(pending_id)
        await self._do_rollback(reason="manual")
        return await self.state()

    async def startup_recover(self) -> None:
        if self.pending is not None:
            await self._do_rollback(reason="restart")

    # ----------------------------------------------------------------- ssh state/apply
    async def _ssh_state(self) -> dict[str, Any]:
        active = (await self._run_text(["systemctl", "is-active", "ssh"])).strip() == "active"
        effective = await self._sshd_effective()
        all_listen = await self._listening_ports()
        login_users = parse_passwd_login_users(self.executor.read_text("/etc/passwd") or "")
        host_fw = "innova" if nftables_conf_is_innova(self.executor.read_text(NFTABLES_CONF_PATH)) else "external"
        return {
            "port": effective["ports"][0], "active": active,
            "listening_ports": sorted(set(all_listen) & set(effective["ports"])),
            "password_auth": effective["password_auth"], "root_login": effective["root_login"],
            "login_users": login_users, "host_firewall": host_fw,
        }

    def _web_state(self) -> dict[str, Any]:
        env = parse_env(self.executor.read_text(ENV_PATH) or "")
        return {"http_port": int(env.get("WEB_HOST_PORT") or 80), "https_port": int(env.get("WEB_HTTPS_PORT") or 443)}

    async def _sshd_effective(self) -> dict[str, Any]:
        text = await self._run_text(["sshd", "-T"])
        if text.strip():
            return parse_sshd_dash_t(text)
        main = self.executor.read_text(SSHD_MAIN_CONFIG_PATH) or ""
        dropin = self.executor.read_text(SSHD_DROPIN_PATH) or ""
        return parse_sshd_config_fallback(main, dropin)

    async def _listening_ports(self) -> list[int]:
        return parse_ss_listen_ports(await self._run_text(["ss", "-Hltn"]))

    async def _ssh_socket_active(self) -> bool:
        return (await self._run_text(["systemctl", "is-active", "ssh.socket"])).strip() == "active"

    async def _write_ssh_ports(self, ports: list[int], *, use_socket: bool) -> None:
        self.executor.write_text_atomic(SSHD_DROPIN_PATH, render_sshd_port_dropin(ports))
        check = await self.executor.run(["sshd", "-t"], timeout=5.0)
        if not check.ok:
            raise NetdError("invalid_config", f"sshd konfiguratsiyasi xato: {check.stderr.strip()}")
        effective = await self._sshd_effective()
        if set(ports) - set(effective["ports"]):
            raise NetdError("sshd_config_conflict", "sshd_config'da asosiy `Port` direktivasi "
                                                      "ustun turadi — avval uni olib tashlang")
        if use_socket:
            self.executor.write_text_atomic(SSH_SOCKET_DROPIN_PATH, render_ssh_socket_dropin(ports))
            await self._must_run(["systemctl", "daemon-reload"])
            await self._must_run(["systemctl", "restart", "ssh.socket"])
        else:
            await self._must_run(["systemctl", "reload", "ssh"])

    async def _update_host_firewall_ssh_ports(self, ports: list[int]) -> str | None:
        if not nftables_conf_is_innova(self.executor.read_text(NFTABLES_CONF_PATH)):
            return "Host firewall Innova'niki emas — yangi SSH portini o'zingiz ochishingiz kerak"
        old_ports_nft = self.executor.read_text(PORTS_NFT_PATH)
        self.executor.write_text_atomic(PORTS_NFT_PATH, render_ports_nft(ports))
        check = await self.executor.run(["nft", "-c", "-f", NFTABLES_CONF_PATH], timeout=5.0)
        if not check.ok:
            self.executor.write_text_atomic(PORTS_NFT_PATH, old_ports_nft if old_ports_nft is not None else "")
            raise NetdError("apply_failed", f"nft sintaksisi xato: {check.stderr.strip()}")
        applied = await self.executor.run(["nft", "-f", NFTABLES_CONF_PATH], timeout=5.0)
        if not applied.ok:
            self.executor.write_text_atomic(PORTS_NFT_PATH, old_ports_nft if old_ports_nft is not None else "")
            await self.executor.run(["nft", "-f", NFTABLES_CONF_PATH], timeout=5.0)
            raise NetdError("apply_failed", f"nft qo'llash xato: {applied.stderr.strip()}")
        return None

    async def _confirm_ssh(self, record: _PendingRecord) -> None:
        new_port = record.new_ports[0]
        use_socket = await self._ssh_socket_active()
        await self._write_ssh_ports([new_port], use_socket=use_socket)
        await self._update_host_firewall_ssh_ports([new_port])

    def _ssh_snapshot(self) -> _Snapshot:
        return _Snapshot(files={
            SSHD_DROPIN_PATH: self.executor.read_text(SSHD_DROPIN_PATH),
            SSH_SOCKET_DROPIN_PATH: self.executor.read_text(SSH_SOCKET_DROPIN_PATH),
            PORTS_NFT_PATH: self.executor.read_text(PORTS_NFT_PATH),
        })

    async def _rollback_ssh(self, snapshot: _Snapshot) -> None:
        self._restore_files(snapshot)
        if await self._ssh_socket_active():
            await self._safe_run(["systemctl", "daemon-reload"])
            await self._safe_run(["systemctl", "restart", "ssh.socket"])
        else:
            await self._safe_run(["systemctl", "reload", "ssh"])
        if nftables_conf_is_innova(self.executor.read_text(NFTABLES_CONF_PATH)):
            await self._safe_run(["nft", "-f", NFTABLES_CONF_PATH])

    async def _rollback_web(self, snapshot: _Snapshot) -> None:
        self._restore_files(snapshot)
        await self._safe_run(list(COMPOSE_WEB_ARGV))

    def _restore_files(self, snapshot: _Snapshot) -> None:
        for path, content in snapshot.files.items():
            self.executor.write_text_atomic(path, content if content is not None else "")

    async def _do_rollback(self, *, reason: str) -> None:
        record = self.pending
        if record is None:
            return
        if record.kind == "ssh":
            await self._rollback_ssh(record.snapshot)
        else:
            await self._rollback_web(record.snapshot)
        self._close_pending(LastResult("rolled_back", self._now(), _ROLLBACK_MESSAGES[reason]))

    # ----------------------------------------------------------------- guards/helpers
    def _readonly_reason(self) -> str | None:
        if self.readonly:
            return "Bu serverda kirish sozlamalarini tahrirlash o'chirilgan (NETD_READONLY)"
        return None

    def _guard_writable(self) -> None:
        if self.readonly:
            raise NetdError("readonly", self._readonly_reason())
        if self.pending is not None:
            raise NetdError("pending_exists", "Tasdiqlanmagan kirish o'zgarishi allaqachon mavjud (409)")
        if self._other_pending():
            raise NetdError("pending_exists", "Firewall o'zgarishi kutilmoqda — avval uni yakunlang (409)")

    def _require_pending(self, pending_id: str, kind: str | None = None) -> _PendingRecord:
        record = self.pending
        ok = record is not None and secrets.compare_digest(record.id, pending_id)
        if not ok or (kind is not None and record.kind != kind):
            raise NetdError("not_found", "Kutilayotgan kirish o'zgarishi topilmadi")
        return record

    async def _maybe_expire(self) -> None:
        if self.pending is not None and self.pending.is_expired(self._now()):
            await self._do_rollback(reason="timeout")

    @staticmethod
    def _clamp_timeout(timeout_s: int | None, default: int) -> int:
        value = default if timeout_s is None else timeout_s
        return max(MIN_TIMEOUT_S, min(MAX_TIMEOUT_S, value))

    async def _must_run(self, argv: list[str]) -> None:
        result = await self.executor.run(argv, timeout=10.0)
        if not result.ok:
            raise NetdError("command_failed", f"{' '.join(argv)}: {result.stderr.strip() or 'xato'}")

    async def _safe_run(self, argv: list[str]) -> None:
        try:
            await self.executor.run(argv, timeout=10.0)
        except TimeoutError:
            pass

    async def _run_text(self, argv: list[str]) -> str:
        try:
            result = await self.executor.run(argv, timeout=5.0)
        except TimeoutError:
            return ""
        return result.stdout

    # ----------------------------------------------------------------- pending io
    def _open_pending(self, kind: str, old_ports: list[int], new_ports: list[int],
                       timeout_s: int, snapshot: _Snapshot) -> None:
        now = self._now()
        record = _PendingRecord(id=secrets.token_hex(16), kind=kind, applied_at=now,
                                 expires_at=now + timedelta(seconds=timeout_s),
                                 old_ports=old_ports, new_ports=new_ports, snapshot=snapshot)
        self.pending = record
        _save_pending(self.executor, self.pending_path, record)

    def _close_pending(self, result: LastResult) -> None:
        self.last_result = result
        self.pending = None
        _clear_pending(self.executor, self.pending_path)

    def _apply_out(self, warnings: list[str]) -> dict[str, Any]:
        assert self.pending is not None
        return {"pending_id": self.pending.id,
                "expires_at": self.pending.expires_at.astimezone(timezone.utc).isoformat(),
                "warnings": warnings}

    def _pending_out(self) -> dict | None:
        if self.pending is None:
            return None
        p = self.pending
        return {"id": p.id, "kind": p.kind, "expires_at": p.expires_at.astimezone(timezone.utc).isoformat(),
                "old_ports": p.old_ports, "new_ports": p.new_ports}

    def _last_result_out(self) -> dict | None:
        if self.last_result is None:
            return None
        return {"status": self.last_result.kind, "message": self.last_result.message,
                "at": self.last_result.at.astimezone(timezone.utc).isoformat()}
