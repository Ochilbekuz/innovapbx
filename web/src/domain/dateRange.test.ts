import { describe, expect, it } from 'vitest';
import { presetRange, validateRange } from './dateRange';

const NOW = new Date('2026-10-28T09:00:00Z');

describe('dateRange — presetRange', () => {
  it('today — bugungi kun ikki uchida', () => {
    expect(presetRange('today', NOW)).toEqual({ from: '2026-10-28', to: '2026-10-28' });
  });

  it('yesterday — bir kun oldin', () => {
    expect(presetRange('yesterday', NOW)).toEqual({ from: '2026-10-27', to: '2026-10-27' });
  });

  it('7d — bugun bilan birga 7 kun', () => {
    expect(presetRange('7d', NOW)).toEqual({ from: '2026-10-22', to: '2026-10-28' });
  });

  it('30d — bugun bilan birga 30 kun', () => {
    expect(presetRange('30d', NOW)).toEqual({ from: '2026-09-29', to: '2026-10-28' });
  });

  it('custom — berilgan oraliqni qaytaradi', () => {
    expect(presetRange('custom', NOW, { from: '2026-01-01', to: '2026-01-31' })).toEqual({ from: '2026-01-01', to: '2026-01-31' });
  });
});

describe('dateRange — validateRange', () => {
  it('toʻgʻri qisqa oraliq — ok', () => {
    expect(validateRange({ from: '2026-10-01', to: '2026-10-28' })).toEqual({ ok: true });
  });

  it('to < from — bad_order', () => {
    expect(validateRange({ from: '2026-10-28', to: '2026-10-01' })).toEqual({ ok: false, reason: 'bad_order' });
  });

  it('92 kundan uzun — too_long', () => {
    expect(validateRange({ from: '2026-01-01', to: '2026-12-31' })).toEqual({ ok: false, reason: 'too_long' });
  });

  it('aniq 92 kun — ok (chegara qiymati)', () => {
    expect(validateRange({ from: '2026-01-01', to: '2026-04-02' })).toEqual({ ok: true });
  });
});
