// `screens/backup/*` tabidagi formalar/jadval/progress logikasi — sof funksiyalar va kichik
// hook'larga ajratilgan (qarang `devices/deviceForms.ts` izohi — bir xil sabab: CRAP'ni past
// ushlab turish uchun JSX'dagi shoxlanishni chiqarish).
import { useState } from 'react';
import type {
  Backup, BackupComponent, BackupCopy, BackupCopyStatus, BackupLocalTarget, BackupS3Target, BackupSchedule,
  BackupScheduleFrequency, BackupSettings, BackupSftpTarget, BackupStatus, BackupTargetKind,
  CreateBackupPayload, RestoreBackupPayload, RestoreJob, RestoreJobStatus, UpdateBackupPassphrasePayload,
  UpdateBackupSettingsPayload, Weekday,
} from '@/api/types';
import type { Tone } from '@/ui/Status';
import type { ToastInput } from '@/ui/Toast';

// ── Hajm formatlash ──────────────────────────────────────────────────────────────────────────

const BYTE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB'] as const;

/** Baytni odam o'qiydigan ko'rinishga o'tkazadi (1024 asosida) — `null`/`undefined` bo'lsa "—". */
export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return '—';
  if (bytes < 1024) return `${bytes} B`;
  let value = bytes;
  let unitIdx = 0;
  while (value >= 1024 && unitIdx < BYTE_UNITS.length - 1) {
    value /= 1024;
    unitIdx += 1;
  }
  const digits = value < 10 ? 1 : 0;
  return `${value.toFixed(digits)} ${BYTE_UNITS[unitIdx]}`;
}

// ── Holat/nusxa ranglari (Badge `Tone`) ──────────────────────────────────────────────────────

const BACKUP_STATUS_TONE = { ok: 'success', running: 'info', partial: 'warning', failed: 'danger' } satisfies Record<BackupStatus, Tone>;

export function backupStatusTone(status: BackupStatus): Tone {
  return BACKUP_STATUS_TONE[status];
}

const COPY_STATUS_TONE = { ok: 'success', pending: 'info', deleted: 'neutral', failed: 'danger' } satisfies Record<BackupCopyStatus, Tone>;

export function copyStatusTone(status: BackupCopyStatus): Tone {
  return COPY_STATUS_TONE[status];
}

export const COPY_TARGET_ORDER: BackupTargetKind[] = ['local', 's3', 'sftp'];

const RESTORE_STATUS_TONE = { ok: 'success', running: 'info', failed: 'danger' } satisfies Record<RestoreJobStatus, Tone>;

export function restoreStatusTone(status: RestoreJobStatus): Tone {
  return RESTORE_STATUS_TONE[status];
}

// ── "Hozir zaxiralash" — qism tanlash ───────────────────────────────────────────────────────

export function toggleComponent(selected: BackupComponent[], component: BackupComponent): BackupComponent[] {
  return selected.includes(component) ? selected.filter((c) => c !== component) : [...selected, component];
}

export function createBackupPayload(components: BackupComponent[]): CreateBackupPayload {
  return { components };
}

export function useCreateBackupForm(defaults: BackupComponent[]) {
  const [components, setComponents] = useState<BackupComponent[]>(defaults);
  const toggle = (c: BackupComponent) => setComponents((prev) => toggleComponent(prev, c));
  const reset = () => setComponents(defaults);
  return { components, toggle, reset };
}

// ── Zaxiralar jadvali ────────────────────────────────────────────────────────────────────────

export function hasOkLocalCopy(backup: Backup): boolean {
  return backup.copies.some((c) => c.target === 'local' && c.status === 'ok');
}

export function hasFetchableRemoteCopy(backup: Backup): boolean {
  return backup.copies.some((c) => c.target !== 'local' && c.status === 'ok') && !hasOkLocalCopy(backup);
}

export function copyByTarget(backup: Backup, target: BackupTargetKind): BackupCopy | undefined {
  return backup.copies.find((c) => c.target === target);
}

export function canRestoreFrom(backup: Backup): boolean {
  return backup.status === 'ok' || backup.status === 'partial';
}

