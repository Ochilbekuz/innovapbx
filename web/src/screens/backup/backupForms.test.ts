import { describe, expect, it } from 'vitest';
import type { Backup, BackupCopy, BackupSchedule, RestoreJob } from '@/api/types';
import {
  backupFailedToast, backupFinishedToast, backupSettingsPayload, backupStatusTone, canRestoreFrom, copyByTarget, copyStatusTone, createBackupPayload,
  createdByLabel, hasFetchableRemoteCopy, hasOkLocalCopy, localPayload, nextScheduledAt, passphrasePayload,
  passphraseStrength, passphraseValid, restoreConfirmValid, restorePayload, restoreStatusTone, s3Payload, s3Valid,
  schedulePayload, scheduleValid, sftpPayload, sftpValid, startedByLabel, toggleComponent, formatBytes,
  type LocalFormState, type S3FormState, type ScheduleFormState, type SftpFormState,
} from './backupForms';

const COPY = (target: BackupCopy['target'], status: BackupCopy['status']): BackupCopy =>
  ({ target, status, remote_path: status === 'ok' ? '/x' : null, size_bytes: status === 'ok' ? 10 : null, error: status === 'failed' ? 'xato' : null, uploaded_at: null });

const BACKUP = (status: Backup['status'], copies: BackupCopy[]): Backup => ({
  id: 'bk-1', kind: 'manual', status, components: ['config'], step: null, progress: 100, file_name: 'f.ibk',
  sha256: 'a', manifest: null, size_bytes: 1024, copies, created_by: null, created_at: '2026-01-01T00:00:00Z',
});

describe('formatBytes', () => {
  it('null/undefined — "—"', () => { expect(formatBytes(null)).toBe('—'); expect(formatBytes(undefined)).toBe('—'); });
  it('1024 dan kam — bayt', () => { expect(formatBytes(512)).toBe('512 B'); });
  it('katta qiymat — mos birlikka oʻtadi', () => { expect(formatBytes(26_738_688)).toBe('26 MB'); });
});

describe('tone funksiyalari', () => {
  it('backupStatusTone', () => {
    expect(backupStatusTone('ok')).toBe('success');
    expect(backupStatusTone('running')).toBe('info');
    expect(backupStatusTone('partial')).toBe('warning');
    expect(backupStatusTone('failed')).toBe('danger');
  });
  it('copyStatusTone', () => {
    expect(copyStatusTone('ok')).toBe('success');
    expect(copyStatusTone('pending')).toBe('info');
    expect(copyStatusTone('deleted')).toBe('neutral');
    expect(copyStatusTone('failed')).toBe('danger');
  });
  it('restoreStatusTone', () => {
    expect(restoreStatusTone('ok')).toBe('success');
    expect(restoreStatusTone('running')).toBe('info');
    expect(restoreStatusTone('failed')).toBe('danger');
  });
});

describe('toggleComponent / createBackupPayload', () => {
  it('yoʻq boʻlsa qoʻshadi, bor boʻlsa olib tashlaydi', () => {
    expect(toggleComponent(['config'], 'sounds')).toEqual(['config', 'sounds']);
    expect(toggleComponent(['config', 'sounds'], 'sounds')).toEqual(['config']);
  });
  it('createBackupPayload — components massivini payloadga oʻraydi', () => {
    expect(createBackupPayload(['config'])).toEqual({ components: ['config'] });
  });
});

describe('zaxiralar jadvali yordamchilari', () => {
  it('hasOkLocalCopy — lokal nusxa ok boʻlsa true', () => {
    expect(hasOkLocalCopy(BACKUP('ok', [COPY('local', 'ok')]))).toBe(true);
    expect(hasOkLocalCopy(BACKUP('ok', [COPY('local', 'failed')]))).toBe(false);
  });
  it('hasFetchableRemoteCopy — lokal yoʻq, masofaviy ok boʻlsa true', () => {
    expect(hasFetchableRemoteCopy(BACKUP('ok', [COPY('s3', 'ok')]))).toBe(true);
  });
  it('hasFetchableRemoteCopy — lokal ok boʻlsa false (fetch kerak emas)', () => {
    expect(hasFetchableRemoteCopy(BACKUP('ok', [COPY('local', 'ok'), COPY('s3', 'ok')]))).toBe(false);
  });
  it('copyByTarget — mos nusxani topadi, boʻlmasa undefined', () => {
    const b = BACKUP('ok', [COPY('local', 'ok')]);
    expect(copyByTarget(b, 'local')?.status).toBe('ok');
    expect(copyByTarget(b, 'sftp')).toBeUndefined();
  });
  it('canRestoreFrom — faqat ok/partial holatdan tiklash mumkin', () => {
    expect(canRestoreFrom(BACKUP('ok', []))).toBe(true);
    expect(canRestoreFrom(BACKUP('partial', []))).toBe(true);
    expect(canRestoreFrom(BACKUP('running', []))).toBe(false);
    expect(canRestoreFrom(BACKUP('failed', []))).toBe(false);
  });
});

