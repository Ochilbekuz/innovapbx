import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link2Off, Pencil, Plus, Route as RouteIcon, ShieldAlert, Trash2 } from 'lucide-react';
import {
  useCidSources, useCreateInboundRoute, useDeleteInboundRoute, useFlow, useInboundRoutes, useTargets, useUpdateInboundRoute,
} from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { InboundRoute } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { applyToast } from '@/lib/applyToast';
import { resolveDestination, type Catalog, type Destination } from '@/domain/destination';
import { fromApiFlow } from '@/domain/flow';
import { DestinationPicker } from '@/pbx/DestinationPicker';
import { CallFlowTree } from '@/pbx/CallFlow';
import { toCatalog } from '@/pbx/catalog';
import { M1A_KINDS } from '@/pbx/kinds';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input, Select } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

const DID_RE = /^\d{3,15}$/;
const CID_RE = /^\+?\d{3,15}$/;
// M9 B3 — qarang ../../../replica/m9-freepbx-gaps-contract.md §B3
const ALERT_INFO_RE = /^[A-Za-z0-9=<>:;/._@-]{1,128}$/;

type FormState = {
  name: string; didAny: boolean; did: string; cidAny: boolean; cid: string; destination: Destination | null; enabled: boolean;
  cidLookupSourceId: string; cidNamePrefix: string; alertInfo: string;
};

function toForm(r?: InboundRoute): FormState {
  return {
    name: r?.name ?? '',
    didAny: r ? r.did === null : true,
    did: r?.did ?? '',
    cidAny: r ? r.cid === null : true,
    cid: r?.cid ?? '',
    destination: r ? { kind: r.target.kind, targetId: r.target.id } : null,
    enabled: r?.enabled ?? true,
    cidLookupSourceId: r?.cid_lookup_source?.id ?? '',
    cidNamePrefix: r?.cid_name_prefix ?? '',
    alertInfo: r?.alert_info ?? '',
  };
}

