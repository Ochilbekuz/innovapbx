"""`app/core/security.py::check_internal_api_token` — `internal*.py`ning BARCHA
endpointlari uchun YAGONA token tekshiruvi (Item 6, LOW: avval `!=` vaqt
asosidagi solishtirish ishlatilardi, endi `hmac.compare_digest`). Bu yerda sof
funksiya darajasida sinaladi; HTTP darajasidagi xatti-harakat
`tests/test_internal_pin_check.py` va boshqa `test_internal_*`larda allaqachon
qamrab olingan (ular shu funksiyani ichida ishlatadi)."""
from __future__ import annotations

from app.core.security import check_internal_api_token


def test_rejects_when_internal_api_token_not_configured(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "internal_api_token", "")
    assert check_internal_api_token("anything") is False
    assert check_internal_api_token("") is False


def test_accepts_exact_match(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "internal_api_token", "s3cr3t-token-value")
    assert check_internal_api_token("s3cr3t-token-value") is True


def test_rejects_mismatch(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "internal_api_token", "s3cr3t-token-value")
    assert check_internal_api_token("wrong") is False
    assert check_internal_api_token("s3cr3t-token-valu") is False  # bir belgi kam


def test_uses_constant_time_comparison_not_dunder_eq(monkeypatch):
    """`!=`/`==` o'rniga `hmac.compare_digest` chaqirilganini tasdiqlaydi —
    mantiqiy natija emas, MEXANIZM to'g'riligini tekshirish (vaqt kanali)."""
    import hmac as hmac_module

    from app.core.config import settings

    calls: list[tuple[bytes, bytes]] = []
    real_compare_digest = hmac_module.compare_digest

    def tracking_compare_digest(a, b):
        calls.append((a, b))
        return real_compare_digest(a, b)

    monkeypatch.setattr(settings, "internal_api_token", "tok")
    monkeypatch.setattr("app.core.security.hmac.compare_digest", tracking_compare_digest)
    check_internal_api_token("tok")
    assert calls == [(b"tok", b"tok")]


def test_non_ascii_token_rejected_without_error(monkeypatch):
    """`str` bilan compare_digest ASCII bo'lmagan belgida TypeError (500) beradi —
    bytes'ga o'tkazilgani uchun shunchaki `False`."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "internal_api_token", "tok")
    assert check_internal_api_token("тok") is False
