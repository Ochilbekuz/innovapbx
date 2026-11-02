import type { ApplyResult } from '@/api/types';
import type { ToastInput } from '@/ui/Toast';

/**
 * Har yozuv `apply: ApplyResult` qaytaradi — bu shuni bir xil toastʼga aylantiradi.
 * `rolled_back` — baza saqlangan, lekin dialplan tekshiruvidan oʻtmay oldingi holatga qaytarilgan; bu doim xato sifatida ko'rsatiladi.
 */
export function applyToast(apply: ApplyResult, okTitle = 'Saqlandi'): ToastInput {
  if (apply.status === 'rolled_back') {
    return { kind: 'not-applied', title: 'PBXʼga qoʻllanmadi', description: apply.message ?? 'Oʻzgarish bazada saqlandi, lekin dialplan tekshiruvidan oʻtmadi va avtomatik qaytarildi.' };
  }
  if (apply.status === 'unchanged') {
    return { kind: 'info', title: 'Oʻzgarish yoʻq', description: apply.message ?? undefined };
  }
  const desc = apply.revision !== null ? `Reviziya r${apply.revision}${apply.message ? ` — ${apply.message}` : ''}` : (apply.message ?? undefined);
  return { kind: 'success', title: okTitle, description: desc };
}
