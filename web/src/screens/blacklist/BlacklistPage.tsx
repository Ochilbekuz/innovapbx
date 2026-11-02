import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { EyeOff, Plus, ShieldAlert, ShieldOff, Trash2 } from 'lucide-react';
import { useBlacklist, useCreateBlacklistEntry, useDeleteBlacklistEntry } from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { BlacklistEntry } from '@/api/types';
import { usePermission } from '@/auth/permissions';
import { formatDateTimeShort } from '@/lib/time';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { Field, Input } from '@/ui/Field';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

const ANONYMOUS = 'anonymous';

/** S27 — qora roʻyxat: raqam/sabab, yashirin raqamlarni bloklash, qoʻshish/olib tashlash. Qarang ../../../replica/m2a-contract.md §5. */
export function BlacklistPage() {
  const { t } = useTranslation('blacklist');
  const { data, isLoading, isError, refetch } = useBlacklist({});
  const canManage = usePermission('pbx.manage');
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState<BlacklistEntry | null>(null);

  const createM = useCreateBlacklistEntry();
  const deleteM = useDeleteBlacklistEntry();
  const anonymousToggleM = useCreateBlacklistEntry();
  const anonymousDeleteM = useDeleteBlacklistEntry();

  const items = data?.items ?? [];
  const blocksAnonymous = items.some((b) => b.number === ANONYMOUS);

  const closeAdd = () => { setAdding(false); createM.reset(); };

  const columns: Column<BlacklistEntry>[] = [
    {
      key: 'number', header: t('column.number'), sortValue: (b) => b.number,
      cell: (b) => b.number === ANONYMOUS ? (
        <span className="flex items-center gap-1.5 text-fg"><EyeOff aria-hidden className="size-3.5 text-muted" /> {t('anonymousLabel')}</span>
      ) : <span className="num">{b.number}</span>,
    },
    { key: 'reason', header: t('column.reason'), cell: (b) => <span className="text-muted">{b.reason ?? '—'}</span> },
    { key: 'createdAt', header: t('column.createdAt'), cell: (b) => <span className="text-muted">{formatDateTimeShort(b.created_at)}</span> },
    {
      key: 'actions', header: '', align: 'right', cell: (b) => (
        <div className="flex justify-end">
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('deleteAriaLabel', { number: b.number })} disabled={!canManage} onClick={() => setDeleting(b)} />
        </div>
      ),
    },
  ];

  return (
    <AppShellPage title={t('title')}>
      {!canManage && (
        <p className="mb-3 flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2 text-sm text-muted">
          <ShieldAlert aria-hidden className="size-4 shrink-0" />
          {t('readOnlyNotice')}
        </p>
      )}

      <div className="mb-3 flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2.5">
        <ShieldOff aria-hidden className="size-4 shrink-0 text-brand" />
        <Toggle
          checked={blocksAnonymous}
          disabled={!canManage || anonymousToggleM.isPending || anonymousDeleteM.isPending}
          onCheckedChange={(v) => {
            if (v) {
              anonymousToggleM.mutate({ number: ANONYMOUS }, {
                onSuccess: () => toast({ kind: 'success', title: t('toast.added', { number: t('anonymousLabel') }) }),
              });
            } else {
              anonymousDeleteM.mutate(ANONYMOUS, {
                onSuccess: () => toast({ kind: 'success', title: t('toast.deleted', { number: t('anonymousLabel') }) }),
              });
            }
          }}
          label={t('anonymousToggle.label')}
          description={t('anonymousToggle.desc')}
        />
      </div>

      <DataTable
        caption={t('caption')}
        rows={items.filter((b) => b.number !== ANONYMOUS)}
        columns={columns}
        rowId={(b) => b.number}
        searchText={(b) => `${b.number} ${b.reason ?? ''}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        empty={{ title: t('empty.title'), body: t('empty.body'), action: canManage ? <Button size="sm" onClick={() => setAdding(true)}>{t('addForm.add')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setAdding(true)}>{t('addForm.add')}</Button> : undefined}
      />

      <AddBlacklistModal
        open={adding}
        pending={createM.isPending}
        errorField={isApiError(createM.error) ? createM.error.field : undefined}
        errorMessage={isApiError(createM.error) ? createM.error.message : undefined}
        onClose={closeAdd}
        onSubmit={(payload) => createM.mutate(payload, {
          onSuccess: (res) => { closeAdd(); toast({ kind: 'success', title: t('toast.added', { number: res.item.number }) }); },
        })}
      />

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={deleting ? t('deleteModal.title', { number: deleting.number }) : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleting(null)}>{t('cancel')}</Button>
            <Button
              variant="danger" loading={deleteM.isPending}
              onClick={() => deleting && deleteM.mutate(deleting.number, {
                onSuccess: () => { toast({ kind: 'success', title: t('toast.deleted', { number: deleting.number }) }); setDeleting(null); },
                onError: (e) => { toast({ kind: 'error', title: t('toast.deleteFailed'), description: e.message }); setDeleting(null); },
              })}
            >
              {t('delete')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">{t('deleteModal.body', { number: deleting?.number })}</p>
      </Modal>
    </AppShellPage>
  );
}

function AddBlacklistModal({
  open, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: { number: string; reason: string | null }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('blacklist');
  const [number, setNumber] = useState('');
  const [reason, setReason] = useState('');

  const valid = number.trim().length > 0;
  const submit = () => {
    if (!valid) return;
    onSubmit({ number: number.trim(), reason: reason.trim() || null });
  };
  const closeAndReset = () => { setNumber(''); setReason(''); onClose(); };

  return (
    <Modal
      open={open}
      onOpenChange={(v) => !v && closeAndReset()}
      title={t('addForm.add')}
      footer={
        <>
          <Button variant="ghost" onClick={closeAndReset}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={submit}>{t('addForm.add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label={t('addForm.numberLabel')} required error={errorField === 'number' ? errorMessage : undefined}>
          {(a) => <Input {...a} mono autoFocus placeholder={t('addForm.numberPlaceholder')} value={number} onChange={(e) => setNumber(e.target.value)} />}
        </Field>
        <Field label={t('addForm.reasonLabel')} aside={t('addForm.reasonAside')}>
          {(a) => <Input {...a} placeholder={t('addForm.reasonPlaceholder')} value={reason} onChange={(e) => setReason(e.target.value)} />}
        </Field>
        {errorMessage && errorField !== 'number' ? <p className="text-sm text-danger">{errorMessage}</p> : null}
      </div>
    </Modal>
  );
}
