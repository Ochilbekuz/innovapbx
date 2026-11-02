// Integratsiyalar formalari oʻrtasida ulashiladigan mutatsiya-xato yordamchisi va bir martalik sir modali.
// M3b forma xatolari bir xil shaklda keladi: maydon xatosi yoki 409 `stale` holati.
import { useTranslation } from 'react-i18next';
import { Copy, ShieldAlert } from 'lucide-react';
import { isApiError } from '@/api/errors';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { useToast } from '@/ui/Toast';
import { copyText } from '@/lib/browser';

export type MutationErrorInfo = { field: string | undefined; message: string | undefined; stale: boolean };

/** Mutatsiya xatosidan maydon nomi / umumiy xabar / 409 `stale` holatini chiqarib beradi. */
export function useMutationError(error: unknown): MutationErrorInfo {
  if (!isApiError(error)) return { field: undefined, message: undefined, stale: false };
  return { field: error.field, message: error.message, stale: error.code === 'stale' };
}

/** 409 `stale` xatosi boʻlsa umumiy ogohlantirish bannerini koʻrsatadi — aks holda hech nima chiqarmaydi. */
export function StaleBanner({ stale, message }: { stale: boolean; message: string | undefined }) {
  if (!stale || !message) return null;
  return <p className="flex items-center gap-2 text-sm text-danger"><ShieldAlert aria-hidden className="size-3.5 shrink-0" />{message}</p>;
}

/** Forma maydoniga tegishli boʻlmagan qolgan mutatsiya xatosi — maydon xatolari allaqachon oʻz joyida koʻrsatiladi. */
export function OtherFormError({ message }: { message: string | null | undefined }) {
  if (!message) return null;
  return <p className="text-sm text-danger">{message}</p>;
}

/** Faqat boshqarish huquqi bor foydalanuvchiga koʻrinadigan forma saqlash tugmasi qatori. */
export function SaveButtonRow({ canManage, pending, onClick, label }: { canManage: boolean; pending: boolean; onClick: () => void; label: string }) {
  if (!canManage) return null;
  return <div><Button variant="primary" loading={pending} onClick={onClick}>{label}</Button></div>;
}

/** API kalit / vebhuk sirini bir martalik koʻrsatadigan modal — API kalitlari va vebhuklar bir xil shaklda ishlatadi. */
export function SecretOnceModal({
  open, title, warning, secret, secretTestId, onClose,
}: { open: boolean; title: string; warning: string; secret: string | undefined; secretTestId: string; onClose: () => void }) {
  const { t } = useTranslation('integrations');
  const toast = useToast();
  return (
    <Modal
      open={open}
      onOpenChange={(v) => !v && onClose()}
      title={title}
      footer={<Button variant="primary" onClick={onClose}>{t('apiKeys.close')}</Button>}
    >
      <div className="flex flex-col gap-3">
        <p className="flex items-start gap-1.5 text-sm text-danger">
          <ShieldAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
          {warning}
        </p>
        <div className="flex items-center justify-between gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2">
          <span data-testid={secretTestId} className="num text-sm font-medium text-fg break-all">{secret}</span>
          <Button
            size="sm" variant="ghost" iconOnly icon={<Copy />} aria-label={t('apiKeys.copy')}
            onClick={() => { void copyText(secret ?? ''); toast({ kind: 'success', title: t('apiKeys.copied') }); }}
          />
        </div>
      </div>
    </Modal>
  );
}
