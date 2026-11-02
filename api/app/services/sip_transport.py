"""SIP/RTP sozlamalarini Asterisk'ga yetkazish — m1b-contract.md bo'lim 4 (S32).

`system_settings` → ikki fayl umumiy `dialplan` hajmiga (`settings.dialplan_dir`):
`pjsip_transports_innova.conf` (pjsip.conf `#include` qiladi) va `rtp_innova.conf`
(rtp.conf `#include` qiladi). Restart qarori BITTA joyda — `needs_restart()`:
- RTP oralig'i — `module reload res_rtp_asterisk.so` bilan darhol (restart'siz);
- transport maydonlari (port, tashqi manzil, local_net) — PJSIP transportlarni
  reload qilmaydi (`allow_reload=false`), shuning uchun haqiqiy restart kerak
  (`POST /settings/sip/restart` → `core restart now`, jonli tasdiqlangan
  2026-10-28: Asterisk PID 1 da o'zini qayta exec qiladi, konteyner qoladi).
TLS (m1c-contract.md bo'lim 3, S32 davomi): `sip_tls_port` BOR va diskda
sertifikat BOR bo'lsa `transport-tls` generatsiya qilinadi — ikkisi birga
bitta qarorda (`_tls_enabled`). DB qatori + diskdagi sertifikat holatini
BIRLASHTIRISH BITTA joyda — `current_sip_config()`.
WebRTC (m3a-contract.md §1): `transport-wss` DOIM generatsiya qilinadi — u o'z
portiga emas, Asterisk HTTP serveriga (`http.conf` 8088, `/ws`) ulanadi va ws/wss
ikkisini oladi; `local_net`/`external_*` UDP bilan bir xil. ICE uchun RTP'da
`icesupport=yes` (statik)."""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from app.core.config import settings
from app.db.models import SystemSettings
from app.services.ami import AmiError
from app.services.atomic_write import atomic_write
from app.services.live_status import run_command
from app.services.tenant_scope import only_tenant_id
from app.services.tls_cert import cert_path, key_path, read_cert_metadata

_RTP_STATIC = ("rtpchecksums=no", "icesupport=yes")
_RTP_RANGE_RE = re.compile(r"Port start:\s*(\d+).*?Port end:\s*(\d+)", re.DOTALL)


@dataclass(frozen=True)
class SipConfig:
    external_ip: str | None
    external_host: str | None
    local_nets: tuple[str, ...]
    sip_udp_port: int
    rtp_start: int
    rtp_end: int
    sip_tls_port: int | None = None
    # Diskdagi joriy sertifikat barmoq izi — bazada saqlanmaydi (`current_sip_config`
    # orqali to'ldiriladi). `None` — sertifikat yo'q YOKI TLS o'rnatilmagan.
    tls_cert_fingerprint: str | None = None

    @classmethod
    def from_row(cls, row, *, tls_fingerprint: str | None = None) -> "SipConfig":
        return cls(
            external_ip=str(row.external_ip) if row.external_ip else None,
            external_host=row.external_host or None,
            local_nets=tuple(str(n) for n in row.local_nets),
            sip_udp_port=row.sip_udp_port, rtp_start=row.rtp_start, rtp_end=row.rtp_end,
            sip_tls_port=row.sip_tls_port, tls_cert_fingerprint=tls_fingerprint,
        )

    @property
    def transport_key(self) -> tuple:
        return (self.external_ip, self.external_host, tuple(sorted(self.local_nets)), self.sip_udp_port,
                self.sip_tls_port, self.tls_cert_fingerprint)

    @property
    def public_address(self) -> str | None:
        return self.external_ip or self.external_host

    @property
    def tls_enabled(self) -> bool:
        """`sip_tls_port` BOR va diskda yaroqli sertifikat BOR — ikkisi birga
        (m1c-contract.md bo'lim 3). Portgina yoki sertifikatgina yetarli emas."""
        return self.sip_tls_port is not None and self.tls_cert_fingerprint is not None


