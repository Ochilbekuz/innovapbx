"""Host buyruqlari/fayllari — m8-network-contract.md bo'lim 1: FAQAT
`nsenter -t 1 -m -u -n -i -p --` orqali (shell YO'Q, argv ro'yxati, qat'iy
allowlist), fayllar `/proc/1/root/<yo'l>` orqali. `NETD_EXEC=local` +
`NETD_HOST_ROOT=/` — integratsiya testlari uchun (nsenter'siz, izolyatsiya
qilingan konteyner ichida haqiqiy `ifupdown`)."""
from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import os
import signal
import re
import tempfile
from dataclasses import dataclass
from typing import Callable

# M12 B3 — panel firewall qoidalari shu fayliga yoziladi, `nft`ga FAQAT shu
# aniq yo'l bilan ishlashga ruxsat beriladi (pastda `_nft_argv_ok`). Fayl
# mustaqil `table inet innova_fw` ni e'lon qiladi (asosiy `table inet innova`
# — `/etc/nftables.conf`, sip_guard `innova_guard` — TEGILMAYDI, mustaqil
# hook ustida faqat qo'shimcha `drop` qatlami, m12-contract.md B3).
FIREWALL_CONF_PATH = "/etc/innova/firewall.nft"

# Kirish (SSH/Veb) — host firewall (asosiy `table inet innova`,
# `/etc/nftables.conf`). netd faqat shu ANIQ fayl bilan `-c -f`/`-f` orqali
# ishlaydi (`access.py` SSH portini `include "/etc/innova/ports.nft"` orqali
# yozadi, `/etc/nftables.conf`ning qolgan qismiga TEGMAYDI).
NFTABLES_CONF_PATH = "/etc/nftables.conf"

# Veb konteynerini QAYTA YARATISH (faqat `web`, chaqiruvlarga tegmasdan) —
# yagona qattiq kodlangan argv, boshqa hech qanday compose amali (down/pull/
# boshqa xizmat) ishlatilmaydi.
COMPOSE_WEB_ARGV = [
    "docker", "compose",
    "-f", "/opt/innova/deploy/docker-compose.yml",
    "-f", "/opt/innova/deploy/docker-compose.appliance.yml",
    "--env-file", "/opt/innova/deploy/.env",
    "up", "-d", "--no-deps", "web",
]

ALLOWED_BINARIES = frozenset(
    {"ip", "ifup", "ifdown", "hostname", "timedatectl", "systemctl", "nft", "sshd", "ss", "docker", "ping"})

_TIMEZONE_RE = re.compile(r"^[A-Za-z0-9_+\-/]{1,64}$")


def _timedatectl_argv_ok(args: list[str]) -> bool:
    """M12 B1 — faqat holat o'qish va vaqt/NTP sozlash; boshqa hech narsa."""
    if args in (["show"], ["show-timesync"]):
        return True
    if args in (["set-ntp", "true"], ["set-ntp", "false"]):
        return True
    return len(args) == 2 and args[0] == "set-timezone" and bool(_TIMEZONE_RE.match(args[1]))


_SYSTEMCTL_ALLOWED_ARGS = (
    ["reboot"], ["poweroff"], ["restart", "systemd-timesyncd"], ["restart", "chrony"],
    # Kirish (SSH): holat, qayta yuklash (drop-in'dan keyin) va Debian 13
    # `ssh.socket` soket-aktivatsiyasi uchun `daemon-reload`/`restart ssh.socket`.
    ["is-active", "ssh"], ["is-active", "ssh.socket"], ["reload", "ssh"],
    ["restart", "ssh.socket"], ["daemon-reload"],
)
_SSHD_ALLOWED_ARGS = (["-t"], ["-T"])
_SS_ALLOWED_ARGS = (["-Hltn"],)


def _systemctl_argv_ok(args: list[str]) -> bool:
    """M12 B2 + kirish (access) — FAQAT `reboot`/`poweroff`, vaqt sinxron
    xizmatini qayta ishga tushirish (B1) va SSH holati/qayta yuklash; boshqa
    argument (masalan `stop <xizmat>`, `restart sshd`) RAD ETILADI — bu
    yagona maqsadli allowlist."""
    return args in _SYSTEMCTL_ALLOWED_ARGS


