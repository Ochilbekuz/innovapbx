import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Plus, Send, ShieldAlert, X } from 'lucide-react';
import { useAlertLog, useAlertSettings, useTestAlert, useUpdateAlertSettings } from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { AlertEventFlags, AlertLogEntry, AlertSettings, AlertStatus } from '@/api/types';
import { usePermission } from '@/auth/permissions';
import { formatDateTimeShort } from '@/lib/time';
import { useEnumText } from '@/lib/useEnumText';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Field, Input } from '@/ui/Field';
import { Badge, type Tone } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

const EVENT_KEYS: (keyof AlertEventFlags)[] = ['ip_banned', 'toll_blocked', 'concurrent_limit', 'trunk_down', 'trunk_up'];
const STATUS_TONE: Record<AlertStatus, Tone> = { pending: 'neutral', sent: 'success', failed: 'danger', suppressed: 'warning', disabled: 'neutral' };

/** /settings/alerts — Telegram ogohlantirishlari: chatlar, hodisa turlari, sinov xabari, tarix. Qarang ../../../replica/m2c-contract.md §4. */
export function AlertsPage() {
  const { t } = useTranslation('alerts');
  const canManage = usePermission('*');
  const toast = useToast();
  const { data, isLoading, isError, refetch } = useAlertSettings();
  const updateM = useUpdateAlertSettings();
  const testM = useTestAlert();
  const { data: log, isLoading: logLoading, isError: logError, refetch: refetchLog } = useAlertLog({ limit: 50 });

  if (isLoading || !data) {
    return <LoadErrorPlaceholder isError={isError} onRetry={() => void refetch()} />;
  }

  const sendTest = () => testM.mutate(undefined, {
    onSuccess: (res) => { toast({ kind: 'success', title: t('test.sentTitle'), description: t('test.sentDesc', { count: res.sent }) }); void refetchLog(); },
    onError: (e) => toast({ kind: 'error', title: t('test.failedTitle'), description: e.message }),
  });

  return (
    <AppShellPage title={t('title')}>
      {!canManage && <ReadOnlyNotice text={t('readOnlyNotice')} />}
      <p className="mb-4 max-w-2xl text-sm text-muted">{t('description')}</p>

      <div className="flex flex-col gap-5">
        {!data.has_telegram_token && <NoTokenBanner notice={t('noTokenNotice')} linkLabel={t('noTokenLink')} />}

        <SettingsForm
          settings={data}
          canManage={canManage}
          pending={updateM.isPending}
          errorField={isApiError(updateM.error) ? updateM.error.field : undefined}
          errorMessage={isApiError(updateM.error) ? updateM.error.message : undefined}
          stale={isApiError(updateM.error) && updateM.error.code === 'stale'}
          onRetry={() => void refetch()}
          onSubmit={(payload) => updateM.mutate({ ...payload, updated_at: data.updated_at }, {
            onSuccess: () => toast({ kind: 'success', title: t('saved') }),
          })}
        />

        <TestAlertSection canManage={canManage} pending={testM.isPending} onSend={sendTest} />

        <AlertHistoryTable items={log?.items ?? []} state={logLoading ? 'loading' : logError ? 'error' : 'ready'} onRetry={() => void refetchLog()} />
      </div>
    </AppShellPage>
  );
}

function LoadErrorPlaceholder({ isError, onRetry }: { isError: boolean; onRetry: () => void }) {
  const { t } = useTranslation('alerts');
  return (
    <AppShellPage title={t('title')}>
      <p className="rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">{isError ? t('loadFailed') : t('loading')}</p>
      {isError && <Button size="sm" variant="secondary" className="mt-2" onClick={onRetry}>{t('retry')}</Button>}
    </AppShellPage>
  );
}

function AlertHistoryTable({ items, state, onRetry }: { items: AlertLogEntry[]; state: 'loading' | 'error' | 'ready'; onRetry: () => void }) {
  const { t } = useTranslation('alerts');
  const columns: Column<AlertLogEntry>[] = [
    { key: 'at', header: t('history.column.at'), sortValue: (e) => e.at, cell: (e) => <span className="num text-sm">{formatDateTimeShort(e.at)}</span> },
    { key: 'text', header: t('history.column.text'), cell: (e) => <span className="text-sm">{e.text}</span> },
    { key: 'status', header: t('history.column.status'), cell: (e) => <AlertStatusBadge status={e.status} /> },
  ];
  return (
    <DataTable
      caption={t('history.caption')}
      rows={items}
      columns={columns}
      rowId={(e) => e.id}
      searchText={(e) => e.text}
      state={state}
      onRetry={onRetry}
      empty={{ title: t('history.empty.title'), body: t('history.empty.body') }}
    />
  );
}

function ReadOnlyNotice({ text }: { text: string }) {
  return (
    <p className="mb-3 flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2 text-sm text-muted">
      <ShieldAlert aria-hidden className="size-4 shrink-0" />
      {text}
    </p>
  );
}

function NoTokenBanner({ notice, linkLabel }: { notice: string; linkLabel: string }) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-sm text-on-warning-soft">
      <ShieldAlert aria-hidden className="size-4 shrink-0" />
      <span className="flex-1">{notice}</span>
      <Link to="/settings/sip" className="font-medium underline underline-offset-2 hover:no-underline">{linkLabel}</Link>
    </div>
  );
}

function TestAlertSection({ canManage, pending, onSend }: { canManage: boolean; pending: boolean; onSend: () => void }) {
  const { t } = useTranslation('alerts');
  return (
    <section className="max-w-2xl rounded-lg border border-line bg-surface p-4 shadow-card">
      <h3 className="mb-1 font-display text-base font-semibold">{t('test.title')}</h3>
      <p className="mb-3 text-sm text-muted">{t('test.description')}</p>
      <Button variant="secondary" icon={<Send />} disabled={!canManage} loading={pending} onClick={onSend}>{t('test.send')}</Button>
    </section>
  );
}

