"""`app/netd/hostname.py` + `app/netd/dns.py` — `/etc/hostname`, `/etc/hosts`
127.0.1.1 qatori, `/etc/resolv.conf` parse/render + symlink=readonly aniqlash."""
from __future__ import annotations

import pytest

from app.netd import dns, hostname
from app.netd.executor import CommandResult
from app.netd.safety import UnsafeRenderError


class _Fs:
    def __init__(self, files: dict[str, str] | None = None, symlinks: set[str] | None = None):
        self.files = dict(files or {})
        self.symlinks = symlinks or set()
        self.commands: list[list[str]] = []

    def path(self, p: str) -> str:
        return p

    def read_text(self, path: str) -> str | None:
        return self.files.get(path)

    def write_text_atomic(self, path: str, content: str, mode: int = 0o644) -> None:
        self.files[path] = content

    def exists(self, path: str) -> bool:
        return path in self.files

    def is_symlink(self, path: str) -> bool:
        return path in self.symlinks

    async def run(self, argv, *, timeout=5.0):
        self.commands.append(argv)
        return CommandResult(0, "", "")


def test_read_hostname_defaults_to_localhost_when_missing():
    assert hostname.read_hostname(_Fs()) == "localhost"


def test_read_hostname_strips_whitespace():
    assert hostname.read_hostname(_Fs({"/etc/hostname": "pbx1\n"})) == "pbx1"


def test_render_hosts_replaces_only_127_0_1_1_line():
    old = "127.0.0.1\tlocalhost\n127.0.1.1\toldname\n192.168.1.1\tother\n"
    rendered = hostname.render_hosts(old, "newname")
    assert rendered == "127.0.0.1\tlocalhost\n127.0.1.1\tnewname\n192.168.1.1\tother\n"


def test_render_hosts_noop_when_no_matching_line():
    old = "127.0.0.1\tlocalhost\n"
    assert hostname.render_hosts(old, "newname") == old


@pytest.mark.asyncio
async def test_apply_hostname_writes_files_and_runs_command():
    fs = _Fs({"/etc/hosts": "127.0.0.1\tlocalhost\n127.0.1.1\toldname\n"})
    await hostname.apply_hostname(fs, "newname")
    assert fs.files["/etc/hostname"] == "newname\n"
    assert "127.0.1.1\tnewname\n" in fs.files["/etc/hosts"]
    assert fs.commands == [["hostname", "newname"]]


def test_parse_resolv_conf():
    text = "nameserver 1.1.1.1\nnameserver 8.8.8.8\nsearch example.com corp.local\n"
    servers, search = dns.parse_resolv_conf(text)
    assert servers == ["1.1.1.1", "8.8.8.8"]
    assert search == ["example.com", "corp.local"]


def test_render_resolv_conf_roundtrip():
    text = dns.render_resolv_conf(["1.1.1.1"], ["example.com"])
    assert text == "nameserver 1.1.1.1\nsearch example.com\n"
    assert dns.parse_resolv_conf(text) == (["1.1.1.1"], ["example.com"])


def test_render_resolv_conf_empty_is_empty_string():
    assert dns.render_resolv_conf([], []) == ""


def test_is_dns_editable_false_when_symlink():
    fs = _Fs({dns.RESOLV_PATH: "x"}, symlinks={dns.RESOLV_PATH})
    assert dns.is_dns_editable(fs) is False


def test_is_dns_editable_false_when_missing():
    assert dns.is_dns_editable(_Fs()) is False


def test_is_dns_editable_true_for_plain_file():
    fs = _Fs({dns.RESOLV_PATH: "nameserver 1.1.1.1\n"})
    assert dns.is_dns_editable(fs) is True


def test_write_resolv_conf():
    fs = _Fs()
    dns.write_resolv_conf(fs, ["9.9.9.9"], [])
    assert fs.files[dns.RESOLV_PATH] == "nameserver 9.9.9.9\n"


# --------------------------------------------------------------------------
# So'nggi himoya chizig'i: `validate.py`dan o'tib ketgan taqdirda ham,
# render qatlami o'zi qator ko'chirish/NUL in'eksiyasini to'xtatadi.
def test_render_resolv_conf_rejects_injected_server():
    with pytest.raises(UnsafeRenderError):
        dns.render_resolv_conf(["1.1.1.1\n    pre-up touch /tmp/pwned #"], [])


def test_render_resolv_conf_rejects_injected_search():
    with pytest.raises(UnsafeRenderError):
        dns.render_resolv_conf([], ["example.com\n    pre-up touch /tmp/pwned #"])


@pytest.mark.asyncio
async def test_apply_hostname_rejects_injected_newline():
    fs = _Fs({"/etc/hosts": "127.0.0.1\tlocalhost\n127.0.1.1\toldname\n"})
    with pytest.raises(UnsafeRenderError):
        await hostname.apply_hostname(fs, "newname\n    pre-up touch /tmp/pwned #")
    assert "/etc/hostname" not in fs.files  # yarim yozuv yo'q — guard FAYLNI o'zgartirishdan OLDIN ishlaydi


def test_render_hosts_rejects_injected_newline():
    old = "127.0.0.1\tlocalhost\n127.0.1.1\toldname\n"
    with pytest.raises(UnsafeRenderError):
        hostname.render_hosts(old, "newname\n    pre-up touch /tmp/pwned #")
