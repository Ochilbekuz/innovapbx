// Yangilashni tasdiqlash — versiya raqamini qoʻlda yozish shart (M11 §5: xato bosilib ketmasligi uchun).
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { TriangleAlert } from 'lucide-react';
import { closeOnOpenChange } from '@/lib/formHelpers';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { Field, Input } from '@/ui/Field';

export function ConfirmUpdateModal({
  open, version, loading, onConfirm, onClose,
}: {
  open: boolean;
  version: string;
  loading: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation('update');
  const [typed, setTyped] = useState('');
  const matches = typed.trim() === version;

  const close = () => { setTyped(''); onClose(); };
  const submit = () => { if (matches) onConfirm(); };

  return (
    <Modal
      open={open}
      onOpenChange={(v) => closeOnOpenChange(v, close)}
      title={t('confirm.modalTitle', { version })}
      footer={
        <>
          <Button variant="ghost" onClick={close}>{t('confirm.cancelButton')}</Button>
          <Button variant="primary" loading={loading} disabled={!matches} onClick={submit}>{t('confirm.confirmButton')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-sm text-on-warning-soft">
          <p className="mb-1 flex items-center gap-1.5 font-medium"><TriangleAlert aria-hidden className="size-4" />{t('confirm.warningBackup')}</p>
          <ul className="list-inside list-disc space-y-0.5">
            <li>{t('confirm.warningDuration')}</li>
            <li>{t('confirm.warningCalls')}</li>
          </ul>
        </div>
        <Field label={t('confirm.typeLabel', { version })} error={typed && !matches ? t('confirm.typeMismatch') : undefined}>
          {(a) => (
            <Input {...a} mono placeholder={t('confirm.typePlaceholder')} value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus />
          )}
        </Field>
      </div>
    </Modal>
  );
}
