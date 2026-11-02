import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pencil, Plug, Plus, ShieldAlert, Trash2 } from 'lucide-react';
import { useCreateTrunk, useDeleteTrunk, useTestTrunk, useTrunks, useUpdateTrunk } from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { Trunk, TrunkAuthMode, TrunkTestResult } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { applyToast } from '@/lib/applyToast';
import { isValidCidr, isValidHost, splitList } from '@/lib/validators';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { Field, Input, Select, Textarea } from '@/ui/Field';
import { Badge, StatusPill, type Status } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

const CODECS = ['ulaw', 'alaw', 'g722', 'opus'] as const;
const HEALTH_STATUS: Record<Trunk['health']['state'], Status> = { ok: 'online', unreachable: 'error', unknown: 'offline', disabled: 'disabled' };
const REGISTRATION_TONE: Record<Exclude<Trunk['health']['registration'], null>, Status> = { registered: 'online', rejected: 'error', unregistered: 'offline' };

type FormState = {
  name: string; host: string; port: string; match: string; codecs: Set<string>; maxChannels: string; enabled: boolean;
  authMode: TrunkAuthMode; username: string; password: string; fromDomain: string; outboundCallerid: string;
};

function toForm(t?: Trunk): FormState {
  return {
    name: t?.name ?? '',
    host: t?.host ?? '',
    port: String(t?.port ?? 5060),
    match: (t?.match ?? []).join('\n'),
    codecs: new Set(t?.codecs ?? ['ulaw', 'alaw']),
    maxChannels: t?.max_channels ? String(t.max_channels) : '',
    enabled: t?.enabled ?? true,
    authMode: t?.auth_mode ?? 'ip',
    username: t?.username ?? '',
    password: '',
    fromDomain: t?.from_domain ?? '',
    outboundCallerid: t?.outbound_callerid ?? '',
  };
}

