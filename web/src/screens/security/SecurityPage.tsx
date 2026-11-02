import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, ShieldAlert, Trash2 } from 'lucide-react';
import {
  useCreateBan, useDeleteBan, useSecurityBans, useSecurityEvents, useSecuritySettings, useSecurityStats,
  useTollBlocks, useUnblockToll, useUpdateSecuritySettings,
} from '@/api/queries';
import { isApiError } from '@/api/errors';
import type {
  CreateBanPayload, IpBan, SecurityEvent, SecurityEventKind, SecuritySettings, SecurityStats, SecurityStatsHour,
  SecurityStatsTopIp, TollBlock,
} from '@/api/types';
import { usePermission } from '@/auth/permissions';
import { applyToast } from '@/lib/applyToast';
import { splitList } from '@/lib/validators';
import { formatDateTimeShort } from '@/lib/time';
import { useEnumText } from '@/lib/useEnumText';
import { AppShellPage } from '@/shell/AppShellPage';
import { BarChart, ChartCard, ChartLegend } from '@/ui/Chart';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { Field, Input, Select, Textarea } from '@/ui/Field';
import { Kpi } from '@/ui/Kpi';
import { Badge } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Tabs } from '@/ui/Tabs';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

const EVENT_KINDS: SecurityEventKind[] = ['ip_banned', 'ip_unbanned', 'ban_expired', 'toll_blocked', 'toll_unblocked', 'concurrent_limit'];

/** S33 — Xavfsizlik: SIP hujum himoyasi, toll-fraud bloklari va sozlamalar. Qarang ../../../replica/m2c-contract.md §1-3. */
export function SecurityPage() {
  const { t } = useTranslation('security');
  const canManage = usePermission('system.manage');

  return (
    <AppShellPage title={t('title')}>
      {!canManage && (
        <p className="mb-3 flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2 text-sm text-muted">
          <ShieldAlert aria-hidden className="size-4 shrink-0" />
          {t('readOnlyNotice')}
        </p>
      )}
      <Tabs
        label={t('tabs.label')}
        items={[
          { value: 'status', label: t('tabs.status'), content: <StatusTab canManage={canManage} /> },
          { value: 'bans', label: t('tabs.bans'), content: <BansTab canManage={canManage} /> },
          { value: 'toll', label: t('tabs.toll'), content: <TollTab canManage={canManage} /> },
          { value: 'settings', label: t('tabs.settings'), content: <SettingsTab canManage={canManage} /> },
          { value: 'events', label: t('tabs.events'), content: <EventsTab /> },
        ]}
      />
    </AppShellPage>
  );
}

// ─────────────────────── Holat ───────────────────────

function StatusTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('security');
  const toast = useToast();
  const { data, isLoading } = useSecurityStats({ hours: 24 });
  const banM = useCreateBan();

  const hours = data?.hours ?? [];
  const topIps = data?.top_ips ?? [];
  const totals = data?.totals;

  const block = (ip: string) => banM.mutate({ ip }, {
    onSuccess: () => toast({ kind: 'success', title: t('bans.toast.blocked', { ip }) }),
    onError: (e) => toast({ kind: 'error', title: t('bans.toast.failed'), description: e.message }),
  });

  return (
    <div className="flex flex-col gap-4">
      <StatusKpis t={t} totals={totals} loading={isLoading} />
      <StatusChart t={t} hours={hours} />
      <section className="rounded-lg border border-line bg-surface p-4 shadow-card">
        <h3 className="mb-3 font-display text-base font-semibold">{t('status.topIpsTitle')}</h3>
        {topIps.length === 0 ? (
          <p className="text-sm text-muted">{t('status.empty')}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-line">
            {topIps.map((ip) => <TopIpRow key={ip.ip} ip={ip} canManage={canManage} pending={banM.isPending} onBlock={block} />)}
          </ul>
        )}
      </section>
    </div>
  );
}

