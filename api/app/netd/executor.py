"""Host buyruqlari/fayllari — m8-network-contract.md bo'lim 1: FAQAT
`nsenter -t 1 -m -u -n -i -p --` orqali (shell YO'Q, argv ro'yxati, qat'iy
allowlist), fayllar `/proc/1/root/<yo'l>` orqali. `NETD_EXEC=local` +
`NETD_HOST_ROOT=/` — integratsiya testlari uchun (nsenter'siz, izolyatsiya
qilingan konteyner ichida haqiqiy `ifupdown`)."""
from __future__ import annotations

import asyncio
import contextlib
import os
import tempfile
from dataclasses import dataclass

ALLOWED_BINARIES = frozenset({"ip", "ifup", "ifdown", "hostname"})


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
        full_argv = self._wrap(argv)
        proc = await asyncio.create_subprocess_exec(
            *full_argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
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
