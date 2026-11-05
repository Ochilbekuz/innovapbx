import { type ReactNode, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CircleCheck, CircleX, Copy, Link2, Plug, RefreshCw, ShieldAlert, Unlink2 } from 'lucide-react';
import {
  useAmoCrmConfig, useBitrix24Config, useBitrix24License, useConnectBitrix24, useCrmUsers, useDisconnectBitrix24,
  useIntegrationsSettings, usePollBitrix24Connect, useSetupBitrix24, useSyncCrm, useTestCrm,
  useUpdateAmoCrmConfig, useUpdateBitrix24Config, useUpdateCrmUserMap,
} from '@/api/queries';
import type {
  AmoConfigResult, Bitrix24License, Bitrix24LicenseState, Bitrix24Setup, BitrixConfigResult, CrmProvider,
  CrmStatusState, CrmUser, CrmUserMapEntry, UpdateBitrixPayload,
} from '@/api/types';
import { apiErrorMessage } from '@/api/errors';
import { bitrix24LicenseStateArgs, cloudCannotReachPrivateHost, normalizeBitrixDomain } from '@/domain/crm';
import { copyText } from '@/lib/browser';
import { formatDateShort, formatDateTime } from '@/lib/time';
import { Button } from '@/ui/Button';
import { ConfirmDeleteModal } from '@/ui/ConfirmDeleteModal';
import { Field, Input, Select } from '@/ui/Field';
import { Badge, type Tone } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';
import { OtherFormError, SaveButtonRow, useMutationError } from './shared';

/** «Ulash» bosilgandan keyin har 2 soniyada so'raladi, 5 daqiqadan keyin to'xtaydi (shartnoma §2). */
const BITRIX_POLL_INTERVAL_MS = 2000;
const BITRIX_POLL_MAX_ATTEMPTS = 150;

/** Forma ichida bir xil ko'rinishdagi sozlama guruhi (ClockPanel/CampaignForm uslubi). */
function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3.5 border-t border-line pt-4 first:border-t-0 first:pt-0">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">{title}</h3>
      {children}
    </section>
  );
}

function UnmappedBanner({ list }: { list: string[] }) {
  const { t } = useTranslation('integrations');
  if (list.length === 0) return null;
  return <p className="rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-sm text-on-warning-soft">{t('crm.unmapped', { list: list.join(', ') })}</p>;
}

/** amoCRM (va hali sinxronlanmagan Bitrix24) uchun — erkin matn kiritib, qo'lda saqlash. */
function LegacyUserMapTable({ provider, entries, canManage }: { provider: CrmProvider; entries: CrmUserMapEntry[]; canManage: boolean }) {
  const { t } = useTranslation('integrations');
  const toast = useToast();
  const updateM = useUpdateCrmUserMap(provider);
  const [edits, setEdits] = useState<Record<string, string>>({});

  const valueFor = (e: CrmUserMapEntry) => edits[e.extension] ?? e.crm_user_id ?? '';
  const save = (e: CrmUserMapEntry) => {
    const crm_user_id = valueFor(e).trim() || null;
    updateM.mutate({ entries: [{ extension: e.extension, crm_user_id }] }, {
      onSuccess: () => toast({ kind: 'success', title: t('crm.saved') }),
    });
  };

  const columns: Column<CrmUserMapEntry>[] = [
    { key: 'extension', header: t('crm.userMapColumns.extension'), cell: (e) => <span className="num font-medium">{e.extension}</span> },
    { key: 'source', header: t('crm.userMapColumns.source'), cell: (e) => <Badge tone={e.source === 'manual' ? 'accent' : 'neutral'}>{t(`crm.source.${e.source}`)}</Badge> },
    {
      key: 'crm_user', header: t('crm.userMapColumns.crmUser'), cell: (e) => canManage ? (
        <div className="flex items-center gap-1.5">
          <Input size="sm" value={valueFor(e)} onChange={(ev) => setEdits((prev) => ({ ...prev, [e.extension]: ev.target.value }))} />
          <Button size="sm" variant="secondary" loading={updateM.isPending} onClick={() => save(e)}>{t('crm.saveMap')}</Button>
        </div>
      ) : <span className="text-sm">{e.crm_user_name ?? e.crm_user_id ?? '—'}</span>,
    },
  ];

  return (
    <DataTable
      caption={t('crm.userMap')}
      rows={entries}
      columns={columns}
      rowId={(e) => e.extension}
      searchText={(e) => e.extension}
      pageSize={10}
      empty={{ title: t('crm.userMapDesc'), body: '' }}
    />
  );
}

