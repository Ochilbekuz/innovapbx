// Navbat SLA foizini vizual darajaga aylantirish (S13/S29) — sof funksiya, UI `Tone`ga bilmasdan.
// Qarang ../../replica/m2b-contract.md §5. UI qatlami `SlaLevel` → `Tone` xaritalashni o'zi qiladi.

export type SlaLevel = 'good' | 'warn' | 'bad' | 'unknown';

const GOOD_THRESHOLD = 80;
const WARN_THRESHOLD = 50;

/** `null` — hisoblab bo'lmaydi (masalan `entered=0`) → `unknown`; aks holda chegaralar bo'yicha daraja. */
export function slaLevel(pct: number | null): SlaLevel {
  if (pct === null || Number.isNaN(pct)) return 'unknown';
  if (pct >= GOOD_THRESHOLD) return 'good';
  if (pct >= WARN_THRESHOLD) return 'warn';
  return 'bad';
}