def _nft_argv_ok(args: list[str]) -> bool:
    """M12 B3 + kirish (access) — FAQAT FIREWALL_CONF_PATH yoki
    NFTABLES_CONF_PATH'ni tekshirish (`-c -f`) va qo'llash (`-f`); boshqa
    fayl/amal (masalan `list ruleset`, `flush ruleset`) RAD ETILADI — bu
    bilan panel hech qachon sip_guard'ga tegolmaydi, faqat shu ikki aniq
    faylni yuklay oladi."""
    return args in (
        ["-c", "-f", FIREWALL_CONF_PATH], ["-f", FIREWALL_CONF_PATH],
        ["-c", "-f", NFTABLES_CONF_PATH], ["-f", NFTABLES_CONF_PATH],
    )


def _sshd_argv_ok(args: list[str]) -> bool:
    """Kirish (access) — FAQAT sintaksis tekshirish (`-t`) va samarali
    konfiguratsiyani o'qish (`-T`); hech qachon haqiqiy ishga tushirish/
    konfiguratsiyasiz chaqiruv emas."""
    return args in _SSHD_ALLOWED_ARGS


def _ss_argv_ok(args: list[str]) -> bool:
    """Kirish (access) — FAQAT tinglovchi TCP portlarini sanash (`-Hltn`)."""
    return args in _SS_ALLOWED_ARGS


def _docker_argv_ok(args: list[str]) -> bool:
    """Kirish (access) — FAQAT `web` konteynerini qayta yaratish
    (COMPOSE_WEB_ARGV, asterisk/api/postgres'ga HECH QACHON tegmaydi)."""
    return args == COMPOSE_WEB_ARGV[1:]


# Tarmoq «Ping» tabi — `ping -c N -W S [-4|-6] <host>` (shell yo'q, argv).
# Host `-` bilan boshlana olmaydi (argument in'eksiyasi yo'q): faqat IPv4/IPv6
# literal (scope-id `%` siz) yoki RFC1123 uslubidagi nom.
PING_COUNTS = range(1, 11)
PING_WAITS = range(1, 6)
_PING_NAME_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,62})(\.[A-Za-z0-9-]{1,63})*$")
_PING_FAMILY_FLAG = {"ipv4": ["-4"], "ipv6": ["-6"], "name": []}


def _ip_version(host: str) -> int | None:
    try:
        return ipaddress.ip_address(host).version
    except ValueError:
        return None


def ping_host_kind(host: str) -> str | None:
    """`"ipv4"`/`"ipv6"`/`"name"` yoki yaroqsiz bo'lsa `None` — API chegarasi,
    netd va argv guard UCHALASI shu bitta qarorni ishlatadi."""
    if "%" in host:  # IPv6 scope-id (`fe80::1%eth0`) — ruxsat yo'q
        return None
    version = _ip_version(host)
    if version is not None:
        return f"ipv{version}"
    return "name" if len(host) <= 253 and _PING_NAME_RE.fullmatch(host) else None


def ping_argv(host: str, count: int, wait_s: int) -> list[str]:
    """Kanonik argv — oila bayrog'i faqat IP literal uchun (nom — tizim tanlaydi)."""
    return ["ping", "-c", str(count), "-W", str(wait_s), *_PING_FAMILY_FLAG[ping_host_kind(host) or "name"], host]


def _int_in(value: str, allowed: range) -> int | None:
    """ASCII raqamlar va diapazon ichida bo'lsa son, aks holda `None`."""
    return int(value) if value.isascii() and value.isdigit() and int(value) in allowed else None


