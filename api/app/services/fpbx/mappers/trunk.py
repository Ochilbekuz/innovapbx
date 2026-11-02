"""`trunks` + `pjsip`/`sip` (EAV, `id`=`trunkid`) -> `trunks` (m5a-contract.md §1.2,
proof §4: register/ip auth_mode, host/user/CID/kanal soni). `devices.tech`dagi kabi
`chan`/`iax2`/boshqa texnologiyalar `unsupported`."""
from __future__ import annotations

from app.services.fpbx.mappers import Ctx, Entry, first_of, int_or, warning, weak_secret

_KNOWN_CODECS = {"ulaw", "alaw", "g722", "opus"}
_SUPPORTED_TECH = {"pjsip", "sip"}


def _codecs(raw: str | None) -> tuple[list[str], bool]:
    items = [c.strip() for c in (raw or "").split(",") if c.strip()]
    known = [c for c in items if c in _KNOWN_CODECS]
    return known, len(known) != len(items)


def _auth_mode(fields: dict[str, str]) -> str:
    if (fields.get("registration") or "") == "send":
        return "register"
    if (fields.get("identify_by") or "") == "ip":
        return "ip"
    return "register"


def _unsupported_trunk_entry(source_ref: str, name: str, tech: str | None) -> Entry:
    return Entry(
        kind="trunk", source_ref=source_ref, name=name, number=None,
        action="unsupported", reason="trunk_tech_unsupported",
        warnings=[warning("trunk_tech_unsupported", f"Qo'llab-quvvatlanmaydigan texnologiya: {tech}")],
    )


def _trunk_payload(row: dict, name: str, fields: dict, codecs: list[str], match_ips: list[str]) -> dict:
    return {
        "name": name, "auth_mode": _auth_mode(fields),
        "host": first_of(fields.get("sip_server"), fields.get("from_domain"), fields.get("host")),
        "port": int_or(fields.get("sip_server_port"), None),
        "transport": "udp" if "udp" in (fields.get("transport") or "") else "tcp",
        "username": first_of(fields.get("auth_username"), fields.get("username"), fields.get("account")),
        "secret_plain": fields.get("secret"),
        "from_domain": fields.get("from_domain") or None,
        "match_ips": match_ips,
        "codecs": codecs,
        "max_channels": int_or(row.get("maxchans"), 0),
        "outbound_callerid": row.get("outcid") or None,
        "enabled": (row.get("disabled") or "off") != "on",
    }


def map_trunk(ctx: Ctx) -> list[Entry]:
    pjsip_by_id = ctx.eav("pjsip")
    sip_by_id = ctx.eav("sip")
    entries: list[Entry] = []
    for row in ctx.table("trunks"):
        trunk_id = row["trunkid"]
        source_ref = f"trunks:{trunk_id}"
        name = row.get("name") or trunk_id
        tech = row.get("tech")
        if tech not in _SUPPORTED_TECH:
            entries.append(_unsupported_trunk_entry(source_ref, name, tech))
            continue

        fields = first_of(pjsip_by_id.get(trunk_id), sip_by_id.get(trunk_id)) or {}
        entry_warnings: list[dict[str, str]] = []
        codecs, dropped = _codecs(first_of(fields.get("codecs"), fields.get("allow")))
        if dropped:
            entry_warnings.append(warning(
                "codec_unsupported", f"Innova qo'llab-quvvatlamaydigan kodek(lar) tashlandi: {fields.get('codecs')}"))

        match_ips = [m.strip() for m in (fields.get("match") or "").split(",") if m.strip()]
        payload = _trunk_payload(row, name, fields, codecs, match_ips)
        secret = payload["secret_plain"]

        entries.append(Entry(
            kind="trunk", source_ref=source_ref, name=name, number=None,
            action="create", warnings=entry_warnings,
            has_secret=bool(secret), weak_secret=weak_secret(secret, equals_number=None),
            payload=payload,
        ))
    return entries
