"""`netd` ni HAQIQIY `ifupdown` ustida sinovdan o'tkazadi — FAQAT
izolyatsiyalangan `debian:trixie` konteynerida (host tarmog'iga tegilmaydi,
`dummy` tipidagi `eth1` interfeysi ishlatiladi). `NETD_EXEC=local` +
`NETD_HOST_ROOT=/` orqali `nsenter`siz, konteyner ichidagi haqiqiy
`/etc/network/interfaces`/`ip`/`ifup`/`ifdown`ga yoziladi
(m8-network-contract.md bo'lim 1-2). Ishga tushirish:
`python3 netd_ifupdown_driver.py <a|b|c|d|e>` — har biri mustaqil stsenariy,
chaqiruvchi shell skript konteynerni har safar qayta boshlaydi (toza holat)."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

sys.path.insert(0, "/src")

from app.netd import dns as dns_mod  # noqa: E402
from app.netd.backend import INTERFACES_PATH  # noqa: E402
from app.netd.executor import Executor  # noqa: E402
from app.netd.service import NetdService  # noqa: E402
from app.netd.settings import NetdSettings  # noqa: E402

BASELINE = "auto lo\niface lo inet loopback\n\nauto eth1\niface eth1 inet dhcp\n"
SETTINGS = NetdSettings(readonly=False, exec_mode="local", host_root="/",
                         pending_path="/var/lib/innova/netd/pending.json")


def _write_baseline() -> None:
    with open(INTERFACES_PATH, "w") as f:
        f.write(BASELINE)


def _current_hostname() -> str:
    """Konfiguratsiyada hostname'ni JORIY qiymat bilan bir xil qo'yamiz —
    `/etc/hostname` Docker tomonidan bind-mount qilingan (konteynerning
    o'z boshqaruv fayli), shu sabab unga `os.replace()` orqali ustidan
    yozish `EBUSY` beradi (haqiqiy serverda bu oddiy fayl bo'lib, muammo
    bo'lmaydi — bu faqat test muhitining Docker-xos cheklovi, netd kodi
    o'zi emas). Interfeys/marshrut stsenariylari hostname'ga tegmaydi."""
    with open("/etc/hostname") as f:
        return f.read().strip()


def _current_dns() -> SimpleNamespace:
    """Xuddi `_current_hostname()` kabi — Dockerning o'z `/etc/resolv.conf`
    bind-mounti ustidan yozishga urinmaymiz (EBUSY); DNS'ga stsenariylar
    (a-e) tegmaydi, shu sabab joriy qiymat bilan bir xil qo'yamiz."""
    with open(dns_mod.RESOLV_PATH) as f:
        servers, search = dns_mod.parse_resolv_conf(f.read())
    return SimpleNamespace(servers=servers, search=search)


def _static_config(address="10.9.9.5/24", routes=(), timeout_s=60):
    return SimpleNamespace(
        hostname=_current_hostname(),
        interfaces=[SimpleNamespace(name="eth1", mode="static", address=address, gateway=None, mtu=None)],
        routes=list(routes), dns=_current_dns(), timeout_s=timeout_s,
    )


def _ok(label: str, condition: bool, detail: str = "") -> None:
    status = "OK" if condition else "FAIL"
    print(f"[{status}] {label} {detail}")
    if not condition:
        raise SystemExit(f"stsenariy muvaffaqiyatsiz: {label} {detail}")


async def scenario_a() -> None:
    """(a) dhcp -> static apply: `/etc/network/interfaces` yangilanadi,
    `ifdown --force eth1`/`ifup eth1` haqiqatan chaqiriladi, manzil
    konteyner ichida HAQIQATDA o'rnatiladi (`ip addr show eth1`)."""
    _write_baseline()
    service = NetdService(Executor("local", "/"), SETTINGS)
    state = await service.apply(_static_config("10.9.9.5/24"))
    _ok("a1: pending ochildi", state["pending"] is not None)
    with open(INTERFACES_PATH) as f:
        text = f.read()
    _ok("a2: fayl static manzilga ega", "address 10.9.9.5/24" in text, text)
    proc = await asyncio.create_subprocess_exec("ip", "addr", "show", "eth1",
                                                 stdout=asyncio.subprocess.PIPE)
    out, _ = await proc.communicate()
    _ok("a3: eth1 HAQIQATDA 10.9.9.5 ga ega", b"10.9.9.5/24" in out, out.decode())
    # Tozalash shart emas — har stsenariy YANGI konteynerda ishlaydi (wrapper
    # skript); qolaversa dhcp'ga qaytarish dhclient'ni chaqirib, server
    # bo'lmagani uchun keraksiz kutishga olib kelardi (bu yo'l c/e'da allaqachon
    # sinaladi — ularning BASELINE'i ham dhcp).


async def scenario_b() -> None:
    """(b) marshrut qo'shish: statik interfeys + marshrut; fayl va jonli
    `ip route` HAR IKKISI tekshiriladi."""
    _write_baseline()
    service = NetdService(Executor("local", "/"), SETTINGS)
    route = SimpleNamespace(destination="10.50.0.0/24", gateway=None, interface="eth1", metric=None)
    state = await service.apply(_static_config("10.9.9.5/24", routes=[route]))
    _ok("b1: pending ochildi", state["pending"] is not None)
    with open(INTERFACES_PATH) as f:
        text = f.read()
    _ok("b2: fayl marshrutga ega", "up ip route replace 10.50.0.0/24 dev eth1" in text, text)
    proc = await asyncio.create_subprocess_exec("ip", "route", "show", "10.50.0.0/24",
                                                 stdout=asyncio.subprocess.PIPE)
    out, _ = await proc.communicate()
    _ok("b3: marshrut HAQIQATDA jonli jadvalda", b"10.50.0.0/24" in out, out.decode())


async def scenario_c() -> None:
    """(c) tasdiqlanmasa — muddat tugagach avtomatik qaytarish (haqiqiy
    soat, qisqa timeout_s=60 — `min_timeout_s` chegarasi)."""
    _write_baseline()
    clock = {"now": datetime.now(timezone.utc)}

    def now_fn():
        return clock["now"]

    service = NetdService(Executor("local", "/"), SETTINGS, now_fn=now_fn)
    await service.apply(_static_config("10.9.9.6/24", timeout_s=60))
    clock["now"] += timedelta(seconds=61)
    state = await service.state()
    _ok("c1: muddat tugagach pending yo'q", state["pending"] is None)
    _ok("c2: last_result = rolled_back", state["last_result"]["kind"] == "rolled_back", state["last_result"])
    with open(INTERFACES_PATH) as f:
        text = f.read()
    _ok("c3: fayl BASELINE ga qaytdi", text == BASELINE, text)
    proc = await asyncio.create_subprocess_exec("ip", "addr", "show", "eth1", stdout=asyncio.subprocess.PIPE)
    out, _ = await proc.communicate()
    _ok("c4: HAQIQIY manzil ham qaytarildi (10.9.9.6 YO'Q)", b"10.9.9.6" not in out, out.decode())


async def scenario_d() -> None:
    """(d) tasdiqlash o'zgarishni saqlaydi (keyingi `state()` da ham)."""
    _write_baseline()
    service = NetdService(Executor("local", "/"), SETTINGS)
    applied = await service.apply(_static_config("10.9.9.7/24"))
    confirmed = await service.confirm(applied["pending"]["id"])
    _ok("d1: tasdiqlangandan keyin pending yo'q", confirmed["pending"] is None)
    _ok("d2: last_result = confirmed", confirmed["last_result"]["kind"] == "confirmed", confirmed["last_result"])
    state = await service.state()
    _ok("d3: keyingi state() da ham saqlanib qoladi", state["pending"] is None)
    with open(INTERFACES_PATH) as f:
        text = f.read()
    _ok("d4: fayl statik manzilni saqlab qoladi", "10.9.9.7/24" in text, text)
    proc = await asyncio.create_subprocess_exec("ip", "addr", "show", "eth1", stdout=asyncio.subprocess.PIPE)
    out, _ = await proc.communicate()
    _ok("d5: HAQIQIY manzil ham saqlanadi", b"10.9.9.7/24" in out, out.decode())


async def scenario_e() -> None:
    """(e) `netd` qayta ishga tushishi (yangi `NetdService` instansi,
    diskdagi `pending.json`ni topadi) — DARHOL qaytarish."""
    _write_baseline()
    first = NetdService(Executor("local", "/"), SETTINGS)
    await first.apply(_static_config("10.9.9.8/24"))
    with open(INTERFACES_PATH) as f:
        assert "10.9.9.8/24" in f.read()
    restarted = NetdService(Executor("local", "/"), SETTINGS)
    _ok("e1: qayta ishga tushgandan keyin diskdan pending topildi", restarted.pending is not None)
    await restarted.startup_recover()
    _ok("e2: startup_recover dan keyin pending yo'q", restarted.pending is None)
    state = await restarted.state()
    _ok("e3: last_result = rolled_back (restart)", state["last_result"]["kind"] == "rolled_back", state["last_result"])
    with open(INTERFACES_PATH) as f:
        text = f.read()
    _ok("e4: fayl BASELINE ga qaytdi", text == BASELINE, text)


SCENARIOS = {"a": scenario_a, "b": scenario_b, "c": scenario_c, "d": scenario_d, "e": scenario_e}


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in SCENARIOS:
        raise SystemExit(f"foydalanish: {sys.argv[0]} <{'|'.join(SCENARIOS)}>")
    asyncio.run(SCENARIOS[sys.argv[1]]())
    print(f"=== stsenariy {sys.argv[1]!r} MUVAFFAQIYATLI ===")


if __name__ == "__main__":
    main()