/** Bitrix24, "Внутренний номер" bo'yicha sinxrondan keyin — har bir ichki raqamga Select orqali foydalanuvchi tanlanadi. */
function BitrixUserMapTable({ entries, users, canManage }: { entries: CrmUserMapEntry[]; users: CrmUser[]; canManage: boolean }) {
  const { t } = useTranslation('integrations');
  const toast = useToast();
  const updateM = useUpdateCrmUserMap('bitrix24');

  const options = [
    { value: '', label: t('crm.bitrix24.autoMapOption') },
    ...users.map((u) => ({ value: u.id, label: `${u.name} (${u.id})` })),
  ];

  const sourceTone: Record<'auto' | 'manual' | 'unlinked', Tone> = { auto: 'success', manual: 'accent', unlinked: 'warning' };
  const sourceKind = (e: CrmUserMapEntry): 'auto' | 'manual' | 'unlinked' => (e.crm_user_id ? e.source : 'unlinked');
  const sourceLabel = (e: CrmUserMapEntry) => {
    const kind = sourceKind(e);
    return kind === 'manual' ? t('crm.source.manual') : t(`crm.bitrix24.source.${kind}`);
  };

  const columns: Column<CrmUserMapEntry>[] = [
    { key: 'extension', header: t('crm.userMapColumns.extension'), cell: (e) => <span className="num font-medium">{e.extension}</span> },
    {
      key: 'crm_user', header: t('crm.bitrix24.userMapUserColumn'), cell: (e) => canManage ? (
        <Select
          size="sm"
          value={e.crm_user_id ?? ''}
          options={options}
          disabled={updateM.isPending}
          onValueChange={(v) => updateM.mutate({ entries: [{ extension: e.extension, crm_user_id: v || null }] }, {
            onSuccess: () => toast({ kind: 'success', title: t('crm.saved') }),
          })}
        />
      ) : <span className="text-sm">{e.crm_user_name ?? '—'}</span>,
    },
    { key: 'source', header: t('crm.userMapColumns.source'), cell: (e) => <Badge tone={sourceTone[sourceKind(e)]}>{sourceLabel(e)}</Badge> },
  ];

  return (
    <DataTable
      caption={t('crm.userMap')}
      rows={entries}
      columns={columns}
      rowId={(e) => e.extension}
      searchText={(e) => e.extension}
      pageSize={10}
      empty={{ title: t('crm.bitrix24.usersEmptyHint'), body: '' }}
    />
  );
}

/** Bitrix24'da ichki raqami Bitrix'da bor-u, PBX'da yo'q (unknown_inner) va bir raqam ikki foydalanuvchida (conflicts) holatlari. */
function SyncReportBanner({ report }: { report: BitrixConfigResult['config']['sync'] }) {
  const { t } = useTranslation('integrations');
  if (!report || (report.unknown_inner.length === 0 && report.conflicts.length === 0)) return null;
  return (
    <div className="flex flex-col gap-2 rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-sm text-on-warning-soft">
      {report.unknown_inner.length > 0 && (
        <div>
          <p className="font-medium">{t('crm.bitrix24.report.unknownInnerTitle')}</p>
          <ul className="ml-4 list-disc">
            {report.unknown_inner.map((u) => (
              <li key={u.user_id}>{t('crm.bitrix24.report.unknownInnerItem', { name: u.user_name, phone: u.inner_phone })}</li>
            ))}
          </ul>
        </div>
      )}
      {report.conflicts.map((c) => (
        <p key={c.inner_phone}>{t('crm.bitrix24.report.conflictItem', { phone: c.inner_phone, names: c.user_names.join(', ') })}</p>
      ))}
    </div>
  );
}

/** Masʼul CRM holatiga mos belgi — `integrations.status.*` umumiy kalitlardan foydalanadi (IntegrationsPage bilan bir xil). */
const STATUS_TONE: Record<CrmStatusState, Tone> = { ok: 'success', error: 'danger', disabled: 'neutral' };

function BitrixStatusCard({ data, canManage }: { data: BitrixConfigResult; canManage: boolean }) {
  const { t } = useTranslation('integrations');
  const toast = useToast();
  const syncM = useSyncCrm('bitrix24');
  const lastAt = data.config.sync?.last_at;
  const host = data.config.connected ? data.config.domain : data.config.portal_host;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-surface-2/60 px-4 py-3">
      <div className="flex flex-col gap-0.5">
        <div className="flex items-center gap-2">
          <span className="font-display text-base font-semibold">
            {host ? t('crm.bitrix24.connected', { host }) : t('crm.bitrix24.notConnected')}
          </span>
          <Badge tone={STATUS_TONE[data.status.state]}>{t(`status.${data.status.state}`)}</Badge>
        </div>
        <p className="text-sm text-muted">
          {lastAt ? t('crm.bitrix24.lastSyncAt', { time: formatDateTime(lastAt) }) : t('crm.bitrix24.neverSynced')}
        </p>
        {data.status.last_error && <p className="text-sm text-danger">{data.status.last_error}</p>}
      </div>
      {canManage && (
        <Button
          data-testid="crm-sync" size="sm" variant="secondary" icon={<RefreshCw />} loading={syncM.isPending}
          onClick={() => syncM.mutate(undefined, {
            onSuccess: () => toast({ kind: 'success', title: t('crm.bitrix24.syncOk') }),
            onError: (e) => toast({ kind: 'error', title: t('crm.bitrix24.syncFail'), description: e.message }),
          })}
        >
          {t('crm.bitrix24.syncNow')}
        </Button>
      )}
    </div>
  );
}

