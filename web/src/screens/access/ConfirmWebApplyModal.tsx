// Veb-panel portini o'zgartirishni tasdiqlash modali — manzil o'zgarishi haqida ogohlantirish + tasdiqlash
// muddati tanlagich. `firewall/ConfirmApplyModal.tsx` bilan bir xil naqsh, qasddan mustaqil komponent.
import { useTranslation } from 'react-i18next';
import { Button } from '@/ui/Button';
import { Segmented } from '@/ui/Field';
import { Modal } from '@/ui/Dialog';
import { closeOnOpenChange } from '@/lib/formHelpers';
import { ACCESS_TIMEOUT_OPTIONS } from '@/domain/access';

export function ConfirmWebApplyModal({
  open, url, timeoutS, onTimeoutChange, onConfirm, onClose, loading,
}: {
  open: boolean;
  url: string;
  timeoutS: number;
  onTimeoutChange: (s: number) => void;
  onConfirm: () => void;
  onClose: () => void;
  loading: boolean;
}) {
  const { t } = useTranslation('access');
  return (
    <Modal
      open={open}
      onOpenChange={(v) => closeOnOpenChange(v, onClose)}
      title={t('web.confirmModal.title')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('web.confirmModal.cancel')}</Button>
          <Button variant="primary" loading={loading} onClick={onConfirm}>{t('web.confirmModal.confirm')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-sm text-on-warning-soft">
          {t('web.confirmModal.warning', { url })}
        </p>
        <div>
          <p className="mb-1.5 text-sm font-medium text-fg">{t('web.confirmModal.timeoutLabel')}</p>
          <Segmented
            value={String(timeoutS)}
            onChange={(v) => onTimeoutChange(Number(v))}
            label={t('web.confirmModal.timeoutLabel')}
            options={ACCESS_TIMEOUT_OPTIONS.map((s) => ({ value: String(s), label: `${s}s` }))}
          />
        </div>
      </div>
    </Modal>
  );
}
