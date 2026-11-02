import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, RotateCw, Send, Trash2 } from 'lucide-react';
import {
  useCreateWebhook, useDeleteWebhook, useReplayDelivery, useRotateWebhookSecret, useTestWebhook,
  useUpdateWebhook, useWebhookDeliveries, useWebhooks,
} from '@/api/queries';
import { WEBHOOK_EVENTS, type Webhook, type WebhookEvent } from '@/api/types';
import { formatDateTimeShort } from '@/lib/time';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { Field, Input } from '@/ui/Field';
import { Badge, type Tone } from '@/ui/Status';
import { DataTable, queryState, type Column } from '@/ui/Table';
import { Checkbox, Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';
import { OtherFormError, SecretOnceModal, StaleBanner, useMutationError } from './shared';

const EVENT_KEY: Record<WebhookEvent, string> = { 'call.ringing': 'callRinging', 'call.answered': 'callAnswered', 'call.ended': 'callEnded' };
function eventLabel(t: (k: string) => string, e: WebhookEvent): string { return t(`webhooks.event.${EVENT_KEY[e]}`); }

const DELIVERY_TONE: Record<string, Tone> = { pending: 'neutral', success: 'success', failed: 'warning', dead: 'danger' };

function WebhookNameCell({ webhook }: { webhook: Webhook }) {
  const { t } = useTranslation('integrations');
  return (
    <div>
      <span className="font-medium">{webhook.name}</span>
      {webhook.disabled_reason && <p className="text-xs text-danger">{t('webhooks.disabledBanner', { reason: webhook.disabled_reason })}</p>}
    </div>
  );
}

function WebhookRowActions({
  webhook, canManage, onTest, onDeliveries, onEdit, onDelete,
}: {
  webhook: Webhook; canManage: boolean; onTest: () => void; onDeliveries: () => void; onEdit: () => void; onDelete: () => void;
}) {
  const { t } = useTranslation('integrations');
  return (
    <div className="flex justify-end gap-1.5">
      <Button size="sm" variant="ghost" data-testid={`webhook-test-${webhook.id}`} icon={<Send />} onClick={onTest}>{t('webhooks.test')}</Button>
      <Button size="sm" variant="ghost" data-testid={`webhook-deliveries-${webhook.id}`} onClick={onDeliveries}>{t('webhooks.deliveries')}</Button>
      {canManage && <Button size="sm" variant="ghost" onClick={onEdit}>{t('webhooks.edit')}</Button>}
      {canManage && <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('webhooks.delete')} onClick={onDelete} />}
    </div>
  );
}