// ── Keyingi rejalashtirilgan zaxira vaqti ───────────────────────────────────────────────────

/** Jadval asosida keyingi ishga tushish momentini hisoblaydi — `schedule.weekday`: 1=Dushanba..7=Yakshanba. */
export function nextScheduledAt(schedule: BackupSchedule, now: Date = new Date()): Date | null {
  if (!schedule.enabled) return null;
  const [hhRaw, mmRaw] = schedule.time.split(':');
  const hh = Number(hhRaw ?? 0);
  const mm = Number(mmRaw ?? 0);
  const candidate = new Date(now);
  candidate.setSeconds(0, 0);
  candidate.setHours(hh, mm);
  if (schedule.frequency === 'daily') {
    if (candidate <= now) candidate.setDate(candidate.getDate() + 1);
    return candidate;
  }
  const jsTargetDay = schedule.weekday % 7; // 1..6 o'zi qoladi, 7 (yakshanba) -> 0 (Date.getDay())
  while (candidate.getDay() !== jsTargetDay || candidate <= now) candidate.setDate(candidate.getDate() + 1);
  return candidate;
}

// ── Umumiy "serverdan bir marta yuklab, keyin controlled" hook ─────────────────────────────

/** `source` kelgach (yoki `key(source)` o'zgargach) `map` orqali holatni (qayta) o'rnatadi; shu
 * oraliqda foydalanuvchi kiritgan qiymatlar saqlanadi — qayta kelgan bir xil `source` ularni
 * ustidan yozib yubormaydi. To'rtta sozlamalar formasi (jadval/lokal/S3/SFTP) shu naqshni
 * ulashadi, shuning uchun bitta generik hook'ga chiqarilgan (dryer takrorlanishni kamaytiradi). */
function useLoadedForm<Source, State>(
  source: Source | undefined, key: (s: Source) => string, map: (s: Source) => State,
): [State | null, (updater: (prev: State) => State) => void] {
  const [state, setState] = useState<State | null>(null);
  const [loadedKey, setLoadedKey] = useState<string | undefined>(undefined);
  if (source && key(source) !== loadedKey) {
    setLoadedKey(key(source));
    setState(map(source));
  }
  const update = (updater: (prev: State) => State) => setState((prev) => (prev ? updater(prev) : prev));
  return [state, update];
}

// ── Jadval (schedule) ────────────────────────────────────────────────────────────────────────

export type ScheduleFormState = {
  enabled: boolean; frequency: BackupScheduleFrequency; weekday: Weekday; time: string; components: BackupComponent[];
};

function scheduleFormState(schedule: BackupSchedule): ScheduleFormState {
  return { enabled: schedule.enabled, frequency: schedule.frequency, weekday: schedule.weekday, time: schedule.time, components: schedule.components };
}

export function scheduleValid(state: ScheduleFormState): boolean {
  return /^([01]\d|2[0-3]):[0-5]\d$/.test(state.time) && state.components.length > 0;
}

export function schedulePayload(state: ScheduleFormState): BackupSchedule {
  return { enabled: state.enabled, frequency: state.frequency, weekday: state.weekday, time: state.time, components: state.components };
}

export function useScheduleForm(settings: BackupSettings | undefined) {
  const [state, update] = useLoadedForm(settings, (s) => s.updated_at, (s) => scheduleFormState(s.schedule));
  return {
    state,
    setEnabled: (v: boolean) => update((p) => ({ ...p, enabled: v })),
    setFrequency: (v: BackupScheduleFrequency) => update((p) => ({ ...p, frequency: v })),
    setWeekday: (v: Weekday) => update((p) => ({ ...p, weekday: v })),
    setTime: (v: string) => update((p) => ({ ...p, time: v })),
    toggleComponentAt: (c: BackupComponent) => update((p) => ({ ...p, components: toggleComponent(p.components, c) })),
  };
}

// ── Lokal saqlash ────────────────────────────────────────────────────────────────────────────

export type LocalFormState = { keepLast: number };

function localFormState(target: BackupLocalTarget): LocalFormState {
  return { keepLast: target.keep_last };
}

