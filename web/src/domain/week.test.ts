import { describe, expect, it } from 'vitest';
import { emptyWeek, isRangeOrderValid, paint, rangesToWeek, summarizeWeek, weekToRanges, type TimeRange } from './week';

const D = ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'];

describe('week', () => {
  it('ish kunlarini bitta qatorga yig‘adi', () => {
    let w = emptyWeek();
    for (let d = 0; d < 5; d++) w = paint(w, d, 9, 18, true);
    w = paint(w, 5, 10, 14, true);
    expect(summarizeWeek(w, D)).toEqual(['Du–Ju 09:00–18:00', 'Sh 10:00–14:00']);
  });

  it("bo'sh hafta", () => {
    expect(summarizeWeek(emptyWeek(), D)).toEqual([]);
  });

  it('kun ichida ikki oraliq', () => {
    let w = paint(emptyWeek(), 0, 9, 13, true);
    w = paint(w, 0, 14, 18, true);
    expect(summarizeWeek(w, D)).toEqual(['Du 09:00–13:00, 14:00–18:00']);
  });
});

describe('weekToRanges / rangesToWeek', () => {
  it("ish kunlari setkasi — server oraliqlariga aylanadi (har kun alohida 'weekdays')", () => {
    let w = emptyWeek();
    for (let d = 0; d < 5; d++) w = paint(w, d, 9, 18, true);
    const ranges = weekToRanges(w);
    expect(ranges).toEqual([
      { weekdays: [1], start: '09:00', end: '18:00' },
      { weekdays: [2], start: '09:00', end: '18:00' },
      { weekdays: [3], start: '09:00', end: '18:00' },
      { weekdays: [4], start: '09:00', end: '18:00' },
      { weekdays: [5], start: '09:00', end: '18:00' },
    ]);
  });

  it("bo'sh setka — bo'sh oraliqlar", () => {
    expect(weekToRanges(emptyWeek())).toEqual([]);
  });

  it('server oraliqlari setkaga qaytib chiziladi (round-trip)', () => {
    const ranges: TimeRange[] = [{ weekdays: [1, 2, 3, 4, 5], start: '09:00', end: '18:00' }, { weekdays: [6], start: '10:00', end: '14:00' }];
    const week = rangesToWeek(ranges);
    expect(summarizeWeek(week, D)).toEqual(['Du–Ju 09:00–18:00', 'Sh 10:00–14:00']);
  });
});

describe('isRangeOrderValid', () => {
  it("tugash boshlanishdan keyin bo'lsa — toʻgʻri", () => {
    expect(isRangeOrderValid([{ weekdays: [1], start: '09:00', end: '18:00' }])).toBe(true);
  });

  it("tugash boshlanishdan oldin (yoki teng) bo'lsa — 422 range_order", () => {
    expect(isRangeOrderValid([{ weekdays: [1], start: '18:00', end: '09:00' }])).toBe(false);
    expect(isRangeOrderValid([{ weekdays: [1], start: '09:00', end: '09:00' }])).toBe(false);
  });

  it("boʻsh roʻyxat — toʻgʻri (cheklov yoʻq)", () => {
    expect(isRangeOrderValid([])).toBe(true);
  });
});
