// Sof funksiya testi — UpdatePage.tsx ichidagi 409 "versiya mos kelmadi" xabar tanlovi (qarang FollowMe.test.tsx uslubi).
import { describe, expect, it } from 'vitest';
import { ApiError } from '@/api/errors';
import { mismatchOrGenericMessage } from './UpdatePage';

const t = (k: string) => (k === 'confirm.stale' ? 'Versiya eskirdi — sahifa qayta yuklanadi.' : k);

describe('UpdatePage — mismatchOrGenericMessage', () => {
  it('update_version_mismatch (409) — oʻzbekcha "eskirdi" xabari', () => {
    const e = new ApiError(409, { code: 'update_version_mismatch', message: 'Versiya mos kelmadi' });
    expect(mismatchOrGenericMessage(e, t)).toBe('Versiya eskirdi — sahifa qayta yuklanadi.');
  });

  it('boshqa ApiError kodi — kod uchun umumiy (i18n) xabar, "stale" emas', () => {
    const e = new ApiError(409, { code: 'update_busy', message: 'server xabari' });
    expect(mismatchOrGenericMessage(e, t)).not.toBe('Versiya eskirdi — sahifa qayta yuklanadi.');
    expect(mismatchOrGenericMessage(e, t)).toBeTruthy();
  });

  it('ApiError emas — generic xabar', () => {
    expect(mismatchOrGenericMessage(new Error('tarmoq xatosi'), t)).toBeTruthy();
  });
});