function DeleteWebhookModal({ webhook, onClose }: { webhook: Webhook | null; onClose: () => void }) {
  const { t } = useTranslation('integrations');
  const deleteM = useDeleteWebhook();
  return (
    <Modal
      open={!!webhook}
      onOpenChange={(v) => !v && onClose()}
      title={t('webhooks.deleteConfirmTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('apiKeys.cancel')}</Button>
          <Button
            variant="danger" loading={deleteM.isPending}
            onClick={() => webhook && deleteM.mutate(webhook.id, { onSuccess: onClose })}
          >
            {t('webhooks.delete')}
          </Button>
        </>
      }
    >
      <p className="text-sm text-muted">{t('webhooks.deleteConfirmBody', { name: webhook?.name })}</p>
    </Modal>
  );
}

function WebhookEnabledBadge({ enabled }: { enabled: boolean }) {
  const { t } = useTranslation('integrations');
  return <Badge tone={enabled ? 'success' : 'neutral'}>{enabled ? t('webhooks.enabledLabel') : t('webhooks.edit')}</Badge>;
}

type WebhookRowHandlers = {
  onTest: (webhook: Webhook) => void; onDeliveries: (webhook: Webhook) => void; onEdit: (webhook: Webhook) => void; onDelete: (webhook: Webhook) => void;
};

function webhookColumns(
  t: (k: string) => string, canManage: boolean, handlers: WebhookRowHandlers,
): Column<Webhook>[] {
  return [
    { key: 'name', header: t('webhooks.name'), sortValue: (r) => r.name, cell: (r) => <WebhookNameCell webhook={r} /> },
    { key: 'url', header: t('webhooks.url'), cell: (r) => <span className="num text-sm text-muted break-all">{r.url}</span> },
    { key: 'events', header: t('webhooks.events'), cell: (r) => <div className="flex flex-wrap gap-1">{r.events.map((e) => <Badge key={e}>{eventLabel(t, e)}</Badge>)}</div> },
    { key: 'enabled', header: t('webhooks.enabledLabel'), cell: (r) => <WebhookEnabledBadge enabled={r.enabled} /> },
    {
      key: 'actions', header: '', align: 'right', cell: (r) => (
        <WebhookRowActions
          webhook={r} canManage={canManage}
          onTest={() => handlers.onTest(r)}
          onDeliveries={() => handlers.onDeliveries(r)}
          onEdit={() => handlers.onEdit(r)}
          onDelete={() => handlers.onDelete(r)}
        />
      ),
    },
  ];
}

/** M3b §3 — vebhuklar roʻyxati, yaratish/tahrirlash, sinov, yetkazishlar jurnali va qayta yuborish. */
export function WebhooksTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('integrations');
  const { data, isLoading, isError, refetch } = useWebhooks();
  const toast = useToast();
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<Webhook | null>(null);
  const [deleting, setDeleting] = useState<Webhook | null>(null);
  const [deliveriesFor, setDeliveriesFor] = useState<Webhook | null>(null);
  const [secret, setSecret] = useState<{ title: string; secret: string } | null>(null);
  const testM = useTestWebhook();
  const rotateM = useRotateWebhookSecret();

  const columns = webhookColumns(t, canManage, {
    onTest: (webhook) => testM.mutate(webhook.id, { onSuccess: () => toast({ kind: 'success', title: t('webhooks.testSent') }) }),
    onDeliveries: setDeliveriesFor,
    onEdit: setEditing,
    onDelete: setDeleting,
  });

  return (
    <section>
      <div className="mb-3 flex items-start justify-between gap-3">
        <p className="max-w-2xl text-sm text-muted">{t('webhooks.desc')}</p>
        {canManage && <Button data-testid="webhook-create" icon={<Plus />} onClick={() => setCreateOpen(true)}>{t('webhooks.create')}</Button>}
      </div>
      <DataTable
        caption={t('webhooks.title')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(r) => r.id}
        searchText={(r) => `${r.name} ${r.url}`}
        state={queryState(isLoading, isError)}
        onRetry={() => void refetch()}
        empty={{ title: t('webhooks.empty'), body: '' }}
      />

      <WebhookFormModal
        open={createOpen || !!editing}
        webhook={editing}
        onClose={() => { setCreateOpen(false); setEditing(null); }}
        onCreated={(secretValue) => { setCreateOpen(false); setSecret({ title: t('webhooks.secretTitle'), secret: secretValue }); }}
      />

      <DeleteWebhookModal webhook={deleting} onClose={() => setDeleting(null)} />
      <SecretOnceModal
        open={!!secret}
        title={secret ? secret.title : ''}
        warning={t('webhooks.secretWarning')}
        secret={secret?.secret}
        secretTestId="webhook-secret"
        onClose={() => setSecret(null)}
      />
      <DeliveriesModal
        webhook={deliveriesFor}
        onClose={() => setDeliveriesFor(null)}
        onRotateSecret={(id) => rotateM.mutate(id, { onSuccess: (res) => setSecret({ title: t('webhooks.rotatedTitle'), secret: res.secret }) })}
        rotating={rotateM.isPending}
        canManage={canManage}
      />
    </section>
  );
}

type WebhookFormState = {
  name: string; url: string; events: Set<WebhookEvent>; includeInternal: boolean; enabled: boolean;
};

const EMPTY_WEBHOOK_FORM: WebhookFormState = { name: '', url: '', events: new Set(), includeInternal: false, enabled: true };

function webhookFormState(webhook: Webhook | null): WebhookFormState {
  if (!webhook) return EMPTY_WEBHOOK_FORM;
  return { name: webhook.name, url: webhook.url, events: new Set(webhook.events), includeInternal: webhook.include_internal, enabled: webhook.enabled };
}

/** `webhook` prop har ochilishda yangilanishi mumkin — formani shunga moslab qayta ishga tushiradi. */
function useWebhookForm(webhook: Webhook | null) {
  const [state, setState] = useState(() => webhookFormState(webhook));
  const [lastId, setLastId] = useState(webhook?.id);
  if (webhook?.id !== lastId) {
    setLastId(webhook?.id);
    setState(webhookFormState(webhook));
  }
  const toggleEvent = (e: WebhookEvent, v: boolean) => setState((prev) => {
    const next = new Set(prev.events);
    if (v) next.add(e); else next.delete(e);
    return { ...prev, events: next };
  });
  return { state, setState, toggleEvent };
}

