import { describe, expect, it } from 'vitest';
import type { Call } from './types';
import { callsToCsv, matchesCallFilters } from './fakeCalls';

function makeCall(overrides: Partial<Call> = {}): Call {
  return {
    uniqueid: '1', started_at: '2026-10-27T09:00:00.000Z', src: '998901234567', dst: '101', did: '998712000000',
    direction: 'in', disposition: 'answered', duration: 60, billsec: 60, trunk: 'Uztelecom — asosiy',
    recordings: [], src_name: 'Anvar Yusupov', pin_label: null, qa: null,
    ...overrides,
  };
}

describe('matchesCallFilters', () => {
  it('boʻsh filtr — hamma qoʻngʻiroqqa mos', () => {
    expect(matchesCallFilters(makeCall(), {})).toBe(true);
  });

  it('src: contains (sukut) moslik topadi, mos kelmasa rad etadi', () => {
    expect(matchesCallFilters(makeCall({ src: '998901234567' }), { src: '234567' })).toBe(true);
    expect(matchesCallFilters(makeCall({ src: '998901234567' }), { src: '000000' })).toBe(false);
  });

  it('src_mode=exact — faqat toʻliq moslik', () => {
    const c = makeCall({ src: '101' });
    expect(matchesCallFilters(c, { src: '101', src_mode: 'exact' })).toBe(true);
    expect(matchesCallFilters(c, { src: '10', src_mode: 'exact' })).toBe(false);
  });

  it('src_not=true — moslikni inkor qiladi', () => {
    const c = makeCall({ src: '101' });
    expect(matchesCallFilters(c, { src: '101', src_not: true })).toBe(false);
    expect(matchesCallFilters(c, { src: '202', src_not: true })).toBe(true);
  });

  it('did: null boʻlsa boʻsh satr bilan solishtiriladi (xato otmaydi)', () => {
    const c = makeCall({ did: null });
    expect(matchesCallFilters(c, { did: '998' })).toBe(false);
  });

  it('name — src_name boʻyicha contains', () => {
    expect(matchesCallFilters(makeCall({ src_name: 'Anvar Yusupov' }), { name: 'yusupov' })).toBe(true);
    expect(matchesCallFilters(makeCall({ src_name: null }), { name: 'yusupov' })).toBe(false);
  });

  it('ext — src YOKI dst ga aniq teng', () => {
    const c = makeCall({ src: '101', dst: '102' });
    expect(matchesCallFilters(c, { ext: '101' })).toBe(true);
    expect(matchesCallFilters(c, { ext: '102' })).toBe(true);
    expect(matchesCallFilters(c, { ext: '103' })).toBe(false);
  });

  it('trunk — aniq teng', () => {
    const c = makeCall({ trunk: 'Beeline — zaxira' });
    expect(matchesCallFilters(c, { trunk: 'Beeline — zaxira' })).toBe(true);
    expect(matchesCallFilters(c, { trunk: 'Uztelecom — asosiy' })).toBe(false);
  });

  it('account — pin_label boʻyicha contains', () => {
    expect(matchesCallFilters(makeCall({ pin_label: 'Mijoz — Tashkent' }), { account: 'tashkent' })).toBe(true);
    expect(matchesCallFilters(makeCall({ pin_label: null }), { account: 'tashkent' })).toBe(false);
  });

  it('disposition — vergul bilan ajratilgan roʻyxatda boʻlsa mos', () => {
    const c = makeCall({ disposition: 'busy' });
    expect(matchesCallFilters(c, { disposition: 'answered,busy' })).toBe(true);
    expect(matchesCallFilters(c, { disposition: 'answered,failed' })).toBe(false);
  });

  it('min_duration/max_duration — oraliq tashqarisini rad etadi', () => {
    const c = makeCall({ duration: 60 });
    expect(matchesCallFilters(c, { min_duration: 30, max_duration: 90 })).toBe(true);
    expect(matchesCallFilters(c, { min_duration: 90 })).toBe(false);
    expect(matchesCallFilters(c, { max_duration: 30 })).toBe(false);
  });

  it('recording — with/without qoʻngiroqni yozuv borligiga qarab filtrlaydi', () => {
    const withRec = makeCall({ recordings: [{ id: 'r1', duration_s: 10 }] });
    const withoutRec = makeCall({ recordings: [] });
    expect(matchesCallFilters(withRec, { recording: 'with' })).toBe(true);
    expect(matchesCallFilters(withoutRec, { recording: 'with' })).toBe(false);
    expect(matchesCallFilters(withRec, { recording: 'without' })).toBe(false);
    expect(matchesCallFilters(withoutRec, { recording: 'without' })).toBe(true);
    expect(matchesCallFilters(withoutRec, { recording: 'any' })).toBe(true);
  });
});

describe('callsToCsv', () => {
  it('sarlavha + har qator uchun bitta satr, maxsus belgilar qochiriladi', () => {
    const csv = callsToCsv([makeCall({ src_name: 'Anvar, Yusupov' })]);
    const lines = csv.trim().split('\n');
    expect(lines).toHaveLength(2);
    expect(lines[0]).toBe('started_at,direction,src,src_name,dst,did,disposition,duration,trunk,pin_label');
    expect(lines[1]).toContain('"Anvar, Yusupov"');
  });
});