export function localPayload(state: LocalFormState): BackupLocalTarget {
  return { keep_last: state.keepLast };
}

export function useLocalForm(settings: BackupSettings | undefined) {
  const [state, update] = useLoadedForm(settings, (s) => s.updated_at, (s) => localFormState(s.targets.local));
  return { state, setKeepLast: (v: number) => update((p) => ({ ...p, keepLast: v })) };
}

// ── S3 ───────────────────────────────────────────────────────────────────────────────────────

export type S3FormState = {
  enabled: boolean; endpoint: string; region: string; bucket: string; prefix: string;
  accessKey: string; secretKey: string; pathStyle: boolean; keepLast: number; hasSecretKey: boolean;
};

function s3FormState(target: BackupS3Target): S3FormState {
  return {
    enabled: target.enabled, endpoint: target.endpoint, region: target.region, bucket: target.bucket, prefix: target.prefix,
    accessKey: target.access_key, secretKey: '', pathStyle: target.path_style, keepLast: target.keep_last, hasSecretKey: target.has_secret_key,
  };
}

export function s3Valid(state: S3FormState): boolean {
  if (!state.enabled) return true;
  return !!state.endpoint && !!state.bucket && !!state.accessKey && (state.hasSecretKey || !!state.secretKey);
}

export function s3Payload(state: S3FormState): Omit<BackupS3Target, 'has_secret_key'> & { secret_key?: string } {
  return {
    enabled: state.enabled, endpoint: state.endpoint, region: state.region, bucket: state.bucket, prefix: state.prefix,
    access_key: state.accessKey, path_style: state.pathStyle, keep_last: state.keepLast,
    ...(state.secretKey ? { secret_key: state.secretKey } : {}),
  };
}

export function useS3Form(settings: BackupSettings | undefined) {
  const [state, update] = useLoadedForm(settings, (s) => s.updated_at, (s) => s3FormState(s.targets.s3));
  return {
    state,
    setEnabled: (v: boolean) => update((p) => ({ ...p, enabled: v })),
    setEndpoint: (v: string) => update((p) => ({ ...p, endpoint: v })),
    setRegion: (v: string) => update((p) => ({ ...p, region: v })),
    setBucket: (v: string) => update((p) => ({ ...p, bucket: v })),
    setPrefix: (v: string) => update((p) => ({ ...p, prefix: v })),
    setAccessKey: (v: string) => update((p) => ({ ...p, accessKey: v })),
    setSecretKey: (v: string) => update((p) => ({ ...p, secretKey: v })),
    setPathStyle: (v: boolean) => update((p) => ({ ...p, pathStyle: v })),
    setKeepLast: (v: number) => update((p) => ({ ...p, keepLast: v })),
  };
}

// ── SFTP ─────────────────────────────────────────────────────────────────────────────────────

export type SftpFormState = {
  enabled: boolean; host: string; port: number; user: string; password: string; key: string;
  folder: string; keepLast: number; hasPassword: boolean; hasKey: boolean;
};

function sftpFormState(target: BackupSftpTarget): SftpFormState {
  return {
    enabled: target.enabled, host: target.host, port: target.port, user: target.user, password: '', key: '',
    folder: target.folder, keepLast: target.keep_last, hasPassword: target.has_password, hasKey: target.has_key,
  };
}

export function sftpValid(state: SftpFormState): boolean {
  if (!state.enabled) return true;
  return !!state.host && !!state.user && (state.hasPassword || state.hasKey || !!state.password || !!state.key);
}

export function sftpPayload(state: SftpFormState): Omit<BackupSftpTarget, 'has_password' | 'has_key' | 'host_key_fp'> & { password?: string; key?: string } {
  return {
    enabled: state.enabled, host: state.host, port: state.port, user: state.user, folder: state.folder, keep_last: state.keepLast,
    ...(state.password ? { password: state.password } : {}),
    ...(state.key ? { key: state.key } : {}),
  };
}

