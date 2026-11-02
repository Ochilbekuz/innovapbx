"""S32 — SIP/RTP sozlamalaridan Asterisk fayllarini generatsiya qilish
(m1b-contract.md bo'lim 4). Sof funksiyalar — Asterisk'siz."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.services import sip_transport
from app.services.sip_transport import (
    BOOT_DEFAULT,
    SipConfig,
    apply_sip_config,
    build_rtp_conf,
    build_transports_conf,
    needs_restart,
    restart_and_verify,
)

BASE = SipConfig(external_ip=None, external_host=None, local_nets=("10.0.0.0/8", "192.168.0.0/16"),
                 sip_udp_port=5060, rtp_start=10000, rtp_end=20000)


def _section(text: str, name: str) -> list[str]:
    lines = text.splitlines()
    start = lines.index(f"[{name}]")
    out = []
    for line in lines[start + 1:]:
        if line.startswith("["):
            break
        if line.strip() and not line.startswith(";"):
            out.append(line)
    return out


def test_transports_bind_udp_and_tcp_on_configured_port():
    conf = build_transports_conf(replace(BASE, sip_udp_port=5080))
    assert "bind = 0.0.0.0:5080" in _section(conf, "transport-udp")
    assert "bind = 0.0.0.0:5080" in _section(conf, "transport-tcp")
    assert "protocol = udp" in _section(conf, "transport-udp")
    assert "protocol = tcp" in _section(conf, "transport-tcp")


def test_transports_list_every_local_net_on_both_transports():
    conf = build_transports_conf(BASE)
    for name in ("transport-udp", "transport-tcp"):
        section = _section(conf, name)
        assert "local_net = 10.0.0.0/8" in section
        assert "local_net = 192.168.0.0/16" in section


def test_transports_without_external_address_have_no_nat_lines():
    conf = build_transports_conf(BASE)
    assert "external_" not in conf


def test_transports_external_ip_sets_media_and_signaling_address():
    section = _section(build_transports_conf(replace(BASE, external_ip="203.0.113.7")), "transport-udp")
    assert "external_media_address = 203.0.113.7" in section
    assert "external_signaling_address = 203.0.113.7" in section


def test_transports_external_host_used_when_no_ip():
    section = _section(build_transports_conf(replace(BASE, external_host="pbx.example.uz")), "transport-udp")
    assert "external_signaling_address = pbx.example.uz" in section
    assert "external_media_address = pbx.example.uz" in section


def test_transports_external_ip_wins_over_host():
    section = _section(build_transports_conf(
        replace(BASE, external_ip="203.0.113.7", external_host="pbx.example.uz")), "transport-udp")
    assert "external_signaling_address = 203.0.113.7" in section
    assert "pbx.example.uz" not in "\n".join(section)


def test_rtp_conf_has_range_and_keeps_static_options():
    section = _section(build_rtp_conf(replace(BASE, rtp_start=12000, rtp_end=12999)), "general")
    # M3a §1: WebRTC (ICE) uchun `icesupport=yes` — doimiy.
    assert section == ["rtpstart=12000", "rtpend=12999", "rtpchecksums=no", "icesupport=yes"]


def test_no_restart_when_equal():
    assert needs_restart(BASE, BASE) is False


def test_no_restart_for_rtp_range():
    assert needs_restart(BASE, replace(BASE, rtp_start=11000, rtp_end=15000)) is False


@pytest.mark.parametrize("changes", [
    {"sip_udp_port": 5080}, {"external_ip": "203.0.113.7"}, {"external_host": "pbx.example.uz"},
    {"local_nets": ("10.0.0.0/8",)}, {"sip_udp_port": 5080, "rtp_end": 15000},
])
def test_restart_for_transport_fields(changes):
    assert needs_restart(BASE, replace(BASE, **changes)) is True


class FakeAmi:
    def __init__(self, outputs: dict[str, str]):
        self.outputs = outputs
        self.commands: list[str] = []

    async def ensure_connected(self) -> None:
        return None

    async def action(self, action: str, **fields):
        self.commands.append(fields["Command"])
        return {"Response": "Success", "Output": self.outputs.get(fields["Command"], "")}


@pytest.fixture
def conf_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(sip_transport.settings, "dialplan_dir", str(tmp_path))
    return tmp_path


async def test_apply_writes_both_files(conf_dir):
    ami = FakeAmi({"rtp show settings": "Port start: 10000\nPort end: 20000"})
    await apply_sip_config(ami, BASE, reload_rtp=True)
    assert (conf_dir / sip_transport.settings.pjsip_transports_filename).read_text() == build_transports_conf(BASE)
    assert (conf_dir / sip_transport.settings.rtp_filename).read_text() == build_rtp_conf(BASE)


async def test_apply_reload_rtp_reloads_module_and_verifies(conf_dir):
    cfg = replace(BASE, rtp_start=12000, rtp_end=12999)
    ami = FakeAmi({"rtp show settings": "  Port start:      12000\n  Port end:        12999\n"})
    await apply_sip_config(ami, cfg, reload_rtp=True)
    assert ami.commands == ["module reload res_rtp_asterisk.so", "rtp show settings"]


async def test_apply_reload_rtp_raises_when_asterisk_shows_old_range(conf_dir):
    ami = FakeAmi({"rtp show settings": "  Port start:      10000\n  Port end:        20000\n"})
    with pytest.raises(RuntimeError, match="RTP"):
        await apply_sip_config(ami, replace(BASE, rtp_start=12000, rtp_end=12999), reload_rtp=True)


async def test_apply_without_reload_only_writes_files(conf_dir):
    ami = FakeAmi({})
    await apply_sip_config(ami, BASE, reload_rtp=False)
    assert ami.commands == []
    assert (conf_dir / sip_transport.settings.rtp_filename).exists()


class RestartingAmi:
    """`core restart now` dan keyin uptime nolga tushadigan soxta Asterisk."""

    def __init__(self, transport_output: str, *, restarts: bool = True, tls_transport_output: str = ""):
        self.uptime = 500
        self.restarts = restarts
        self.transport_output = transport_output
        self.tls_transport_output = tls_transport_output
        self.commands: list[str] = []

    async def ensure_connected(self) -> None:
        return None

    async def action(self, action: str, **fields):
        cmd = fields["Command"]
        self.commands.append(cmd)
        if cmd == "core restart now":
            if self.restarts:
                self.uptime = 1
            raise ConnectionError("AMI ulanishi uzildi")
        if cmd == "core show uptime seconds":
            return {"Response": "Success", "Output": f"System uptime: {self.uptime}\n"}
        if cmd == "pjsip show transport transport-udp":
            return {"Response": "Success", "Output": self.transport_output}
        if cmd == "pjsip show transport transport-tls":
            return {"Response": "Success", "Output": self.tls_transport_output}
        return {"Response": "Success", "Output": ""}


async def _no_sleep(_s: float) -> None:
    return None


async def test_restart_writes_files_restarts_and_verifies_transport(conf_dir):
    cfg = replace(BASE, external_ip="203.0.113.7")
    ami = RestartingAmi(" bind : 0.0.0.0:5060\n external_signaling_address : 203.0.113.7\n")
    await restart_and_verify(ami, cfg, sleep=_no_sleep)
    assert "core restart now" in ami.commands
    assert ami.commands[-1] == "pjsip show transport transport-udp"
    assert (conf_dir / sip_transport.settings.pjsip_transports_filename).read_text() == build_transports_conf(cfg)


async def test_restart_times_out_when_uptime_never_resets(conf_dir):
    ami = RestartingAmi(" bind : 0.0.0.0:5060\n", restarts=False)
    with pytest.raises(RuntimeError, match="qayta ishga tushmadi"):
        await restart_and_verify(ami, BASE, sleep=_no_sleep, attempts=3)


async def test_restart_fails_when_transport_lacks_new_port(conf_dir):
    ami = RestartingAmi(" bind : 0.0.0.0:5060\n")
    with pytest.raises(RuntimeError, match="transport"):
        await restart_and_verify(ami, replace(BASE, sip_udp_port=5080), sleep=_no_sleep)


async def test_restart_fails_when_transport_lacks_external_address(conf_dir):
    ami = RestartingAmi(" bind : 0.0.0.0:5060\n external_signaling_address : \n")
    with pytest.raises(RuntimeError, match="transport"):
        await restart_and_verify(ami, replace(BASE, external_ip="203.0.113.7"), sleep=_no_sleep)


async def test_restart_verifies_transport_tls_when_enabled(conf_dir):
    cfg = replace(BASE, sip_tls_port=5061, tls_cert_fingerprint="cd" * 32)
    ami = RestartingAmi(" bind : 0.0.0.0:5060\n", tls_transport_output=" bind : 0.0.0.0:5061\n")
    await restart_and_verify(ami, cfg, sleep=_no_sleep)
    assert ami.commands[-1] == "pjsip show transport transport-tls"


async def test_restart_fails_when_transport_tls_lacks_new_port(conf_dir):
    cfg = replace(BASE, sip_tls_port=5061, tls_cert_fingerprint="cd" * 32)
    ami = RestartingAmi(" bind : 0.0.0.0:5060\n", tls_transport_output=" bind : 0.0.0.0:9999\n")
    with pytest.raises(RuntimeError, match="transport-tls"):
        await restart_and_verify(ami, cfg, sleep=_no_sleep)


async def test_restart_skips_transport_tls_check_when_disabled(conf_dir):
    ami = RestartingAmi(" bind : 0.0.0.0:5060\n")
    await restart_and_verify(ami, BASE, sleep=_no_sleep)
    assert "pjsip show transport transport-tls" not in ami.commands


ETC = Path(__file__).resolve().parents[2] / "asterisk" / "etc-asterisk"


def test_boot_default_files_match_generator():
    """Asterisk birinchi ishga tushishda (API hali yozmagan) image'dagi standart fayllarni
    oladi — ular `BOOT_DEFAULT` generatsiyasi bilan AYNAN bir xil bo'lishi shart, aks holda
    `restart_required` hisobi yolg'on chiqadi."""
    assert (ETC / "pjsip_transports_innova.default.conf").read_text() == build_transports_conf(BOOT_DEFAULT)
    assert (ETC / "rtp_innova.default.conf").read_text() == build_rtp_conf(BOOT_DEFAULT)


