import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pencil, Plus, ShieldAlert, Trash2 } from 'lucide-react';
import {
  useCreatePageGroup, useDeletePageGroup, useExtensions, usePageGroups, useUpdatePageGroup,
} from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { PageGroup } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { applyToast } from '@/lib/applyToast';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input } from '@/ui/Field';
import { DataTable, type Column } from '@/ui/Table';
import { Checkbox, Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

/** S40 — paging/intercom guruhlari: bir vaqtda bir nechta ichki raqamga ovozli xabar eshittiradi. */
export function PagingPage() {
  const { t } = useTranslation('paging');
  const { data, isLoading, isError, refetch } = usePageGroups();
  const { data: extData } = useExtensions({});
  const extensions = extData?.items ?? [];
  const canManage = useCanEdit('routing');
  const toast = useToast();
  const [editing, setEditing] = useState<PageGroup | 'new' | null>(null);
  const [deleting, setDeleting] = useState<PageGroup | null>(null);

  const createM = useCreatePageGroup();
  const updateM = useUpdatePageGroup();
  const deleteM = useDeletePageGroup();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;

  const columns: Column<PageGroup>[] = [
    { key: 'name', header: t('column.name'), sortValue: (g) => g.name, cell: (g) => <span className="font-medium">{g.name}</span> },
    { key: 'number', header: t('column.number'), cell: (g) => <span className="num text-muted">{g.number}</span> },
    { key: 'members', header: t('column.members'), cell: (g) => <span className="num text-muted">{g.members.length}</span> },
    {
      key: 'duplex', header: t('column.duplex'), cell: (g) => (
        g.duplex ? <span className="text-fg">✓</span> : <span className="text-muted">—</span>
      ),
    },
    {
      key: 'actions', header: '', align: 'right', cell: (g) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('editAriaLabel', { name: g.name })} disabled={!canManage} onClick={() => setEditing(g)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('deleteAriaLabel', { name: g.name })} disabled={!canManage} onClick={() => setDeleting(g)} />
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
        rowId={(g) => g.id}
        searchText={(g) => `${g.name} ${g.number}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (g) => setEditing(g) : undefined}
        empty={{ title: t('empty.title'), body: t('empty.body'), action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('empty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('newGroup')}</Button> : undefined}
      />

      {editing && (
        <PageGroupForm
          group={editing === 'new' ? undefined : editing}
          extensions={extensions}
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
    </AppShellPage>
  );
}

function PageGroupForm({
  group, extensions, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  group?: PageGroup;
  extensions: { id: string; number: string; name: string }[];
  onClose: () => void;
  onSubmit: (payload: { name: string; number: string; duplex: boolean; skip_busy: boolean; beep: boolean; member_ids: string[] }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('paging');
  const [name, setName] = useState(group?.name ?? '');
  const [number, setNumber] = useState(group?.number ?? '');
  const [duplex, setDuplex] = useState(group?.duplex ?? false);
  const [skipBusy, setSkipBusy] = useState(group?.skip_busy ?? true);
  const [beep, setBeep] = useState(group?.beep ?? true);
  const [memberIds, setMemberIds] = useState<string[]>(group?.members.map((m) => m.id) ?? []);

  const valid = name.trim().length > 0 && number.trim().length > 0 && memberIds.length > 0;
  const toggleMember = (id: string, on: boolean) => setMemberIds((ids) => (on ? [...ids, id] : ids.filter((i) => i !== id)));

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={group ? t('form.editTitle', { name: group.name }) : t('form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button
            variant="primary" loading={pending} disabled={!valid}
            onClick={() => onSubmit({ name: name.trim(), number: number.trim(), duplex, skip_busy: skipBusy, beep, member_ids: memberIds })}
          >
            {group ? t('save') : t('add')}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && !['name', 'number', 'member_ids'].includes(errorField ?? '') && <p className="text-sm text-danger">{errorMessage}</p>}
        <Field label={t('form.nameLabel')} required error={errorField === 'name' ? errorMessage : undefined}>
          {(a) => <Input {...a} autoFocus value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Field label={t('form.numberLabel')} hint={t('form.numberHint')} required error={errorField === 'number' ? errorMessage : undefined}>
          {(a) => <Input {...a} className="num" value={number} onChange={(e) => setNumber(e.target.value)} />}
        </Field>
        <Toggle checked={duplex} onCheckedChange={setDuplex} label={t('form.duplexLabel')} description={t('form.duplexDesc')} />
        <Toggle checked={skipBusy} onCheckedChange={setSkipBusy} label={t('form.skipBusyLabel')} description={t('form.skipBusyDesc')} />
        <Toggle checked={beep} onCheckedChange={setBeep} label={t('form.beepLabel')} description={t('form.beepDesc')} />

        <div>
          <p className="mb-2 text-sm font-medium text-fg">{t('form.membersLabel')}</p>
          <p className="mb-2 text-xs text-muted">{t('form.membersHint')}</p>
          <ul className="flex max-h-64 flex-col gap-1 overflow-y-auto rounded-md border border-line p-2">
            {extensions.map((e) => (
              <li key={e.id} className="flex items-center gap-2 rounded-sm px-1.5 py-1 hover:bg-surface-2/60">
                <Checkbox checked={memberIds.includes(e.id)} onCheckedChange={(v) => toggleMember(e.id, v)} aria-label={t('form.memberCheckboxAriaLabel', { number: e.number, name: e.name })} />
                <span className="num text-sm text-fg">{e.number}</span>
                <span className="truncate text-sm text-muted">{e.name}</span>
              </li>
            ))}
          </ul>
          {errorField === 'member_ids' && errorMessage && <p className="mt-1.5 text-sm text-danger">{errorMessage}</p>}
        </div>
      </div>
    </Drawer>
  );
}
