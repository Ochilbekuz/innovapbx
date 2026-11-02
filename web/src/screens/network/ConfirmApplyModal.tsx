// Qo'llashni tasdiqlash modali — diff + ogohlantirishlar + tasdiqlash muddati tanlagich. M8 §4/§5.
import { useTranslation } from 'react-i18next';
import { TriangleAlert } from 'lucide-react';
import { Button } from '@/ui/Button';
import { Segmented } from '@/ui/Field';
import { Modal } from '@/ui/Dialog';
import { closeOnOpenChange } from '@/lib/formHelpers';
import { TIMEOUT_OPTIONS } from './networkDraft';

export function ConfirmApplyModal({
  open, diff, warnings, timeoutS, onTimeoutChange, onConfirm, onClose, loading,
}: {
  open: boolean;
  diff: string[];
  warnings: string[];
  timeoutS: number;
  onTimeoutChange: (s: number) => void;
  onConfirm: () => void;
  onClose: () => void;
  loading: boolean;
}) {
  const { t } = useTranslation('network');
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
        {warnings.length > 0 && (
          <div className="rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-sm text-on-warning-soft">
            <p className="mb-1 flex items-center gap-1.5 font-medium"><TriangleAlert aria-hidden className="size-4" />{t('confirmModal.warningsTitle')}</p>
            <ul className="flex flex-col gap-1">
              {warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          </div>
        )}
        <div>
          <p className="mb-1.5 text-sm font-medium text-fg">{t('confirmModal.timeoutLabel')}</p>
          <Segmented
            value={String(timeoutS)}
            onChange={(v) => onTimeoutChange(Number(v))}
            label={t('confirmModal.timeoutLabel')}
            options={TIMEOUT_OPTIONS.map((s) => ({ value: String(s), label: `${s}s` }))}
          />
          <p className="mt-1.5 text-xs text-muted">{t('confirmModal.timeoutHint')}</p>
        </div>
      </div>
    </Modal>
  );
}