export function useSftpForm(settings: BackupSettings | undefined) {
  const [state, update] = useLoadedForm(settings, (s) => s.updated_at, (s) => sftpFormState(s.targets.sftp));
  return {
    state,
    setEnabled: (v: boolean) => update((p) => ({ ...p, enabled: v })),
    setHost: (v: string) => update((p) => ({ ...p, host: v })),
    setPort: (v: number) => update((p) => ({ ...p, port: v })),
    setUser: (v: string) => update((p) => ({ ...p, user: v })),
    setPassword: (v: string) => update((p) => ({ ...p, password: v })),
    setKey: (v: string) => update((p) => ({ ...p, key: v })),
    setFolder: (v: string) => update((p) => ({ ...p, folder: v })),
    setKeepLast: (v: number) => update((p) => ({ ...p, keepLast: v })),
  };
}

export function backupSettingsPayload(
  schedule: ScheduleFormState, local: LocalFormState, s3: S3FormState, sftp: SftpFormState, updatedAt: string,
): UpdateBackupSettingsPayload {
  return {
    schedule: schedulePayload(schedule),
    targets: { local: localPayload(local), s3: s3Payload(s3), sftp: sftpPayload(sftp) },
    updated_at: updatedAt,
  };
}

// ── Zaxira paroli ────────────────────────────────────────────────────────────────────────────

export type PassphraseFormState = { current: string; next: string };
const EMPTY_PASSPHRASE_FORM: PassphraseFormState = { current: '', next: '' };

export type PassphraseStrength = 'weak' | 'fair' | 'strong';

/** Taxminiy kuch — 12 belgidan kam bo'lsa zaif; 16+ va kamida 3 xil belgi turi bo'lsa kuchli. */
export function passphraseStrength(pw: string): PassphraseStrength {
  if (pw.length < 12) return 'weak';
  const varietyCount = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^a-zA-Z0-9]/].filter((re) => re.test(pw)).length;
  if (pw.length >= 16 && varietyCount >= 3) return 'strong';
  return 'fair';
}

export function passphraseValid(state: PassphraseFormState, hasPassphrase: boolean): boolean {
  if (state.next.length < 12) return false;
  return !hasPassphrase || !!state.current;
}

export function passphrasePayload(state: PassphraseFormState, hasPassphrase: boolean): UpdateBackupPassphrasePayload {
  return { passphrase: state.next, ...(hasPassphrase ? { current: state.current } : {}) };
}

export function usePassphraseForm() {
  const [state, setState] = useState<PassphraseFormState>(EMPTY_PASSPHRASE_FORM);
  const setCurrent = (v: string) => setState((p) => ({ ...p, current: v }));
  const setNext = (v: string) => setState((p) => ({ ...p, next: v }));
  const reset = () => setState(EMPTY_PASSPHRASE_FORM);
  return { state, setCurrent, setNext, reset };
}

// ── Fayldan tiklash ──────────────────────────────────────────────────────────────────────────

export const RESTORE_CONFIRM_WORD = 'TIKLASH';

export function restoreConfirmValid(text: string): boolean {
  return text === RESTORE_CONFIRM_WORD;
}

export function restorePayload(passphrase: string, force: boolean): RestoreBackupPayload {
  return { confirm: RESTORE_CONFIRM_WORD, ...(passphrase ? { passphrase } : {}), ...(force ? { force: true } : {}) };
}

export function startedByLabel(job: RestoreJob, unknown: string): string {
  return job.started_by?.login ?? unknown;
}

export function createdByLabel(backup: Backup, unknown: string): string {
  return backup.created_by?.login ?? unknown;
}

// ------------------------------------------------------------------ zaxiralash ishi tugashi
type JobToastTranslate = (k: string, o?: Record<string, unknown>) => string;

/** Ish `ok` bo'lgach: eng so'nggi zaxira `partial` bo'lsa ogohlantirish, aks holda muvaffaqiyat. */
export function backupFinishedToast(latestStatus: BackupStatus | undefined, t: JobToastTranslate): ToastInput {
  return latestStatus === 'partial' ? { kind: 'not-applied', title: t('job.partialToast') } : { kind: 'success', title: t('job.okToast') };
}

export function backupFailedToast(error: string | null | undefined, t: JobToastTranslate): ToastInput {
  return { kind: 'error', title: t('job.failedToast', { error: error ?? '' }) };
}