type Tfn = ReturnType<typeof useTranslation<'security'>>['t'];

function StatusKpis({ t, totals, loading }: { t: Tfn; totals: SecurityStats['totals'] | undefined; loading: boolean }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Kpi label={t('status.kpi.failures')} value={totals ? String(totals.failures) : null} loading={loading} />
      <Kpi label={t('status.kpi.blocked')} value={totals ? String(totals.blocked) : null} loading={loading} />
      <Kpi label={t('status.kpi.bansActive')} value={totals ? String(totals.bans_active) : null} loading={loading} />
      <Kpi label={t('status.kpi.bansPeriod')} value={totals ? String(totals.bans_period) : null} loading={loading} />
    </div>
  );
}

function chartTickLabel(h: SecurityStatsHour, i: number): string | null {
  return i % 4 === 0 ? formatTickHour(h.hour) : null;
}

function StatusChart({ t, hours }: { t: Tfn; hours: SecurityStatsHour[] }) {
  return (
    <ChartCard
      ariaLabel={t('status.chartTitle')}
      title={t('status.chartTitle')}
      legend={<ChartLegend items={[{ swatchClass: 'fill-chart-1', label: t('status.legendFailures') }, { swatchClass: 'fill-danger', label: t('status.legendBlocked') }]} />}
    >
      <BarChart
        data={hours}
        series={[
          { key: 'failures', swatchClass: 'fill-chart-1', value: (h) => h.failures },
          { key: 'blocked', swatchClass: 'fill-danger', value: (h) => h.blocked },
        ]}
        tickLabel={chartTickLabel}
        emptyText={t('status.empty')}
      />
    </ChartCard>
  );
}

function formatTickHour(iso: string): string {
  return new Date(iso).toLocaleTimeString('uz-UZ', { hour: '2-digit', timeZone: 'Asia/Tashkent' });
}

function TopIpRow({ ip, canManage, pending, onBlock }: { ip: SecurityStatsTopIp; canManage: boolean; pending: boolean; onBlock: (ip: string) => void }) {
  const { t } = useTranslation('security');
  return (
    <li className="flex items-center justify-between gap-3 py-2">
      <div className="flex items-center gap-3">
        <span className="num text-sm text-fg">{ip.ip}</span>
        <span className="text-xs text-muted">{t('status.column.failures')}: {ip.failures}</span>
        <span className="text-xs text-muted">{formatDateTimeShort(ip.last_at)}</span>
      </div>
      {ip.banned ? (
        <Badge tone="danger">{t('status.bannedBadge')}</Badge>
      ) : canManage ? (
        <Button size="sm" variant="secondary" loading={pending} aria-label={t('status.blockAriaLabel', { ip: ip.ip })} onClick={() => onBlock(ip.ip)}>
          {t('status.blockAction')}
        </Button>
      ) : null}
    </li>
  );
}

// ─────────────────────── Bloklangan IP ───────────────────────

function BansTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('security');
  const toast = useToast();
  const { data, isLoading, isError, refetch } = useSecurityBans();
  const createM = useCreateBan();
  const deleteM = useDeleteBan();
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<IpBan | null>(null);

  const closeAdd = () => { setAdding(false); createM.reset(); };
  const columns = useBanColumns(t, canManage, setRemoving);

  return (
    <div>
      <DataTable
        caption={t('bans.caption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(b) => b.id}
        searchText={(b) => `${b.ip} ${b.note ?? ''}`}
        searchPlaceholder={t('bans.searchPlaceholder')}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        empty={{ title: t('bans.empty.title'), body: t('bans.empty.body') }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setAdding(true)}>{t('bans.add')}</Button> : undefined}
      />

      <AddBanModal
        open={adding}
        pending={createM.isPending}
        errorField={isApiError(createM.error) ? createM.error.field : undefined}
        errorMessage={isApiError(createM.error) ? createM.error.message : undefined}
        onClose={closeAdd}
        onSubmit={(payload) => createM.mutate(payload, {
          onSuccess: (res) => { closeAdd(); toast(applyToast(res.apply, t('bans.toast.blocked', { ip: res.item.ip }))); },
        })}
      />

      <RemoveBanModal removing={removing} pending={deleteM.isPending} onClose={() => setRemoving(null)} onConfirm={(ban) => deleteM.mutate(ban.id, {
        onSuccess: (res) => { toast(applyToast(res.apply, t('bans.toast.unblocked', { ip: ban.ip }))); setRemoving(null); },
        onError: (e) => { toast({ kind: 'error', title: t('bans.toast.failed'), description: e.message }); setRemoving(null); },
      })} />
    </div>
  );
}

