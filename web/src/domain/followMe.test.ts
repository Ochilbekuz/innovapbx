// M5b §1 — Follow Me sof yordamchilari (UI va fake API ikkalasi ishlatadi).
import { describe, expect, it } from 'vitest';
import { FOLLOW_ME_MAX_NUMBERS } from '@/api/types';
import { cleanNumber, defaultFollowMe, isExternalNumber, isRingSecondsValid, moveItem, numberProblem, sameFollowMe } from './followMe';

describe('cleanNumber', () => {
  it('boʻshliq, qavs, chiziqcha, nuqta va boshidagi + olib tashlanadi', () => {
    expect(cleanNumber(' +998 (90) 123-45.67 ')).toBe('998901234567');
  });
  it('oʻrtadagi + saqlanadi (keyin invalid boʻladi)', () => {
    expect(cleanNumber('99+8')).toBe('99+8');
  });
});

describe('isExternalNumber', () => {
  it('5+ raqam — tashqi, 4 gacha — ichki', () => {
    expect(isExternalNumber('1234')).toBe(false);
    expect(isExternalNumber('12345')).toBe(true);
  });
});

describe('numberProblem', () => {
  it.each([
    ['1', 'invalid'], ['1234567890123456', 'invalid'], ['12a', 'invalid'], ['101', 'self'], ['205', 'duplicate'],
  ] as const)('%s → %s', (n, problem) => {
    expect(numberProblem(n, '101', ['205'])).toBe(problem);
  });
  it('chegaralar: 2 va 15 raqam — toʻgʻri', () => {
    expect(numberProblem('12', '101', [])).toBeNull();
    expect(numberProblem('123456789012345', '101', [])).toBeNull();
  });
  it('roʻyxat toʻla boʻlsa — full; bittasi kam boʻlsa — qoʻshiladi', () => {
    const full = Array.from({ length: FOLLOW_ME_MAX_NUMBERS }, (_, i) => `20${i}`);
    expect(numberProblem('300', '101', full)).toBe('full');
    expect(numberProblem('300', '101', full.slice(1))).toBeNull();
  });
});

describe('moveItem', () => {
  it('yuqoriga va pastga siljitadi, asl massiv oʻzgarmaydi', () => {
    const src = ['a', 'b', 'c'];
    expect(moveItem(src, 1, -1)).toEqual(['b', 'a', 'c']);
    expect(moveItem(src, 1, 1)).toEqual(['a', 'c', 'b']);
    expect(src).toEqual(['a', 'b', 'c']);
  });
  it('chegaradan chiqsa — nusxa, oʻzgarishsiz', () => {
    const src = ['a', 'b'];
    const up = moveItem(src, 0, -1);
    expect(up).toEqual(['a', 'b']);
    expect(up).not.toBe(src);
    expect(moveItem(src, 1, 1)).toEqual(['a', 'b']);
  });
});

describe('sameFollowMe', () => {
  const base = { ...defaultFollowMe(), numbers: ['205', '998901234567'] };
  it('bir xil qiymatlar — true', () => {
    expect(sameFollowMe(base, { ...base, numbers: [...base.numbers] })).toBe(true);
  });
  it.each([
    ['enabled', { enabled: true }], ['strategy', { strategy: 'sequential' as const }], ['include_extension', { include_extension: false }],
    ['ring_seconds', { ring_seconds: 21 }], ['confirm', { confirm: false }], ['tartib', { numbers: ['998901234567', '205'] }],
    ['uzunlik', { numbers: ['205'] }],
  ])('%s farq qilsa — false', (_name, change) => {
    expect(sameFollowMe(base, { ...base, ...change })).toBe(false);
  });
});

describe('defaultFollowMe', () => {
  it('xavfsiz sukut: oʻchiq, birga, ichki raqam ham, 20 s, tasdiq bilan', () => {
    expect(defaultFollowMe()).toEqual({ enabled: false, numbers: [], strategy: 'ring_all', include_extension: true, ring_seconds: 20, confirm: true });
  });
});

describe('isRingSecondsValid', () => {
  it.each([[5, true], [120, true], [4, false], [121, false], [20.5, false], [Number.NaN, false]])('%f → %s', (n, ok) => {
    expect(isRingSecondsValid(n)).toBe(ok);
  });
});
