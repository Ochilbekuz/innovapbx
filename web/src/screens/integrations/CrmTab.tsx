import { type ReactNode, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CircleCheck, CircleX, Copy, Plug, RefreshCw, ShieldAlert } from 'lucide-react';
import {
  useAmoCrmConfig, useBitrix24Config, useCrmUsers, useIntegrationsSettings, useSyncCrm, useTestCrm,
  useUpdateAmoCrmConfig, useUpdateBitrix24Config, useUpdateCrmUserMap,
} from '@/api/queries';
import type { AmoConfigResult, BitrixConfigResult, CrmProvider, CrmStatusState, CrmUser, CrmUserMapEntry, UpdateBitrixPayload } from '@/api/types';
import { cloudCannotReachPrivateHost } from '@/domain/crm';
import { copyText } from '@/lib/browser';
import { Button } from '@/ui/Button';
import { Field, Input, Select } from '@/ui/Field';
import { Badge, type Tone } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';
import { OtherFormError, SaveButtonRow, useMutationError } from './shared';

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

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-surface-2/60 px-4 py-3">
      <div className="flex flex-col gap-0.5">
        <div className="flex items-center gap-2">
          <span className="font-display text-base font-semibold">
            {data.config.portal_host ? t('crm.bitrix24.connected', { host: data.config.portal_host }) : t('crm.bitrix24.notConnected')}
          </span>
          <Badge tone={STATUS_TONE[data.status.state]}>{t(`status.${data.status.state}`)}</Badge>
        </div>
        <p className="text-sm text-muted">
          {lastAt ? t('crm.bitrix24.lastSyncAt', { time: new Date(lastAt).toLocaleString() }) : t('crm.bitrix24.neverSynced')}
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

/** Bitrix24 — sozlamalar, holat/sinxron kartasi va "Внутренний номер" asosidagi avto-moslashuv jadvali. */
function Bitrix24Tab({ data, canManage }: { data: BitrixConfigResult; canManage: boolean }) {
  const { t } = useTranslation('integrations');
  const usersQ = useCrmUsers('bitrix24');
  const users = usersQ.data?.items ?? [];
  const synced = data.config.sync !== null;

  return (
    <section className="flex flex-col gap-5">
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
export function CrmTab({ provider, canManage }: { provider: CrmProvider; canManage: boolean }) {
  const { t } = useTranslation('integrations');
  const bitrix = useBitrix24Config();
  const amo = useAmoCrmConfig();
  const query = provider === 'bitrix24' ? bitrix : amo;

  if (query.isLoading || !query.data) {
    return <p className="text-sm text-muted">{query.isError ? t('crm.testFail') : '…'}</p>;
  }

  if (provider === 'bitrix24') {
    return <Bitrix24Tab data={bitrix.data as BitrixConfigResult} canManage={canManage} />;
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
