// Haftalik ish vaqti setkasi: 7 kun × 24 soat. Hafta dushanbadan (O'zbekiston odati).
export type Week = readonly (readonly boolean[])[];

// Kun nomlari domen qatlamida YO'Q — tilga bog'liq, UI `pbx/domainText.ts` (`dayLabels`) dan oladi.
export const emptyWeek = (): Week => Array.from({ length: 7 }, () => Array<boolean>(24).fill(false));

/** [from, to) soat oralig'ini bo'yaydi. */
export function paint(week: Week, day: number, from: number, to: number, on: boolean): Week {
  return week.map((row, d) => (d === day ? row.map((v, h) => (h >= from && h < to ? on : v)) : row));
}

const hh = (h: number) => `${String(h).padStart(2, '0')}:00`;

function dayRanges(row: readonly boolean[]): string {
  const out: string[] = [];
  let start = -1;
  row.concat(false).forEach((on, h) => {
    if (on && start < 0) start = h;
    if (!on && start >= 0) {
      out.push(`${hh(start)}–${hh(h)}`);
      start = -1;
    }
  });
  return out.join(', ');
}

/** Ketma-ket bir xil kunlarni guruhlab, «Du–Ju 09:00–18:00» ko'rinishida qaytaradi (`days` — 7 ta qisqa kun nomi, dushanbadan). */
export function summarizeWeek(week: Week, days: readonly string[]): string[] {
  const ranges = week.map(dayRanges);
  const out: string[] = [];
  let i = 0;
  while (i < ranges.length) {
    let j = i;
    while (j + 1 < ranges.length && ranges[j + 1] === ranges[i]) j++;
    if (ranges[i]) out.push(`${days[i]}${j > i ? `–${days[j]}` : ''} ${ranges[i]}`);
    i = j + 1;
  }
  return out;
}

// ─────── Server shakli (`TimeRange[]`, API shartnomasi) bilan ko'rish shakli (`Week`) orasidagi ko'prik ───────
// `../api/types.ts`dagi `Weekday`/`TimeRange` bilan tuzilishi bir xil — domen qatlami API'dan mustaqil bo'lishi uchun
// shu yerda alohida e'lon qilingan (qarang `domain/destination.ts`'dagi xuddi shu naqsh).

export type Weekday = 1 | 2 | 3 | 4 | 5 | 6 | 7;
export type TimeRange = { weekdays: Weekday[]; start: string; end: string };

const hourOf = (hhmm: string) => Number(hhmm.slice(0, 2));

/** `Week` setkasini server kutgan oraliqlar ro'yxatiga aylantiradi — har kun uchun qoʻshni soatlar bitta oraliqqa birlashadi. */
export function weekToRanges(week: Week): TimeRange[] {
  const out: TimeRange[] = [];
  week.forEach((row, d) => {
    let start = -1;
    [...row, false].forEach((on, h) => {
      if (on && start < 0) start = h;
      if (!on && start >= 0) {
        out.push({ weekdays: [(d + 1) as Weekday], start: hh(start), end: hh(h) });
        start = -1;
      }
    });
  });
  return out;
}

/** Server oraliqlarini `Week` setkasiga aylantiradi (WeekGrid'da chizish uchun). Daqiqalar soat chegarasiga yumaloqlanadi. */
export function rangesToWeek(ranges: readonly TimeRange[]): Week {
  const week = emptyWeek().map((row) => [...row]);
  for (const r of ranges) {
    const from = hourOf(r.start);
    const to = hourOf(r.end);
    for (const w of r.weekdays) {
      const row = week[w - 1];
      if (row) for (let h = from; h < to; h++) row[h] = true;
    }
  }
  return week;
}

/** Shartnoma: `end <= start` boʻlsa 422 `range_order`. UI saqlashdan oldin shu bilan oldindan tekshiradi. */
export function isRangeOrderValid(ranges: readonly TimeRange[]): boolean {
  return ranges.every((r) => r.end > r.start);
}
