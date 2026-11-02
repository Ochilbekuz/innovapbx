"""Yozuv siyosati (m3b-contract.md §1) — SPETSIFIKATSIYA. Dialplan `innova-rec`
(`app/services/dialplan_recording.py`) AYNAN shu qoidani Asterisk ichida bajaradi
(javob bergan B kanalida, `Dial(U())`/`Queue(gosub)`), shu sabab bu yerda faqat sof qaror.

  B — trunk (chiquvchi): siyosat manba ichki raqamniki (`src` — forward/transfer qilgan raqam,
      bo'lmasa A). `on_demand` A → A'ga `*1`.
  B — ichki, A — trunk/bo'sh (kiruvchi): siyosat B (javob bergan raqam). `on_demand` B → B'ga `*1`.
  Ichki (A va B ichki): `external_only` → yozilmaydi; aks holda biri `always` va hech biri `never`
      emas → yoziladi; `on_demand` tomonlarga `*1`.
`on_demand` A uchun `*1` A'ning o'z kanalida (Dial'dan oldin) har doim beriladi.
"""
from __future__ import annotations

from dataclasses import dataclass

ALWAYS, NEVER, ON_DEMAND = "always", "never", "on_demand"


@dataclass(frozen=True)
class Decision:
    record: bool
    on_demand_a: bool = False
    on_demand_b: bool = False


def decide(*, a: str | None, b: str | None, src: str | None, a_is_ext: bool, b_is_ext: bool,
           external_only: bool) -> Decision:
    on_demand_a = a_is_ext and a == ON_DEMAND
    if not b_is_ext:
        policy = src if src is not None else a
        return Decision(record=policy == ALWAYS, on_demand_a=on_demand_a)
    on_demand_b = b == ON_DEMAND
    if not a_is_ext:
        return Decision(record=b == ALWAYS, on_demand_b=on_demand_b)
    if external_only:
        return Decision(record=False, on_demand_a=on_demand_a)
    record = ALWAYS in (a, b) and NEVER not in (a, b)
    return Decision(record=record, on_demand_a=on_demand_a, on_demand_b=on_demand_b)