def test_local_net_order_does_not_require_restart():
    assert needs_restart(BASE, replace(BASE, local_nets=tuple(reversed(BASE.local_nets)))) is False


def test_from_row_converts_db_types_to_strings():
    """asyncpg INET/CIDR obyekt qaytaradi — generatsiya va solishtirish uchun str bo'lishi shart."""
    from ipaddress import ip_address, ip_network
    from types import SimpleNamespace
    row = SimpleNamespace(external_ip=ip_address("203.0.113.7"), external_host="",
                          local_nets=[ip_network("10.0.0.0/8")], sip_udp_port=5060, rtp_start=10000, rtp_end=20000,
                          sip_tls_port=None)
    assert SipConfig.from_row(row) == replace(BASE, external_ip="203.0.113.7", local_nets=("10.0.0.0/8",))
    assert SipConfig.from_row(SimpleNamespace(**{**vars(row), "external_ip": None})).external_ip is None


def test_from_row_passes_through_tls_port_and_fingerprint():
    from types import SimpleNamespace
    row = SimpleNamespace(external_ip=None, external_host=None, local_nets=[], sip_udp_port=5060,
                          rtp_start=10000, rtp_end=20000, sip_tls_port=5061)
    cfg = SipConfig.from_row(row, tls_fingerprint="ab" * 32)
    assert cfg.sip_tls_port == 5061
    assert cfg.tls_cert_fingerprint == "ab" * 32


