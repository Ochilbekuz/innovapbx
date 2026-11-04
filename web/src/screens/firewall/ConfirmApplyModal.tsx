// Qo'llashni tasdiqlash modali — diff + ogohlantirishlar + tasdiqlash muddati tanlagich. M12 B3.
// `network/ConfirmApplyModal.tsx` bilan bir xil naqsh (shartnoma bo'yicha mustaqil, lekin UI izchil); faqat
// namespace ('firewall') va muddat ro'yxati (`firewallDraft.ts`) farqli — bitta komponentga birlashtirish
// ikki ekranni keraksiz bog'lab qo'yardi (network o'zgarishi firewallga ta'sir qilmasligi kerak).
import { useTranslation } from 'react-i18next';
import { Button } from '@/ui/Button';
import { Segmented } from '@/ui/Field';
import { Modal } from '@/ui/Dialog';
import { closeOnOpenChange } from '@/lib/formHelpers';
import { TIMEOUT_OPTIONS } from './firewallDraft';

export function ConfirmApplyModal({
  open, diff, timeoutS, onTimeoutChange, onConfirm, onClose, loading,
}: {
  open: boolean;
  diff: string[];
  timeoutS: number;
  onTimeoutChange: (s: number) => void;
  onConfirm: () => void;
  onClose: () => void;
  loading: boolean;
}) {
  const { t } = useTranslation('firewall');
  return (
    <Modal
      open={open}
      onOpenChange={(v) => closeOnOpenChange(v, onClose)}
      title={t('confirmModal.title')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('confirmModal.cancel')}</Button>
          <Button variant="primary" loading={loading} onClick={onConfirm}>{t('confirmModal.confirm')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div>
          <p className="mb-1.5 text-sm font-medium text-fg">{t('confirmModal.diffTitle')}</p>
          <ul className="num flex flex-col gap-1 rounded-md border border-line bg-surface-2 px-3 py-2 text-sm text-fg">
            {diff.map((line, i) => <li key={i}>{line}</li>)}
          </ul>
        </div>
        <div>
          <p className="mb-1.5 text-sm font-medium text-fg">{t('timeoutLabel')}</p>
          <Segmented
            value={String(timeoutS)}
            onChange={(v) => onTimeoutChange(Number(v))}
            label={t('timeoutLabel')}
            options={TIMEOUT_OPTIONS.map((s) => ({ value: String(s), label: `${s}s` }))}
          />
          <p className="mt-1.5 text-xs text-muted">{t('confirmModal.timeoutHint')}</p>
        </div>
      </div>
    </Modal>
  );
}
