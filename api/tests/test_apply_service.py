"""`app/services/apply.py` uchun izolyatsiyalangan (DB/AMI'siz) birlik testlari.

Bu ikki funksiya shu sessiyada topilgan ikki haqiqiy xatoni tuzatadi:
  1. `write_dialplan_file` — fayl ruxsati (0600 -> 0644), Asterisk boshqa
     foydalanuvchi (uid 1000) sifatida o'qiy olishi uchun.
  2. `_reload_and_verify` — Asterisk 22'ning HAQIQIY "kontekst topilmadi"
     ibora bilan moslashtirish ("There is no existence of ...", "No such
     context" EMAS).
Mutator shu testlar ustida ishlatiladi — regressiyani ushlab turish uchun."""
from __future__ import annotations

import stat

import pytest

from app.services import apply as apply_module


def test_write_dialplan_file_creates_world_readable_file(tmp_path, monkeypatch):
    monkeypatch.setattr(apply_module.settings, "dialplan_dir", str(tmp_path))
    monkeypatch.setattr(apply_module.settings, "dialplan_filename", "extensions_innova.conf")

    apply_module.write_dialplan_file("; test kontent\n")

    target = tmp_path / "extensions_innova.conf"
    assert target.read_text() == "; test kontent\n"
    mode = stat.S_IMODE(target.stat().st_mode)
    # Asterisk konteyneri boshqa UID (asterisk, 1000) bilan ishlaydi — fayl
    # kamida "boshqalar o'qiy oladi" bo'lishi SHART (0600 bilan EMAS).
    assert mode & stat.S_IROTH, f"fayl dunyoga o'qish uchun ochiq emas: {oct(mode)}"


def test_write_dialplan_file_overwrites_atomically(tmp_path, monkeypatch):
    monkeypatch.setattr(apply_module.settings, "dialplan_dir", str(tmp_path))
    monkeypatch.setattr(apply_module.settings, "dialplan_filename", "extensions_innova.conf")

    apply_module.write_dialplan_file("eski\n")
    apply_module.write_dialplan_file("yangi\n")

    target = tmp_path / "extensions_innova.conf"
    assert target.read_text() == "yangi\n"
    # Vaqtinchalik `.tmp-dialplan-*` fayllar qolmasligi kerak.
    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".tmp-dialplan-")]
    assert leftovers == []


class _FakeAmi:
    def __init__(self, reload_response: dict, show_output: str) -> None:
        self._reload_response = reload_response
        self._show_output = show_output
        self.connected = False

    async def ensure_connected(self) -> None:
        self.connected = True

    async def action(self, action: str, **fields: object) -> dict:
        command = str(fields.get("Command", ""))
        if command == "dialplan reload":
            return self._reload_response
        return {"Response": "Success", "Output": self._show_output}


@pytest.mark.parametrize("missing_output", [
    "There is no existence of 't1-from-trunk' context",  # Asterisk 22 haqiqiy ibora
    "No such context",  # eski/boshqa versiya iborasi — ikkisi ham tutilsin
    "",  # bo'sh javob — kontekst umuman yuklanmagan
    "   ",
])
async def test_reload_and_verify_raises_when_context_missing(missing_output):
    ami = _FakeAmi(reload_response={"Response": "Success"}, show_output=missing_output)
    with pytest.raises(RuntimeError, match="tekshiruv muvaffaqiyatsiz"):
        await apply_module._reload_and_verify(ami, "t1")


async def test_reload_and_verify_passes_when_context_present():
    ami = _FakeAmi(
        reload_response={"Response": "Success"},
        show_output="[ t1-from-trunk ]\n  712 => ...\n",
    )
    await apply_module._reload_and_verify(ami, "t1")  # ko'tarilmasa — PASS


async def test_reload_and_verify_raises_when_reload_rejected():
    ami = _FakeAmi(reload_response={"Response": "Error", "Message": "boom"}, show_output="irrelevant")
    with pytest.raises(RuntimeError, match="dialplan reload rad etildi"):
        await apply_module._reload_and_verify(ami, "t1")
