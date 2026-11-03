"""TOTP (RFC 6238) sof funksiyalari — m10-onlinepbx-contract.md Bo'lak B2."""
from __future__ import annotations

from app.services import totp


# RFC 6238 Appendix B test vektori (SHA1, 8 raqam) — biz 6 raqamli kesilgan
# shaklini tekshiramiz (dinamik kesish bir xil, faqat oxirgi `% 10**digits`).
_SECRET_B32 = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # "12345678901234567890" ASCII -> base32


def test_hotp_matches_rfc4226_vector_counter_0():
    # RFC 4226 Appendix D, secret="12345678901234567890" (ASCII), counter=0 -> 755224
    assert totp.hotp(_SECRET_B32, 0) == "755224"


def test_hotp_matches_rfc4226_vector_counter_1():
    assert totp.hotp(_SECRET_B32, 1) == "287082"


def test_step_for_divides_by_30s():
    assert totp.step_for(0) == 0
    assert totp.step_for(29) == 0
    assert totp.step_for(30) == 1
    assert totp.step_for(59_999_999) == 59_999_999 // 30


def test_totp_at_uses_step_for():
    t = 29
    assert totp.totp_at(_SECRET_B32, t) == totp.hotp(_SECRET_B32, 0)


def test_verify_accepts_current_step():
    step = totp.step_for(100_000)
    code = totp.hotp(_SECRET_B32, step)
    assert totp.verify(_SECRET_B32, code, 100_000, last_step=None) == step


def test_verify_accepts_one_step_tolerance_before_and_after():
    base_time = 100_000
    step = totp.step_for(base_time)
    code_prev = totp.hotp(_SECRET_B32, step - 1)
    code_next = totp.hotp(_SECRET_B32, step + 1)
    assert totp.verify(_SECRET_B32, code_prev, base_time, last_step=None) == step - 1
    assert totp.verify(_SECRET_B32, code_next, base_time, last_step=None) == step + 1


def test_verify_rejects_outside_tolerance():
    base_time = 100_000
    step = totp.step_for(base_time)
    code_far = totp.hotp(_SECRET_B32, step - 2)
    assert totp.verify(_SECRET_B32, code_far, base_time, last_step=None) is None


def test_verify_rejects_replayed_step():
    base_time = 100_000
    step = totp.step_for(base_time)
    code = totp.hotp(_SECRET_B32, step)
    assert totp.verify(_SECRET_B32, code, base_time, last_step=step) is None
    assert totp.verify(_SECRET_B32, code, base_time, last_step=step - 1) == step


def test_verify_rejects_wrong_code():
    assert totp.verify(_SECRET_B32, "000000", 100_000, last_step=None) in (None,) or True
    # haqiqiy noto'g'ri kod aniq rad etilishini tekshiramiz
    base_time = 100_000
    step = totp.step_for(base_time)
    real_code = totp.hotp(_SECRET_B32, step)
    wrong = "000000" if real_code != "000000" else "111111"
    assert totp.verify(_SECRET_B32, wrong, base_time, last_step=None) is None


def test_verify_rejects_malformed_code():
    assert totp.verify(_SECRET_B32, "abc", 100_000, last_step=None) is None
    assert totp.verify(_SECRET_B32, "12345", 100_000, last_step=None) is None
    assert totp.verify(_SECRET_B32, "", 100_000, last_step=None) is None


def test_generate_secret_is_valid_base32_and_unique():
    s1 = totp.generate_secret()
    s2 = totp.generate_secret()
    assert s1 != s2
    import base64
    base64.b32decode(s1 + "=" * (-len(s1) % 8))  # noqa: no exception


def test_otpauth_uri_contains_params():
    uri = totp.otpauth_uri(_SECRET_B32, account="operator1@acme")
    assert uri.startswith("otpauth://totp/")
    assert f"secret={_SECRET_B32}" in uri
    assert "algorithm=SHA1" in uri
    assert "digits=6" in uri
    assert "period=30" in uri


def test_generate_recovery_codes_format_and_uniqueness():
    codes = totp.generate_recovery_codes()
    assert len(codes) == 10
    assert len(set(codes)) == 10
    for code in codes:
        assert len(code) == 9
        assert code[4] == "-"
        head, _, tail = code.partition("-")
        assert len(head) == 4 and len(tail) == 4
