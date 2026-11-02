"""`app/services/moh.py` — sof funksiyalar (build_musiconhold_conf,
asterisk_class_name) va disk sinxronizatsiyasi (DB/AMI'siz, izolyatsiyalangan)
m1b-contract.md bo'lim 8 uchun."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import moh as moh_module
from app.services.moh import (
    MohClassSnapshot,
    MohFileSnapshot,
    asterisk_class_name,
    build_musiconhold_conf,
    moh_class_dir,
    remove_moh_class_dir,
    sync_moh_class_files,
)


class _FakeAmi:
    """`test_apply_service.py::_FakeAmi` BILAN BIR XIL qolip (DRY niyati —
    ikkisi turli modulni sinaydi, shu sabab mustaqil nusxa qoldirildi, lekin
    shakli bir xil bo'lsin)."""

    def __init__(self, reload_response: dict, show_output: str) -> None:
        self._reload_response = reload_response
        self._show_output = show_output

    async def ensure_connected(self) -> None:
        pass

    async def action(self, action: str, **fields: object) -> dict:
        command = str(fields.get("Command", ""))
        if command == "moh reload":
            return self._reload_response
        return {"Response": "Success", "Output": self._show_output}


def test_asterisk_class_name_is_tenant_and_id_scoped():
    """Ikki xil tenant bir xil nomli (yoki ID'li) sinfga ega bo'lsa ham
    Asterisk'dagi nom to'qnashmasligi kerak — tenant kodi prefiks."""
    assert asterisk_class_name("t1", "abc") == "t1-moh-abc"
    assert asterisk_class_name("t2", "abc") != asterisk_class_name("t1", "abc")


def test_build_musiconhold_conf_renders_mode_files_and_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(moh_module.settings, "sounds_dir", str(tmp_path))
    moh = MohClassSnapshot(id="m1", shuffle=False, files=(MohFileSnapshot(audio_file_id="a1", position=0),))

    text = build_musiconhold_conf("t1", [moh])

    assert "[t1-moh-m1]" in text
    assert "mode=files" in text
    assert f"directory={moh_class_dir('t1', 'm1')}" in text
    assert "sort=random" not in text


def test_build_musiconhold_conf_shuffle_adds_sort_random():
    moh = MohClassSnapshot(id="m1", shuffle=True, files=())
    text = build_musiconhold_conf("t1", [moh])
    assert "sort=random" in text


def test_build_musiconhold_conf_empty_classes_still_valid_header():
    text = build_musiconhold_conf("t1", [])
    assert text.strip().startswith(";")


def test_sync_moh_class_files_creates_ordered_symlinks(tmp_path, monkeypatch):
    monkeypatch.setattr(moh_module.settings, "sounds_dir", str(tmp_path))
    (tmp_path / "t1").mkdir()
    (tmp_path / "t1" / "a1.wav").write_bytes(b"RIFF....")
    (tmp_path / "t1" / "a2.wav").write_bytes(b"RIFF....")
    moh = MohClassSnapshot(id="m1", shuffle=False, files=(
        MohFileSnapshot(audio_file_id="a1", position=0),
        MohFileSnapshot(audio_file_id="a2", position=1),
    ))

    sync_moh_class_files("t1", moh)

    directory = moh_class_dir("t1", "m1")
    names = sorted(p.name for p in directory.iterdir())
    assert names == ["0000_a1.wav", "0001_a2.wav"]
    assert (directory / "0000_a1.wav").resolve() == (tmp_path / "t1" / "a1.wav").resolve()


def test_sync_moh_class_files_removes_stale_links(tmp_path, monkeypatch):
    monkeypatch.setattr(moh_module.settings, "sounds_dir", str(tmp_path))
    (tmp_path / "t1").mkdir()
    (tmp_path / "t1" / "a1.wav").write_bytes(b"x")
    moh = MohClassSnapshot(id="m1", shuffle=False, files=(MohFileSnapshot(audio_file_id="a1", position=0),))
    sync_moh_class_files("t1", moh)

    empty_moh = MohClassSnapshot(id="m1", shuffle=False, files=())
    sync_moh_class_files("t1", empty_moh)

    assert list(moh_class_dir("t1", "m1").iterdir()) == []


def test_sync_moh_class_files_is_idempotent_no_unnecessary_rewrite(tmp_path, monkeypatch):
    """Ikkinchi marta bir xil ro'yxat bilan chaqirilsa havolalarni qayta
    yaratmasligi kerak (symlink target o'zgarmagan bo'lsa tegilmaydi)."""
    monkeypatch.setattr(moh_module.settings, "sounds_dir", str(tmp_path))
    (tmp_path / "t1").mkdir()
    (tmp_path / "t1" / "a1.wav").write_bytes(b"x")
    moh = MohClassSnapshot(id="m1", shuffle=False, files=(MohFileSnapshot(audio_file_id="a1", position=0),))
    sync_moh_class_files("t1", moh)
    link = moh_class_dir("t1", "m1") / "0000_a1.wav"
    before = link.lstat().st_ino

    sync_moh_class_files("t1", moh)

    assert link.lstat().st_ino == before


def test_remove_moh_class_dir_deletes_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(moh_module.settings, "sounds_dir", str(tmp_path))
    directory = moh_class_dir("t1", "m1")
    directory.mkdir(parents=True)
    (directory / "leftover.wav").write_bytes(b"x")

    remove_moh_class_dir("t1", "m1")

    assert not directory.exists()


def test_remove_moh_class_dir_missing_directory_is_a_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(moh_module.settings, "sounds_dir", str(tmp_path))
    remove_moh_class_dir("t1", "does-not-exist")  # ko'tarilmasa — PASS


def _audio_on_disk(tmp_path, monkeypatch, *audio_ids: str) -> None:
    monkeypatch.setattr(moh_module.settings, "sounds_dir", str(tmp_path))
    (tmp_path / "t1").mkdir(exist_ok=True)
    for audio_id in audio_ids:
        (tmp_path / "t1" / f"{audio_id}.wav").write_bytes(b"RIFF")


async def test_reload_and_verify_moh_ignores_empty_classes_not_shown_by_asterisk():
    """Haqiqiy Asterisk xatosi (2026-10-28, m1b-proof.sh orqali topilgan):
    `res_musiconhold` 0 fayli bo'lgan sinfni `moh show classes`da UMUMAN
    ko'rsatmaydi (sinfni butunlay tashlab yuboradi) — bu Asterisk'ning
    hujjatlashtirilgan xatti-harakati, SINXRONIZATSIYA XATOSI emas. Tekshiruv
    faqat KAMIDA bitta faylga ega sinflarni talab qilishi SHART, aks holda
    har bo'sh MOH sinfi (CRUD shaklini sinash uchun atayin yaratiladigan,
    `file_ids: []`) 502 bilan yiqilardi."""
    empty = MohClassSnapshot(id="empty1", shuffle=False, files=())
    ami = _FakeAmi(reload_response={"Response": "Success"}, show_output="")
    await moh_module._reload_and_verify_moh(ami, "t1", [empty])  # ko'tarilmasa — PASS


async def test_reload_and_verify_moh_raises_when_nonempty_class_missing(tmp_path, monkeypatch):
    _audio_on_disk(tmp_path, monkeypatch, "a1")
    with_file = MohClassSnapshot(
        id="m1", shuffle=False, files=(MohFileSnapshot(audio_file_id="a1", position=0),),
    )
    ami = _FakeAmi(reload_response={"Response": "Success"}, show_output="")
    with pytest.raises(RuntimeError, match="tekshiruv muvaffaqiyatsiz"):
        await moh_module._reload_and_verify_moh(ami, "t1", [with_file])


async def test_reload_and_verify_moh_passes_when_nonempty_class_present(tmp_path, monkeypatch):
    _audio_on_disk(tmp_path, monkeypatch, "a1")
    with_file = MohClassSnapshot(
        id="m1", shuffle=False, files=(MohFileSnapshot(audio_file_id="a1", position=0),),
    )
    ami = _FakeAmi(reload_response={"Response": "Success"}, show_output="Class: t1-moh-m1\n")
    await moh_module._reload_and_verify_moh(ami, "t1", [with_file])  # ko'tarilmasa — PASS


@pytest.mark.parametrize("on_disk", [(), ("other",)])
async def test_reload_and_verify_moh_skips_class_whose_audio_vanished_from_disk(tmp_path, monkeypatch, caplog, on_disk):
    """m4b-proof.sh (2026-10-29): wav diskdan yo'qolgan (DB'da fayl bor) holat
    zaxirasidan tiklash `failed` bo'lardi — Asterisk bunday sinfni ham
    ko'rsatmaydi. Endi bu ogohlantirish, xato emas."""
    _audio_on_disk(tmp_path, monkeypatch, *on_disk)
    lost = MohClassSnapshot(id="m1", shuffle=False, files=(MohFileSnapshot(audio_file_id="a1", position=0),))
    ami = _FakeAmi(reload_response={"Response": "Success"}, show_output="")
    with caplog.at_level("WARNING", logger=moh_module.__name__):
        await moh_module._reload_and_verify_moh(ami, "t1", [lost])  # ko'tarilmasa — PASS
    assert "MOH sinf m1: DB'dagi 1 fayldan birortasi diskda yo'q" in caplog.text


async def test_reload_and_verify_moh_requires_class_with_any_playable_file(tmp_path, monkeypatch, caplog):
    _audio_on_disk(tmp_path, monkeypatch, "a2")
    partial = MohClassSnapshot(id="m1", shuffle=False, files=(
        MohFileSnapshot(audio_file_id="a1", position=0), MohFileSnapshot(audio_file_id="a2", position=1),
    ))
    ami = _FakeAmi(reload_response={"Response": "Success"}, show_output="")
    with caplog.at_level("WARNING", logger=moh_module.__name__), pytest.raises(RuntimeError, match=r"ko'rinmadi: \['m1'\]"):
        await moh_module._reload_and_verify_moh(ami, "t1", [partial])
    assert "diskda yo'q" not in caplog.text


async def test_reload_and_verify_moh_raises_when_reload_rejected():
    ami = _FakeAmi(reload_response={"Response": "Error", "Message": "boom"}, show_output="irrelevant")
    with pytest.raises(RuntimeError, match="moh reload rad etildi"):
        await moh_module._reload_and_verify_moh(ami, "t1", [])