/** S06 — SIP trunklar: IP-trunk shakli (host/port/CIDR/kodeklar), sogʻlik koʻrsatkichi, «Sinash». */
export function TrunksPage() {
  const { t } = useTranslation('trunks');
  const healthText: Record<Trunk['health']['state'], string> = { ok: t('health.ok'), unreachable: t('health.unreachable'), unknown: t('health.unknown'), disabled: t('health.disabled') };
  const registrationText: Record<Exclude<Trunk['health']['registration'], null>, string> = {
    registered: t('registration.registered'), rejected: t('registration.rejected'), unregistered: t('registration.unregistered'),
  };
  const { data, isLoading, isError, refetch } = useTrunks();
  const canManage = useCanEdit('connect');
  const toast = useToast();
  const [editing, setEditing] = useState<Trunk | 'new' | null>(null);
  const [deleting, setDeleting] = useState<Trunk | null>(null);
  const [testResult, setTestResult] = useState<{ trunk: Trunk; result: TrunkTestResult } | null>(null);

  const createM = useCreateTrunk();
  const updateM = useUpdateTrunk();
  const deleteM = useDeleteTrunk();
  const testM = useTestTrunk();

  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;

  const columns: Column<Trunk>[] = [
    { key: 'name', header: t('column.name'), sortValue: (r) => r.name, cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'host', header: t('column.hostPort'), cell: (r) => <span className="num text-muted">{r.host}:{r.port}</span> },
    {
      key: 'health', header: t('column.health'), cell: (r) => (
        <div className="flex flex-col gap-1">
          <StatusPill status={HEALTH_STATUS[r.health.state]}>
            {healthText[r.health.state]}{r.health.rtt_ms !== null ? ` · ${r.health.rtt_ms} ms` : ''}
          </StatusPill>
          {r.health.registration && (
            <StatusPill status={REGISTRATION_TONE[r.health.registration]}>{registrationText[r.health.registration]}</StatusPill>
          )}
          {r.health.reason && <span className="max-w-[220px] truncate text-xs text-muted" title={r.health.reason}>{r.health.reason}</span>}
        </div>
      ),
    },
    { key: 'codecs', header: t('column.codecs'), cell: (r) => <span className="flex flex-wrap gap-1">{r.codecs.map((c) => <Badge key={c} mono>{c}</Badge>)}</span> },
    { key: 'enabled', header: t('column.enabled'), cell: (r) => <Badge tone={r.enabled ? 'success' : 'neutral'}>{r.enabled ? t('yes') : t('no')}</Badge> },
    {
      key: 'actions', header: '', align: 'right', cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button
            size="sm" variant="ghost" iconOnly icon={<Plug />} aria-label={t('testAriaLabel', { name: r.name })} loading={testM.isPending}
            onClick={() => testM.mutate(r.id, { onSuccess: (result) => setTestResult({ trunk: r, result }) })}
          />
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
        searchText={(r) => `${r.name} ${r.host}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (r) => setEditing(r) : undefined}
        empty={{ title: t('empty.title'), body: t('empty.body'), action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('empty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('newTrunk')}</Button> : undefined}
      />

      {editing && (
        <TrunkForm
          trunk={editing === 'new' ? undefined : editing}
          onClose={close}
          pending={mutation.isPending}
          errorField={isApiError(mutation.error) ? mutation.error.field : undefined}
          errorMessage={isApiError(mutation.error) ? mutation.error.message : undefined}
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
        <p className="text-sm text-muted">{t('deleteModal.body', { name: deleting?.name, host: deleting?.host, port: deleting?.port })}</p>
      </Modal>

      <Modal
        open={!!testResult}
        onOpenChange={(v) => !v && setTestResult(null)}
        title={testResult ? t('testResultTitle', { name: testResult.trunk.name }) : ''}
        footer={<Button variant="primary" onClick={() => setTestResult(null)}>{t('close')}</Button>}
      >
        {testResult && (
          <div className="flex items-center gap-3">
            <StatusPill status={testResult.result.ok ? 'online' : 'error'}>{testResult.result.ok ? t('testOk') : t('testFail')}</StatusPill>
            <p className="text-sm text-muted">
              {testResult.result.detail}
              {testResult.result.rtt_ms !== null && <span className="num"> · {testResult.result.rtt_ms} ms</span>}
            </p>
          </div>
        )}
      </Modal>
    </AppShellPage>
  );
}

function TrunkForm({
  trunk, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  trunk?: Trunk;
  onClose: () => void;
  onSubmit: (payload: {
    name: string; host: string; port: number; match: string[]; codecs: string[]; max_channels: number | null; enabled: boolean;
    auth_mode: TrunkAuthMode; username: string | null; password?: string; from_domain: string | null; outbound_callerid: string | null;
  }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('trunks');
  const authModeLabel: Record<TrunkAuthMode, string> = { ip: t('authMode.ip'), register: t('authMode.register') };
  const [form, setForm] = useState<FormState>(() => toForm(trunk));
  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setForm((f) => ({ ...f, [k]: v }));

  const hostError = form.host.trim() !== '' && !isValidHost(form.host.trim()) ? t('error.badHost') : undefined;
  const portNum = Number(form.port);
  const portError = form.port.trim() !== '' && (!Number.isInteger(portNum) || portNum < 1 || portNum > 65535) ? t('error.badPort') : undefined;
  const matchList = splitList(form.match);
  const badMatch = matchList.find((m) => !isValidCidr(m));
  const matchError = form.match.trim() !== '' && badMatch ? t('error.badMatch', { bad: badMatch }) : undefined;
  const codecsError = form.codecs.size === 0 ? t('error.codecsRequired') : undefined;
  const isRegister = form.authMode === 'register';
  const passwordError = isRegister && !trunk?.has_password && !form.password.trim() ? t('error.passwordRequired') : undefined;

  const valid = form.name.trim().length > 0 && form.host.trim().length > 0 && !hostError && !portError && !matchError && !codecsError && !passwordError;

  const toggleCodec = (c: string) => set('codecs', (() => { const n = new Set(form.codecs); if (n.has(c)) n.delete(c); else n.add(c); return n; })());

  const submit = () => onSubmit({
    name: form.name.trim(), host: form.host.trim(), port: portNum, match: matchList, codecs: [...form.codecs],
    max_channels: form.maxChannels.trim() ? Number(form.maxChannels) : null, enabled: form.enabled,
    auth_mode: form.authMode, username: form.username.trim() || null, from_domain: form.fromDomain.trim() || null,
    outbound_callerid: form.outboundCallerid.trim() || null,
    ...(form.password.trim() ? { password: form.password.trim() } : {}),
  });

  return (
    <Modal
      open
      onOpenChange={(v) => !v && onClose()}
      title={trunk ? t('form.editTitle', { name: trunk.name }) : t('form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={submit}>{trunk ? t('form.save') : t('form.add')}</Button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t('form.name')} required className="sm:col-span-2">
          {(a) => <Input {...a} autoFocus value={form.name} onChange={(e) => set('name', e.target.value)} />}
        </Field>
        <Field label={t('form.host')} required error={hostError ?? (errorField === 'host' ? errorMessage : undefined)} hint={t('form.hostHint')}>
          {(a) => <Input {...a} mono placeholder={t('form.hostPlaceholder')} value={form.host} onChange={(e) => set('host', e.target.value)} />}
        </Field>
        <Field label={t('form.port')} required error={portError}>
          {(a) => <Input {...a} mono inputMode="numeric" value={form.port} onChange={(e) => set('port', e.target.value)} />}
        </Field>

        <Field label={t('form.authModeLabel')} required className="sm:col-span-2">
          {({ id }) => <Select id={id} value={form.authMode} onValueChange={(v) => set('authMode', v as TrunkAuthMode)} options={Object.entries(authModeLabel).map(([value, label]) => ({ value, label }))} />}
        </Field>

        {form.authMode === 'ip' ? (
          <Field label={t('form.matchLabel')} className="sm:col-span-2" error={matchError} hint={t('form.matchHint')}>
            {(a) => <Textarea {...a} className="num min-h-16" placeholder="203.0.113.0/24" value={form.match} onChange={(e) => set('match', e.target.value)} />}
          </Field>
        ) : (
          <>
            <Field label={t('form.login')} required>
              {(a) => <Input {...a} mono value={form.username} onChange={(e) => set('username', e.target.value)} />}
            </Field>
            <Field
              label={t('form.password')} required={!trunk?.has_password} error={passwordError ?? (errorField === 'password' ? errorMessage : undefined)}
              hint={trunk?.has_password ? t('form.passwordHintChange') : undefined}
            >
              {(a) => <Input {...a} type="password" mono placeholder={trunk?.has_password ? '••••••••' : undefined} value={form.password} onChange={(e) => set('password', e.target.value)} />}
            </Field>
            <Field label={t('form.fromDomain')} className="sm:col-span-2" hint={t('form.fromDomainHint')}>
              {(a) => <Input {...a} mono placeholder={t('form.fromDomainPlaceholder')} value={form.fromDomain} onChange={(e) => set('fromDomain', e.target.value)} />}
            </Field>
          </>
        )}

        <Field label={t('form.outboundCallerid')} aside={t('form.optional')} className="sm:col-span-2" hint={t('form.outboundCalleridHint')}>
          {(a) => <Input {...a} mono placeholder="+998712000000" value={form.outboundCallerid} onChange={(e) => set('outboundCallerid', e.target.value)} />}
        </Field>

        <Field label={t('form.codecs')} className="sm:col-span-2" error={codecsError}>
          {() => (
            <div className="flex flex-wrap gap-3">
              {CODECS.map((c) => (
                <label key={c} className="flex items-center gap-1.5 text-sm">
                  <input type="checkbox" className="size-4 accent-brand" checked={form.codecs.has(c)} onChange={() => toggleCodec(c)} />
                  <span className="num">{c}</span>
                </label>
              ))}
            </div>
          )}
        </Field>
        <Field label={t('form.maxChannels')} aside={t('form.optional')} hint={t('form.maxChannelsHint')}>
          {(a) => <Input {...a} mono inputMode="numeric" placeholder={t('form.unlimited')} value={form.maxChannels} onChange={(e) => set('maxChannels', e.target.value)} />}
        </Field>
        <div className="flex items-end pb-2">
          <Toggle checked={form.enabled} onCheckedChange={(v) => set('enabled', v)} label={t('form.enabled')} />
        </div>
      </div>
      {errorMessage && errorField !== 'host' && errorField !== 'password' ? <p className="mt-3 text-sm text-danger">{errorMessage}</p> : null}
    </Modal>
  );
}
