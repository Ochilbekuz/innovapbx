"""`app/services/audit.mask_secrets` — sof funksiya (ub-mode TDD).
m1b-contract.md bo'lim 6/8: parol/PIN/sir maydonlari audit `diff`da `"***"`."""
from __future__ import annotations

import pytest

from app.services.audit import MASK, mask_secrets, normalize_action, record_audit


def test_password_field_masked_as_from_to_dict():
    diff = {"password": {"from": "old-plain", "to": "new-plain"}, "name": "Trunk A"}
    masked = mask_secrets(diff)
    assert masked["password"] == {"from": MASK, "to": MASK}
    assert masked["name"] == "Trunk A"


def test_pin_field_masked_as_flat_value():
    masked = mask_secrets({"pin": "1234"})
    assert masked["pin"] == MASK


def test_pin_hash_and_password_enc_also_masked():
    masked = mask_secrets({"pin_hash": "abc", "password_enc": "xyz", "sip_password_enc": "qqq"})
    assert masked["pin_hash"] == MASK
    assert masked["password_enc"] == MASK
    assert masked["sip_password_enc"] == MASK


def test_secret_field_substring_also_masked():
    masked = mask_secrets({"outbound_secret_token": "abc"})
    assert masked["outbound_secret_token"] == MASK


def test_telegram_token_masked():
    masked = mask_secrets({"telegram_token": "123:ABC", "telegram_chat_id": "42"})
    assert masked["telegram_token"] == MASK
    assert masked["telegram_chat_id"] == "42"


def test_non_secret_fields_pass_through_unchanged():
    diff = {"enabled": {"from": False, "to": True}, "ring_seconds": {"from": 20, "to": 30}}
    assert mask_secrets(diff) == diff


def test_no_plaintext_secret_leaks_anywhere_in_masked_output():
    diff = {"password": {"from": "supersecret123", "to": "newsecret456"}}
    masked = mask_secrets(diff)
    assert "supersecret123" not in str(masked)
    assert "newsecret456" not in str(masked)


# ================= normalize_action — m1b-contract.md bo'lim 6
# Regressiya: `AuditEntryOut.action` qattiq Literal (8 umumiy fe'l), lekin
# routerlar "entity.fe'l" shaklida yozadi (masalan "moh_class.create") —
# normalizatsiyasiz GET /audit har qanday haqiqiy CRUD yozuvida 500 bilan
# yiqilardi (jonli sinovda topilgan, 2026-10-28).
@pytest.mark.parametrize("raw,expected", [
    ("login", "login"),
    ("login_failed", "login_failed"),
    ("restart", "restart"),
    ("restore", "restore"),
    ("update", "update"),
    ("moh_class.create", "create"),
    ("moh_class.update", "update"),
    ("moh_class.delete", "delete"),
    ("extension.rotate_secret", "update"),
    ("holiday.import_uz", "create"),
    ("outbound_route.reorder", "update"),
    ("queue.add_member", "update"),
    ("time_condition.override", "override"),
])
def test_normalize_action_maps_dotted_actions_to_contract_verbs(raw: str, expected: str):
    assert normalize_action(raw) == expected


def test_normalize_action_defaults_unknown_suffix_to_update():
    assert normalize_action("whatever.some_unmapped_future_verb") == "update"


class _FakeSession:
    """`session.add(...)` ni ushlaydigan soxta sessiya — `record_audit`ni
    haqiqiy DB'siz (ub-mode: sof mantiqni DB'dan ajratib sinash) tekshiradi."""

    def __init__(self) -> None:
        self.added = None

    def add(self, obj) -> None:
        self.added = obj


@pytest.mark.asyncio
async def test_record_audit_defaults_missing_diff_to_empty_dict():
    """Regressiya: `diff=mask_secrets(diff or {})` — `diff=None` (sukut)
    bo'lganda ham `AuditLog.diff` bo'sh `{}` bo'lishi SHART, `None` emas."""
    session = _FakeSession()
    await record_audit(session, tenant_id="t1", user_id="u1", action="login", entity="auth")
    assert session.added.diff == {}


@pytest.mark.asyncio
async def test_record_audit_normalizes_action_and_masks_diff():
    session = _FakeSession()
    await record_audit(
        session, tenant_id="t1", user_id="u1", action="moh_class.create", entity="moh_class",
        entity_id="m1", diff={"password": "plain"}, ip="127.0.0.1",
    )
    assert session.added.action == "create"
    assert session.added.diff == {"password": MASK}
    assert session.added.ip == "127.0.0.1"
