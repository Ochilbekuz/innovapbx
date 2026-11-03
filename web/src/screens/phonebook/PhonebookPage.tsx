import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Download, Pencil, Plus, ShieldAlert, Trash2, Upload, X } from 'lucide-react';
import { apiClient } from '@/api';
import {
  useCreateContact, useDeleteContact, useImportPhonebookCsv, usePhonebook, useUpdateContact,
} from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { Contact, ImportPhonebookResult, PhonebookNumber } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { applyToast } from '@/lib/applyToast';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input } from '@/ui/Field';
import { DataTable, type Column } from '@/ui/Table';
import { useToast } from '@/ui/Toast';

async function downloadPhonebookCsv() {
  const blob = await apiClient.exportPhonebookCsv();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'phonebook.csv';
  a.click();
  URL.revokeObjectURL(url);
}

/** S41 — telefon kitobi: kontaktlar (chaqiruvchi raqamni nom bilan koʻrsatish uchun) + CSV import/eksport. */
export function PhonebookPage() {
  const { t } = useTranslation('phonebook');
  const { data, isLoading, isError, refetch } = usePhonebook({});
  const canManage = useCanEdit('routing');
  const toast = useToast();
  const [editing, setEditing] = useState<Contact | 'new' | null>(null);
  const [deleting, setDeleting] = useState<Contact | null>(null);
  const [importing, setImporting] = useState(false);

  const createM = useCreateContact();
  const updateM = useUpdateContact();
  const deleteM = useDeleteContact();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;

  const columns: Column<Contact>[] = [
    { key: 'name', header: t('column.name'), sortValue: (c) => c.name, cell: (c) => <span className="font-medium">{c.name}</span> },
    { key: 'company', header: t('column.company'), cell: (c) => <span className="truncate text-sm text-muted">{c.company ?? '—'}</span> },
    { key: 'numbers', header: t('column.numbers'), cell: (c) => <span className="num text-sm text-muted">{c.numbers.map((n) => n.number).join(', ')}</span> },
    { key: 'note', header: t('column.note'), cell: (c) => <span className="truncate text-sm text-muted">{c.note ?? '—'}</span> },
    {
      key: 'actions', header: '', align: 'right', cell: (c) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('editAriaLabel', { name: c.name })} disabled={!canManage} onClick={() => setEditing(c)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('deleteAriaLabel', { name: c.name })} disabled={!canManage} onClick={() => setDeleting(c)} />
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
        rowId={(c) => c.id}
        searchPlaceholder={t('searchPlaceholder')}
        searchText={(c) => `${c.name} ${c.company ?? ''} ${c.numbers.map((n) => n.number).join(' ')}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (c) => setEditing(c) : undefined}
        empty={{ title: t('empty.title'), body: t('empty.body'), action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('empty.action')}</Button> : undefined }}
        toolbar={canManage ? (
          <div className="flex gap-2">
            <Button size="sm" variant="ghost" icon={<Download />} onClick={() => void downloadPhonebookCsv()}>{t('importExport.exportButton')}</Button>
            <Button size="sm" variant="ghost" icon={<Upload />} onClick={() => setImporting(true)}>{t('importExport.importButton')}</Button>
            <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('newContact')}</Button>
          </div>
        ) : undefined}
      />

      {editing && (
        <ContactForm
          contact={editing === 'new' ? undefined : editing}
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

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={deleting ? t('deleteModal.title', { name: deleting.name }) : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleting(null)}>{t('cancel')}</Button>
            <Button
              variant="danger" loading={deleteM.isPending}
              onClick={() => deleting && deleteM.mutate(deleting.id, {
                onSuccess: () => { toast({ kind: 'success', title: t('toast.deleted', { name: deleting.name }) }); setDeleting(null); },
                onError: (e) => toast({ kind: 'error', title: t('toast.deleteFailed'), description: e.message }),
              })}
            >
              {t('delete')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">{t('deleteModal.body', { name: deleting?.name })}</p>
      </Modal>

      {importing && <ImportDialog onClose={() => setImporting(false)} onDone={() => void refetch()} />}
    </AppShellPage>
  );
}

function ContactForm({
  contact, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  contact?: Contact;
  onClose: () => void;
  onSubmit: (payload: { name: string; company: string | null; note: string | null; numbers: PhonebookNumber[] }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('phonebook');
  const [name, setName] = useState(contact?.name ?? '');
  const [company, setCompany] = useState(contact?.company ?? '');
  const [note, setNote] = useState(contact?.note ?? '');
  const [numbers, setNumbers] = useState<PhonebookNumber[]>(contact?.numbers ?? [{ number: '', label: '' }]);

  const trimmedNumbers = numbers.map((n) => ({ number: n.number.trim(), label: n.label.trim() })).filter((n) => n.number);
  const valid = name.trim().length > 0 && trimmedNumbers.length > 0;

  const setNumberAt = (i: number, patch: Partial<PhonebookNumber>) => setNumbers((ns) => ns.map((n, idx) => (idx === i ? { ...n, ...patch } : n)));
  const removeNumberAt = (i: number) => setNumbers((ns) => ns.filter((_, idx) => idx !== i));

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={contact ? t('form.editTitle', { name: contact.name }) : t('form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button
            variant="primary" loading={pending} disabled={!valid}
            onClick={() => onSubmit({ name: name.trim(), company: company.trim() || null, note: note.trim() || null, numbers: trimmedNumbers })}
          >
            {contact ? t('save') : t('add')}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && !['name', 'numbers'].includes(errorField ?? '') && <p className="text-sm text-danger">{errorMessage}</p>}
        <Field label={t('form.nameLabel')} required error={errorField === 'name' ? errorMessage : undefined}>
          {(a) => <Input {...a} autoFocus value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Field label={t('form.companyLabel')}>
          {(a) => <Input {...a} value={company} onChange={(e) => setCompany(e.target.value)} />}
        </Field>
        <Field label={t('form.noteLabel')}>
          {(a) => <Input {...a} value={note} onChange={(e) => setNote(e.target.value)} />}
        </Field>

        <div>
          <p className="mb-2 text-sm font-medium text-fg">{t('form.numbersLabel')}</p>
          <div className="flex flex-col gap-2">
            {numbers.map((n, i) => (
              <div key={i} className="flex items-center gap-2">
                <Input className="num" placeholder={t('form.numberPlaceholder')} value={n.number} onChange={(e) => setNumberAt(i, { number: e.target.value })} aria-label={t('form.numberFieldAriaLabel', { index: i + 1 })} />
                <Input placeholder={t('form.labelPlaceholder')} value={n.label} onChange={(e) => setNumberAt(i, { label: e.target.value })} aria-label={t('form.labelFieldAriaLabel', { index: i + 1 })} />
                <Button size="sm" variant="ghost" iconOnly icon={<X />} aria-label={t('form.removeNumberAriaLabel')} disabled={numbers.length <= 1} onClick={() => removeNumberAt(i)} />
              </div>
            ))}
          </div>
          <Button size="sm" variant="ghost" className="mt-2" onClick={() => setNumbers((ns) => [...ns, { number: '', label: '' }])}>{t('form.addNumber')}</Button>
          {errorField === 'numbers' && errorMessage && <p className="mt-1.5 text-sm text-danger">{errorMessage}</p>}
        </div>
      </div>
    </Drawer>
  );
}

function ImportDialog({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const { t } = useTranslation('phonebook');
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPhonebookResult | null>(null);
  const importM = useImportPhonebookCsv();

  const pickFile = (f: File) => {
    setFile(f);
    setPreview(null);
    importM.mutate({ file: f, dry_run: true }, { onSuccess: (res) => setPreview(res) });
  };

  const apply = () => {
    if (!file) return;
    importM.mutate({ file, dry_run: false }, {
      onSuccess: () => { toast({ kind: 'success', title: t('importExport.applied') }); onDone(); onClose(); },
    });
  };

  return (
    <Modal
      open
      onOpenChange={(v) => !v && onClose()}
      title={t('importExport.dialogTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('importExport.cancel')}</Button>
          <Button variant="primary" loading={importM.isPending} disabled={!preview || preview.errors.length > 0 && preview.created + preview.updated === 0} onClick={apply}>
            {t('importExport.apply')}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-sm text-muted">{t('importExport.dryRunHint')}</p>
        <Button size="sm" variant="secondary" loading={importM.isPending && !preview} onClick={() => inputRef.current?.click()}>{t('importExport.chooseFile')}</Button>
        <input
          ref={inputRef} type="file" accept=".csv,text/csv" className="sr-only"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) pickFile(f); e.target.value = ''; }}
        />
        {file && <p className="text-sm text-fg">{file.name}</p>}

        {preview && (
          <div className="flex flex-col gap-2 rounded-md border border-line bg-surface-2/40 p-3">
            <p className="text-sm font-medium text-fg">{t('importExport.preview')}</p>
            <p className="text-sm text-muted">{t('importExport.created', { count: preview.created })} · {t('importExport.updated', { count: preview.updated })} · {t('importExport.skipped', { count: preview.skipped })} · {t('importExport.errorsCount', { count: preview.errors.length })}</p>
            {preview.errors.length > 0 && (
              <ul className="flex flex-col gap-0.5 text-sm text-danger">
                {preview.errors.slice(0, 10).map((e, i) => <li key={i}>{t('importExport.rowError', { row: e.row, message: e.message })}</li>)}
              </ul>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}