def current_sip_config(row) -> SipConfig:
    """`SipConfig.from_row` (DB qatori) + diskdagi sertifikat holatini
    BIRLASHTIRADI — chaqiruvchilar (`auth.py` sehrgar, `settings.py`) FAQAT
    shu funksiyadan foydalansin, cherti holati qayerdan olinishi bitta joyda
    qolsin."""
    meta = read_cert_metadata()
    return SipConfig.from_row(row, tls_fingerprint=meta.fingerprint_sha256 if meta else None)


# Asterisk API hali hech narsa yozmaganda yuklaydigan holat — image'dagi
# `asterisk/etc-asterisk/*_innova.default.conf` (test bir xilligini majburlaydi).
# `sip_tls_port=5061` — `system_settings` ustun standarti bilan bir xil (ustun
# NOT NULL); sertifikat yo'q (`tls_cert_fingerprint=None`) bo'lgani uchun TLS
# baribir o'chiq — port qiymati o'zi `needs_restart`ni yolg'on ishga tushirmasin.
BOOT_DEFAULT = SipConfig(external_ip=None, external_host=None,
                         local_nets=("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"),
                         sip_udp_port=5060, rtp_start=10000, rtp_end=20000, sip_tls_port=5061)


def needs_restart(old: SipConfig, new: SipConfig) -> bool:
    """PJSIP transportlari reload bo'lmaydi — ularning maydoni (TLS port/sertifikat
    ham) o'zgarsa restart shart."""
    return old.transport_key != new.transport_key


def _transport_section(name: str, protocol: str, bind_port: int | None, cfg: SipConfig, *,
                       extra: tuple[str, ...] = ()) -> list[str]:
    """`bind_port=None` — o'z porti yo'q transport (ws/wss: Asterisk HTTP serveri porti)."""
    bind = "0.0.0.0" if bind_port is None else f"0.0.0.0:{bind_port}"
    lines = [f"[{name}]", "type = transport", f"protocol = {protocol}", f"bind = {bind}"]
    lines += list(extra)
    lines += [f"local_net = {net}" for net in cfg.local_nets]
    if cfg.public_address:
        lines += [f"external_media_address = {cfg.public_address}",
                  f"external_signaling_address = {cfg.public_address}"]
    return lines + [""]


def _tls_transport_section(cfg: SipConfig) -> list[str]:
    extra = (f"cert_file = {cert_path()}", f"priv_key_file = {key_path()}", "method = tlsv1_2")
    return _transport_section("transport-tls", "tls", cfg.sip_tls_port, cfg, extra=extra)


def build_transports_conf(cfg: SipConfig) -> str:
    lines = ["; Innova PBX — API generatsiya qiladi (app/services/sip_transport.py). Qo'lda tahrirlamang.", ""]
    lines += _transport_section("transport-udp", "udp", cfg.sip_udp_port, cfg)
    lines += _transport_section("transport-tcp", "tcp", cfg.sip_udp_port, cfg)
    if cfg.tls_enabled:
        lines += _tls_transport_section(cfg)
    lines += _transport_section("transport-wss", "wss", None, cfg)
    return "\n".join(lines)


def build_rtp_conf(cfg: SipConfig) -> str:
    lines = ["; Innova PBX — API generatsiya qiladi (app/services/sip_transport.py). Qo'lda tahrirlamang.",
             "[general]", f"rtpstart={cfg.rtp_start}", f"rtpend={cfg.rtp_end}", *_RTP_STATIC, ""]
    return "\n".join(lines)


async def sync_sip_files(session) -> bool:
    """Deploy paytida (`app/db/bootstrap.py`, `migrate` servisi — Asterisk'dan OLDIN) fayllarni
    DB'dan (yagona haqiqat manbai) qayta yozadi: generatorga qo'shilgan yangi bo'lim (M3a
    `transport-wss`) eski hajmdagi faylga ham tushadi. Idempotent; `restart_required`ga
    TEGMAYDI (Asterisk konteyneri qayta ishga tushmasligi mumkin). Setup'gacha — `False`."""
    tenant_id = await only_tenant_id(session)
    row = await session.get(SystemSettings, tenant_id) if tenant_id else None
    if row is None:
        return False
    write_sip_files(current_sip_config(row))
    return True


