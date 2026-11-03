import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { FlaskConical, Pencil, Plus, ShieldAlert, Trash2 } from 'lucide-react';
import {
  useCreateMissedCallRule, useDeleteMissedCallRule, useExtensions, useMissedCallNotices, useMissedCallRules,
  useQueues, useRingGroups, useTestMissedCallRule, useUpdateMissedCallRule,
} from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { MissedCallNoticeStatus, MissedCallRule, MissedCallScopeKind } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { formatDateTimeShort } from '@/lib/time';
import { ChipListField } from '@/pbx/ChipListField';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input, Select } from '@/ui/Field';
import { Badge, type Tone } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Tabs } from '@/ui/Tabs';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

const SCOPE_KINDS: MissedCallScopeKind[] = ['any', 'did', 'queue', 'ring_group', 'extension'];
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const NOTICE_STATUS_TONE: Record<MissedCallNoticeStatus, Tone> = { pending: 'neutral', sent: 'success', failed: 'danger' };

/** S44 — javobsiz qoʻngʻiroq haqida Telegram/e-mail orqali xabar (M10 C A2). */
export function MissedCallsPage() {
  const { t } = useTranslation('missedcalls');
  const canManage = useCanEdit('apps');
  return (
    <AppShellPage title={t('title')}>
      {!canManage && (
        <p className="mb-3 flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2 text-sm text-muted">
          <ShieldAlert aria-hidden className="size-4 shrink-0" />
          {t('readOnlyNotice')}
        </p>
      )}
      <Tabs
        label={t('title')}
        items={[
          { value: 'rules', label: t('tabs.rules'), content: <RulesTab canManage={canManage} /> },
          { value: 'notices', label: t('tabs.notices'), content: <NoticesTab /> },
        ]}
      />
    </AppShellPage>
  );
}

function RulesTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('missedcalls');
  const { data, isLoading, isError, refetch } = useMissedCallRules();
  const toast = useToast();
  const [editing, setEditing] = useState<MissedCallRule | 'new' | null>(null);
  const [deleting, setDeleting] = useState<MissedCallRule | null>(null);

  const createM = useCreateMissedCallRule();
  const updateM = useUpdateMissedCallRule();
  const deleteM = useDeleteMissedCallRule();
  const testM = useTestMissedCallRule();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;

  const runTest = (r: MissedCallRule) => {
    testM.mutate(r.id, {
      onSuccess: (res) => toast(res.ok ? { kind: 'success', title: t('toast.testOk') } : { kind: 'error', title: t('toast.testFailed', { message: res.message }) }),
      onError: (e) => toast({ kind: 'error', title: t('toast.testFailed', { message: e.message }) }),
    });
  };

  const columns: Column<MissedCallRule>[] = [
    { key: 'name', header: t('column.name'), sortValue: (r) => r.name, cell: (r) => <span className="font-medium">{r.name}</span> },
    {
      key: 'scope', header: t('column.scope'), cell: (r) => (
        <span className="text-sm text-muted">{t(`scope.${r.scope_kind}`)}{r.scope_value ? ` — ${r.scope_value}` : ''}</span>
      ),
    },
    {
      key: 'recipients', header: t('column.recipients'), cell: (r) => (
        <div className="flex flex-wrap gap-1">
          {r.telegram_chat_ids.length > 0 && <Badge tone="neutral" mono>TG {r.telegram_chat_ids.length}</Badge>}
          {r.emails.length > 0 && <Badge tone="neutral" mono>@ {r.emails.length}</Badge>}
          {r.telegram_chat_ids.length === 0 && r.emails.length === 0 && <span className="text-muted">—</span>}
        </div>
      ),
    },
    {
      key: 'enabled', header: t('column.enabled'), cell: (r) => (
        r.enabled ? <span className="text-fg">✓</span> : <span className="text-muted">—</span>
      ),
    },
    {
      key: 'actions', header: '', align: 'right', cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<FlaskConical />} disabled={!canManage} loading={testM.isPending} aria-label={t('testAriaLabel', { name: r.name })} onClick={() => runTest(r)} />
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} disabled={!canManage} aria-label={t('editAriaLabel', { name: r.name })} onClick={() => setEditing(r)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} disabled={!canManage} aria-label={t('deleteAriaLabel', { name: r.name })} onClick={() => setDeleting(r)} />
        </div>
      ),
    },
  ];

  return (
    <div>
      <DataTable
        caption={t('caption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(r) => r.id}
        searchText={(r) => r.name}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (r) => setEditing(r) : undefined}
        empty={{ title: t('empty.title'), body: t('empty.body'), action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('empty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('newRule')}</Button> : undefined}
      />

      {editing && (
        <RuleForm
          item={editing === 'new' ? undefined : editing}
          pending={mutation.isPending}
          errorMessage={isApiError(mutation.error) ? mutation.error.message : undefined}
          onClose={close}
          onSubmit={(payload) => {
            if (editing === 'new') {
              createM.mutate(payload, { onSuccess: () => { close(); toast({ kind: 'success', title: t('toast.added') }); } });
            } else {
              updateM.mutate({ id: editing.id, payload: { ...payload, updated_at: editing.updated_at } }, {
                onSuccess: () => { close(); toast({ kind: 'success', title: t('toast.saved') }); },
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
        <p className="text-sm text-muted">{t('deleteModal.body')}</p>
      </Modal>
    </div>
  );
}

type RulePayload = {
  name: string;
  scope_kind: MissedCallScopeKind;
  scope_value: string | null;
  telegram_chat_ids: string[];
  emails: string[];
  include_internal: boolean;
  enabled: boolean;
};

function RuleForm({
  item, onClose, onSubmit, pending, errorMessage,
}: {
  item?: MissedCallRule;
  onClose: () => void;
  onSubmit: (payload: RulePayload) => void;
  pending: boolean;
  errorMessage?: string;
}) {
  const { t } = useTranslation('missedcalls');
  const { data: queues } = useQueues();
  const { data: ringGroups } = useRingGroups();
  const { data: extensions } = useExtensions({ size: 200 });

  const [name, setName] = useState(item?.name ?? '');
  const [scopeKind, setScopeKind] = useState<MissedCallScopeKind>(item?.scope_kind ?? 'any');
  const [scopeValue, setScopeValue] = useState(item?.scope_value ?? '');
  const [telegramChatIds, setTelegramChatIds] = useState<string[]>(item?.telegram_chat_ids ?? []);
  const [emails, setEmails] = useState<string[]>(item?.emails ?? []);
  const [includeInternal, setIncludeInternal] = useState(item?.include_internal ?? false);
  const [enabled, setEnabled] = useState(item?.enabled ?? true);

  const valid = name.trim().length > 0 && (scopeKind === 'any' || scopeValue.trim().length > 0);

  const scopeOptions: { value: string; label: string }[] =
    scopeKind === 'queue' ? (queues?.items ?? []).map((q) => ({ value: q.id, label: q.name }))
      : scopeKind === 'ring_group' ? (ringGroups?.items ?? []).map((g) => ({ value: g.id, label: g.name }))
      : scopeKind === 'extension' ? (extensions?.items ?? []).map((e) => ({ value: e.id, label: `${e.number} — ${e.name}` }))
      : [];

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
              name: name.trim(), scope_kind: scopeKind, scope_value: scopeKind === 'any' ? null : scopeValue.trim(),
              telegram_chat_ids: telegramChatIds, emails, include_internal: includeInternal, enabled,
            })}
          >
            {item ? t('save') : t('add')}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-5">
        {errorMessage && <p className="text-sm text-danger">{errorMessage}</p>}

        <Field label={t('form.nameLabel')} required>
          {(a) => <Input {...a} autoFocus value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label={t('form.scopeKindLabel')}>
            {(a) => (
              <Select
                {...a} value={scopeKind} onValueChange={(v) => { setScopeKind(v as MissedCallScopeKind); setScopeValue(''); }}
                options={SCOPE_KINDS.map((k) => ({ value: k, label: t(`scope.${k}`) }))}
              />
            )}
          </Field>
          {scopeKind !== 'any' && (
            <Field label={t('form.scopeValueLabel')}>
              {(a) => (
                scopeKind === 'did' ? (
                  <Input {...a} className="num" placeholder={t('form.scopeValuePlaceholderDid')} value={scopeValue} onChange={(e) => setScopeValue(e.target.value)} />
                ) : (
                  <Select {...a} value={scopeValue} onValueChange={setScopeValue} placeholder={t('form.scopeValuePlaceholderSelect')} options={scopeOptions} />
                )
              )}
            </Field>
          )}
        </div>

        <ChipListField
          items={telegramChatIds} onChange={setTelegramChatIds}
          label={t('form.telegramLabel')} hint={t('form.telegramHint')} emptyLabel={t('form.telegramEmpty')}
          placeholder={t('form.telegramPlaceholder')} addLabel={t('form.telegramAdd')}
          removeAriaLabel={(v) => t('form.telegramRemoveAriaLabel', { value: v })}
        />

        <ChipListField
          items={emails} onChange={setEmails} mono={false}
          label={t('form.emailLabel')} hint={t('form.emailHint')} emptyLabel={t('form.emailEmpty')}
          placeholder={t('form.emailPlaceholder')} addLabel={t('form.emailAdd')}
          removeAriaLabel={(v) => t('form.emailRemoveAriaLabel', { value: v })}
          normalize={(v) => (EMAIL_RE.test(v) ? v.toLowerCase() : null)}
        />

        <Toggle checked={includeInternal} onCheckedChange={setIncludeInternal} label={t('form.includeInternalLabel')} />
        <Toggle checked={enabled} onCheckedChange={setEnabled} label={t('form.enabledLabel')} />
      </div>
    </Drawer>
  );
}

function NoticesTab() {
  const { t } = useTranslation('missedcalls');
  const { data, isLoading, isError, refetch } = useMissedCallNotices({ page: 1, page_size: 100 });
  const rows = data?.items ?? [];

  const columns: Column<typeof rows[number]>[] = [
    { key: 'created_at', header: t('notices.column.created'), sortValue: (n) => n.created_at, cell: (n) => <span className="num text-sm text-muted">{formatDateTimeShort(n.created_at)}</span> },
    { key: 'rule_name', header: t('notices.column.rule'), cell: (n) => <span className="truncate text-sm">{n.rule_name}</span> },
    { key: 'call_id', header: t('notices.column.call'), cell: (n) => <span className="num truncate text-xs text-muted">{n.call_id}</span> },
    { key: 'status', header: t('notices.column.status'), cell: (n) => <Badge tone={NOTICE_STATUS_TONE[n.status]}>{t(`notices.status.${n.status}`)}</Badge> },
    { key: 'attempts', header: t('notices.column.attempts'), align: 'right', cell: (n) => <span className="num">{n.attempts}</span> },
    { key: 'last_error', header: t('notices.column.error'), cell: (n) => <span className="truncate text-sm text-muted">{n.last_error ?? '—'}</span> },
  ];

  return (
    <DataTable
      caption={t('notices.caption')}
      rows={rows}
      columns={columns}
      rowId={(n) => n.id}
      searchText={(n) => `${n.rule_name} ${n.call_id}`}
      state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
      onRetry={() => void refetch()}
      empty={{ title: t('notices.empty'), body: '' }}
      pageSize={10}
    />
  );
}
