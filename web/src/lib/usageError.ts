import type { ApiError } from '@/api/errors';
import type { Usage } from '@/api/types';

/** `409 in_use`'ning `details.usages` ro'yxatini chiqaradi — "kim ishlatayotgani" xabari uchun (hamma M1a ekranlarida bir xil). */
export function usagesOf(e: ApiError): Usage[] {
  return e.code === 'in_use' ? ((e.details?.usages as Usage[] | undefined) ?? []) : [];
}

/** `usage.kind` -> obyekt sahifasiga havola, bo'lmasa `undefined` (bosilmaydigan matn sifatida ko'rsatiladi). */
export const USAGE_PATH: Partial<Record<string, string>> = {
  inbound_route: '/inbound',
  time_condition: '/timegroups',
  ivr: '/ivr',
  ring_group: '/ringgroups',
  queue: '/queues',
};