def _ping_argv_ok(args: list[str]) -> bool:
    """FAQAT `ping_argv` hosil qiladigan aniq shakl: N 1..10, S 1..5, host
    `ping_host_kind`dan o'tgan — argv qayta qurilib, so'zma-so'z solishtiriladi
    (`04`, ortiqcha bayroq, tartib almashishi — hammasi rad)."""
    if len(args) < 5:
        return False
    count, wait_s, host = _int_in(args[1], PING_COUNTS), _int_in(args[3], PING_WAITS), args[-1]
    if count is None or wait_s is None or ping_host_kind(host) is None:
        return False
    return args == ping_argv(host, count, wait_s)[1:]


# Binar nomi -> argumentlar (argv[1:]) tekshiruvchisi. Ro'yxatda yo'q binar
# (masalan `ip`/`ifup`/`ifdown`/`hostname`) argumentlarsiz ham ishlayveradi —
# ularning xavfsizligi allaqachon yuqori darajada (`ifupdown.py`/`hostname.py`)
# ta'minlangan, bu yerda FAQAT yangi (M12+) binarlar uchun qo'shimcha chiziq.
_ARGV_GUARDS: dict[str, Callable[[list[str]], bool]] = {
    "timedatectl": _timedatectl_argv_ok,
    "systemctl": _systemctl_argv_ok,
    "nft": _nft_argv_ok,
    "sshd": _sshd_argv_ok,
    "ss": _ss_argv_ok,
    "docker": _docker_argv_ok,
    "ping": _ping_argv_ok,
}


class CommandNotAllowedError(ValueError):
    pass


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def host_path(host_root: str, path: str) -> str:
    if not path.startswith("/"):
        raise ValueError(f"mutlaq yo'l kerak: {path!r}")
    return os.path.join(host_root, path.lstrip("/"))


class Executor:
    """`mode` — `"nsenter"` (haqiqiy host) yoki `"local"` (test konteyneri);
    `host_root` — `"/proc/1/root"` yoki `"/"`."""

    def __init__(self, mode: str, host_root: str) -> None:
        if mode not in ("nsenter", "local"):
            raise ValueError(f"Noma'lum NETD_EXEC: {mode!r}")
        self.mode = mode
        self.host_root = host_root

    def path(self, p: str) -> str:
        return host_path(self.host_root, p)

    async def run(self, argv: list[str], *, timeout: float = 10.0) -> CommandResult:
        if not argv or argv[0] not in ALLOWED_BINARIES:
            raise CommandNotAllowedError(f"Ruxsat etilmagan buyruq: {argv[0] if argv else ''!r}")
        guard = _ARGV_GUARDS.get(argv[0])
        if guard is not None and not guard(argv[1:]):
            raise CommandNotAllowedError(f"Ruxsat etilmagan argumentlar: {argv!r}")
        full_argv = self._wrap(argv)
        # O'z jarayon guruhi: `nsenter -p` buyruqni bola jarayonda bajaradi — timeout'da faqat
        # nsenter o'ldirilsa bola stdout quvurini ushlab turadi va `wait()` u tugaguncha osiladi.
        proc = await asyncio.create_subprocess_exec(
            *full_argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, start_new_session=True,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            await proc.wait()
            raise
        return CommandResult(proc.returncode or 0, stdout.decode(errors="replace"), stderr.decode(errors="replace"))

    def _wrap(self, argv: list[str]) -> list[str]:
        if self.mode == "local":
            return argv
        return ["nsenter", "-t", "1", "-m", "-u", "-n", "-i", "-p", "--", *argv]

    def read_text(self, path: str) -> str | None:
        try:
            with open(self.path(path), encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return None

    def write_text_atomic(self, path: str, content: str, mode: int = 0o644) -> None:
        full = self.path(path)
        directory = os.path.dirname(full)
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".netd-tmp-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp_path, mode)
            os.replace(tmp_path, full)
        except Exception:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp_path)
            raise

    def is_symlink(self, path: str) -> bool:
        return os.path.islink(self.path(path))

    def exists(self, path: str) -> bool:
        return os.path.exists(self.path(path))

    def listdir(self, path: str) -> list[str]:
        try:
            return os.listdir(self.path(path))
        except FileNotFoundError:
            return []