function AlertStatusBadge({ status }: { status: AlertStatus }) {
  const { t } = useTranslation('alerts');
  return <Badge tone={STATUS_TONE[status]}>{t(`history.status.${status}`)}</Badge>;
}

function SettingsForm({
  settings, canManage, onSubmit, pending, errorField, errorMessage, stale, onRetry,
}: {
  settings: AlertSettings;
  canManage: boolean;
  onSubmit: (payload: { chat_ids: string[]; dedup_s: number; events: AlertEventFlags }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
  stale: boolean;
  onRetry: () => void;
}) {
  const { t } = useTranslation('alerts');
  const eventLabel = useEnumText('alerts', 'events', EVENT_KEYS);
  const [chatIds, setChatIds] = useState<string[]>(settings.chat_ids);
  const [newChatId, setNewChatId] = useState('');
  const [dedupS, setDedupS] = useState(String(settings.dedup_s));
  const [events, setEvents] = useState<AlertEventFlags>(settings.events);

  const valid = /^\d+$/.test(dedupS.trim());
  const addChatId = () => {
    const v = newChatId.trim();
    if (!v || chatIds.includes(v)) return;
    setChatIds((prev) => [...prev, v]);
    setNewChatId('');
  };
  const removeChatId = (id: string) => setChatIds((prev) => prev.filter((c) => c !== id));
  const toggleEvent = (key: keyof AlertEventFlags, v: boolean) => setEvents((prev) => ({ ...prev, [key]: v }));

  return (
    <div className="flex max-w-2xl flex-col gap-5">
      {stale && (
        <div className="flex items-center gap-2 rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-sm text-on-warning-soft">
          <ShieldAlert aria-hidden className="size-4 shrink-0" />
          <span className="flex-1">{t('staleNotice')}</span>
          <Button size="sm" variant="secondary" onClick={onRetry}>{t('retry')}</Button>
        </div>
      )}

      <ChatIdsSection
        chatIds={chatIds} newChatId={newChatId} canManage={canManage}
        errorMessage={errorField === 'chat_ids' ? errorMessage : undefined}
        onNewChatIdChange={setNewChatId} onAdd={addChatId} onRemove={removeChatId}
      />

      <section className="rounded-lg border border-line bg-surface p-4 shadow-card">
        <h3 className="mb-3 font-display text-base font-semibold">{t('events.title')}</h3>
        <div className="flex flex-col gap-3">
          {EVENT_KEYS.map((key) => (
            <Toggle key={key} checked={events[key]} disabled={!canManage} onCheckedChange={(v) => toggleEvent(key, v)} label={eventLabel[key]} />
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-line bg-surface p-4 shadow-card">
        <Field label={t('dedup.label')} hint={t('dedup.hint')} error={errorField === 'dedup_s' ? errorMessage : undefined} className="max-w-xs">
          {(a) => <Input {...a} mono inputMode="numeric" disabled={!canManage} value={dedupS} onChange={(e) => setDedupS(e.target.value)} />}
        </Field>
      </section>

      {errorMessage && errorField !== 'chat_ids' && errorField !== 'dedup_s' && !stale ? <p className="text-sm text-danger">{errorMessage}</p> : null}

      {canManage && (
        <div>
          <Button
            variant="primary" disabled={!valid} loading={pending}
            onClick={() => onSubmit({ chat_ids: chatIds, dedup_s: Number(dedupS), events })}
          >
            {t('save')}
          </Button>
        </div>
      )}
    </div>
  );
}

function ChatIdsSection({
  chatIds, newChatId, canManage, errorMessage, onNewChatIdChange, onAdd, onRemove,
}: {
  chatIds: string[];
  newChatId: string;
  canManage: boolean;
  errorMessage?: string;
  onNewChatIdChange: (v: string) => void;
  onAdd: () => void;
  onRemove: (id: string) => void;
}) {
  const { t } = useTranslation('alerts');
  return (
    <section className="rounded-lg border border-line bg-surface p-4 shadow-card">
      <h3 className="mb-1 font-display text-base font-semibold">{t('chatIds.title')}</h3>
      <p className="mb-3 text-sm text-muted">{t('chatIds.hint')}</p>
      {chatIds.length === 0 ? (
        <p className="mb-3 text-sm text-muted">{t('chatIds.empty')}</p>
      ) : (
        <ul className="mb-3 flex flex-wrap gap-2">
          {chatIds.map((id) => <ChatIdBadge key={id} id={id} canManage={canManage} onRemove={onRemove} />)}
        </ul>
      )}
      {canManage && (
        <div className="flex items-end gap-2">
          <Field label="" className="flex-1" error={errorMessage}>
            {(a) => (
              <Input
                {...a} mono placeholder={t('chatIds.placeholder')} value={newChatId}
                onChange={(e) => onNewChatIdChange(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); onAdd(); } }}
              />
            )}
          </Field>
          <Button variant="secondary" icon={<Plus />} onClick={onAdd}>{t('chatIds.add')}</Button>
        </div>
      )}
    </section>
  );
}

function ChatIdBadge({ id, canManage, onRemove }: { id: string; canManage: boolean; onRemove: (id: string) => void }) {
  const { t } = useTranslation('alerts');
  return (
    <li>
      <Badge mono className="h-7 pr-1">
        {id}
        {canManage && (
          <button type="button" aria-label={t('chatIds.removeAriaLabel', { id })} className="ml-1 rounded-sm p-0.5 hover:bg-surface-2" onClick={() => onRemove(id)}>
            <X aria-hidden className="size-3" />
          </button>
        )}
      </Badge>
    </li>
  );
}
