import { describe, expect, it } from 'vitest';
import { ApiError } from './errors';
import { jobStep, validatedLocalTarget, validatedS3Target, validatedSftpTarget, type S3TargetInput, type SftpTargetInput } from './fakeBackup';
import type { BackupS3Target, BackupSftpTarget } from './types';

const S3_CURRENT: BackupS3Target = {
  enabled: false, endpoint: '', region: '', bucket: '', prefix: '', access_key: '', path_style: false, keep_last: 7, has_secret_key: false,
};
const S3_IN: S3TargetInput = {
  enabled: true, endpoint: 'https://s3.local', region: 'us-east-1', bucket: 'bk', prefix: 'p/', access_key: 'AK', path_style: true, keep_last: 5,
};
const SFTP_CURRENT: BackupSftpTarget = {
  enabled: true, host: 'old.host', port: 22, user: 'u', folder: '/b', keep_last: 7, has_password: false, has_key: false, host_key_fp: 'SHA256:x',
};
const SFTP_IN: SftpTargetInput = { enabled: true, host: 'old.host', port: 2222, user: 'bk', folder: '/z', keep_last: 3 };

function apiError(fn: () => unknown): ApiError {
  try {
    fn();
  } catch (e) {
    if (e instanceof ApiError) return e;
    throw e;
  }
  throw new Error('xato kutilgan edi');
}

describe('validatedLocalTarget', () => {
  it('kelmasa joriyni qaytaradi, kelsa — o‘zini', () => {
    const current = { keep_last: 7 };
    expect(validatedLocalTarget(undefined, current)).toBe(current);
    expect(validatedLocalTarget({ keep_last: 365 }, current)).toEqual({ keep_last: 365 });
  });

  it.each([0, 366])('keep_last=%i -> 422 bad_value (targets)', (keep) => {
    const e = apiError(() => validatedLocalTarget({ keep_last: keep }, { keep_last: 7 }));
    expect([e.status, e.code, e.field]).toEqual([422, 'bad_value', 'targets']);
  });
});

describe('validatedS3Target', () => {
  it('kelmasa joriyni qaytaradi', () => {
    expect(validatedS3Target(undefined, S3_CURRENT)).toBe(S3_CURRENT);
  });

  it('maydonlarni ko‘chiradi, sirni javobga chiqarmaydi', () => {
    const out = validatedS3Target({ ...S3_IN, secret_key: 'SK' }, S3_CURRENT);
    expect(out).toEqual({ ...S3_IN, has_secret_key: true });
    expect(out).not.toHaveProperty('secret_key');
  });

  it.each([
    ['sir yangilanmasa — eskisi saqlanadi', undefined, true, true],
    ['sir yangilanmasa, avval yo‘q edi', undefined, false, false],
    ['bo‘sh sir — yangilanmaydi', '', false, false],
  ])('%s', (_n, secret, had, expected) => {
    expect(validatedS3Target({ ...S3_IN, secret_key: secret }, { ...S3_CURRENT, has_secret_key: had }).has_secret_key).toBe(expected);
  });

  it.each(['endpoint', 'bucket', 'access_key'] as const)('yoqilgan, %s bo‘sh -> 422', (field) => {
    const e = apiError(() => validatedS3Target({ ...S3_IN, [field]: '' }, S3_CURRENT));
    expect([e.status, e.message]).toEqual([422, 'S3 uchun endpoint, bucket va kalit toʻldirilishi kerak.']);
  });

  it('o‘chirilgan bo‘lsa bo‘sh maydonlar ruxsat', () => {
    expect(validatedS3Target({ ...S3_IN, enabled: false, endpoint: '', bucket: '', access_key: '' }, S3_CURRENT).enabled).toBe(false);
  });

  it.each([0, 366])('keep_last=%i -> 422', (keep) => {
    expect(apiError(() => validatedS3Target({ ...S3_IN, keep_last: keep }, S3_CURRENT)).message).toMatch(/1–365/);
  });

  it.each([1, 365])('keep_last=%i chegarasi ruxsat', (keep) => {
    expect(validatedS3Target({ ...S3_IN, keep_last: keep }, S3_CURRENT).keep_last).toBe(keep);
  });
});

describe('validatedSftpTarget', () => {
  it('kelmasa joriyni qaytaradi', () => {
    expect(validatedSftpTarget(undefined, SFTP_CURRENT, 'old.host')).toBe(SFTP_CURRENT);
  });

  it('maydonlarni ko‘chiradi, parol/kalitni chiqarmaydi, ishonchli host izini saqlaydi', () => {
    const out = validatedSftpTarget({ ...SFTP_IN, password: 'pw', key: 'k' }, SFTP_CURRENT, 'old.host');
    expect(out).toEqual({ ...SFTP_IN, has_password: true, has_key: true, host_key_fp: 'SHA256:x' });
    expect(out).not.toHaveProperty('password');
    expect(out).not.toHaveProperty('key');
  });

  it.each([
    ['yangilanmasa eskisi saqlanadi', undefined, true, true],
    ['yangilanmasa, avval yo‘q', undefined, false, false],
    ['bo‘sh qiymat yangilamaydi', '', false, false],
  ])('parol/kalit: %s', (_n, value, had, expected) => {
    const out = validatedSftpTarget({ ...SFTP_IN, password: value, key: value }, { ...SFTP_CURRENT, has_password: had, has_key: had }, 'old.host');
    expect([out.has_password, out.has_key]).toEqual([expected, expected]);
  });

  it.each([
    ['host almashdi', 'new.host', 'old.host'],
    ['host ishonilmagan', 'old.host', null],
    ['ishonchli host bo‘sh', 'old.host', ''],
  ])('%s -> host_key_fp tozalanadi', (_n, host, trusted) => {
    expect(validatedSftpTarget({ ...SFTP_IN, host }, SFTP_CURRENT, trusted).host_key_fp).toBeNull();
  });

  it.each(['host', 'user'] as const)('yoqilgan, %s bo‘sh -> 422', (field) => {
    const e = apiError(() => validatedSftpTarget({ ...SFTP_IN, [field]: '' }, SFTP_CURRENT, 'old.host'));
    expect([e.status, e.field, e.message]).toEqual([422, 'targets', 'SFTP uchun server va foydalanuvchi toʻldirilishi kerak.']);
  });

  it('o‘chirilgan bo‘lsa bo‘sh host/user ruxsat', () => {
    expect(validatedSftpTarget({ ...SFTP_IN, enabled: false, host: '', user: '' }, SFTP_CURRENT, null).enabled).toBe(false);
  });

  it.each([0, 366])('keep_last=%i -> 422', (keep) => {
    expect(apiError(() => validatedSftpTarget({ ...SFTP_IN, keep_last: keep }, SFTP_CURRENT, 'old.host')).message).toMatch(/1–365/);
  });
});

describe('jobStep', () => {
  const steps = ['dump', 'files', 'upload'];
  it.each([
    [0, 'dump'], [33, 'dump'], [34, 'files'], [66, 'files'], [67, 'upload'], [99, 'upload'], [100, 'upload'], [150, 'upload'],
  ])('progress=%i -> %s', (progress, step) => {
    expect(jobStep(steps, progress)).toBe(step);
  });

  it('bosqich yo‘q -> bo‘sh satr', () => {
    expect(jobStep([], 50)).toBe('');
  });
});