/** Bitrix24 bulutdan xususiy (ichki) tarmoqdagi click-to-call manziliga yeta olmasligi haqida ogohlantirish + nusxalash. */
function CloudPrivateWarning({ cloud, hookUrl }: { cloud: boolean; hookUrl: string }) {
  const { t } = useTranslation('integrations');
  const toast = useToast();
  if (!cloudCannotReachPrivateHost(cloud, hookUrl)) return null;
  return (
    <div className="flex items-start gap-2 rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-sm text-on-warning-soft">
      <ShieldAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
      <span className="flex-1">{t('crm.bitrix24.cloudWarning')}</span>
      <Button
        size="sm" variant="ghost" iconOnly icon={<Copy />} aria-label={t('crm.bitrix24.copyAddress')}
        onClick={() => { void copyText(hookUrl); toast({ kind: 'success', title: t('crm.bitrix24.copied') }); }}
      />
    </div>
  );
}

/** Topshirish xatosi — alohida maydon xatosi sifatida allaqachon koʻrsatilgan boʻlsa, umumiy banner chiqarilmaydi. */
function formError(message: string | undefined, field: string | undefined, excludedFields: string[]): string | null {
  return message && !excludedFields.includes(field ?? '') ? message : null;
}

/** M3b §5 — Bitrix24 sozlamalari: has_webhook_url/application_token_set bilan maskalangan maydonlar. */
/** Bitrix'ga beriladigan TO'LIQ manzil: `public_base_url` (Sozlamalar) yoki brauzerdagi manzil. */
export function bitrixHookUrl(token: string, base: string | null | undefined, origin: string): string {
  return `${(base || origin).replace(/\/+$/, '')}/api/public/v1/crm/bitrix24/${token}/call`;
}

/** M3b §5 — `Bitrix24Form`ning forma holatini `UpdateBitrixPayload`ga aylantiradi (sof funksiya — CrmTab.test.tsx orqali sinaladi). */
export function bitrixSubmitPayload(form: {
  enabled: boolean; createLead: boolean; popupDelay: string; defaultUserId: string; webhookUrl: string; appToken: string;
  routeToResponsible: boolean; responsibleRingS: string; setCallerName: boolean; uploadRecords: boolean; autoSyncUsers: boolean;
  updatedAt: string;
}): UpdateBitrixPayload {
  return {
    enabled: form.enabled, create_lead: form.createLead, popup_max_delay_s: Number(form.popupDelay) || 0,
    default_user_id: form.defaultUserId.trim() || null, webhook_url: form.webhookUrl.trim() || undefined,
    application_token: form.appToken.trim() || undefined, updated_at: form.updatedAt,
    route_to_responsible: form.routeToResponsible, responsible_ring_s: Number(form.responsibleRingS) || 0,
    set_caller_name: form.setCallerName, upload_records: form.uploadRecords, auto_sync_users: form.autoSyncUsers,
  };
}

/** Standart Bitrix24 foydalanuvchisi: roʻyxat yuklangan boʻlsa Select, aks holda erkin matn (ID qoʻlda). */
function DefaultUserField({ users, value, onChange, canManage, label, noneLabel }: {
  users: CrmUser[]; value: string; onChange: (v: string) => void; canManage: boolean; label: string; noneLabel: string;
}) {
  return (
    <Field label={label} className="max-w-xs">
      {(a) =>
        users.length > 0 ? (
          <Select
            {...a} disabled={!canManage} value={value}
            options={[{ value: '', label: noneLabel }, ...users.map((u) => ({ value: u.id, label: `${u.name} (${u.id})` }))]}
            onValueChange={onChange}
          />
        ) : (
          <Input {...a} mono disabled={!canManage} value={value} onChange={(e) => onChange(e.target.value)} />
        )
      }
    </Field>
  );
}

