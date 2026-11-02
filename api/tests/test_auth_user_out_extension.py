"""M2b: `/auth/me` (va login javobi) foydalanuvchining O'Z ichki raqamini qaytaradi —
web shell yuqori panelda shu raqamni ko'rsatadi (ilgari maketdan qolgan "101" edi)."""
from types import SimpleNamespace

from app.api.v1.auth import _user_out


def _user(extension):
    return SimpleNamespace(
        id="u1", username="op", full_name="Operator", must_change_password=False, language=None,
        role=SimpleNamespace(name="operator", permissions=["calls:read:own"]),
        tenant=SimpleNamespace(language="uz"), extension=extension,
    )


def test_user_out_includes_own_extension():
    ext = SimpleNamespace(id="e1", number="178", name="Operator 178")
    out = _user_out(_user(ext))
    assert out.extension is not None
    assert (out.extension.id, out.extension.number, out.extension.name) == ("e1", "178", "Operator 178")


def test_user_out_without_extension_is_null():
    assert _user_out(_user(None)).extension is None
