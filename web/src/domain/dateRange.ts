// Analitika sana oralig'i (S13) — sof funksiyalar, qarang ../../replica/m2b-contract.md §5.
// UI/i18n'ga bog'liq emas; `isoDate` ("YYYY-MM-DD" formatlagich) `lib/time.ts`dan — ular ham sof, i18n'siz.
import { isoDate } from '../lib/time';

export type RangePreset = 'today' | 'yesterday' | '7d' | '30d' | 'custom';

/** Shartnoma: oraliq 92 kundan oshmasin (M2b §5). */
export const MAX_RANGE_DAYS = 92;

export type DateRange = { from: string; to: string };

/** Berilgan vaqt oʻrnida (odatda `new Date()`) tanlangan preset uchun `{from,to}` ("YYYY-MM-DD") hisoblaydi. */
export function presetRange(preset: RangePreset, now: Date, custom?: DateRange): DateRange {
  if (preset === 'custom') return custom ?? { from: isoDate(now), to: isoDate(now) };
  if (preset === 'today') return { from: isoDate(now), to: isoDate(now) };
  if (preset === 'yesterday') {
    const y = daysAgoFrom(now, 1);
    return { from: y, to: y };
  }
  if (preset === '7d') return { from: daysAgoFrom(now, 6), to: isoDate(now) };
  return { from: daysAgoFrom(now, 29), to: isoDate(now) };
}

function daysAgoFrom(now: Date, n: number): string {
  const d = new Date(now);
  d.setDate(d.getDate() - n);
  return isoDate(d);
}

export type RangeValidation = { ok: true } | { ok: false; reason: 'bad_order' | 'too_long' };

/** `from` > `to` yoki oraliq 92 kundan uzun — rad etiladi (serverdagi 422 `bad_range` bilan mos). */
export function validateRange(range: DateRange): RangeValidation {
  const fromTs = Date.parse(range.from);
  const toTs = Date.parse(range.to);
  if (Number.isNaN(fromTs) || Number.isNaN(toTs) || toTs < fromTs) return { ok: false, reason: 'bad_order' };
  const days = Math.round((toTs - fromTs) / 86_400_000) + 1;
  if (days > MAX_RANGE_DAYS) return { ok: false, reason: 'too_long' };
  return { ok: true };
}