/** S07 — kiruvchi marshrutlar: DID/CID, manzil (M1a: ichki raqam, guruh, navbat, IVR, ish vaqti, yakunlash/band), uzilgan manzil holati, oqim grafigi. */
export function InboundRoutesPage() {
  const { t } = useTranslation('routes');
  const { data, isLoading, isError, refetch } = useInboundRoutes();
  const { data: targets } = useTargets({ kind: M1A_KINDS.join(',') });
  const { data: cidSourcesData } = useCidSources();
  const canManage = useCanEdit('connect');
  const toast = useToast();
  const [editing, setEditing] = useState<InboundRoute | 'new' | null>(null);
  const [deleting, setDeleting] = useState<InboundRoute | null>(null);
  const [viewingFlow, setViewingFlow] = useState<InboundRoute | null>(null);

  const createM = useCreateInboundRoute();
  const updateM = useUpdateInboundRoute();
  const deleteM = useDeleteInboundRoute();

  const catalog: Catalog = useMemo(() => toCatalog(targets?.items ?? []), [targets]);

  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;

  const columns: Column<InboundRoute>[] = [
    { key: 'name', header: t('column.name'), sortValue: (r) => r.name, cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'did', header: t('column.did'), cell: (r) => <span className="num text-muted">{r.did ?? t('any')}</span> },
    { key: 'cid', header: t('column.cid'), cell: (r) => <span className="num text-muted">{r.cid ?? t('any')}</span> },
    {
      key: 'target', header: t('column.target'), cell: (r) => r.target.broken ? (
        <span className="flex items-center gap-1.5 text-danger"><Link2Off aria-hidden className="size-3.5" /> {t('targetBroken', { id: r.target.id })}</span>
      ) : (
        <span>{r.target.label}</span>
      ),
    },
    { key: 'enabled', header: t('column.enabled'), cell: (r) => <Badge tone={r.enabled ? 'success' : 'neutral'}>{r.enabled ? t('yes') : t('no')}</Badge> },
    {
      key: 'actions', header: '', align: 'right', cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<RouteIcon />} aria-label={t('viewFlowAriaLabel', { name: r.name })} onClick={() => setViewingFlow(r)} />
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('editAriaLabel', { name: r.name })} disabled={!canManage} onClick={() => setEditing(r)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('deleteAriaLabel', { name: r.name })} disabled={!canManage} onClick={() => setDeleting(r)} />
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
        rowId={(r) => r.id}
        searchText={(r) => `${r.name} ${r.did ?? ''} ${r.cid ?? ''} ${r.target.label}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (r) => setEditing(r) : undefined}
        empty={{ title: t('empty.title'), body: t('empty.body'), action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('empty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('newRoute')}</Button> : undefined}
      />

      {editing && (
        <RouteForm
          route={editing === 'new' ? undefined : editing}
          catalog={catalog}
          cidSources={cidSourcesData?.items ?? []}
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
        description={t('deleteModal.description')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleting(null)}>{t('cancel')}</Button>
            <Button
              variant="danger" loading={deleteM.isPending}
              onClick={() => deleting && deleteM.mutate(deleting.id, {
                onSuccess: () => { toast({ kind: 'success', title: t('toast.deleted', { name: deleting.name }) }); setDeleting(null); },
                onError: (e) => { toast({ kind: 'error', title: t('toast.deleteFailed'), description: e.message }); setDeleting(null); },
              })}
            >
              {t('delete')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">{t('deleteModal.body', { name: deleting?.name })}</p>
      </Modal>

      <Drawer
        open={!!viewingFlow}
        onOpenChange={(v) => !v && setViewingFlow(null)}
        title={viewingFlow ? t('flowDrawer.title', { name: viewingFlow.name }) : ''}
        description={t('flowDrawer.description')}
      >
        {viewingFlow && <RouteFlowView route={viewingFlow} />}
      </Drawer>
    </AppShellPage>
  );
}

function RouteFlowView({ route }: { route: InboundRoute }) {
  const { t } = useTranslation('routes');
  const { data, isLoading, isError, refetch } = useFlow(route.id);
  if (isLoading) return <p className="text-sm text-muted">{t('flowDrawer.loading')}</p>;
  if (isError || !data) {
    return (
      <div className="flex flex-col items-start gap-2 text-sm">
        <p className="text-danger">{t('flowDrawer.loadFailed')}</p>
        <Button size="sm" variant="ghost" onClick={() => void refetch()}>{t('flowDrawer.retry')}</Button>
      </div>
    );
  }
  return <CallFlowTree did={route.did ?? t('any')} tree={fromApiFlow(data.root)} layout="stacked" />;
}

function RouteForm({
  route, catalog, cidSources, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  route?: InboundRoute;
  catalog: Catalog;
  cidSources: { id: string; name: string }[];
  onClose: () => void;
  onSubmit: (payload: {
    name: string; did: string | null; cid: string | null; target_id: string; enabled: boolean;
    cid_lookup_source_id: string | null; cid_name_prefix: string | null; alert_info: string | null;
  }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('routes');
  const [form, setForm] = useState<FormState>(() => toForm(route));
  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setForm((f) => ({ ...f, [k]: v }));

  const didError = !form.didAny && form.did.trim() !== '' && !DID_RE.test(form.did.trim()) ? t('error.didFormat') : undefined;
  const cidError = !form.cidAny && form.cid.trim() !== '' && !CID_RE.test(form.cid.trim()) ? t('error.cidFormat') : undefined;
  const alertInfoError = form.alertInfo.trim() !== '' && !ALERT_INFO_RE.test(form.alertInfo.trim()) ? t('error.alertInfoFormat') : undefined;
  const destResolved = resolveDestination(form.destination, catalog);
  const destOk = destResolved.state === 'ok';

  const valid = form.name.trim().length > 0 && destOk && !didError && !cidError && !alertInfoError
    && (form.didAny || form.did.trim() !== '') && (form.cidAny || form.cid.trim() !== '');

  const submit = () => {
    if (!valid || !form.destination || form.destination.kind === 'external') return;
    onSubmit({
      name: form.name.trim(),
      did: form.didAny ? null : form.did.trim(),
      cid: form.cidAny ? null : form.cid.trim(),
      target_id: form.destination.targetId,
      enabled: form.enabled,
      cid_lookup_source_id: form.cidLookupSourceId || null,
      cid_name_prefix: form.cidNamePrefix.trim() || null,
      alert_info: form.alertInfo.trim() || null,
    });
  };

  return (
    <Modal
      open
      onOpenChange={(v) => !v && onClose()}
      title={route ? t('form.editTitle', { name: route.name }) : t('form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={submit}>{route ? t('save') : t('add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label={t('form.nameLabel')} required>
          {(a) => <Input {...a} autoFocus value={form.name} onChange={(e) => set('name', e.target.value)} />}
        </Field>

        <div className="flex flex-col gap-2">
          <Toggle checked={form.didAny} onCheckedChange={(v) => set('didAny', v)} label={t('form.didAnyLabel')} description={t('form.didAnyDesc')} />
          {!form.didAny && (
            <Field label={t('form.didLabel')} required error={didError ?? (errorField === 'did' ? errorMessage : undefined)} hint={t('form.didHint')}>
              {(a) => <Input {...a} mono value={form.did} onChange={(e) => set('did', e.target.value)} />}
            </Field>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <Toggle checked={form.cidAny} onCheckedChange={(v) => set('cidAny', v)} label={t('form.cidAnyLabel')} />
          {!form.cidAny && (
            <Field label={t('form.cidLabel')} required error={cidError}>
              {(a) => <Input {...a} mono placeholder={t('form.cidPlaceholder')} value={form.cid} onChange={(e) => set('cid', e.target.value)} />}
            </Field>
          )}
        </div>

        <DestinationPicker
          label={t('form.destinationLabel')}
          kinds={M1A_KINDS}
          required
          value={form.destination}
          onChange={(d) => set('destination', d)}
          catalog={catalog}
          hint={t('form.destinationHint')}
        />

        <Toggle checked={form.enabled} onCheckedChange={(v) => set('enabled', v)} label={t('form.enabledLabel')} />

        <Field label={t('form.cidLookupSourceLabel')} hint={t('form.cidLookupSourceHint')}>
          {(a) => (
            <Select
              {...a}
              value={form.cidLookupSourceId}
              onValueChange={(v) => set('cidLookupSourceId', v)}
              options={[{ value: '', label: t('form.cidLookupSourceNone') }, ...cidSources.map((s) => ({ value: s.id, label: s.name }))]}
            />
          )}
        </Field>

        <Field label={t('form.cidNamePrefixLabel')} hint={t('form.cidNamePrefixHint')}>
          {(a) => <Input {...a} value={form.cidNamePrefix} onChange={(e) => set('cidNamePrefix', e.target.value)} placeholder={t('form.cidNamePrefixPlaceholder')} />}
        </Field>

        <Field label={t('form.alertInfoLabel')} hint={t('form.alertInfoHint')} error={alertInfoError}>
          {(a) => <Input {...a} mono value={form.alertInfo} onChange={(e) => set('alertInfo', e.target.value)} placeholder={t('form.alertInfoPlaceholder')} />}
        </Field>

        {errorMessage && errorField !== 'did' ? <p className="text-sm text-danger">{errorMessage}</p> : null}
      </div>
    </Modal>
  );
}
