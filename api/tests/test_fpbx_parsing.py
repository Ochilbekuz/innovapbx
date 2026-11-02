"""M5a — sof tahlil qatlami (`app/services/fpbx/`): TSV/astdb/voicemail.conf/manzil
hal qiluvchi + xavfsiz tar ochish. Haqiqiy tuzilma (`tests/freepbx-fixture/bundle/...`)
BUZILMAYDI — faqat o'qiladi (vaqtinchalik papkaga ochiladi)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.services.fpbx import astdb, bundle, dest, tsv, vmconf

FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "freepbx-fixture" / "bundle" / "fpbx-export-fixture.tar.gz"


@pytest.fixture(scope="module")
def extracted(tmp_path_factory) -> Path:
    dest_dir = tmp_path_factory.mktemp("fpbx-bundle")
    bundle.extract_bundle(FIXTURE, dest_dir, max_total_bytes=20 * 1024 * 1024 * 1024)
    return bundle.find_bundle_root(dest_dir)


def test_extract_reads_meta(extracted: Path) -> None:
    meta = bundle.read_meta(extracted)
    assert meta["format"] == "INNOVA-FPBX-EXPORT/1"
    assert "users" in meta["tables"]


def test_extracted_files_are_locked_down(extracted: Path) -> None:
    assert (oct(extracted.stat().st_mode)[-3:]) == "700"
    a_file = next(p for p in extracted.rglob("*") if p.is_file())
    assert oct(a_file.stat().st_mode)[-3:] == "600"


def test_traversal_member_rejected(tmp_path: Path) -> None:
    import tarfile

    evil_tar = tmp_path / "evil.tar.gz"
    with tarfile.open(evil_tar, "w:gz") as tar:
        info = tarfile.TarInfo(name="fpbx-export-x/../../../tmp/m5a-pwned")
        data = b"pwned"
        info.size = len(data)
        import io
        tar.addfile(info, io.BytesIO(data))
    with pytest.raises(bundle.BundleInvalidError):
        bundle.extract_bundle(evil_tar, tmp_path / "out", max_total_bytes=10_000_000)
    assert not (tmp_path / "tmp" / "m5a-pwned").exists()
    assert not Path("/tmp/m5a-pwned").exists()


def test_tsv_null_token_becomes_none() -> None:
    rows = tsv.parse_tsv("a\tb\nx\tNULL\ny\tNULL-ish\n")
    assert rows[0] == {"a": "x", "b": None}
    assert rows[1] == {"a": "y", "b": "NULL-ish"}


def test_tsv_escapes() -> None:
    rows = tsv.parse_tsv("a\nline1\\nline2\\tcol\\\\end\n")
    assert rows[0]["a"] == "line1\nline2\tcol\\end"


def test_tsv_real_users_table(extracted: Path) -> None:
    rows = tsv.parse_tsv_file(extracted / "tables" / "users.tsv")
    assert len(rows) == 6
    ext101 = next(r for r in rows if r["extension"] == "101")
    assert ext101["voicemail"] == "novm"


def test_tsv_group_by_and_pivot_sip_eav(extracted: Path) -> None:
    rows = tsv.parse_tsv_file(extracted / "tables" / "sip.tsv")
    by_id = tsv.group_by(rows, "id")
    pivoted = tsv.pivot_first(by_id["101"])
    assert pivoted["secret"] == "SinovSecret101!"
    assert pivoted["allow"] == "ulaw,alaw,g722"


def test_astdb_family_and_top_level(extracted: Path) -> None:
    flat = astdb.parse_astdb_file(extracted / "astdb" / "astdb.txt")
    fam = astdb.family(flat, "AMPUSER/101")
    assert fam["device"] == "101"
    cf = astdb.top_level(flat, "CF")
    assert cf["102"] == "106"


def test_voicemail_conf_default_section(extracted: Path) -> None:
    boxes = vmconf.parse_voicemail_conf_file(extracted / "conf" / "voicemail.conf")
    assert boxes["105"]["pin"] == "1105"
    assert boxes["105"]["options"]["attach"] == "no"
    assert boxes["1234"]["pin"] == "4242"


@pytest.mark.parametrize(
    "raw, expected_kind, expected_ref",
    [
        ("ext-local,101,1", "extension", "101"),
        ("ext-group,601,1", "ring_group", "601"),
        ("ext-queues,700,1", "queue", "700"),
        ("ivr-5,s,1", "ivr", "5"),
        ("timeconditions,3,1", "time_condition", "3"),
        ("app-announcement-9,s,1", "announcement", "9"),
        ("ext-meetme,8000,1", "conference", "8000"),
        ("ext-conference,8000,1", "conference", "8000"),
        ("ext-findmefollow,FM107,1", "extension", "107"),
        ("app-blackhole,hangup,1", "hangup", None),
        ("app-blackhole,busy,1", "busy", None),
    ],
)
def test_resolve_dest_grammar(raw, expected_kind, expected_ref) -> None:
    catalog = dest.DestCatalog()
    result = dest.resolve_dest(raw, catalog)
    assert result.kind == expected_kind
    assert result.ref == expected_ref


def test_resolve_dest_blackhole_ring_is_unsupported_with_warning() -> None:
    result = dest.resolve_dest("app-blackhole,ring,1", dest.DestCatalog())
    assert result.kind == "hangup"
    assert result.warning is not None
    assert result.warning[0] == "blackhole_unsupported"


def test_resolve_dest_voicemail_prefix_found_vs_missing() -> None:
    catalog = dest.DestCatalog(voicemail_boxes=frozenset({"105"}))
    found = dest.resolve_dest("ext-local,vmu105,1", catalog)
    assert found.kind == "voicemail" and found.ref == "105"
    missing = dest.resolve_dest("ext-local,vmu999,1", catalog)
    assert missing.kind == "extension" and missing.ref == "999"
    assert missing.warning[0] == "voicemail_missing"


def test_resolve_dest_unknown_falls_back_to_hangup_with_warning() -> None:
    result = dest.resolve_dest("some-unknown-context,1,1", dest.DestCatalog())
    assert result.kind == "hangup"
    assert result.warning[0] == "dest_unsupported"


def test_resolve_dest_empty_is_none() -> None:
    assert dest.resolve_dest("", dest.DestCatalog()) is None
    assert dest.resolve_dest(None, dest.DestCatalog()) is None
