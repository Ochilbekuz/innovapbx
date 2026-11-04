"""Host buyruqlari/fayllari — m8-network-contract.md bo'lim 1: FAQAT
`nsenter -t 1 -m -u -n -i -p --` orqali (shell YO'Q, argv ro'yxati, qat'iy
allowlist), fayllar `/proc/1/root/<yo'l>` orqali. `NETD_EXEC=local` +
`NETD_HOST_ROOT=/` — integratsiya testlari uchun (nsenter'siz, izolyatsiya
qilingan konteyner ichida haqiqiy `ifupdown`)."""
from __future__ import annotations

import asyncio
import contextlib
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

ALLOWED_BINARIES = frozenset({"ip", "ifup", "ifdown", "hostname", "timedatectl", "systemctl", "nft"})

_TIMEZONE_RE = re.compile(r"^[A-Za-z0-9_+\-/]{1,64}$")


def _timedatectl_argv_ok(args: list[str]) -> bool:
    """M12 B1 — faqat holat o'qish va vaqt/NTP sozlash; boshqa hech narsa."""
    if args in (["show"], ["show-timesync"]):
        return True
    if args in (["set-ntp", "true"], ["set-ntp", "false"]):
        return True
    return len(args) == 2 and args[0] == "set-timezone" and bool(_TIMEZONE_RE.match(args[1]))


def _systemctl_argv_ok(args: list[str]) -> bool:
    """M12 B2 — FAQAT `reboot`/`poweroff` + vaqt sinxron xizmatini qayta ishga
    tushirish (B1 «Hozir sinxronlash»); boshqa argument (masalan `stop <xizmat>`,
    `restart sshd`) RAD ETILADI — bu yagona maqsadli allowlist."""
    return args in (["reboot"], ["poweroff"], ["restart", "systemd-timesyncd"], ["restart", "chrony"])


def _nft_argv_ok(args: list[str]) -> bool:
    """M12 B3 — FAQAT FIREWALL_CONF_PATH'ni tekshirish (`-c -f`) va qo'llash
    (`-f`); boshqa fayl/amal (masalan `list ruleset`, `flush ruleset`, `-f
    /etc/nftables.conf`) RAD ETILADI — bu bilan panel hech qachon asosiy
    jadval/sip_guard'ga tegolmaydi, faqat OʻZ faylini yuklay oladi."""
    return args in (["-c", "-f", FIREWALL_CONF_PATH], ["-f", FIREWALL_CONF_PATH])


# Binar nomi -> argumentlar (argv[1:]) tekshiruvchisi. Ro'yxatda yo'q binar
# (masalan `ip`/`ifup`/`ifdown`/`hostname`) argumentlarsiz ham ishlayveradi —
# ularning xavfsizligi allaqachon yuqori darajada (`ifupdown.py`/`hostname.py`)
# ta'minlangan, bu yerda FAQAT yangi (M12) binarlar uchun qo'shimcha chiziq.
_ARGV_GUARDS: dict[str, Callable[[list[str]], bool]] = {
    "timedatectl": _timedatectl_argv_ok,
    "systemctl": _systemctl_argv_ok,
    "nft": _nft_argv_ok,
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
