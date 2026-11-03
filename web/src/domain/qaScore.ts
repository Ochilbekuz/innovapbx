// M10 B1 — Sifat baholash ball formulasi (backend `api/app/services/qa_scoring.py`
// BILAN BITTA XIL bo'lishi SHART, shartnoma §B1):
// - `yesno` mezon: ha=1, yo'q=0, og'irlik bilan ko'paytiriladi.
// - `scale5` mezon: (qiymat-1)/4 (1..5 -> 0..1), og'irlik bilan ko'paytiriladi.
// - `critical` mezon muvaffaqiyatsiz (yesno=false, YOKI scale5<5, YOKI javob
//   umuman yo'q) bo'lsa — BUTUN baholash foizi 0 (boshqa mezonlar hisobga olinmaydi).
// - Javob berilmagan mezon — ulushi 0, LEKIN og'irligi maxrajga QO'SHILADI
//   (backend `score_pct()` shunday — qisman to'ldirilgan baholash past ball oladi,
//   mezon tashlab ketilmaydi).
// - Foiz = (Σ ulush*og'irlik / Σ og'irlik) * 100, 2 xonaga yaxlitlanadi.

export type QaCriterionLike = { id: string; kind: 'yesno' | 'scale5'; weight: number; critical: boolean };
// Backend `answers: dict[str, bool | int]` — criterion_id -> qiymat (object-map, massiv EMAS).
export type QaAnswers = Record<string, boolean | number>;

function criterionFraction(kind: 'yesno' | 'scale5', value: boolean | number | undefined): number {
  if (value === undefined) return 0;
  if (kind === 'yesno') return value ? 1 : 0;
  return Math.max(0, Math.min(1, (Number(value) - 1) / 4));
}

function isCriticalFail(criterion: QaCriterionLike, value: boolean | number | undefined): boolean {
  if (!criterion.critical) return false;
  if (value === undefined) return true;
  return criterion.kind === 'yesno' ? !value : Number(value) < 5;
}

/** Barcha mezonlarga javob berilganmi (final holatga o'tishdan oldin shart). */
export function isComplete(criteria: QaCriterionLike[], answers: QaAnswers): boolean {
  return criteria.every((c) => answers[c.id] !== undefined);
}

export function computeScorePct(criteria: QaCriterionLike[], answers: QaAnswers): number {
  const totalWeight = criteria.reduce((sum, c) => sum + c.weight, 0);
  if (totalWeight <= 0) return 0;
  if (criteria.some((c) => isCriticalFail(c, answers[c.id]))) return 0;
  const earned = criteria.reduce((sum, c) => sum + criterionFraction(c.kind, answers[c.id]) * c.weight, 0);
  return Math.round((earned / totalWeight) * 100 * 100) / 100;
}