describe('nextScheduledAt', () => {
  const now = new Date('2026-10-29T10:00:00Z');
  it('oʻchirilgan jadval — null', () => {
    const s: BackupSchedule = { enabled: false, frequency: 'daily', weekday: 1, time: '03:00', components: ['config'] };
    expect(nextScheduledAt(s, now)).toBeNull();
  });
  it('daily — vaqt oʻtib ketgan boʻlsa ertaga', () => {
    const s: BackupSchedule = { enabled: true, frequency: 'daily', weekday: 1, time: '03:00', components: ['config'] };
    const next = nextScheduledAt(s, now)!;
    expect(next.getUTCDate()).toBe(now.getUTCDate() + 1);
  });
  it('daily — vaqt hali kelmagan boʻlsa bugun', () => {
    const s: BackupSchedule = { enabled: true, frequency: 'daily', weekday: 1, time: '23:00', components: ['config'] };
    const next = nextScheduledAt(s, now)!;
    expect(next.getUTCDate()).toBe(now.getUTCDate());
  });
  it('weekly — mos hafta kuniga qadar ildiraydi', () => {
    const s: BackupSchedule = { enabled: true, frequency: 'weekly', weekday: 7, time: '03:00', components: ['config'] };
    const next = nextScheduledAt(s, now)!;
    expect(next.getDay()).toBe(0); // 7 = yakshanba -> JS getDay() 0
    expect(next > now).toBe(true);
  });
});

describe('schedule/local/S3/SFTP forma validatsiyasi va payloadi', () => {
  it('scheduleValid — vaqt formati va kamida 1 qism shart', () => {
    const base: ScheduleFormState = { enabled: true, frequency: 'daily', weekday: 1, time: '03:00', components: ['config'] };
    expect(scheduleValid(base)).toBe(true);
    expect(scheduleValid({ ...base, time: '25:99' })).toBe(false);
    expect(scheduleValid({ ...base, components: [] })).toBe(false);
  });
  it('schedulePayload — state\'ni BackupSchedule shakliga oʻtkazadi', () => {
    const s: ScheduleFormState = { enabled: true, frequency: 'daily', weekday: 1, time: '03:00', components: ['config'] };
    expect(schedulePayload(s)).toEqual({ enabled: true, frequency: 'daily', weekday: 1, time: '03:00', components: ['config'] });
  });
  it('localPayload — keepLast ni keep_last qilib oʻraydi', () => {
    const s: LocalFormState = { keepLast: 5 };
    expect(localPayload(s)).toEqual({ keep_last: 5 });
  });

  const s3Base: S3FormState = {
    enabled: true, endpoint: 'https://s3', region: 'r', bucket: 'b', prefix: '', accessKey: 'ak',
    secretKey: '', pathStyle: false, keepLast: 7, hasSecretKey: true,
  };
  it('s3Valid — oʻchirilgan boʻlsa har doim valid', () => {
    expect(s3Valid({ ...s3Base, enabled: false, endpoint: '' })).toBe(true);
  });
  it('s3Valid — yoqilgan boʻlsa endpoint/bucket/accessKey va (saqlangan yoki yangi) secret shart', () => {
    expect(s3Valid(s3Base)).toBe(true);
    expect(s3Valid({ ...s3Base, endpoint: '' })).toBe(false);
    expect(s3Valid({ ...s3Base, hasSecretKey: false, secretKey: '' })).toBe(false);
    expect(s3Valid({ ...s3Base, hasSecretKey: false, secretKey: 'yangi' })).toBe(true);
  });
  it('s3Payload — secretKey boʻsh boʻlsa jo\'natilmaydi, toʻldirilgan boʻlsa qoʻshiladi', () => {
    expect(s3Payload(s3Base)).not.toHaveProperty('secret_key');
    expect(s3Payload({ ...s3Base, secretKey: 'yangi-sir' })).toMatchObject({ secret_key: 'yangi-sir' });
  });

  const sftpBase: SftpFormState = {
    enabled: true, host: 'h', port: 22, user: 'u', password: '', key: '', folder: '/b', keepLast: 7,
    hasPassword: true, hasKey: false,
  };
  it('sftpValid — oʻchirilgan boʻlsa har doim valid', () => {
    expect(sftpValid({ ...sftpBase, enabled: false, host: '' })).toBe(true);
  });
  it('sftpValid — yoqilgan boʻlsa host/user va (saqlangan yoki yangi) maxfiylik shart', () => {
    expect(sftpValid(sftpBase)).toBe(true);
    expect(sftpValid({ ...sftpBase, host: '' })).toBe(false);
    expect(sftpValid({ ...sftpBase, hasPassword: false, hasKey: false, password: '', key: '' })).toBe(false);
    expect(sftpValid({ ...sftpBase, hasPassword: false, hasKey: false, key: 'kalit' })).toBe(true);
  });
  it('sftpPayload — password/key boʻsh boʻlsa jo\'natilmaydi', () => {
    expect(sftpPayload(sftpBase)).not.toHaveProperty('password');
    expect(sftpPayload({ ...sftpBase, password: 'p' })).toMatchObject({ password: 'p' });
    expect(sftpPayload({ ...sftpBase, key: 'k' })).toMatchObject({ key: 'k' });
  });

  it('backupSettingsPayload — toʻrtta formani bitta UpdateBackupSettingsPayloadga yigʻadi', () => {
    const payload = backupSettingsPayload(
      { enabled: true, frequency: 'daily', weekday: 1, time: '03:00', components: ['config'] },
      { keepLast: 7 }, s3Base, sftpBase, '2026-01-01T00:00:00Z',
    );
    expect(payload.updated_at).toBe('2026-01-01T00:00:00Z');
    expect(payload.schedule?.time).toBe('03:00');
    expect(payload.targets?.local).toEqual({ keep_last: 7 });
  });
});

