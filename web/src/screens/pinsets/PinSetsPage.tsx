import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { KeyRound, Pencil, Plus, ShieldAlert, Trash2, X } from 'lucide-react';
import {
  useAddPins, useCreatePinSet, useDeletePin, useDeletePinSet, usePinSetPins, usePinSets, useUpdatePinSet,
} from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { PinSet, Usage } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { applyToast } from '@/lib/applyToast';
import { usagesOf } from '@/lib/usageError';
import { UsageList } from '@/pbx/UsageList';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input, Textarea } from '@/ui/Field';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

const PIN_ONLY_RE = /^\d{4,12}$/;

/** S42 — PIN toʻplamlari: chiquvchi marshrutda qoʻngʻiroqdan oldin so'raladigan kodlar toʻplami. */
export function PinSetsPage() {
  const { t } = useTranslation('pinsets');
  const { data, isLoading, isError, refetch } = usePinSets();
  const canManage = useCanEdit('connect');
  const toast = useToast();
  const [editing, setEditing] = useState<PinSet | 'new' | null>(null);
  const [deleting, setDeleting] = useState<PinSet | null>(null);
  const [deleteErr, setDeleteErr] = useState<Usage[] | null>(null);
  const [pinsFor, setPinsFor] = useState<PinSet | null>(null);

  const createM = useCreatePinSet();
  const updateM = useUpdatePinSet();
  const deleteM = useDeletePinSet();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;

  const columns: Column<PinSet>[] = [
    { key: 'name', header: t('column.name'), sortValue: (p) => p.name, cell: (p) => <span className="font-medium">{p.name}</span> },
    {
      key: 'recordInCdr', header: t('column.recordInCdr'), cell: (p) => (
        p.record_in_cdr ? <span className="text-fg">✓</span> : <span className="text-muted">—</span>
      ),
    },
    { key: 'pinCount', header: t('column.pinCount'), cell: (p) => <span className="num text-muted">{p.pin_count}</span> },
    { key: 'usedBy', header: t('column.usedBy'), cell: (p) => <span className="truncate text-sm text-muted">{p.used_by.map((u) => u.name).join(', ') || '—'}</span> },
    {
      key: 'actions', header: '', align: 'right', cell: (p) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<KeyRound />} aria-label={t('openPinsAriaLabel', { name: p.name })} disabled={!canManage} onClick={() => setPinsFor(p)} />
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('editAriaLabel', { name: p.name })} disabled={!canManage} onClick={() => setEditing(p)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('deleteAriaLabel', { name: p.name })} disabled={!canManage} onClick={() => setDeleting(p)} />
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
      <DataTable
        caption={t('caption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(p) => p.id}
        searchText={(p) => p.name}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (p) => setEditing(p) : undefined}
        empty={{ title: t('empty.title'), body: t('empty.body'), action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('empty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('newSet')}</Button> : undefined}
      />

      {editing && (
        <PinSetForm
          item={editing === 'new' ? undefined : editing}
          pending={mutation.isPending}
          errorField={isApiError(mutation.error) ? mutation.error.field : undefined}
          errorMessage={isApiError(mutation.error) ? mutation.error.message : undefined}
          onClose={close}
          onSubmit={(payload) => {
            if (editing === 'new') {
              createM.mutate(payload, { onSuccess: (res) => { close(); toast(applyToast(res.apply, t('toast.added'))); } });
            } else {
              updateM.mutate({ id: editing.id, payload: { ...payload, updated_at: editing.updated_at } }, {
                onSuccess: (res) => { close(); toast(applyToast(res.apply, t('toast.saved'))); },
              });
            }
          }}
        />
      )}

      {pinsFor && <PinsDrawer set={pinsFor} onClose={() => setPinsFor(null)} />}

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && (setDeleting(null), setDeleteErr(null))}
        title={deleting ? t('deleteModal.title', { name: deleting.name }) : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => { setDeleting(null); setDeleteErr(null); }}>{t('cancel')}</Button>
            {!deleteErr && (
              <Button
                variant="danger" loading={deleteM.isPending}
                onClick={() => deleting && deleteM.mutate(deleting.id, {
                  onSuccess: () => { toast({ kind: 'success', title: t('toast.deleted', { name: deleting.name }) }); setDeleting(null); },
                  onError: (e) => { if (isApiError(e) && e.code === 'in_use') setDeleteErr(usagesOf(e)); else toast({ kind: 'error', title: t('toast.deleteFailed'), description: e.message }); },
                })}
              >
                {t('delete')}
              </Button>
            )}
          </>
        }
      >
        {deleteErr ? (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-danger">{t('deleteModal.usagePrefix', { name: deleting?.name })}</p>
            <UsageList usages={deleteErr} />
          </div>
        ) : (
          <p className="text-sm text-muted">{t('deleteModal.body', { name: deleting?.name })}</p>
        )}
      </Modal>
    </AppShellPage>
  );
}

function PinSetForm({
  item, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  item?: PinSet;
  onClose: () => void;
  onSubmit: (payload: { name: string; record_in_cdr: boolean }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('pinsets');
  const [name, setName] = useState(item?.name ?? '');
  const [recordInCdr, setRecordInCdr] = useState(item?.record_in_cdr ?? false);
  const valid = name.trim().length > 0;

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={item ? t('form.editTitle', { name: item.name }) : t('form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={() => onSubmit({ name: name.trim(), record_in_cdr: recordInCdr })}>{item ? t('save') : t('add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && errorField !== 'name' && <p className="text-sm text-danger">{errorMessage}</p>}
        <Field label={t('form.nameLabel')} required error={errorField === 'name' ? errorMessage : undefined}>
          {(a) => <Input {...a} autoFocus value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Toggle checked={recordInCdr} onCheckedChange={setRecordInCdr} label={t('form.recordInCdrLabel')} description={t('form.recordInCdrDesc')} />
      </div>
    </Drawer>
  );
}

function PinsDrawer({ set, onClose }: { set: PinSet; onClose: () => void }) {
  const { t } = useTranslation('pinsets');
  const { data } = usePinSetPins(set.id);
  const toast = useToast();
  const addM = useAddPins();
  const deleteM = useDeletePin();
  const [raw, setRaw] = useState('');
  const [rowErr, setRowErr] = useState<string | null>(null);

  const submitAdd = () => {
    setRowErr(null);
    const lines = raw.split('\n').map((l) => l.trim()).filter(Boolean);
    if (lines.length === 0) return;
    const pins: { pin: string; label: string }[] = [];
    for (const [i, line] of lines.entries()) {
      const sep = line.indexOf(';');
      const pin = sep < 0 ? line : line.slice(0, sep).trim();
      const label = sep < 0 ? '' : line.slice(sep + 1).trim();
      if (sep < 0 || !PIN_ONLY_RE.test(pin) || !label) { setRowErr(t('pinsDrawer.pinFormatError', { row: i + 1 })); return; }
      pins.push({ pin, label });
    }
    addM.mutate({ id: set.id, payload: { pins } }, {
      // DIQQAT (jonli isbotda topilgan haqiqiy ildiz sabab): backend
      // POST .../pins SO'ROVIDA FAQAT yangi yaratilgan PIN'larni qaytaradi
      // (to'liq ro'yxat EMAS) -- shuning uchun eski-yangi farqini hisoblash
      // ("res.items.length - data?.items.length") noto'g'ri (hatto manfiy)
      // son berardi; to'g'ri son -- shu so'rovda qaytgan `res.items.length`ning o'zi.
      onSuccess: (res) => { setRaw(''); toast({ kind: 'success', title: t('toast.pinsAdded', { count: res.items.length }) }); },
      onError: (e) => { if (isApiError(e) && e.code === 'pin_taken') setRowErr(e.message); else toast({ kind: 'error', title: t('toast.deleteFailed'), description: e.message }); },
    });
  };

  return (
    <Drawer open onOpenChange={(v) => !v && onClose()} title={t('pinsDrawer.title', { name: set.name })} footer={<Button variant="ghost" onClick={onClose}>{t('close')}</Button>}>
      <div className="flex flex-col gap-4">
        <div>
          <p className="mb-2 text-sm font-medium text-fg">{t('pinsDrawer.pinColumn')}</p>
          {(data?.items.length ?? 0) === 0 ? (
            <p className="text-sm text-muted">{t('pinsDrawer.empty')}</p>
          ) : (
            <ul className="flex flex-col gap-1">
              {data?.items.map((p) => (
                <li key={p.id} className="flex items-center justify-between rounded-sm border border-line px-2.5 py-1.5">
                  <span className="text-sm text-fg">{p.label || '—'}</span>
                  <Button
                    size="sm" variant="ghost" iconOnly icon={<X />} aria-label={t('pinsDrawer.removeAriaLabel', { label: p.label || p.id })}
                    onClick={() => deleteM.mutate({ id: set.id, pinId: p.id })}
                  />
                </li>
              ))}
            </ul>
          )}
        </div>

        <Field label={t('pinsDrawer.addLabel')} hint={t('pinsDrawer.addHint')} error={rowErr ?? undefined}>
          {(a) => <Textarea {...a} rows={4} placeholder={t('pinsDrawer.addPlaceholder')} value={raw} onChange={(e) => setRaw(e.target.value)} />}
        </Field>
        <div className="flex justify-end">
          <Button variant="secondary" loading={addM.isPending} disabled={raw.trim().length === 0} onClick={submitAdd}>{t('pinsDrawer.addButton')}</Button>
        </div>
      </div>
    </Drawer>
  );
}