/** Bitrix24'da (webhook_url/application_token) va amoCRM'da (token) ishlatiladigan — sirni maskalab koʻrsatadigan maydon. */
function MaskedSecretField({
  label, hint, setHint, isSet, value, onChange, disabled, error,
}: {
  label: string; hint: string; setHint: string; isSet: boolean; value: string;
  onChange: (v: string) => void; disabled: boolean; error?: string;
}) {
  return (
    <Field label={label} hint={isSet && !value ? setHint : hint} error={error}>
      {(a) => <Input {...a} mono disabled={disabled} placeholder={isSet ? '••••••••' : ''} value={value} onChange={(e) => onChange(e.target.value)} />}
    </Field>
  );
}

/** OnlinePBX uslubidagi «Ulash» oqimi natijasi: qaysi liniya/hodisa sozlandi, nechta xodim sinxronlandi. */
function Bitrix24SetupSummary({ setup, onGoToSettings }: { setup: Bitrix24Setup; onGoToSettings?: () => void }) {
  const { t } = useTranslation('integrations');
  const rows: { ok: boolean; label: string }[] = [
    { ok: setup.default_line, label: t(`crm.bitrix24.oauth.setup.${setup.default_line ? 'defaultLineOk' : 'defaultLineFail'}`) },
    { ok: setup.event_bound, label: t(`crm.bitrix24.oauth.setup.${setup.event_bound ? 'eventBoundOk' : 'eventBoundFail'}`) },
  ];
  return (
    <div data-testid="crm-bitrix24-setup" className="flex flex-col gap-2 rounded-lg border border-line bg-surface-2/60 px-4 py-3 text-sm">
      <p className="font-display text-base font-semibold">{t('crm.bitrix24.oauth.setup.title')}</p>
      <ul className="flex flex-col gap-1">
        <li>{t('crm.bitrix24.oauth.setup.lines', { count: setup.lines })}</li>
        {rows.map((r) => (
          <li key={r.label} className="flex items-center gap-1.5">
            {r.ok ? <CircleCheck aria-hidden className="size-3.5 shrink-0 text-success" /> : <CircleX aria-hidden className="size-3.5 shrink-0 text-danger" />}
            {r.label}
          </li>
        ))}
        <li>{t('crm.bitrix24.oauth.setup.usersSynced', { count: setup.users_synced })}</li>
      </ul>
      {setup.warnings.length > 0 && (
        <div className="flex flex-col gap-2 rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-on-warning-soft">
          {setup.warnings.map((w) => (
            <div key={w} className="flex flex-wrap items-center justify-between gap-2">
              <span>{t(`crm.bitrix24.oauth.warnings.${w}`)}</span>
              {w === 'public_url_missing' && onGoToSettings && (
                <Button size="sm" variant="ghost" onClick={onGoToSettings}>{t('crm.bitrix24.oauth.goToSettings')}</Button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Shartnoma §1 — litsenziya holatiga mos belgi. `sinov`/`faol` sanaga qarab matn oladi, qolganlari sobit. */
export const BITRIX_LICENSE_TONE: Record<Bitrix24LicenseState, Tone> = { sinov: 'warning', faol: 'success', imtiyoz: 'warning', tugagan: 'danger', bloklangan: 'danger' };

export function bitrix24LicenseLabel(t: (key: string, opts?: Record<string, unknown>) => string, license: Bitrix24License): string {
  const a = bitrix24LicenseStateArgs(license);
  if (a.state === 'sinov') return t('crm.bitrix24.oauth.license.sinov', { days: a.days });
  if (a.state === 'faol') return t('crm.bitrix24.oauth.license.faol', { date: formatDateShort(a.date!) });
  return t(`crm.bitrix24.oauth.license.${a.state}`);
}

function Bitrix24LicenseBadge({ license }: { license: Bitrix24License }) {
  const { t } = useTranslation('integrations');
  return <Badge tone={BITRIX_LICENSE_TONE[license.holat]}>{bitrix24LicenseLabel(t, license)}</Badge>;
}

/** Bitrix24 ulanmagan — portal domenini kiritib «Ulash» bosiladi: popup OAuth sahifasiga ketadi, keyin har 2s so'raladi. */
function Bitrix24ConnectCard({ canManage, onGoToSettings, onConnected }: { canManage: boolean; onGoToSettings?: () => void; onConnected?: (setup: Bitrix24Setup) => void }) {
  const { t } = useTranslation('integrations');
  const toast = useToast();
  const connectM = useConnectBitrix24();
  const pollM = usePollBitrix24Connect();
  const [domain, setDomain] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [waiting, setWaiting] = useState(false);
  const [setup, setSetup] = useState<Bitrix24Setup | null>(null);
  const popupRef = useRef<Window | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const attemptsRef = useRef(0);
  const busyRef = useRef(false);

  const stopPolling = () => {
    if (timerRef.current !== null) { clearInterval(timerRef.current); timerRef.current = null; }
    setWaiting(false);
  };
  useEffect(() => stopPolling, []);

  const tick = () => {
    if (busyRef.current) return;
    attemptsRef.current += 1;
    if (attemptsRef.current > BITRIX_POLL_MAX_ATTEMPTS) {
      stopPolling();
      popupRef.current?.close();
      setError(t('crm.bitrix24.oauth.timeout'));
      return;
    }
    busyRef.current = true;
    pollM.mutate(undefined, {
      onSettled: () => { busyRef.current = false; },
      onSuccess: (res) => {
        if (res.status === 'pending') return;
        stopPolling();
        popupRef.current?.close();
        if (res.status === 'error') { setError(t(`errors:${res.code}`, res.message)); return; }
        setSetup(res.setup);
        onConnected?.(res.setup);
        toast({ kind: 'success', title: t('crm.bitrix24.oauth.connectedTitle') });
      },
      onError: (e) => { stopPolling(); popupRef.current?.close(); setError(apiErrorMessage(e)); },
    });
  };

  const connect = () => {
    if (!canManage) return;
    setError(null);
    setSetup(null);
    if (!domain.trim()) { setError(t('crm.bitrix24.oauth.domainRequired')); return; }
    if (!normalizeBitrixDomain(domain)) { setError(t('crm.bitrix24.oauth.domainInvalid')); return; }

    const popup = window.open('about:blank', 'bitrix_ulash', 'width=560,height=720');
    if (!popup) { setError(t('crm.bitrix24.oauth.popupBlocked')); return; }
    popupRef.current = popup;
    connectM.mutate(domain, {
      onSuccess: (res) => {
        popup.location.href = res.authorize_url;
        attemptsRef.current = 0;
        setWaiting(true);
        timerRef.current = setInterval(tick, BITRIX_POLL_INTERVAL_MS);
      },
      onError: (e) => { popup.close(); setError(apiErrorMessage(e)); },
    });
  };

  return (
    <div data-testid="crm-bitrix24-connect" className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4 shadow-card">
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t('crm.bitrix24.oauth.domainLabel')} error={error ?? undefined} className="max-w-xs grow">
          {(a) => (
            <Input
              {...a} mono disabled={!canManage || connectM.isPending || waiting} placeholder={t('crm.bitrix24.oauth.domainPlaceholder')}
              value={domain} onChange={(e) => setDomain(e.target.value)}
            />
          )}
        </Field>
        <Button
          variant="primary" icon={<Link2 />} loading={connectM.isPending} disabled={!canManage || waiting}
          onClick={connect}
        >
          {t('crm.bitrix24.oauth.connect')}
        </Button>
        {waiting && (
          <Button variant="ghost" onClick={() => { stopPolling(); popupRef.current?.close(); }}>{t('common:cancel')}</Button>
        )}
      </div>
      {waiting && <p className="text-sm text-muted">{t('crm.bitrix24.oauth.waitingAuth')}</p>}
      {setup && <Bitrix24SetupSummary setup={setup} onGoToSettings={onGoToSettings} />}
    </div>
  );
}

/**
 * Bitrix24 OAuth orqali ulangan — domen, litsenziya holati, qayta sozlash va uzish.
 * `initialSetup` — yangi ulanishdan keyin darhol qaytgan sozlash natijasi (ota komponent — `Bitrix24Tab` —
 * «ulash» kartasidan bu yerga «kirib kelish» chegarasida ko'chiradi, aks holda holat ulanish bilan birga
 * yangi komponentga o'tganda yo'qolib qoladi).
 */
function Bitrix24ConnectedCard({ data, canManage, onGoToSettings, initialSetup }: { data: BitrixConfigResult; canManage: boolean; onGoToSettings?: () => void; initialSetup?: Bitrix24Setup | null }) {
  const { t } = useTranslation('integrations');
  const toast = useToast();
  const licenseQ = useBitrix24License(true);
  const setupM = useSetupBitrix24();
  const disconnectM = useDisconnectBitrix24();
  const [setup, setSetup] = useState<Bitrix24Setup | null>(initialSetup ?? null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  return (
    <div data-testid="crm-bitrix24-connected" className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-0.5">
          <span className="font-display text-base font-semibold">{data.config.domain}</span>
          {licenseQ.data?.license && <Bitrix24LicenseBadge license={licenseQ.data.license} />}
          {licenseQ.isError && <span className="text-sm text-danger">{t('crm.bitrix24.oauth.license.loadError')}</span>}
        </div>
        {canManage && (
          <div className="flex items-center gap-2">
            <Button
              variant="secondary" size="sm" icon={<RefreshCw />} loading={setupM.isPending}
              onClick={() => setupM.mutate(undefined, {
                onSuccess: (res) => { setSetup(res.setup); toast({ kind: 'success', title: t('crm.bitrix24.oauth.reconfigured') }); },
                onError: (e) => toast({ kind: 'error', title: t('crm.bitrix24.oauth.reconfigured'), description: apiErrorMessage(e) }),
              })}
            >
              {t('crm.bitrix24.oauth.reconfigure')}
            </Button>
            <Button variant="danger-ghost" size="sm" icon={<Unlink2 />} onClick={() => setConfirmOpen(true)}>
              {t('crm.bitrix24.oauth.disconnect')}
            </Button>
          </div>
        )}
      </div>
      {setup && <Bitrix24SetupSummary setup={setup} onGoToSettings={onGoToSettings} />}
      <ConfirmDeleteModal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        loading={disconnectM.isPending}
        title={t('crm.bitrix24.oauth.disconnectConfirmTitle')}
        body={t('crm.bitrix24.oauth.disconnectConfirmBody')}
        cancelLabel={t('common:cancel')}
        deleteLabel={t('crm.bitrix24.oauth.disconnectConfirmButton')}
        onConfirm={() => disconnectM.mutate(undefined, {
          onSuccess: () => { setConfirmOpen(false); toast({ kind: 'success', title: t('crm.bitrix24.oauth.disconnected') }); },
          onError: (e) => toast({ kind: 'error', title: t('crm.bitrix24.oauth.disconnect'), description: apiErrorMessage(e) }),
        })}
      />
    </div>
  );
}

function Bitrix24Form({ data, users, canManage }: { data: BitrixConfigResult; users: CrmUser[]; canManage: boolean }) {
  const { t } = useTranslation('integrations');
  const toast = useToast();
  const updateM = useUpdateBitrix24Config();
  const [enabled, setEnabled] = useState(data.enabled);
  const publicBase = useIntegrationsSettings().data?.public_base_url;
  const [webhookUrl, setWebhookUrl] = useState('');
  const [createLead, setCreateLead] = useState(data.config.create_lead);
  const [popupDelay, setPopupDelay] = useState(String(data.config.popup_max_delay_s));
  const [defaultUserId, setDefaultUserId] = useState(data.config.default_user_id ?? '');
  const [appToken, setAppToken] = useState('');
  const [routeToResponsible, setRouteToResponsible] = useState(data.config.route_to_responsible);
  const [responsibleRingS, setResponsibleRingS] = useState(String(data.config.responsible_ring_s));
  const [setCallerName, setSetCallerName] = useState(data.config.set_caller_name);
  const [uploadRecords, setUploadRecords] = useState(data.config.upload_records);
  const [autoSyncUsers, setAutoSyncUsers] = useState(data.config.auto_sync_users);

  const { field: errorField, message: errorMessage } = useMutationError(updateM.error);
  const hookUrl = bitrixHookUrl(data.config.hook_token, publicBase, window.location.origin);

  const submit = () => {
    const payload = bitrixSubmitPayload({
      enabled, createLead, popupDelay, defaultUserId, webhookUrl, appToken, routeToResponsible,
      responsibleRingS, setCallerName, uploadRecords, autoSyncUsers, updatedAt: data.updated_at,
    });
    updateM.mutate(payload, { onSuccess: () => { toast({ kind: 'success', title: t('crm.bitrix24.saved') }); setWebhookUrl(''); setAppToken(''); } });
  };

  return (
    <div data-testid="crm-bitrix24-form" className="flex max-w-2xl flex-col gap-4">
      <Toggle checked={enabled} disabled={!canManage} onCheckedChange={setEnabled} label={t('crm.bitrix24.enabled')} />

      <details open={data.config.auth_mode === 'webhook'} className="border-t border-line pt-4 first:border-t-0 first:pt-0">
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-muted">{t('crm.bitrix24.oauth.legacyTitle')}</summary>
        <div className="mt-3.5">
          <Section title={t('crm.bitrix24.sections.connection')}>
            <MaskedSecretField
              label={t('crm.bitrix24.webhookUrl')} hint={t('crm.bitrix24.webhookUrlHint')} setHint={t('crm.bitrix24.webhookUrlSet')}
              isSet={data.config.has_webhook_url} value={webhookUrl} onChange={setWebhookUrl} disabled={!canManage}
              error={errorField === 'webhook_url' ? errorMessage : undefined}
            />
            <MaskedSecretField
              label={t('crm.bitrix24.appToken')} hint={t('crm.bitrix24.appTokenHint')} setHint={t('crm.bitrix24.appTokenSet')}
              isSet={data.config.application_token_set} value={appToken} onChange={setAppToken} disabled={!canManage}
            />
            <Field label={t('crm.bitrix24.hookUrl')} hint={t('crm.bitrix24.hookUrlHint')}>
              {(a) => <Input {...a} mono readOnly value={hookUrl} />}
            </Field>
            <CloudPrivateWarning cloud={data.config.portal_cloud} hookUrl={hookUrl} />
          </Section>
        </div>
      </details>

      <Section title={t('crm.bitrix24.sections.calls')}>
        <Toggle checked={createLead} disabled={!canManage} onCheckedChange={setCreateLead} label={t('crm.bitrix24.createLead')} />
        <Field label={t('crm.bitrix24.popupMaxDelay')} className="max-w-xs">
          {(a) => <Input {...a} mono inputMode="numeric" disabled={!canManage} value={popupDelay} onChange={(e) => setPopupDelay(e.target.value)} />}
        </Field>
        <DefaultUserField
          users={users} value={defaultUserId} onChange={setDefaultUserId} canManage={canManage}
          label={t('crm.bitrix24.defaultUserId')} noneLabel={t('crm.bitrix24.defaultUserIdNone')}
        />
        <Toggle checked={setCallerName} disabled={!canManage} onCheckedChange={setSetCallerName} label={t('crm.bitrix24.setCallerName')} />
        <Toggle checked={uploadRecords} disabled={!canManage} onCheckedChange={setUploadRecords} label={t('crm.bitrix24.uploadRecords')} />
      </Section>

      <Section title={t('crm.bitrix24.sections.routing')}>
        <Toggle
          checked={routeToResponsible} disabled={!canManage} onCheckedChange={setRouteToResponsible}
          label={t('crm.bitrix24.routeToResponsible')} description={t('crm.bitrix24.responsibleHint')}
        />
        <Field label={t('crm.bitrix24.responsibleRingS')} className="max-w-xs">
          {(a) => (
            <Input
              {...a} mono inputMode="numeric" disabled={!canManage || !routeToResponsible}
              value={responsibleRingS} onChange={(e) => setResponsibleRingS(e.target.value)}
            />
          )}
        </Field>
      </Section>

      <Section title={t('crm.bitrix24.sections.users')}>
        <Toggle checked={autoSyncUsers} disabled={!canManage} onCheckedChange={setAutoSyncUsers} label={t('crm.bitrix24.autoSyncUsers')} />
      </Section>

      <OtherFormError message={formError(errorMessage, errorField, ['webhook_url'])} />
      <SaveButtonRow canManage={canManage} pending={updateM.isPending} onClick={submit} label={t('crm.bitrix24.save')} />
    </div>
  );
}

/** M3b §5 — amoCRM sozlamalari: token_set bilan maskalangan token maydoni. */
function AmoCrmForm({ data, canManage }: { data: AmoConfigResult; canManage: boolean }) {
  const { t } = useTranslation('integrations');
  const toast = useToast();
  const updateM = useUpdateAmoCrmConfig();
  const [enabled, setEnabled] = useState(data.enabled);
  const [baseUrl, setBaseUrl] = useState(data.config.base_url);
  const [token, setToken] = useState('');
  const [unsorted, setUnsorted] = useState(data.config.unsorted_for_unknown);
  const [defaultUserId, setDefaultUserId] = useState(data.config.default_user_id ?? '');

  const { field: errorField, message: errorMessage } = useMutationError(updateM.error);

  const submit = () => {
    updateM.mutate({
      enabled, base_url: baseUrl.trim(), unsorted_for_unknown: unsorted, default_user_id: defaultUserId.trim() || null,
      token: token.trim() || undefined, updated_at: data.updated_at,
    }, { onSuccess: () => { toast({ kind: 'success', title: t('crm.amocrm.saved') }); setToken(''); } });
  };

  return (
    <div data-testid="crm-amocrm-form" className="flex max-w-2xl flex-col gap-4">
      <Toggle checked={enabled} disabled={!canManage} onCheckedChange={setEnabled} label={t('crm.amocrm.enabled')} />
      <Field label={t('crm.amocrm.baseUrl')} hint={t('crm.amocrm.baseUrlHint')} error={errorField === 'base_url' ? errorMessage : undefined}>
        {(a) => <Input {...a} mono disabled={!canManage} value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />}
      </Field>
      <MaskedSecretField
        label={t('crm.amocrm.token')} hint="" setHint={t('crm.amocrm.tokenSet')}
        isSet={data.config.token_set} value={token} onChange={setToken} disabled={!canManage}
      />
      <Toggle checked={unsorted} disabled={!canManage} onCheckedChange={setUnsorted} label={t('crm.amocrm.unsortedForUnknown')} />
      <Field label={t('crm.amocrm.defaultUserId')} className="max-w-xs">
        {(a) => <Input {...a} mono disabled={!canManage} value={defaultUserId} onChange={(e) => setDefaultUserId(e.target.value)} />}
      </Field>
      <OtherFormError message={formError(errorMessage, errorField, ['base_url'])} />
      <SaveButtonRow canManage={canManage} pending={updateM.isPending} onClick={submit} label={t('crm.amocrm.save')} />
    </div>
  );
}

function TestConnectionButton({ provider }: { provider: CrmProvider }) {
  const { t } = useTranslation('integrations');
  const toast = useToast();
  const testM = useTestCrm(provider);
  return (
    <Button
      data-testid="crm-test" variant="secondary" icon={testM.data ? (testM.data.ok ? <CircleCheck /> : <CircleX />) : <Plug />}
      loading={testM.isPending}
      onClick={() => testM.mutate(undefined, {
        onSuccess: (res) => toast({ kind: res.ok ? 'success' : 'error', title: res.ok ? t('crm.testOk') : t('crm.testFail'), description: res.message }),
        onError: (e) => toast({ kind: 'error', title: t('crm.testFail'), description: e.message }),
      })}
    >
      {t('crm.testConnection')}
    </Button>
  );
}

/** Bitrix24 — OnlinePBX uslubidagi «Ulash», holat/sinxron kartasi va "Внутренний номер" asosidagi avto-moslashuv jadvali. */
function Bitrix24Tab({ data, canManage, onGoToSettings }: { data: BitrixConfigResult; canManage: boolean; onGoToSettings?: () => void }) {
  const { t } = useTranslation('integrations');
  const usersQ = useCrmUsers('bitrix24');
  const users = usersQ.data?.items ?? [];
  const synced = data.config.sync !== null;
  // Yangi ulanishdan qaytgan sozlash natijasi — "ulash" kartasidan "ulandi" kartasiga o'tishda yo'qolmasin.
  const [freshSetup, setFreshSetup] = useState<Bitrix24Setup | null>(null);

  return (
    <section className="flex flex-col gap-5">
      {data.config.connected
        ? <Bitrix24ConnectedCard data={data} canManage={canManage} onGoToSettings={onGoToSettings} initialSetup={freshSetup} />
        : <Bitrix24ConnectCard canManage={canManage} onGoToSettings={onGoToSettings} onConnected={setFreshSetup} />}
      <BitrixStatusCard data={data} canManage={canManage} />
      <Bitrix24Form data={data} users={users} canManage={canManage} />
      <SyncReportBanner report={data.config.sync} />
      <div data-testid="crm-usermap">
        <h3 className="mb-1 font-display text-base font-semibold">{t('crm.userMap')}</h3>
        <p className="mb-2 text-sm text-muted">{t('crm.userMapDesc')}</p>
        {synced
          ? <BitrixUserMapTable entries={data.user_map} users={users} canManage={canManage} />
          : <LegacyUserMapTable provider="bitrix24" entries={data.user_map} canManage={canManage} />}
      </div>
    </section>
  );
}

/** Bitrix24/amoCRM — konfiguratsiya, ulanishni tekshirish va foydalanuvchi moslashuvi. Provider bo'yicha parametrlangan. */
export function CrmTab({ provider, canManage, onGoToSettings }: { provider: CrmProvider; canManage: boolean; onGoToSettings?: () => void }) {
  const { t } = useTranslation('integrations');
  const bitrix = useBitrix24Config();
  const amo = useAmoCrmConfig();
  const query = provider === 'bitrix24' ? bitrix : amo;

  if (query.isLoading || !query.data) {
    return <p className="text-sm text-muted">{query.isError ? t('crm.testFail') : '…'}</p>;
  }

  if (provider === 'bitrix24') {
    return <Bitrix24Tab data={bitrix.data as BitrixConfigResult} canManage={canManage} onGoToSettings={onGoToSettings} />;
  }

  return (
    <section className="flex flex-col gap-5">
      <AmoCrmForm data={amo.data as AmoConfigResult} canManage={canManage} />
      <div><TestConnectionButton provider={provider} /></div>
      <UnmappedBanner list={query.data.status.unmapped_extensions} />
      <div data-testid="crm-usermap">
        <h3 className="mb-1 font-display text-base font-semibold">{t('crm.userMap')}</h3>
        <p className="mb-2 text-sm text-muted">{t('crm.userMapDesc')}</p>
        <LegacyUserMapTable provider={provider} entries={query.data.user_map} canManage={canManage} />
      </div>
    </section>
  );
}