function useBanColumns(t: Tfn, canManage: boolean, onRemove: (b: IpBan) => void) {
  const columns: Column<IpBan>[] = [
    { key: 'ip', header: t('bans.column.ip'), sortValue: (b) => b.ip, cell: (b) => <span className="num text-fg">{b.ip}</span> },
    { key: 'reason', header: t('bans.column.reason'), cell: (b) => <Badge tone={b.reason === 'manual' ? 'info' : 'neutral'}>{t(`bans.reason.${b.reason}`)}</Badge> },
    { key: 'failures', header: t('bans.column.failures'), cell: (b) => <span className="num text-sm">{b.failures}</span> },
    { key: 'createdAt', header: t('bans.column.createdAt'), sortValue: (b) => b.created_at, cell: (b) => <span className="text-sm text-muted">{formatDateTimeShort(b.created_at)}</span> },
    { key: 'expiresAt', header: t('bans.column.expiresAt'), cell: (b) => <span className="text-sm text-muted">{b.expires_at ? formatDateTimeShort(b.expires_at) : t('bans.neverExpires')}</span> },
    { key: 'note', header: t('bans.column.note'), cell: (b) => <span className="truncate text-sm text-muted">{b.note ?? '—'}</span> },
    {
      key: 'actions', header: '', align: 'right', cell: (b) => (
        <div className="flex justify-end">
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('bans.unblockAriaLabel', { ip: b.ip })} disabled={!canManage} onClick={() => onRemove(b)} />
        </div>
      ),
    },
  ];
  return columns;
}

function RemoveBanModal({ removing, pending, onClose, onConfirm }: { removing: IpBan | null; pending: boolean; onClose: () => void; onConfirm: (ban: IpBan) => void }) {
  const { t } = useTranslation('security');
  return (
    <Modal
      open={!!removing}
      onOpenChange={(v) => !v && onClose()}
      title={removing ? t('bans.unblockAriaLabel', { ip: removing.ip }) : ''}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="danger" loading={pending} onClick={() => removing && onConfirm(removing)}>{t('bans.unblock')}</Button>
        </>
      }
    >
      <p className="text-sm text-muted">{removing?.ip}</p>
    </Modal>
  );
}

