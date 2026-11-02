"""`app/services/acl_apply.py` — ACL fayl generatsiyasi (sof) + AMI qo'llash
(`atomic_write`/AMI monkeypatch, DB'siz soxta sessiya)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import acl_apply as mod


def test_render_acl_empty_is_comment_only():
    text = mod.render_acl([])
    assert "deny=" not in text
    assert text.startswith(";")


def test_render_acl_has_object_and_deny_lines():
    text = mod.render_acl(["1.2.3.4", "5.6.7.8"])
    assert text.splitlines()[0] == "[innova-ban]"
    assert "deny=1.2.3.4/32" in text
    assert "deny=5.6.7.8/32" in text


def test_hash_ips_is_order_independent_and_stable():
    assert mod.hash_ips(["b", "a"]) == mod.hash_ips(["a", "b"])
    assert mod.hash_ips(["a"]) != mod.hash_ips(["a", "b"])


def test_write_acl_file_calls_atomic_write(monkeypatch):
    calls = []
    monkeypatch.setattr(mod, "atomic_write", lambda *a, **kw: calls.append((a, kw)))
    mod.write_acl_file(["9.9.9.9"])
    assert len(calls) == 1
    (directory, filename, text), kw = calls[0]
    assert filename == mod.settings.sip_acl_filename
    assert "deny=9.9.9.9/32" in text
    assert kw["tmp_prefix"] == ".tmp-sip-acl-"


class _FakeAmi:
    def __init__(self, *, response="Success", raise_connect=False):
        self.response = response
        self.raise_connect = raise_connect
        self.commands = []

    async def ensure_connected(self):
        if self.raise_connect:
            raise ConnectionError("AMI yo'q")

    async def action(self, _action, **kw):
        self.commands.append(kw.get("Command"))
        return {"Response": self.response, "Message": "xato" if self.response != "Success" else None}


@pytest.mark.asyncio
async def test_apply_acl_ips_success(monkeypatch):
    monkeypatch.setattr(mod, "write_acl_file", lambda ips: None)
    ami = _FakeAmi()
    result = await mod.apply_acl_ips(["1.1.1.1"], ami)
    assert result.status == "applied" and result.message is None
    assert ami.commands == ["module reload res_pjsip.so"]


@pytest.mark.asyncio
async def test_apply_acl_ips_ami_connect_failure(monkeypatch):
    monkeypatch.setattr(mod, "write_acl_file", lambda ips: None)
    ami = _FakeAmi(raise_connect=True)
    result = await mod.apply_acl_ips([], ami)
    assert result.status == "failed"
    assert "AMI yo'q" in result.message


@pytest.mark.asyncio
async def test_apply_acl_ips_ami_rejects_reload(monkeypatch):
    monkeypatch.setattr(mod, "write_acl_file", lambda ips: None)
    ami = _FakeAmi(response="Error")
    result = await mod.apply_acl_ips([], ami)
    assert result.status == "failed" and "xato" in result.message


def test_apply_result_to_dict_shape():
    result = mod.AclApplyResult(status="applied", message=None)
    assert result.to_dict() == {"status": "applied", "revision": None, "message": None}


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return SimpleNamespace(all=lambda: self._rows)


class _Session:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _stmt):
        return _Result(self.rows)


@pytest.mark.asyncio
async def test_active_banned_ips_sorted_and_stringified():
    session = _Session(["2.2.2.2", "1.1.1.1"])
    ips = await mod.active_banned_ips(session)
    assert ips == ["2.2.2.2", "1.1.1.1"]  # tartib -- SQL `order_by` (soxta sessiya qayta tartiblamaydi)


@pytest.mark.asyncio
async def test_apply_acl_reads_active_bans_then_applies(monkeypatch):
    session = _Session(["3.3.3.3"])
    monkeypatch.setattr(mod, "write_acl_file", lambda ips: None)
    ami = _FakeAmi()
    result = await mod.apply_acl(session, ami)
    assert result.status == "applied"
