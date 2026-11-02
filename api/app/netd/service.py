"""netd asosiy orkestratsiya — `state`/`validate`/`apply`/`confirm`/`rollback`
+ commit-confirm muhofazasi (m8-network-contract.md bo'lim 1-2). Protokol
qatlamidan (`protocol.py`) mustaqil — DB/socket importsiz, sof holat mashinasi
bo'lib qoladi (unit test uchun soxta `Executor` + `now_fn` yetarli)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.netd import backend as backend_mod
from app.netd import dns as dns_mod
from app.netd import hostname as hostname_mod
from app.netd import live as live_mod
from app.netd import warnings as warnings_mod
from app.netd.executor import Executor
from app.netd.ifupdown import DesiredInterface, IfupdownFile, Transition, build_target, parse, plan_transition, render
from app.netd.pending import PendingRecord, Snapshot, clear_pending, load_pending, save_pending
from app.netd.settings import NetdSettings
from app.netd.validate import EDITABLE_KINDS, validate_config

_ROLLBACK_MESSAGES = {
    "timeout": "Vaqt tugadi — sozlama avtomatik qaytarildi",
    "manual": "Sozlama qo'lda qaytarildi",
    "restart": "netd qayta ishga tushdi — tasdiqlanmagan sozlama qaytarildi",
}


class NetdError(Exception):
    def __init__(self, code: str, message: str, fields: list[dict] | None = None) -> None:
        self.code = code
        self.message = message
        self.fields = fields or []
        super().__init__(message)


@dataclass(frozen=True)
class LastResult:
    kind: str  # confirmed | rolled_back | apply_failed
    at: datetime
    message: str | None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NetdService:
    def __init__(self, executor: Executor, settings: NetdSettings, now_fn: Callable[[], datetime] = _utcnow) -> None:
        self.executor = executor
        self.settings = settings
        self._now = now_fn
        self.pending: PendingRecord | None = load_pending(executor, settings.pending_path)
        self.last_result: LastResult | None = None

    # --------------------------------------------------------------- reads
    def _interfaces_text(self) -> str:
        return self.executor.read_text(backend_mod.INTERFACES_PATH) or ""

    def _backend(self) -> backend_mod.BackendInfo:
        return backend_mod.detect_backend(self.executor)

    async def _live(self) -> list[live_mod.LiveInterface]:
        return await live_mod.gather_interfaces(self.executor)

    def _resolv(self) -> str:
        return self.executor.read_text(dns_mod.RESOLV_PATH) or ""

    # --------------------------------------------------------------- public ops
    async def state(self, *, skip_expiry_check: bool = False) -> dict[str, Any]:
        if not skip_expiry_check:
            await self._maybe_expire()
        backend = self._backend()
        live = await self._live()
        file = parse(self._interfaces_text()) if backend.name == "ifupdown" else IfupdownFile([], True)
        routes_live = await live_mod.gather_routes(self.executor)
        default_gw = await live_mod.gather_default_gateway(self.executor)
        dns_servers, dns_search = dns_mod.parse_resolv_conf(self._resolv())
        editable = backend.editable and not self.settings.readonly
        return {
            "helper": {"available": True, "version": self.settings.version, "error": None},
            "backend": backend.name, "editable": editable,
            "readonly_reason": self._readonly_reason(backend),
            "hostname": hostname_mod.read_hostname(self.executor),
            "dns": {"servers": dns_servers, "search": dns_search, "editable": dns_mod.is_dns_editable(self.executor)},
            "default_gateway": {"address": default_gw.address, "interface": default_gw.interface},
            "interfaces": [self._interface_out(i, file, backend) for i in live],
            "routes": {
                "static": [self._route_out(r) for r in file.all_routes()],
                "live": [self._live_route_out(r) for r in routes_live],
            },
            "pending": self._pending_out(),
            "last_result": self._last_result_out(),
        }

    async def validate(self, config: Any, *, request_host: str | None = None) -> dict[str, Any]:
        live = await self._live()
        result = validate_config(config, live)
        errors = [{"field": e.field, "message": e.message} for e in result.errors]
        if not result.ok:
            return {"ok": False, "errors": errors, "warnings": [], "diff": []}
        target = self._build_target_file(config, result.resolved_routes)
        transition = plan_transition(parse(self._interfaces_text()), target)
        warn = warnings_mod.host_ip_change_warnings(request_host, live, config, config.timeout_s)
        return {"ok": True, "errors": [], "warnings": warn, "diff": self._summarize(transition, config)}

    async def apply(self, config: Any, *, request_host: str | None = None, meta: dict | None = None) -> dict:
        await self._maybe_expire()
        self._guard_writable()
        live = await self._live()
        result = validate_config(config, live)
        if not result.ok:
            raise NetdError("invalid_config", "Konfiguratsiya yaroqsiz",
                             [{"field": e.field, "message": e.message} for e in result.errors])
        timeout = max(self.settings.min_timeout_s, min(self.settings.max_timeout_s, config.timeout_s))
        snapshot = self._snapshot()
        target = self._build_target_file(config, result.resolved_routes)
        transition = plan_transition(parse(snapshot.interfaces), target)
        await self._write_transition(render(target), transition)
        if config.hostname != snapshot.hostname:
            await hostname_mod.apply_hostname(self.executor, config.hostname)
        self._apply_dns_if_changed(config, snapshot)
        self._open_pending(timeout, self._summarize(transition, config), snapshot, meta or {})
        return await self.state(skip_expiry_check=True)

    async def confirm(self, pending_id: str) -> dict:
        await self._maybe_expire()
        self._require_pending(pending_id)
        self._close_pending(LastResult("confirmed", self._now(), None))
        return await self.state(skip_expiry_check=True)

    async def rollback(self, pending_id: str) -> dict:
        self._require_pending(pending_id)
        await self._do_rollback(reason="manual")
        return await self.state(skip_expiry_check=True)

    async def startup_recover(self) -> None:
        if self.pending is not None:
            await self._do_rollback(reason="restart")

    # --------------------------------------------------------------- guards
    def _readonly_reason(self, backend: backend_mod.BackendInfo) -> str | None:
        if backend.editable and self.settings.readonly:
            return "Bu serverda tarmoqni tahrirlash o'chirilgan (NETD_READONLY)"
        return backend.readonly_reason

    def _guard_writable(self) -> None:
        backend = self._backend()
        if self.settings.readonly or not backend.editable:
            raise NetdError("readonly", self._readonly_reason(backend) or "Tarmoqni tahrirlash o'chirilgan")
        if self.pending is not None:
            raise NetdError("pending_exists", "Tasdiqlanmagan o'zgarish allaqachon mavjud (409)")

    def _require_pending(self, pending_id: str) -> None:
        if self.pending is None or self.pending.id != pending_id:
            raise NetdError("not_found", "Kutilayotgan o'zgarish topilmadi")

    async def _maybe_expire(self) -> None:
        if self.pending is not None and self.pending.is_expired(self._now()):
            await self._do_rollback(reason="timeout")

    # --------------------------------------------------------------- build/apply
    def _build_target_file(self, config: Any, resolved_routes: dict) -> IfupdownFile:
        desired = [
            DesiredInterface(i.name, i.mode, i.address, i.gateway, i.mtu, resolved_routes.get(i.name, []))
            for i in config.interfaces
        ]
        return build_target(parse(self._interfaces_text()), desired)

    async def _write_transition(self, target_text: str, transition: Transition) -> None:
        """`ifdown` /etc/network/interfaces'ni O'QIB, qaysi usul (dhcp/
        static) bo'yicha ERISHILGANINI aniqlaydi va shunga mos yechadi
        (static — manzilni `ip addr del`, dhcp — `dhclient -r`). Shu sabab
        faylni YANGI mazmun bilan almashtirishdan OLDIN `ifdown` chaqirish
        SHART — aks holda `ifdown` YANGI (masalan dhcp) usul bo'yicha
        yechishga urinadi-yu, ESKI (masalan static) manzil interfeysda
        osilib qoladi (M8 izolyatsiyalangan integratsiya sinovida haqiqiy
        `ifupdown` ustida topilgan xato)."""
        for name in transition.restart_ifaces:
            await self.executor.run(["ifdown", "--force", name], timeout=20.0)
        self.executor.write_text_atomic(backend_mod.INTERFACES_PATH, target_text)
        for name in transition.restart_ifaces:
            await self.executor.run(["ifup", name], timeout=20.0)
        for cmd in transition.route_live_cmds:
            await self.executor.run(cmd, timeout=10.0)

    def _apply_dns_if_changed(self, config: Any, snapshot: Snapshot) -> None:
        if dns_mod.is_dns_editable(self.executor):
            old_servers, old_search = dns_mod.parse_resolv_conf(snapshot.resolv_conf or "")
            if (old_servers, old_search) != (config.dns.servers, config.dns.search):
                dns_mod.write_resolv_conf(self.executor, config.dns.servers, config.dns.search)

    def _snapshot(self) -> Snapshot:
        return Snapshot(
            interfaces=self._interfaces_text(), resolv_conf=self._resolv(),
            hostname=hostname_mod.read_hostname(self.executor),
            hosts=self.executor.read_text(hostname_mod.HOSTS_PATH) or "",
        )

    def _summarize(self, transition: Transition, config: Any) -> list[str]:
        lines = [f"{name}: qayta ishga tushiriladi (manzil/rejim o'zgaradi)" for name in transition.restart_ifaces]
        if transition.route_live_cmds:
            lines.append(f"{len(transition.route_live_cmds)} ta marshrut o'zgaradi")
        old_hostname = hostname_mod.read_hostname(self.executor)
        if config.hostname != old_hostname:
            lines.append(f"hostname: {old_hostname} -> {config.hostname}")
        old_servers, old_search = dns_mod.parse_resolv_conf(self._resolv())
        if (old_servers, old_search) != (config.dns.servers, config.dns.search):
            lines.append("DNS sozlamalari o'zgaradi")
        return lines

    # --------------------------------------------------------------- pending lifecycle
    def _open_pending(self, timeout_s: int, summary: list[str], snapshot: Snapshot, meta: dict) -> None:
        now = self._now()
        record = PendingRecord(
            id=uuid.uuid4().hex, applied_at=now, expires_at=now + timedelta(seconds=timeout_s),
            summary=summary, snapshot=snapshot, meta=meta,
        )
        self.pending = record
        save_pending(self.executor, self.settings.pending_path, record)

    def _close_pending(self, result: LastResult) -> None:
        self.last_result = result
        self.pending = None
        clear_pending(self.executor, self.settings.pending_path)

    async def _do_rollback(self, *, reason: str) -> None:
        record = self.pending
        if record is None:
            return
        transition = plan_transition(parse(self._interfaces_text()), parse(record.snapshot.interfaces or ""))
        await self._write_transition(record.snapshot.interfaces or "", transition)
        await self._restore_hostname_dns(record.snapshot)
        self._close_pending(LastResult("rolled_back", self._now(), _ROLLBACK_MESSAGES[reason]))

    async def _restore_hostname_dns(self, snapshot: Snapshot) -> None:
        if snapshot.hostname and snapshot.hostname != hostname_mod.read_hostname(self.executor):
            await hostname_mod.apply_hostname(self.executor, snapshot.hostname)
        if (dns_mod.is_dns_editable(self.executor) and snapshot.resolv_conf is not None
                and snapshot.resolv_conf != self._resolv()):
            # Faqat HAQIQATDA farq bo'lsa yozamiz — `_apply_dns_if_changed`
            # bilan bir xil qoida (keraksiz disk yozuvidan qochish; ba'zi
            # muhitlarda `/etc/resolv.conf` boshqa narsa tomonidan
            # boshqariladigan maxsus fayl tizimi bo'lishi mumkin).
            self.executor.write_text_atomic(dns_mod.RESOLV_PATH, snapshot.resolv_conf)

    # --------------------------------------------------------------- state projections
    def _interface_out(self, live_if: live_mod.LiveInterface, file: IfupdownFile,
                        backend: backend_mod.BackendInfo) -> dict:
        stanza = file.stanza(live_if.name)
        editable = backend.editable and not self.settings.readonly and live_if.kind in EDITABLE_KINDS
        mode, address, gateway, mtu = self._stanza_config(stanza)
        return {
            "name": live_if.name, "mac": live_if.mac, "kind": live_if.kind, "oper_state": live_if.oper_state,
            "carrier": live_if.carrier, "speed_mbps": live_if.speed_mbps, "mtu": live_if.mtu,
            "live_ipv4": live_if.live_ipv4, "live_ipv6": live_if.live_ipv6, "editable": editable,
            "config": {"mode": mode, "address": address, "gateway": gateway, "mtu": mtu},
        }

    @staticmethod
    def _stanza_config(stanza) -> tuple[str, str | None, str | None, int | None]:
        if stanza is None:
            return "unconfigured", None, None, None
        mode = stanza.method if stanza.method in ("dhcp", "static") else "manual"
        return mode, stanza.address, stanza.gateway, stanza.mtu

    @staticmethod
    def _route_out(route) -> dict:
        return {"destination": route.destination, "gateway": route.gateway,
                "interface": route.interface, "metric": route.metric}

    @staticmethod
    def _live_route_out(route) -> dict:
        return {"destination": route.destination, "gateway": route.gateway, "interface": route.interface,
                "metric": route.metric, "protocol": route.protocol}

    def _pending_out(self) -> dict | None:
        if self.pending is None:
            return None
        return {"id": self.pending.id, "applied_at": self.pending.applied_at.isoformat(),
                "expires_at": self.pending.expires_at.isoformat(), "summary": self.pending.summary}

    def _last_result_out(self) -> dict | None:
        if self.last_result is None:
            return None
        return {"kind": self.last_result.kind, "at": self.last_result.at.isoformat(),
                "message": self.last_result.message}