describe('zaxira paroli', () => {
  it('passphraseStrength — 12 dan kam = weak', () => { expect(passphraseStrength('short')).toBe('weak'); });
  it('passphraseStrength — 16+ va 3+ turdagi belgi = strong', () => { expect(passphraseStrength('Abcdef123456!@#$')).toBe('strong'); });
  it('passphraseStrength — 12-15 yoki tur yetarli emas = fair', () => { expect(passphraseStrength('abcdefghijkl')).toBe('fair'); });

  it('passphraseValid — yangi parol 12 belgidan kam boʻlsa invalid', () => {
    expect(passphraseValid({ current: '', next: 'short' }, false)).toBe(false);
  });
  it('passphraseValid — parol birinchi marta oʻrnatilayotganda joriy parol kerak emas', () => {
    expect(passphraseValid({ current: '', next: 'uzun-yangi-parol' }, false)).toBe(true);
  });
  it('passphraseValid — almashtirishda joriy parol shart', () => {
    expect(passphraseValid({ current: '', next: 'uzun-yangi-parol' }, true)).toBe(false);
    expect(passphraseValid({ current: 'eski', next: 'uzun-yangi-parol' }, true)).toBe(true);
  });
  it('passphrasePayload — almashtirishda current qoʻshiladi, birinchi marta oʻrnatishda yoʻq', () => {
    expect(passphrasePayload({ current: '', next: 'yangi' }, false)).toEqual({ passphrase: 'yangi' });
    expect(passphrasePayload({ current: 'eski', next: 'yangi' }, true)).toEqual({ passphrase: 'yangi', current: 'eski' });
  });
});

describe('fayldan tiklash', () => {
  it('restoreConfirmValid — faqat aniq "TIKLASH" soʻzi', () => {
    expect(restoreConfirmValid('TIKLASH')).toBe(true);
    expect(restoreConfirmValid('tiklash')).toBe(false);
    expect(restoreConfirmValid('')).toBe(false);
  });
  it('restorePayload — parol/force boʻsh boʻlsa qoʻshilmaydi', () => {
    expect(restorePayload('', false)).toEqual({ confirm: 'TIKLASH' });
    expect(restorePayload('parol', true)).toEqual({ confirm: 'TIKLASH', passphrase: 'parol', force: true });
  });
});

describe('startedByLabel / createdByLabel', () => {
  const JOB: RestoreJob = {
    id: 'rj-1', backup_id: null, source: 'upload', status: 'ok', step: null, progress: 100, error: null,
    force: false, pre_restore_backup_id: null, started_by: null, started_at: '2026-01-01T00:00:00Z', finished_at: null,
  };
  it('started_by yoʻq boʻlsa — nomaʼlum', () => { expect(startedByLabel(JOB, 'Nomaʼlum')).toBe('Nomaʼlum'); });
  it('started_by bor boʻlsa — login', () => {
    expect(startedByLabel({ ...JOB, started_by: { id: 'u-1', login: 'admin' } }, 'Nomaʼlum')).toBe('admin');
  });
  it('created_by yoʻq boʻlsa — nomaʼlum', () => { expect(createdByLabel(BACKUP('ok', []), 'Nomaʼlum')).toBe('Nomaʼlum'); });
  it('created_by bor boʻlsa — login', () => {
    expect(createdByLabel({ ...BACKUP('ok', []), created_by: { id: 'u-1', login: 'admin' } }, 'Nomaʼlum')).toBe('admin');
  });
});

describe('zaxiralash ishi tugashi toastlari', () => {
  const t = (k: string, o?: Record<string, unknown>) => (o ? `${k}:${JSON.stringify(o)}` : k);

  it.each([
    ['partial', { kind: 'not-applied', title: 'job.partialToast' }],
    ['ok', { kind: 'success', title: 'job.okToast' }],
    [undefined, { kind: 'success', title: 'job.okToast' }],
  ] as const)('eng so‘nggi zaxira %s -> mos toast', (latest, expected) => {
    expect(backupFinishedToast(latest, t)).toEqual(expected);
  });

  it.each([
    ['disk to‘la', 'job.failedToast:{"error":"disk to‘la"}'],
    [null, 'job.failedToast:{"error":""}'],
    [undefined, 'job.failedToast:{"error":""}'],
  ])('xato %s -> error toast', (error, title) => {
    expect(backupFailedToast(error, t)).toEqual({ kind: 'error', title });
  });
});