function AddBanModal({
  open, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: CreateBanPayload) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('security');
  const [ip, setIp] = useState('');
  const [note, setNote] = useState('');
  const [durationS, setDurationS] = useState('3600');

  const valid = ip.trim().length > 0 && /^\d+$/.test(durationS.trim());
  const submit = () => {
    if (!valid) return;
    onSubmit({ ip: ip.trim(), note: note.trim() || null, ban_s: Number(durationS) });
  };
  const closeAndReset = () => { setIp(''); setNote(''); setDurationS('3600'); onClose(); };

  return (
    <Modal
      open={open}
      onOpenChange={(v) => !v && closeAndReset()}
      title={t('bans.addForm.title')}
      footer={
        <>
          <Button variant="ghost" onClick={closeAndReset}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={submit}>{t('bans.addForm.submit')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label={t('bans.addForm.ipLabel')} required error={errorField === 'ip' ? errorMessage : undefined}>
          {(a) => <Input {...a} mono autoFocus placeholder={t('bans.addForm.ipPlaceholder')} value={ip} onChange={(e) => setIp(e.target.value)} />}
        </Field>
        <Field label={t('bans.addForm.noteLabel')} aside={t('bans.addForm.noteAside')}>
          {(a) => <Input {...a} placeholder={t('bans.addForm.notePlaceholder')} value={note} onChange={(e) => setNote(e.target.value)} />}
        </Field>
        <Field label={t('bans.addForm.durationLabel')} hint={t('bans.addForm.durationHint')}>
          {(a) => <Input {...a} mono inputMode="numeric" value={durationS} onChange={(e) => setDurationS(e.target.value)} />}
        </Field>
        {errorMessage && errorField !== 'ip' ? <p className="text-sm text-danger">{errorMessage}</p> : null}
      </div>
    </Modal>
  );
}

// ─────────────────────── Toll-fraud ───────────────────────

function TollTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('security');
  const toast = useToast();
  const { data, isLoading, isError, refetch } = useTollBlocks();
  const unblockM = useUnblockToll();

  const columns: Column<TollBlock>[] = [
    { key: 'number', header: t('toll.column.number'), sortValue: (b) => b.number, cell: (b) => <span className="num text-fg">{b.number}</span> },
    { key: 'name', header: t('toll.column.name'), cell: (b) => <span className="text-sm">{b.name}</span> },
    { key: 'blockedAt', header: t('toll.column.blockedAt'), sortValue: (b) => b.blocked_at, cell: (b) => <span className="text-sm text-muted">{formatDateTimeShort(b.blocked_at)}</span> },
    { key: 'reason', header: t('toll.column.reason'), cell: (b) => <Badge tone="warning">{t(`toll.reason.${b.reason}`)}</Badge> },
    {
      key: 'actions', header: '', align: 'right', cell: (b) => (
        <div className="flex justify-end">
          <Button
            size="sm" variant="secondary" disabled={!canManage} loading={unblockM.isPending}
            aria-label={t('toll.unblockAriaLabel', { number: b.number })}
            onClick={() => unblockM.mutate(b.extension_id, {
              onSuccess: () => toast({ kind: 'success', title: t('toll.toast.unblocked', { number: b.number }) }),
              onError: (e) => toast({ kind: 'error', title: t('bans.toast.failed'), description: e.message }),
            })}
          >
            {t('toll.unblock')}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <DataTable
      caption={t('toll.caption')}
      rows={data?.items ?? []}
      columns={columns}
      rowId={(b) => b.extension_id}
      searchText={(b) => `${b.number} ${b.name}`}
      state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
      onRetry={() => void refetch()}
      empty={{ title: t('toll.empty.title'), body: t('toll.empty.body') }}
    />
  );
}

// ─────────────────────── Sozlamalar ───────────────────────

function SettingsTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('security');
  const { data, isLoading, isError, refetch } = useSecuritySettings();
  const toast = useToast();
  const updateM = useUpdateSecuritySettings();

  if (isLoading || !data) {
    return (
      <p className="rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">{isError ? t('loadFailed') : t('loading')}</p>
    );
  }

  return (
    <SettingsForm
      key={data.updated_at}
      settings={data}
      canManage={canManage}
      pending={updateM.isPending}
      errorField={isApiError(updateM.error) ? updateM.error.field : undefined}
      errorMessage={isApiError(updateM.error) ? updateM.error.message : undefined}
      stale={isApiError(updateM.error) && updateM.error.code === 'stale'}
      onRetry={() => void refetch()}
      onSubmit={(payload) => updateM.mutate({ ...payload, updated_at: data.updated_at }, {
        onSuccess: (res) => toast(applyToast(res.apply, t('settings.save'))),
      })}
    />
  );
}

function SettingsForm({
  settings, canManage, onSubmit, pending, errorField, errorMessage, stale, onRetry,
}: {
  settings: SecuritySettings;
  canManage: boolean;
  onSubmit: (payload: { sip_guard: SecuritySettings['sip_guard']; toll_fraud: SecuritySettings['toll_fraud'] }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
  stale: boolean;
  onRetry: () => void;
}) {
  const { t } = useTranslation('security');
  const [sipEnabled, setSipEnabled] = useState(settings.sip_guard.enabled);
  const [maxFailures, setMaxFailures] = useState(String(settings.sip_guard.max_failures));
  const [windowS, setWindowS] = useState(String(settings.sip_guard.window_s));
  const [banS, setBanS] = useState(String(settings.sip_guard.ban_s));
  const [trustedNets, setTrustedNets] = useState(settings.sip_guard.trusted_nets.join('\n'));
  const [trustLan, setTrustLan] = useState(settings.sip_guard.trust_lan);
  const [tollEnabled, setTollEnabled] = useState(settings.toll_fraud.enabled);
  const [maxConcurrent, setMaxConcurrent] = useState(String(settings.toll_fraud.max_concurrent_outbound));
  const [extMaxPerHour, setExtMaxPerHour] = useState(String(settings.toll_fraud.ext_max_per_hour));
  const [extIntlPerDay, setExtIntlPerDay] = useState(String(settings.toll_fraud.ext_international_per_day));

  const valid = [maxFailures, windowS, banS, maxConcurrent, extMaxPerHour, extIntlPerDay].every((v) => /^\d+$/.test(v.trim()));

  const submit = () => {
    if (!valid) return;
    onSubmit({
      sip_guard: {
        enabled: sipEnabled, max_failures: Number(maxFailures), window_s: Number(windowS), ban_s: Number(banS),
        trusted_nets: splitList(trustedNets), trust_lan: trustLan,
      },
      toll_fraud: {
        enabled: tollEnabled, max_concurrent_outbound: Number(maxConcurrent), ext_max_per_hour: Number(extMaxPerHour),
        ext_international_per_day: Number(extIntlPerDay),
      },
    });
  };

  return (
    <div className="flex max-w-2xl flex-col gap-5">
      {stale && (
        <div className="flex items-center gap-2 rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-sm text-on-warning-soft">
          <ShieldAlert aria-hidden className="size-4 shrink-0" />
          <span className="flex-1">{t('settings.staleNotice')}</span>
          <Button size="sm" variant="secondary" onClick={onRetry}>{t('retry')}</Button>
        </div>
      )}

      <section className="rounded-lg border border-line bg-surface p-4 shadow-card">
        <h3 className="mb-3 font-display text-base font-semibold">{t('settings.sipGuard.title')}</h3>
        <div className="flex flex-col gap-4">
          <Toggle checked={sipEnabled} disabled={!canManage} onCheckedChange={setSipEnabled} label={t('settings.sipGuard.enabled')} />
          <div className="grid grid-cols-3 gap-3">
            <Field label={t('settings.sipGuard.maxFailures')}>
              {(a) => <Input {...a} mono inputMode="numeric" disabled={!canManage} value={maxFailures} onChange={(e) => setMaxFailures(e.target.value)} />}
            </Field>
            <Field label={t('settings.sipGuard.windowS')}>
              {(a) => <Input {...a} mono inputMode="numeric" disabled={!canManage} value={windowS} onChange={(e) => setWindowS(e.target.value)} />}
            </Field>
            <Field label={t('settings.sipGuard.banS')} hint={t('settings.sipGuard.banSHint')}>
              {(a) => <Input {...a} mono inputMode="numeric" disabled={!canManage} value={banS} onChange={(e) => setBanS(e.target.value)} />}
            </Field>
          </div>
          <Field
            label={t('settings.sipGuard.trustedNets')} hint={t('settings.sipGuard.trustedNetsHint')}
            error={errorField === 'trusted_nets' ? errorMessage : undefined}
          >
            {(a) => <Textarea {...a} className="num" disabled={!canManage} rows={3} value={trustedNets} onChange={(e) => setTrustedNets(e.target.value)} />}
          </Field>
          <Toggle
            checked={trustLan} disabled={!canManage} onCheckedChange={setTrustLan}
            label={t('settings.sipGuard.trustLan')} description={t('settings.sipGuard.trustLanHint')}
          />
        </div>
      </section>

      <section className="rounded-lg border border-line bg-surface p-4 shadow-card">
        <h3 className="mb-3 font-display text-base font-semibold">{t('settings.tollFraud.title')}</h3>
        <div className="flex flex-col gap-4">
          <Toggle checked={tollEnabled} disabled={!canManage} onCheckedChange={setTollEnabled} label={t('settings.tollFraud.enabled')} />
          <div className="grid grid-cols-3 gap-3">
            <Field label={t('settings.tollFraud.maxConcurrentOutbound')} hint={t('settings.tollFraud.maxConcurrentOutboundHint')}>
              {(a) => <Input {...a} mono inputMode="numeric" disabled={!canManage} value={maxConcurrent} onChange={(e) => setMaxConcurrent(e.target.value)} />}
            </Field>
            <Field label={t('settings.tollFraud.extMaxPerHour')}>
              {(a) => <Input {...a} mono inputMode="numeric" disabled={!canManage} value={extMaxPerHour} onChange={(e) => setExtMaxPerHour(e.target.value)} />}
            </Field>
            <Field label={t('settings.tollFraud.extInternationalPerDay')}>
              {(a) => <Input {...a} mono inputMode="numeric" disabled={!canManage} value={extIntlPerDay} onChange={(e) => setExtIntlPerDay(e.target.value)} />}
            </Field>
          </div>
        </div>
      </section>

      {errorMessage && errorField !== 'trusted_nets' && !stale ? <p className="text-sm text-danger">{errorMessage}</p> : null}

      {canManage && (
        <div>
          <Button variant="primary" disabled={!valid} loading={pending} onClick={submit}>{t('settings.save')}</Button>
        </div>
      )}
    </div>
  );
}

// ─────────────────────── Hodisalar ───────────────────────

function EventsTab() {
  const { t } = useTranslation('security');
  const [kind, setKind] = useState<'all' | SecurityEventKind>('all');
  const kindLabel = useEnumText('security', 'events.kind', EVENT_KINDS);
  const { data, isLoading, isError, refetch } = useSecurityEvents({ limit: 100, kind: kind === 'all' ? undefined : kind });
  const columns = useEventColumns(t, kindLabel);
  const kindOptions = [{ value: 'all', label: t('events.filterAll') }, ...EVENT_KINDS.map((k) => ({ value: k, label: kindLabel[k] }))];

  return (
    <div className="flex flex-col gap-3">
      <div className="max-w-xs">
        <Field label={t('events.filterLabel')}>
          {({ id }) => <Select id={id} value={kind} onValueChange={(v) => setKind(v as typeof kind)} options={kindOptions} />}
        </Field>
      </div>
      <DataTable
        caption={t('events.caption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(e) => e.id}
        searchText={(e) => `${e.ip ?? ''} ${e.extension ?? ''}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        empty={{ title: t('events.empty.title'), body: t('events.empty.body') }}
      />
    </div>
  );
}

function useEventColumns(t: Tfn, kindLabel: Record<SecurityEventKind, string>) {
  const columns: Column<SecurityEvent>[] = [
    { key: 'at', header: t('events.column.at'), sortValue: (e) => e.at, cell: (e) => <span className="num text-sm">{formatDateTimeShort(e.at)}</span> },
    { key: 'kind', header: t('events.column.kind'), cell: (e) => <Badge>{kindLabel[e.kind]}</Badge> },
    { key: 'target', header: t('events.column.target'), cell: (e) => <span className="num text-sm text-muted">{e.ip ?? e.extension ?? '—'}</span> },
  ];
  return columns;
}
