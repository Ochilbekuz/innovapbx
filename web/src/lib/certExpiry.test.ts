import { describe, expect, it } from 'vitest';
import { daysUntil, isExpired, isExpiringSoon } from './certExpiry';

const NOW = new Date('2026-10-28T00:00:00Z');
const daysFromNow = (n: number) => new Date(NOW.getTime() + n * 86_400_000).toISOString();

describe('certExpiry', () => {
  it('daysUntil — kelajakdagi va oʻtmishdagi sanalarni toʻgʻri hisoblaydi', () => {
    expect(daysUntil(daysFromNow(10), NOW)).toBe(10);
    expect(daysUntil(daysFromNow(-5), NOW)).toBe(-5);
  });

  it('isExpiringSoon — 30 kundan kamiga "true", undan koʻpiga "false"', () => {
    expect(isExpiringSoon(daysFromNow(29), NOW)).toBe(true);
    expect(isExpiringSoon(daysFromNow(1), NOW)).toBe(true);
    expect(isExpiringSoon(daysFromNow(30), NOW)).toBe(false);
    expect(isExpiringSoon(daysFromNow(90), NOW)).toBe(false);
  });

  it('isExpiringSoon — muddati allaqachon tugagan boʻlsa "false" (bu holat isExpired bilan ajratiladi)', () => {
    expect(isExpiringSoon(daysFromNow(-1), NOW)).toBe(false);
  });

  it('isExpired — faqat oʻtgan sanalarda "true"', () => {
    expect(isExpired(daysFromNow(-1), NOW)).toBe(true);
    expect(isExpired(daysFromNow(0), NOW)).toBe(false);
    expect(isExpired(daysFromNow(5), NOW)).toBe(false);
  });
});