function EventsField({ events, onToggle }: { events: Set<WebhookEvent>; onToggle: (e: WebhookEvent, v: boolean) => void }) {
  const { t } = useTranslation('integrations');
  return (
    <div className="flex flex-col gap-2">
      {WEBHOOK_EVENTS.map((e) => (
        <label key={e} className="flex items-center gap-2 text-sm">
          <Checkbox checked={events.has(e)} onCheckedChange={(v) => onToggle(e, v)} aria-label={eventLabel(t, e)} />
          {eventLabel(t, e)}
        </label>
      ))}
    </div>
  );
}

/** `name`/`url`/`events` maydon xatolari allaqachon oʻz joyida koʻrsatiladi — faqat qolgan umumiy xato shu yerda. */
function otherFormError(errorMessage: string | undefined, stale: boolean, errorField: string | undefined): string | null {
  if (!errorMessage || stale) return null;
  return errorField === 'name' || errorField === 'url' || errorField === 'events' ? null : errorMessage;
}

/** Berilgan maydonga tegishli xatoni qaytaradi — aks holda `undefined` (xato boshqa maydonda yoki yoʻq). */
function fieldError(errorField: string | undefined, field: string, message: string | undefined): string | undefined {
  return errorField === field ? message : undefined;
}

function webhookFormTitle(t: (k: string) => string, webhook: Webhook | null): string {
  return webhook ? t('webhooks.edit') : t('webhooks.create');
}

function WebhookFormFooter({ webhook, pending, onCancel, onSubmit }: {
  webhook: Webhook | null; pending: boolean; onCancel: () => void; onSubmit: () => void;
}) {
  const { t } = useTranslation('integrations');
  const submitLabel = webhook ? t('webhooks.save') : t('webhooks.create');
  return (
    <>
      <Button variant="ghost" onClick={onCancel}>{t('apiKeys.cancel')}</Button>
      <Button variant="primary" loading={pending} onClick={onSubmit}>{submitLabel}</Button>
    </>
  );
}

