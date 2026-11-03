import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pencil, Plus, ShieldAlert, Trash2 } from 'lucide-react';
import {
  useCreateMiscApplication, useCreateMiscDestination, useDeleteMiscApplication, useDeleteMiscDestination,
  useMiscApplications, useMiscDestinations, useTargets, useUpdateMiscApplication, useUpdateMiscDestination,
} from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { MiscApplication, MiscDestination, Usage } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { TARGET_KINDS, type Destination } from '@/domain/destination';
import { toCatalog } from '@/pbx/catalog';
import { DestinationPicker } from '@/pbx/DestinationPicker';
import { applyToast } from '@/lib/applyToast';
import { usagesOf } from '@/lib/usageError';
import { UsageList } from '@/pbx/UsageList';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input } from '@/ui/Field';
import { Tabs } from '@/ui/Tabs';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

/** S28 — boshqa manzillar: erkin terish kodlari (manzillar) va ularga toʻgʻridan-toʻgʻri ulanadigan maxsus kodlar. */
export function MiscPage() {
  const { t } = useTranslation('misc');
  const canManage = useCanEdit('routing');
  return (
    <AppShellPage title={t('title')}>
      {!canManage && (
        <p className="mb-3 flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2 text-sm text-muted">
          <ShieldAlert aria-hidden className="size-4 shrink-0" />
          {t('readOnlyNotice')}
        </p>
      )}
      <Tabs
        label={t('tabsAriaLabel')}
        items={[
          { value: 'destinations', label: t('tabs.destinations'), content: <DestinationsTab canManage={canManage} /> },
          { value: 'applications', label: t('tabs.applications'), content: <ApplicationsTab canManage={canManage} /> },
        ]}
      />
    </AppShellPage>
  );
}

// ─────────────────────────── Manzillar ───────────────────────────

function DestinationsTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('misc');
  const { data, isLoading, isError, refetch } = useMiscDestinations();
  const toast = useToast();
  const [editing, setEditing] = useState<MiscDestination | 'new' | null>(null);
  const [deleting, setDeleting] = useState<MiscDestination | null>(null);
  const [deleteErr, setDeleteErr] = useState<Usage[] | null>(null);

  const createM = useCreateMiscDestination();
  const updateM = useUpdateMiscDestination();
  const deleteM = useDeleteMiscDestination();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;

  const columns: Column<MiscDestination>[] = [
    { key: 'name', header: t('destinations.column.name'), sortValue: (d) => d.name, cell: (d) => <span className="font-medium">{d.name}</span> },
    { key: 'dial', header: t('destinations.column.dial'), cell: (d) => <span className="num text-muted">{d.dial}</span> },
    {
      key: 'actions', header: '', align: 'right', cell: (d) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('destinations.editAriaLabel', { name: d.name })} disabled={!canManage} onClick={() => setEditing(d)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('destinations.deleteAriaLabel', { name: d.name })} disabled={!canManage} onClick={() => setDeleting(d)} />
        </div>
      ),
    },
  ];

  return (
    <div className="pt-3">
      <DataTable
        caption={t('destinations.caption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(d) => d.id}
        searchText={(d) => `${d.name} ${d.dial}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (d) => setEditing(d) : undefined}
        empty={{ title: t('destinations.empty.title'), body: t('destinations.empty.body'), action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('destinations.empty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('destinations.newItem')}</Button> : undefined}
      />

      {editing && (
        <DestinationForm
          item={editing === 'new' ? undefined : editing}
          pending={mutation.isPending}
          errorField={isApiError(mutation.error) ? mutation.error.field : undefined}
          errorMessage={isApiError(mutation.error) ? mutation.error.message : undefined}
          onClose={close}
          onSubmit={(payload) => {
            if (editing === 'new') {
              createM.mutate(payload, { onSuccess: (res) => { close(); toast(applyToast(res.apply, t('destinations.toast.added'))); } });
            } else {
              updateM.mutate({ id: editing.id, payload: { ...payload, updated_at: editing.updated_at } }, {
                onSuccess: (res) => { close(); toast(applyToast(res.apply, t('destinations.toast.saved'))); },
              });
            }
          }}
        />
      )}

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && (setDeleting(null), setDeleteErr(null))}
        title={deleting ? t('destinations.deleteModal.title', { name: deleting.name }) : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => { setDeleting(null); setDeleteErr(null); }}>{t('cancel')}</Button>
            {!deleteErr && (
              <Button
                variant="danger" loading={deleteM.isPending}
                onClick={() => deleting && deleteM.mutate(deleting.id, {
                  onSuccess: () => { toast({ kind: 'success', title: t('destinations.toast.deleted', { name: deleting.name }) }); setDeleting(null); },
                  onError: (e) => { if (isApiError(e) && e.code === 'in_use') setDeleteErr(usagesOf(e)); else toast({ kind: 'error', title: t('destinations.toast.deleteFailed'), description: e.message }); },
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
            <p className="text-sm text-danger">{t('destinations.deleteModal.usagePrefix', { name: deleting?.name })}</p>
            <UsageList usages={deleteErr} />
          </div>
        ) : (
          <p className="text-sm text-muted">{t('destinations.deleteModal.body', { name: deleting?.name })}</p>
        )}
      </Modal>
    </div>
  );
}

function DestinationForm({
  item, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  item?: MiscDestination;
  onClose: () => void;
  onSubmit: (payload: { name: string; dial: string }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('misc');
  const [name, setName] = useState(item?.name ?? '');
  const [dial, setDial] = useState(item?.dial ?? '');
  const valid = name.trim().length > 0 && dial.trim().length > 0;

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={item ? t('destinations.form.editTitle', { name: item.name }) : t('destinations.form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={() => onSubmit({ name: name.trim(), dial: dial.trim() })}>{item ? t('save') : t('add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && !['name', 'dial'].includes(errorField ?? '') && <p className="text-sm text-danger">{errorMessage}</p>}
        <Field label={t('destinations.form.nameLabel')} required error={errorField === 'name' ? errorMessage : undefined}>
          {(a) => <Input {...a} autoFocus value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Field label={t('destinations.form.dialLabel')} hint={t('destinations.form.dialHint')} required error={errorField === 'dial' ? errorMessage : undefined}>
          {(a) => <Input {...a} className="num" value={dial} onChange={(e) => setDial(e.target.value)} />}
        </Field>
      </div>
    </Drawer>
  );
}

// ─────────────────────────── Maxsus kodlar ───────────────────────────

function ApplicationsTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('misc');
  const { data, isLoading, isError, refetch } = useMiscApplications();
  const { data: targetsData } = useTargets({ kind: TARGET_KINDS.join(',') });
  const catalog = useMemo(() => toCatalog(targetsData?.items ?? []), [targetsData]);
  const toast = useToast();
  const [editing, setEditing] = useState<MiscApplication | 'new' | null>(null);
  const [deleting, setDeleting] = useState<MiscApplication | null>(null);

  const createM = useCreateMiscApplication();
  const updateM = useUpdateMiscApplication();
  const deleteM = useDeleteMiscApplication();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;

  const columns: Column<MiscApplication>[] = [
    { key: 'name', header: t('applications.column.name'), sortValue: (a) => a.name, cell: (a) => <span className="font-medium">{a.name}</span> },
    { key: 'code', header: t('applications.column.code'), cell: (a) => <span className="num text-muted">{a.code}</span> },
    { key: 'target', header: t('applications.column.target'), cell: (a) => <span className="truncate text-sm text-muted">{a.target.label}</span> },
    {
      key: 'enabled', header: t('applications.column.enabled'), cell: (a) => (
        a.enabled ? <span className="text-fg">✓</span> : <span className="text-muted">—</span>
      ),
    },
    {
      key: 'actions', header: '', align: 'right', cell: (a) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('applications.editAriaLabel', { name: a.name })} disabled={!canManage} onClick={() => setEditing(a)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('applications.deleteAriaLabel', { name: a.name })} disabled={!canManage} onClick={() => setDeleting(a)} />
        </div>
      ),
    },
  ];

  return (
    <div className="pt-3">
      <DataTable
        caption={t('applications.caption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(a) => a.id}
        searchText={(a) => `${a.name} ${a.code}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (a) => setEditing(a) : undefined}
        empty={{ title: t('applications.empty.title'), body: t('applications.empty.body'), action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('applications.empty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('applications.newItem')}</Button> : undefined}
      />

      {editing && (
        <ApplicationForm
          item={editing === 'new' ? undefined : editing}
          catalog={catalog}
          pending={mutation.isPending}
          errorField={isApiError(mutation.error) ? mutation.error.field : undefined}
          errorMessage={isApiError(mutation.error) ? mutation.error.message : undefined}
          onClose={close}
          onSubmit={(payload) => {
            if (editing === 'new') {
              createM.mutate(payload, { onSuccess: (res) => { close(); toast(applyToast(res.apply, t('applications.toast.added'))); } });
            } else {
              updateM.mutate({ id: editing.id, payload: { ...payload, updated_at: editing.updated_at } }, {
                onSuccess: (res) => { close(); toast(applyToast(res.apply, t('applications.toast.saved'))); },
              });
            }
          }}
        />
      )}

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={deleting ? t('applications.deleteModal.title', { name: deleting.name }) : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleting(null)}>{t('cancel')}</Button>
            <Button
              variant="danger" loading={deleteM.isPending}
              onClick={() => deleting && deleteM.mutate(deleting.id, {
                onSuccess: () => { toast({ kind: 'success', title: t('applications.toast.deleted', { name: deleting.name }) }); setDeleting(null); },
                onError: (e) => toast({ kind: 'error', title: t('applications.toast.deleteFailed'), description: e.message }),
              })}
            >
              {t('delete')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">{t('applications.deleteModal.body', { name: deleting?.name })}</p>
      </Modal>
    </div>
  );
}

function ApplicationForm({
  item, catalog, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  item?: MiscApplication;
  catalog: ReturnType<typeof toCatalog>;
  onClose: () => void;
  onSubmit: (payload: { name: string; code: string; target_id: string; enabled: boolean }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('misc');
  const [name, setName] = useState(item?.name ?? '');
  const [code, setCode] = useState(item?.code ?? '');
  const [target, setTarget] = useState<Destination | null>(item ? { kind: item.target.kind, targetId: item.target.id } : null);
  const [enabled, setEnabled] = useState(item?.enabled ?? true);

  const submit = () => {
    if (!target || target.kind === 'external') return;
    if (!name.trim() || !code.trim()) return;
    onSubmit({ name: name.trim(), code: code.trim(), target_id: target.targetId, enabled });
  };
  const valid = name.trim().length > 0 && code.trim().length > 0 && !!target && target.kind !== 'external';

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={item ? t('applications.form.editTitle', { name: item.name }) : t('applications.form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={submit}>{item ? t('save') : t('add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && !['name', 'code', 'target_id'].includes(errorField ?? '') && <p className="text-sm text-danger">{errorMessage}</p>}
        <Field label={t('applications.form.nameLabel')} required error={errorField === 'name' ? errorMessage : undefined}>
          {(a) => <Input {...a} autoFocus value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Field label={t('applications.form.codeLabel')} hint={t('applications.form.codeHint')} required error={errorField === 'code' ? errorMessage : undefined}>
          {(a) => <Input {...a} className="num" value={code} onChange={(e) => setCode(e.target.value)} />}
        </Field>
        <DestinationPicker label={t('applications.form.targetLabel')} required kinds={[...TARGET_KINDS]} value={target} onChange={setTarget} catalog={catalog} />
        <Toggle checked={enabled} onCheckedChange={setEnabled} label={t('applications.form.enabledLabel')} />
      </div>
    </Drawer>
  );
}
