"""Yozuv siyosati (m3c-contract.md §1) — SPETSIFIKATSIYA. Dialplan `innova-rec`
(`app/services/dialplan_recording.py`) AYNAN shu qoidani Asterisk ichida bajaradi
(javob bergan B kanalida, `Dial(U())`/`Queue(gosub)`), shu sabab bu yerda faqat sof qaror.

Har ichki raqamda IKKI alohida siyosat: `recording_in` (shu raqamga KELGAN
qo'ng'iroq) va `recording_out` (shu raqamdan CHIQQAN qo'ng'iroq). Qaror faqat
ikkita qiymatga qaraydi — A tomonining CHIQUVCHI (`a_out`) va B tomonining
KIRUVCHI (`b_in`) siyosati; A'ning kiruvchisi/B'ning chiquvchisi bu qo'ng'iroqqa
aloqasi yo'q (ular o'z chaqirgan/qabul qilgan qo'ng'iroqlarida ishlaydi).

  B — trunk (chiquvchi): siyosat manba ichki raqamning CHIQUVCHISI (`src_out` —
      forward/transfer qilgan raqam, bo'lmasa `a_out`). `on_demand` A → A'ga `*1`.
  B — ichki, A — trunk/bo'sh (kiruvchi): siyosat B'ning KIRUVCHISI (`b_in`).
      `on_demand` B → B'ga `*1`.
  Ichki (A va B ichki): `external_only` → yozilmaydi; aks holda `a_out`/`b_in`
      biri `always` va hech biri `never` emas → yoziladi; `on_demand` tomonlarga `*1`.
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


def decide(*, a_out: str | None, b_in: str | None, src_out: str | None, a_is_ext: bool, b_is_ext: bool,
           external_only: bool) -> Decision:
    on_demand_a = a_is_ext and a_out == ON_DEMAND
    if not b_is_ext:
        policy = src_out if src_out is not None else a_out
        return Decision(record=policy == ALWAYS, on_demand_a=on_demand_a)
    on_demand_b = b_in == ON_DEMAND
    if not a_is_ext:
        return Decision(record=b_in == ALWAYS, on_demand_b=on_demand_b)
    if external_only:
        return Decision(record=False, on_demand_a=on_demand_a)
    record = ALWAYS in (a_out, b_in) and NEVER not in (a_out, b_in)
    return Decision(record=record, on_demand_a=on_demand_a, on_demand_b=on_demand_b)
