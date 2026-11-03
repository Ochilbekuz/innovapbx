import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { FlaskConical, Pencil, Plus, ShieldAlert, Trash2 } from 'lucide-react';
import {
  useCidSources, useCreateCidSource, useDeleteCidSource, useTestCidSource, useUpdateCidSource,
} from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { CidSource, CidSourceKind, CidSourceTestResult, Usage } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { applyToast } from '@/lib/applyToast';
import { usagesOf } from '@/lib/usageError';
import { UsageList } from '@/pbx/UsageList';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input, Select } from '@/ui/Field';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

const KINDS: CidSourceKind[] = ['phonebook', 'crm', 'http'];

/** S43 — CID qidirish manbalari: kiruvchi qoʻngʻiroqda chaqiruvchi nomini topish manbalari. */
export function CidSourcesPage() {
  const { t } = useTranslation('cidsources');
  const { data, isLoading, isError, refetch } = useCidSources();
  const canManage = useCanEdit('connect');
  const toast = useToast();
  const [editing, setEditing] = useState<CidSource | 'new' | null>(null);
  const [deleting, setDeleting] = useState<CidSource | null>(null);
  const [deleteErr, setDeleteErr] = useState<Usage[] | null>(null);
  const [testing, setTesting] = useState<CidSource | null>(null);

  const createM = useCreateCidSource();
  const updateM = useUpdateCidSource();
  const deleteM = useDeleteCidSource();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;

  const columns: Column<CidSource>[] = [
    { key: 'name', header: t('column.name'), sortValue: (c) => c.name, cell: (c) => <span className="font-medium">{c.name}</span> },
    { key: 'kind', header: t('column.kind'), cell: (c) => <span className="text-sm text-muted">{t(`kind.${c.kind}`)}</span> },
    {
      key: 'enabled', header: t('column.enabled'), cell: (c) => (
        c.enabled ? <span className="text-fg">✓</span> : <span className="text-muted">—</span>
      ),
    },
    { key: 'usedBy', header: t('column.usedBy'), cell: (c) => <span className="truncate text-sm text-muted">{c.used_by.map((u) => u.name).join(', ') || '—'}</span> },
    {
      key: 'actions', header: '', align: 'right', cell: (c) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<FlaskConical />} aria-label={t('testAriaLabel', { name: c.name })} onClick={() => setTesting(c)} />
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
        searchText={(c) => `${c.name} ${c.kind}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (c) => setEditing(c) : undefined}
        empty={{ title: t('empty.title'), body: t('empty.body'), action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('empty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('newSource')}</Button> : undefined}
      />

      {editing && (
        <CidSourceForm
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

      {testing && <TestDrawer source={testing} onClose={() => setTesting(null)} />}

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

function CidSourceForm({
  item, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  item?: CidSource;
  onClose: () => void;
  onSubmit: (payload: { name: string; kind: CidSourceKind; http_url?: string | null; http_json_path?: string | null; timeout_ms: number; cache_ttl_s: number; enabled: boolean }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('cidsources');
  const [name, setName] = useState(item?.name ?? '');
  const [kind, setKind] = useState<CidSourceKind>(item?.kind ?? 'phonebook');
  const [httpUrl, setHttpUrl] = useState(item?.http_url ?? '');
  const [httpJsonPath, setHttpJsonPath] = useState(item?.http_json_path ?? '');
  const [timeoutMs, setTimeoutMs] = useState(String(item?.timeout_ms ?? 1500));
  const [cacheTtlS, setCacheTtlS] = useState(String(item?.cache_ttl_s ?? 3600));
  const [enabled, setEnabled] = useState(item?.enabled ?? true);
  const valid = name.trim().length > 0 && (kind !== 'http' || httpUrl.trim().length > 0);

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={item ? t('form.editTitle', { name: item.name }) : t('form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button
            variant="primary" loading={pending} disabled={!valid}
            onClick={() => onSubmit({
              name: name.trim(), kind,
              http_url: kind === 'http' ? httpUrl.trim() : null,
              http_json_path: kind === 'http' && httpJsonPath.trim() ? httpJsonPath.trim() : null,
              timeout_ms: Number(timeoutMs) || 1500,
              cache_ttl_s: Number(cacheTtlS) || 0,
              enabled,
            })}
          >
            {item ? t('save') : t('add')}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && errorField !== 'name' && errorField !== 'http_url' && <p className="text-sm text-danger">{errorMessage}</p>}
        <Field label={t('form.nameLabel')} required error={errorField === 'name' ? errorMessage : undefined}>
          {(a) => <Input {...a} autoFocus value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Field label={t('form.kindLabel')}>
          {(a) => <Select {...a} value={kind} onValueChange={(v) => setKind(v as CidSourceKind)} options={KINDS.map((k) => ({ value: k, label: t(`kind.${k}`) }))} />}
        </Field>
        {kind === 'http' && (
          <>
            <Field label={t('form.httpUrlLabel')} required hint={t('form.httpUrlHint')} error={errorField === 'http_url' ? errorMessage : undefined}>
              {(a) => <Input {...a} value={httpUrl} onChange={(e) => setHttpUrl(e.target.value)} />}
            </Field>
            <Field label={t('form.httpJsonPathLabel')} hint={t('form.httpJsonPathHint')}>
              {(a) => <Input {...a} value={httpJsonPath} onChange={(e) => setHttpJsonPath(e.target.value)} />}
            </Field>
          </>
        )}
        <div className="grid grid-cols-2 gap-4">
          <Field label={t('form.timeoutLabel')}>
            {(a) => <Input {...a} type="number" className="num" value={timeoutMs} onChange={(e) => setTimeoutMs(e.target.value)} />}
          </Field>
          <Field label={t('form.cacheTtlLabel')}>
            {(a) => <Input {...a} type="number" className="num" value={cacheTtlS} onChange={(e) => setCacheTtlS(e.target.value)} />}
          </Field>
        </div>
        <Toggle checked={enabled} onCheckedChange={setEnabled} label={t('form.enabledLabel')} />
      </div>
    </Drawer>
  );
}

function TestDrawer({ source, onClose }: { source: CidSource; onClose: () => void }) {
  const { t } = useTranslation('cidsources');
  const testM = useTestCidSource();
  const [number, setNumber] = useState('');
  const [result, setResult] = useState<CidSourceTestResult | null>(null);

  const run = () => {
    setResult(null);
    testM.mutate({ id: source.id, number: number.trim() }, { onSuccess: setResult });
  };

  return (
    <Drawer open onOpenChange={(v) => !v && onClose()} title={t('form.editTitle', { name: source.name })} footer={<Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>}>
      <div className="flex flex-col gap-4">
        <Field label={t('test.numberLabel')} error={isApiError(testM.error) ? testM.error.message : undefined}>
          {(a) => <Input {...a} className="num" placeholder={t('test.numberPlaceholder')} value={number} onChange={(e) => setNumber(e.target.value)} />}
        </Field>
        <div className="flex justify-end">
          <Button variant="secondary" loading={testM.isPending} disabled={number.trim().length === 0} onClick={run}>{t('test.run')}</Button>
        </div>
        {result && (
          <p className="rounded-md border border-line bg-surface-2/60 px-3 py-2 text-sm text-fg">
            {result.error ? t('test.error', { error: result.error }) : result.name ? t('test.found', { name: result.name, ms: result.ms }) : t('test.notFound', { ms: result.ms })}
          </p>
        )}
      </div>
    </Drawer>
  );
}
