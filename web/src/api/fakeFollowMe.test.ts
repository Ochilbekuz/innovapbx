// M5b §1 — fake API Follow Me validatsiyasi backend kodlari va `field` bilan mos.
import { describe, expect, it } from 'vitest';
import { defaultFollowMe } from '@/domain/followMe';
import { ApiError } from './errors';
import { normalizeFollowMe, type FollowMeContext } from './fakeFollowMe';
import type { FollowMe } from './types';

const ctx: FollowMeContext = { own: '101', extensionNumbers: new Set(['101', '102', '103']), outboundAllowed: true };
const fm = (p: Partial<FollowMe>): FollowMe => ({ ...defaultFollowMe(), ...p });

function failure(f: FollowMe, c: FollowMeContext = ctx): { code: string; field?: string } {
  try {
    normalizeFollowMe(f, c);
  } catch (e) {
    expect(e).toBeInstanceOf(ApiError);
    const err = e as ApiError;
    expect(err.status).toBe(422);
    return { code: err.code, field: err.field };
  }
  throw new Error('xato kutilgan edi');
}

describe('normalizeFollowMe', () => {
  it('raqamlarni tozalaydi va tartibni saqlaydi', () => {
    expect(normalizeFollowMe(fm({ enabled: true, numbers: ['+998 90 123-45-67', '102'] }), ctx).numbers).toEqual(['998901234567', '102']);
  });

  it.each([
    [['1'], 'bad_number', 'numbers.0'],
    [['102', '101'], 'follow_me_self', 'numbers.1'],
    [['102', '1-02'], 'follow_me_duplicate', 'numbers.1'],
    [['999'], 'follow_me_unknown_extension', 'numbers.0'],
  ])('%j → %s (%s)', (numbers, code, field) => {
    expect(failure(fm({ numbers }))).toEqual({ code, field });
  });

  it('6 tadan koʻp raqam — bad_value', () => {
    expect(failure(fm({ numbers: ['102', '103', '20001', '20002', '20003', '20004', '20005'] })).code).toBe('bad_value');
  });

  it.each([4, 121])('ring_seconds %i — bad_value (ring_seconds)', (ring_seconds) => {
    expect(failure(fm({ ring_seconds }))).toEqual({ code: 'bad_value', field: 'ring_seconds' });
  });

  it.each([5, 120])('ring_seconds %i — chegara ichida', (ring_seconds) => {
    expect(normalizeFollowMe(fm({ ring_seconds }), ctx).ring_seconds).toBe(ring_seconds);
  });

  it('yoqilgan, lekin raqamsiz — follow_me_empty; oʻchiq raqamsiz — ruxsat', () => {
    expect(failure(fm({ enabled: true }))).toEqual({ code: 'follow_me_empty', field: 'numbers' });
    expect(normalizeFollowMe(fm({ enabled: false }), ctx).numbers).toEqual([]);
  });

  it('tashqi chiqish taqiqlangan: yoqilgan + tashqi raqam — xato; ichki yoki oʻchiq — ruxsat', () => {
    const blocked = { ...ctx, outboundAllowed: false };
    expect(failure(fm({ enabled: true, numbers: ['998901234567'] }), blocked).code).toBe('follow_me_outbound_forbidden');
    expect(normalizeFollowMe(fm({ enabled: true, numbers: ['102'] }), blocked).enabled).toBe(true);
    expect(normalizeFollowMe(fm({ enabled: false, numbers: ['998901234567'] }), blocked).numbers).toEqual(['998901234567']);
  });
});
