"""`app.services.apply.ApplyResult` — dataclass'ni Pydantic javobiga
yuborishdan oldin albatta `.to_dict()` qilinishi SHART (sinovda topilgan
kritik xato: nomlar bir xil, lekin ikkisi butunlay boshqa tiplar —
`app.schemas.ApplyResult` BaseModel, bu esa frozen dataclass)."""
from __future__ import annotations

from app.services.apply import ApplyResult


def test_to_dict_has_exact_contract_keys():
    result = ApplyResult(status="applied", revision=3, message=None)
    assert result.to_dict() == {"status": "applied", "revision": 3, "message": None}


def test_to_dict_is_a_plain_dict_not_dataclass():
    result = ApplyResult(status="unchanged", revision=1, message=None)
    out = result.to_dict()
    assert isinstance(out, dict)
    assert not hasattr(out, "status")