def write_sip_files(cfg: SipConfig) -> None:
    atomic_write(settings.dialplan_dir, settings.pjsip_transports_filename, build_transports_conf(cfg),
                 tmp_prefix=".tmp-pjsip-")
    atomic_write(settings.dialplan_dir, settings.rtp_filename, build_rtp_conf(cfg), tmp_prefix=".tmp-rtp-")


async def _command(ami, command: str) -> str:
    resp = await ami.action("Command", Command=command)
    if str(resp.get("Response", "")).lower() != "success":
        raise RuntimeError(f"'{command}' rad etildi: {resp.get('Message', '')}")
    return resp.get("Output", "") or ""


async def _reload_and_verify_rtp(ami, cfg: SipConfig) -> None:
    await ami.ensure_connected()
    await _command(ami, "module reload res_rtp_asterisk.so")
    match = _RTP_RANGE_RE.search(await _command(ami, "rtp show settings"))
    shown = (int(match.group(1)), int(match.group(2))) if match else None
    if shown != (cfg.rtp_start, cfg.rtp_end):
        raise RuntimeError(f"RTP oralig'i qo'llanmadi: Asterisk {shown} ko'rsatmoqda")


async def apply_sip_config(ami, cfg: SipConfig, *, reload_rtp: bool) -> None:
    """Fayllarni yozadi (idempotent); `reload_rtp` bo'lsa RTP'ni darhol qo'llab tekshiradi."""
    write_sip_files(cfg)
    if reload_rtp:
        await _reload_and_verify_rtp(ami, cfg)


_UPTIME_RE = re.compile(r"System uptime:\s*(\d+)")


async def _uptime_s(ami) -> int | None:
    match = _UPTIME_RE.search(await run_command(ami, "core show uptime seconds") or "")
    return int(match.group(1)) if match else None


async def _send_restart(ami) -> None:
    try:
        await ami.ensure_connected()
        await ami.action("Command", Command="core restart now")
    except (AmiError, OSError, ConnectionError):
        pass  # Asterisk qayta exec bo'layotganda AMI ulanishi uziladi — kutilgan holat


async def _wait_until_restarted(ami, before: int | None, *, sleep, attempts: int, poll_s: float) -> None:
    for _ in range(attempts):
        await sleep(poll_s)
        uptime = await _uptime_s(ami)
        if uptime is not None and (before is None or uptime < before):
            return
    raise RuntimeError("Asterisk qayta ishga tushmadi (uptime nolga tushmadi)")


def _transport_matches(output: str, bind_port: int, cfg: SipConfig) -> bool:
    if f"0.0.0.0:{bind_port}" not in output:
        return False
    return cfg.public_address is None or cfg.public_address in output


async def _verify_transport(ami, name: str, bind_port: int, cfg: SipConfig) -> None:
    output = await run_command(ami, f"pjsip show transport {name}") or ""
    if not _transport_matches(output, bind_port, cfg):
        raise RuntimeError(f"Restartdan keyin {name} yangi sozlamalarni ko'rsatmadi")


async def restart_and_verify(ami, cfg: SipConfig, *, sleep=asyncio.sleep, attempts: int = 40,
                             poll_s: float = 1.0) -> None:
    """Fayllarni bazadan qayta yozadi (apply=false dan keyin ham to'g'ri), `core restart now`,
    Asterisk qaytishini kutadi va yangi transport(lar) haqiqatan yuklanganini tekshiradi
    (`transport-tls` — faqat TLS yoqilgan bo'lsa)."""
    before = await _uptime_s(ami)
    write_sip_files(cfg)
    await _send_restart(ami)
    await _wait_until_restarted(ami, before, sleep=sleep, attempts=attempts, poll_s=poll_s)
    await _verify_transport(ami, "transport-udp", cfg.sip_udp_port, cfg)
    if cfg.tls_enabled:
        await _verify_transport(ami, "transport-tls", cfg.sip_tls_port, cfg)
