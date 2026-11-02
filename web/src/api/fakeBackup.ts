/** Demo (fake) klient uchun zaxira qoidalari — manzillar validatsiyasi (backend `backup_settings` nusxasi) va ish bosqichi. */
import { ApiError } from './errors';
import type { BackupLocalTarget, BackupS3Target, BackupSftpTarget } from './types';

export type S3TargetInput = Omit<BackupS3Target, 'has_secret_key'> & { secret_key?: string };
export type SftpTargetInput = Omit<BackupSftpTarget, 'has_password' | 'has_key' | 'host_key_fp'> & { password?: string; key?: string };

function badTarget(message: string): never {
  throw new ApiError(422, { code: 'bad_value', message, field: 'targets' });
}

function requireKeepLast(keepLast: number) {
  if (keepLast < 1 || keepLast > 365) badTarget('Saqlanadigan nusxalar soni 1–365 oraligʻida boʻlishi kerak.');
}

export function validatedLocalTarget(incoming: BackupLocalTarget | undefined, current: BackupLocalTarget): BackupLocalTarget {
  if (!incoming) return current;
  requireKeepLast(incoming.keep_last);
  return incoming;
}

export function validatedS3Target(incoming: S3TargetInput | undefined, current: BackupS3Target): BackupS3Target {
  if (!incoming) return current;
  const { secret_key, ...rest } = incoming;
  if (rest.enabled && !(rest.endpoint && rest.bucket && rest.access_key)) badTarget('S3 uchun endpoint, bucket va kalit toʻldirilishi kerak.');
  requireKeepLast(rest.keep_last);
  return { ...rest, has_secret_key: Boolean(secret_key) || current.has_secret_key };
}

export function validatedSftpTarget(incoming: SftpTargetInput | undefined, current: BackupSftpTarget, trustedHost: string | null): BackupSftpTarget {
  if (!incoming) return current;
  const { password, key, ...rest } = incoming;
  if (rest.enabled && !(rest.host && rest.user)) badTarget('SFTP uchun server va foydalanuvchi toʻldirilishi kerak.');
  requireKeepLast(rest.keep_last);
  const keepFingerprint = rest.host === current.host && Boolean(trustedHost);
  return {
    ...rest,
    has_password: Boolean(password) || current.has_password,
    has_key: Boolean(key) || current.has_key,
    host_key_fp: keepFingerprint ? current.host_key_fp : null,
  };
}

/** Progress (0–100) bo'yicha joriy bosqich nomi — oxirgi bosqichdan oshmaydi; bosqich yo'q bo'lsa ''. */
export function jobStep(steps: readonly string[], progress: number): string {
  const idx = Math.min(steps.length - 1, Math.floor((progress / 100) * steps.length));
  return steps[Math.max(0, idx)] ?? '';
}