# ======================================================== TLS (m1c-contract.md bo'lim 3)
TLS_BASE = replace(BASE, sip_tls_port=5061, tls_cert_fingerprint="cd" * 32)


def test_tls_disabled_when_no_fingerprint():
    assert replace(BASE, sip_tls_port=5061).tls_enabled is False


def test_tls_disabled_when_no_port():
    assert replace(BASE, tls_cert_fingerprint="cd" * 32).tls_enabled is False


def test_tls_enabled_when_port_and_fingerprint_present():
    assert TLS_BASE.tls_enabled is True


def test_transports_conf_has_no_tls_section_when_disabled():
    conf = build_transports_conf(BASE)
    assert "[transport-tls]" not in conf


def test_transports_conf_tls_section_binds_configured_port():
    conf = build_transports_conf(TLS_BASE)
    section = _section(conf, "transport-tls")
    assert "bind = 0.0.0.0:5061" in section
    assert "protocol = tls" in section
    assert "method = tlsv1_2" in section


def test_transports_conf_tls_section_references_cert_and_key_paths():
    from app.services.tls_cert import cert_path, key_path
    section = _section(build_transports_conf(TLS_BASE), "transport-tls")
    assert f"cert_file = {cert_path()}" in section
    assert f"priv_key_file = {key_path()}" in section


