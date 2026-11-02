// `screens/migration/*` sehrgari uchun sof funksiyalar — qarang `screens/backup/backupForms.ts`
// izohi: bir xil sabab (CRAP'ni past ushlab turish uchun JSX'dagi shoxlanishni chiqarish).
import { useState } from 'react';
import type {
  ApplyMigrationPayload, MigrationAction, MigrationJob, MigrationJobStatus, MigrationKind, MigrationPatchAction,
  MigrationPlanItem, SshFetchPayload, SshTestPayload,
} from '@/api/types';
import type { Tone } from '@/ui/Status';

export type WizardStep = 'source' | 'analyze' | 'review' | 'apply' | 'result';

/**
 * Joriy ishning holatidan sehrgar bosqichini aniqlaydi — sahifa ochilganda faol ishni davom ettirish uchun.
 * `analyzed` holati ikki bosqichni (3-Ko'rib chiqish, 4-Qo'llash) qamrab oladi — ular orasidagi o'tish
 * UI'ning o'zida ("Davom etish" tugmasi) hal qilinadi, shuning uchun `reviewConfirmed` beriladi.
 */
export function wizardStep(job: Pick<MigrationJob, 'status'> | null | undefined, reviewConfirmed: boolean): WizardStep {
  if (!job) return 'source';
  if (job.status === 'analyzed') return reviewConfirmed ? 'apply' : 'review';
  const map: Record<MigrationJobStatus, WizardStep> = {
    uploaded: 'analyze', analyzing: 'analyze', analyzed: 'review', applying: 'apply', ok: 'result', failed: 'result',
  };
  return map[job.status];
}

const UNFINISHED_STATUSES: MigrationJobStatus[] = ['uploaded', 'analyzing', 'analyzed', 'applying'];

/** Tugallanmagan (`ok`/`failed` emas) eng so'nggi ish — sahifa ochilganda sehrgarni shu ish bilan davom ettirish uchun. */
export function activeMigrationJob(jobs: readonly MigrationJob[]): MigrationJob | null {
  const unfinished = jobs.filter((j) => UNFINISHED_STATUSES.includes(j.status));
  if (unfinished.length === 0) return null;
  return [...unfinished].sort((a, b) => (a.created_at < b.created_at ? 1 : -1))[0] ?? null;
}

const JOB_STATUS_TONE: Record<MigrationJobStatus, Tone> = {
  uploaded: 'neutral', analyzing: 'info', analyzed: 'info', applying: 'info', ok: 'success', failed: 'danger',
};
export function migrationJobStatusTone(status: MigrationJobStatus): Tone {
  return JOB_STATUS_TONE[status];
}

const PLAN_ACTION_TONE: Record<MigrationAction, Tone> = {
  create: 'success', skip: 'neutral', conflict: 'warning', unsupported: 'danger',
};
export function planActionTone(action: MigrationAction): Tone {
  return PLAN_ACTION_TONE[action];
}

export const MIGRATION_CONFIRM_WORD = 'KOCHIRISH';

export function migrationConfirmValid(text: string): boolean {
  return text === MIGRATION_CONFIRM_WORD;
}

export function applyMigrationPayload(rotateWeakSecrets: boolean): ApplyMigrationPayload {
  return { confirm: MIGRATION_CONFIRM_WORD, options: { rotate_weak_secrets: rotateWeakSecrets } };
}

/** PATCH uchun qaysi amallar tanlanishi mumkin: conflict→skip|replace (faqat `replaceable`), create→skip, skip→create. */
export function availablePatchActions(item: MigrationPlanItem): MigrationPatchAction[] {
  if (item.action === 'conflict') return item.replaceable ? ['skip', 'replace'] : ['skip'];
  if (item.action === 'create') return ['skip'];
  if (item.action === 'skip') return ['create'];
  return [];
}

export function planItemKey(item: Pick<MigrationPlanItem, 'kind' | 'source_ref'>): string {
  return `${item.kind}:${item.source_ref}`;
}

/** Turlar bo'yicha "Ko'rib chiqish" kartalari uchun — har tur bo'yicha jami va to'qnashuvlar soni. */
export function byKindRows(summary: MigrationJob['summary']): { kind: MigrationKind; total: number; conflicts: number }[] {
  if (!summary) return [];
  return Object.entries(summary.by_kind).map(([kind, row]) => ({
    kind: kind as MigrationKind,
    total: row.create + row.skip + row.conflict + row.unsupported,
    conflicts: row.conflict,
  }));
}

// ── Manba: to'plam yuklash ──────────────────────────────────────────────────────────────────

export function bundleFileValid(file: File | null): boolean {
  return !!file && /\.(tar\.gz|tgz)$/i.test(file.name);
}

// ── Manba: SSH orqali olib kelish ───────────────────────────────────────────────────────────

export type SshFormState = { host: string; port: number; username: string; password: string; privateKey: string };
const EMPTY_SSH_FORM: SshFormState = { host: '', port: 22, username: '', password: '', privateKey: '' };

export function sshTestValid(state: SshFormState): boolean {
  return !!state.host && !!state.username && (!!state.password || !!state.privateKey);
}

export function sshTestPayload(state: SshFormState): SshTestPayload {
  return {
    host: state.host, port: state.port, username: state.username,
    ...(state.password ? { password: state.password } : {}),
    ...(state.privateKey ? { private_key: state.privateKey } : {}),
  };
}

export function sshFetchPayload(state: SshFormState, hostKeyFp: string): SshFetchPayload {
  return { ...sshTestPayload(state), host_key_fp: hostKeyFp };
}

export function useSshForm() {
  const [state, setState] = useState<SshFormState>(EMPTY_SSH_FORM);
  return {
    state,
    setHost: (v: string) => setState((p) => ({ ...p, host: v })),
    setPort: (v: number) => setState((p) => ({ ...p, port: v })),
    setUsername: (v: string) => setState((p) => ({ ...p, username: v })),
    setPassword: (v: string) => setState((p) => ({ ...p, password: v })),
    setPrivateKey: (v: string) => setState((p) => ({ ...p, privateKey: v })),
    reset: () => setState(EMPTY_SSH_FORM),
  };
}
