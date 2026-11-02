import { describe, expect, it } from 'vitest';
import type { MigrationJob, MigrationPlanItem } from '@/api/types';
import {
  activeMigrationJob, applyMigrationPayload, availablePatchActions, bundleFileValid, byKindRows, migrationConfirmValid,
  migrationJobStatusTone, planActionTone, planItemKey, sshFetchPayload, sshTestPayload, sshTestValid, wizardStep,
} from './migrationForms';

const JOB = (status: MigrationJob['status'], created_at = '2026-01-01T00:00:00Z'): MigrationJob => ({
  id: `mjob-${status}`, source: 'upload', status, step: null, progress: 0,
  source_meta: null, summary: null, options: { rotate_weak_secrets: false }, result: null, error: null,
  pre_import_backup_id: null, backup_ready: true, created_by: null, created_at, finished_at: null,
});

const ITEM = (action: MigrationPlanItem['action'], replaceable = false): MigrationPlanItem => ({
  kind: 'extension', source_ref: 'users:1', name: 'A', number: '1', action, reason: null,
  warnings: [], depends_on: [], replaceable, has_secret: false, weak_secret: false,
});

describe('wizardStep', () => {
  it('ish yoʻq — manba bosqichi', () => { expect(wizardStep(null, false)).toBe('source'); });
  it('uploaded/analyzing — tahlil bosqichi', () => {
    expect(wizardStep(JOB('uploaded'), false)).toBe('analyze');
    expect(wizardStep(JOB('analyzing'), false)).toBe('analyze');
  });
  it('analyzed — reviewConfirmed holatiga qarab koʻrib chiqish yoki qoʻllash', () => {
    expect(wizardStep(JOB('analyzed'), false)).toBe('review');
    expect(wizardStep(JOB('analyzed'), true)).toBe('apply');
  });
  it('applying — qoʻllash bosqichi', () => { expect(wizardStep(JOB('applying'), false)).toBe('apply'); });
  it('ok/failed — natija bosqichi', () => {
    expect(wizardStep(JOB('ok'), false)).toBe('result');
    expect(wizardStep(JOB('failed'), false)).toBe('result');
  });
});

describe('activeMigrationJob', () => {
  it('royxat boʻsh boʻlsa — null', () => { expect(activeMigrationJob([])).toBeNull(); });
  it('faqat tugallangan ishlar boʻlsa — null', () => {
    expect(activeMigrationJob([JOB('ok'), JOB('failed')])).toBeNull();
  });
  it('tugallanmagan ishlar orasida eng soʻnggisini qaytaradi', () => {
    const older = JOB('uploaded', '2026-01-01T00:00:00Z');
    const newer = JOB('analyzing', '2026-01-02T00:00:00Z');
    expect(activeMigrationJob([older, newer, JOB('ok')])).toBe(newer);
  });
});

describe('tone funksiyalari', () => {
  it('migrationJobStatusTone', () => {
    expect(migrationJobStatusTone('uploaded')).toBe('neutral');
    expect(migrationJobStatusTone('analyzing')).toBe('info');
    expect(migrationJobStatusTone('ok')).toBe('success');
    expect(migrationJobStatusTone('failed')).toBe('danger');
  });
  it('planActionTone', () => {
    expect(planActionTone('create')).toBe('success');
    expect(planActionTone('skip')).toBe('neutral');
    expect(planActionTone('conflict')).toBe('warning');
    expect(planActionTone('unsupported')).toBe('danger');
  });
});

describe('migrationConfirmValid / applyMigrationPayload', () => {
  it('faqat aniq "KOCHIRISH" soʻzi toʻgʻri', () => {
    expect(migrationConfirmValid('KOCHIRISH')).toBe(true);
    expect(migrationConfirmValid('kochirish')).toBe(false);
    expect(migrationConfirmValid('')).toBe(false);
  });
  it('applyMigrationPayload — tasdiq soʻzi + rotate_weak_secrets optsiyasi', () => {
    expect(applyMigrationPayload(true)).toEqual({ confirm: 'KOCHIRISH', options: { rotate_weak_secrets: true } });
    expect(applyMigrationPayload(false)).toEqual({ confirm: 'KOCHIRISH', options: { rotate_weak_secrets: false } });
  });
});

describe('availablePatchActions', () => {
  it('conflict + replaceable — skip/replace', () => {
    expect(availablePatchActions(ITEM('conflict', true))).toEqual(['skip', 'replace']);
  });
  it('conflict + replaceable emas — faqat skip', () => {
    expect(availablePatchActions(ITEM('conflict', false))).toEqual(['skip']);
  });
  it('create — faqat skip', () => { expect(availablePatchActions(ITEM('create'))).toEqual(['skip']); });
  it('skip — faqat create', () => { expect(availablePatchActions(ITEM('skip'))).toEqual(['create']); });
  it('unsupported — boʻsh', () => { expect(availablePatchActions(ITEM('unsupported'))).toEqual([]); });
});

describe('planItemKey', () => {
  it('kind:source_ref formatida', () => {
    expect(planItemKey({ kind: 'extension', source_ref: 'users:101' })).toBe('extension:users:101');
  });
});

describe('byKindRows', () => {
  it('summary yoʻq boʻlsa — boʻsh massiv', () => { expect(byKindRows(null)).toEqual([]); });
  it('har tur boʻyicha jami va toʻqnashuvlarni hisoblaydi', () => {
    const summary = { by_kind: { extension: { create: 4, skip: 1, conflict: 1, unsupported: 0 } }, warnings: 0, ignored: 0, weak_secrets: 0 };
    expect(byKindRows(summary)).toEqual([{ kind: 'extension', total: 6, conflicts: 1 }]);
  });
});

describe('bundleFileValid', () => {
  it('fayl yoʻq — notoʻgʻri', () => { expect(bundleFileValid(null)).toBe(false); });
  it('.tar.gz/.tgz — toʻgʻri', () => {
    expect(bundleFileValid(new File([''], 'export.tar.gz'))).toBe(true);
    expect(bundleFileValid(new File([''], 'export.tgz'))).toBe(true);
  });
  it('boshqa kengaytma — notoʻgʻri', () => { expect(bundleFileValid(new File([''], 'export.zip'))).toBe(false); });
});

describe('SSH forma yordamchilari', () => {
  const BASE = { host: '10.0.0.5', port: 22, username: 'root', password: '', privateKey: '' };
  it('sshTestValid — host+username+(password yoki privateKey) boʻlsa toʻgʻri', () => {
    expect(sshTestValid(BASE)).toBe(false);
    expect(sshTestValid({ ...BASE, password: 'p' })).toBe(true);
    expect(sshTestValid({ ...BASE, privateKey: 'k' })).toBe(true);
  });
  it('sshTestPayload — faqat toʻldirilgan maydon yuboriladi', () => {
    expect(sshTestPayload({ ...BASE, password: 'p' })).toEqual({ host: '10.0.0.5', port: 22, username: 'root', password: 'p' });
    expect(sshTestPayload({ ...BASE, privateKey: 'k' })).toEqual({ host: '10.0.0.5', port: 22, username: 'root', private_key: 'k' });
  });
  it('sshFetchPayload — host_key_fp qoʻshiladi', () => {
    expect(sshFetchPayload({ ...BASE, password: 'p' }, 'SHA256:x')).toEqual({ host: '10.0.0.5', port: 22, username: 'root', password: 'p', host_key_fp: 'SHA256:x' });
  });
});