def test_transports_conf_tls_section_shares_local_nets_and_external_address_with_udp():
    cfg = replace(TLS_BASE, external_ip="203.0.113.7")
    conf = build_transports_conf(cfg)
    udp_section, tls_section = _section(conf, "transport-udp"), _section(conf, "transport-tls")
    udp_nets = [line for line in udp_section if line.startswith("local_net")]
    tls_nets = [line for line in tls_section if line.startswith("local_net")]
    assert udp_nets == tls_nets
    assert "external_signaling_address = 203.0.113.7" in tls_section
    assert "external_media_address = 203.0.113.7" in tls_section


def test_restart_for_tls_port_change():
    assert needs_restart(TLS_BASE, replace(TLS_BASE, sip_tls_port=5062)) is True


def test_restart_for_tls_certificate_change():
    assert needs_restart(TLS_BASE, replace(TLS_BASE, tls_cert_fingerprint="ef" * 32)) is True


def test_restart_for_enabling_tls():
    assert needs_restart(BASE, TLS_BASE) is True


# ---------------------------------------------------------------- M3a §1: transport-wss (WebRTC)
def test_transports_conf_always_has_wss_transport_on_http_server():
    """`protocol=wss` Asterisk HTTP serveriga (8088 `/ws`) ulanadi — ws va wss ikkisini oladi;
    bind porti yo'q (HTTP serverniki), TLS'dan qat'i nazar DOIM bor."""
    for cfg in (BASE, TLS_BASE):
        section = _section(build_transports_conf(cfg), "transport-wss")
        assert section[:3] == ["type = transport", "protocol = wss", "bind = 0.0.0.0"]


def test_transports_conf_wss_section_shares_local_nets_and_external_address_with_udp():
    conf = build_transports_conf(replace(BASE, external_host="pbx.example.uz"))
    udp_section, wss_section = _section(conf, "transport-udp"), _section(conf, "transport-wss")
    assert [ln for ln in wss_section if ln.startswith("local_net")] == \
        [ln for ln in udp_section if ln.startswith("local_net")]
    assert "external_media_address = pbx.example.uz" in wss_section
    assert "external_signaling_address = pbx.example.uz" in wss_section


# ---------------------------------------------------------------- M3a: deploy'da fayllarni DB'dan tiklash
class _SyncSession:
    def __init__(self, tenant_id, row):
        self._tenant_id, self._row = tenant_id, row

    async def execute(self, _stmt):
        from types import SimpleNamespace
        return SimpleNamespace(first=lambda: (self._tenant_id,) if self._tenant_id else None)

    async def get(self, _model, _pk):
        return self._row


def _settings_row(**kw):
    from types import SimpleNamespace
    base = dict(external_ip=None, external_host="pbx.example.uz", local_nets=["10.0.0.0/8"], sip_udp_port=5070,
                rtp_start=10000, rtp_end=20000, sip_tls_port=None)
    return SimpleNamespace(**{**base, **kw})


async def test_sync_sip_files_rewrites_from_db_so_upgrade_gets_wss(conf_dir, monkeypatch):
    """Eski hajmda (M3a'gacha yozilgan, wss'siz) fayl qolgan bo'lsa ham, deploy (migrate) DB'dan
    qayta yozadi — Asterisk birinchi ishga tushishdayoq `transport-wss`ni ko'radi."""
    monkeypatch.setattr(sip_transport, "read_cert_metadata", lambda: None)
    (conf_dir / sip_transport.settings.pjsip_transports_filename).write_text("[transport-udp]\n")
    assert await sip_transport.sync_sip_files(_SyncSession("t1", _settings_row())) is True
    text = (conf_dir / sip_transport.settings.pjsip_transports_filename).read_text()
    assert "[transport-wss]" in text and "bind = 0.0.0.0:5070" in text and "pbx.example.uz" in text


@pytest.mark.parametrize("tenant_id,row", [(None, None), ("t1", None)])
async def test_sync_sip_files_before_setup_leaves_image_default(conf_dir, tenant_id, row):
    assert await sip_transport.sync_sip_files(_SyncSession(tenant_id, row)) is False
    assert list(conf_dir.iterdir()) == []
