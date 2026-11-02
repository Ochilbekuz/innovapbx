import type { ReactNode } from 'react';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { closeOnOpenChange } from '@/lib/formHelpers';

/** O'chirishni tasdiqlash dialogi — matnlar chaqiruvchining i18n'idan keladi, mutatsiya ham uniki. */
export function ConfirmDeleteModal({
  open, onClose, onConfirm, loading, title, body, cancelLabel, deleteLabel,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  loading: boolean;
  title: string;
  body: ReactNode;
  cancelLabel: string;
  deleteLabel: string;
}) {
  return (
    <Modal
      size="sm"
      open={open}
      onOpenChange={(v) => closeOnOpenChange(v, onClose)}
      title={title}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{cancelLabel}</Button>
          <Button variant="danger" loading={loading} onClick={onConfirm}>{deleteLabel}</Button>
        </>
      }
    >
      <p className="text-sm text-muted">{body}</p>
    </Modal>
  );
}