function WebhookFormModal({
  open, webhook, onClose, onCreated,
}: { open: boolean; webhook: Webhook | null; onClose: () => void; onCreated: (secret: string) => void }) {
  const { t } = useTranslation('integrations');
  const toast = useToast();
  const createM = useCreateWebhook();
  const updateM = useUpdateWebhook();
  const { state, setState, toggleEvent } = useWebhookForm(webhook);
  const { name, url, events, includeInternal, enabled } = state;

  const pending = createM.isPending || updateM.isPending;
  const { field: errorField, message: errorMessage, stale } = useMutationError(createM.error ?? updateM.error);

  const close = () => { createM.reset(); updateM.reset(); onClose(); };
  const setName = (v: string) => setState((prev) => ({ ...prev, name: v }));
  const setUrl = (v: string) => setState((prev) => ({ ...prev, url: v }));
  const setIncludeInternal = (v: boolean) => setState((prev) => ({ ...prev, includeInternal: v }));
  const setEnabled = (v: boolean) => setState((prev) => ({ ...prev, enabled: v }));

  const submit = () => {
    const payload = { name: name.trim(), url: url.trim(), events: [...events], include_internal: includeInternal, enabled };
    if (webhook) {
      updateM.mutate({ id: webhook.id, payload: { ...payload, updated_at: webhook.updated_at } }, { onSuccess: () => { toast({ kind: 'success', title: t('webhooks.saved') }); close(); } });
    } else {
      createM.mutate(payload, { onSuccess: (res) => onCreated(res.secret) });
    }
  };

  return (
    <Modal
      open={open}
      onOpenChange={(v) => !v && close()}
      title={webhookFormTitle(t, webhook)}
      footer={<WebhookFormFooter webhook={webhook} pending={pending} onCancel={close} onSubmit={submit} />}
    >
      <div className="flex flex-col gap-4">
        <StaleBanner stale={stale} message={errorMessage} />
        <Field label={t('webhooks.name')} error={fieldError(errorField, 'name', errorMessage)}>
          {(a) => <Input {...a} autoFocus value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Field label={t('webhooks.url')} hint={t('webhooks.urlHint')} error={fieldError(errorField, 'url', t('webhooks.errors.url_forbidden'))}>
          {(a) => <Input {...a} mono value={url} onChange={(e) => setUrl(e.target.value)} />}
        </Field>
        <Field label={t('webhooks.events')} error={fieldError(errorField, 'events', errorMessage)}>
          {() => <EventsField events={events} onToggle={toggleEvent} />}
        </Field>
        <Toggle checked={includeInternal} onCheckedChange={setIncludeInternal} label={t('webhooks.includeInternal')} />
        <Toggle checked={enabled} onCheckedChange={setEnabled} label={t('webhooks.enabledLabel')} />
        <OtherFormError message={otherFormError(errorMessage, stale, errorField)} />
      </div>
    </Modal>
  );
}


type Delivery = { id: string; status: string; event_type: string; http_status: number | null; attempts: number; created_at: string };

function DeliveryReplayAction({ delivery, canManage, webhookId }: { delivery: Delivery; canManage: boolean; webhookId: string }) {
  const { t } = useTranslation('integrations');
  const toast = useToast();
  const replayM = useReplayDelivery(webhookId);
  const replayable = delivery.status === 'failed' || delivery.status === 'dead';
  if (!replayable || !canManage) return null;
  return (
    <Button
      size="sm" variant="ghost" data-testid={`delivery-replay-${delivery.id}`}
      onClick={() => replayM.mutate(delivery.id, { onSuccess: () => toast({ kind: 'success', title: t('webhooks.replayed') }) })}
    >
      {t('webhooks.replay')}
    </Button>
  );
}

function deliveryColumns(
  t: (k: string, o?: Record<string, unknown>) => string, canManage: boolean, webhookId: string,
): Column<Delivery>[] {
  return [
    { key: 'event_type', header: t('webhooks.columns.event'), cell: (r) => <span className="text-sm">{r.event_type}</span> },
    { key: 'status', header: t('webhooks.columns.status'), cell: (r) => <Badge tone={DELIVERY_TONE[r.status]}>{t(`webhooks.deliveryStatus.${r.status}`)}</Badge> },
    { key: 'http_status', header: t('webhooks.columns.httpCode'), cell: (r) => <span className="num text-sm text-muted">{r.http_status ?? '—'}</span> },
    { key: 'attempts', header: t('webhooks.columns.attempts'), align: 'right', cell: (r) => <span className="num">{r.attempts}</span> },
    { key: 'created_at', header: t('webhooks.columns.at'), cell: (r) => <span className="num text-sm text-muted">{formatDateTimeShort(r.created_at)}</span> },
    { key: 'actions', header: '', align: 'right', cell: (r) => <DeliveryReplayAction delivery={r} canManage={canManage} webhookId={webhookId} /> },
  ];
}

function deliveriesFooter(
  t: (k: string) => string, webhook: Webhook | null, canManage: boolean, rotating: boolean, onRotateSecret: (id: string) => void,
): React.ReactNode {
  if (!canManage || !webhook) return undefined;
  return <Button variant="secondary" icon={<RotateCw />} loading={rotating} onClick={() => onRotateSecret(webhook.id)}>{t('webhooks.rotateSecret')}</Button>;
}

function DeliveriesModal({
  webhook, onClose, onRotateSecret, rotating, canManage,
}: { webhook: Webhook | null; onClose: () => void; onRotateSecret: (id: string) => void; rotating: boolean; canManage: boolean }) {
  const { t } = useTranslation('integrations');
  const webhookId = webhook?.id ?? '';
  const { data, isLoading, isError, refetch } = useWebhookDeliveries(webhookId, { limit: 50 });
  const columns = deliveryColumns(t, canManage, webhookId);

  return (
    <Modal
      size="sm"
      open={!!webhook}
      onOpenChange={(v) => !v && onClose()}
      title={webhook ? t('webhooks.deliveries') : ''}
      footer={deliveriesFooter(t, webhook, canManage, rotating, onRotateSecret)}
    >
      <DataTable
        caption={t('webhooks.deliveries')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(r) => r.id}
        searchText={(r) => r.event_type}
        state={queryState(isLoading, isError)}
        onRetry={() => void refetch()}
        pageSize={10}
        empty={{ title: t('webhooks.deliveriesEmpty'), body: '' }}
      />
    </Modal>
  );
}
