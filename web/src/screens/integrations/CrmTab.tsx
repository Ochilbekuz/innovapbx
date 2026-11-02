import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CircleCheck, CircleX, Plug } from 'lucide-react';
import {
  useAmoCrmConfig, useBitrix24Config, useIntegrationsSettings, useTestCrm, useUpdateAmoCrmConfig, useUpdateBitrix24Config, useUpdateCrmUserMap,
} from '@/api/queries';
import type { AmoConfigResult, BitrixConfigResult, CrmProvider, CrmUserMapEntry } from '@/api/types';
import { Button } from '@/ui/Button';
import { Field, Input } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';
import { OtherFormError, SaveButtonRow, useMutationError } from './shared';

function UnmappedBanner({ list }: { list: string[] }) {
  const { t } = useTranslation('integrations');
  if (list.length === 0) return null;
  return <p className="rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-sm text-on-warning-soft">{t('crm.unmapped', { list: list.join(', ') })}</p>;
}

function UserMapTable({ provider, entries, canManage }: { provider: CrmProvider; entries: CrmUserMapEntry[]; canManage: boolean }) {
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

/** Topshirish xatosi — alohida maydon xatosi sifatida allaqachon koʻrsatilgan boʻlsa, umumiy banner chiqarilmaydi. */
function formError(message: string | undefined, field: string | undefined, excludedFields: string[]): string | null {
  return message && !excludedFields.includes(field ?? '') ? message : null;
}

/** M3b §5 — Bitrix24 sozlamalari: has_webhook_url/application_token_set bilan maskalangan maydonlar. */
/** Bitrix'ga beriladigan TO'LIQ manzil: `public_base_url` (Sozlamalar) yoki brauzerdagi manzil. */
export function bitrixHookUrl(token: string, base: string | null | undefined, origin: string): string {
  return `${(base || origin).replace(/\/+$/, '')}/api/public/v1/crm/bitrix24/${token}/call`;
}

function Bitrix24Form({ data, canManage }: { data: BitrixConfigResult; canManage: boolean }) {
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

  const { field: errorField, message: errorMessage } = useMutationError(updateM.error);

  const submit = () => {
    updateM.mutate({
      enabled, create_lead: createLead, popup_max_delay_s: Number(popupDelay) || 0, default_user_id: defaultUserId.trim() || null,
      webhook_url: webhookUrl.trim() || undefined, application_token: appToken.trim() || undefined, updated_at: data.updated_at,
    }, { onSuccess: () => { toast({ kind: 'success', title: t('crm.bitrix24.saved') }); setWebhookUrl(''); setAppToken(''); } });
  };

  return (
    <div data-testid="crm-bitrix24-form" className="flex max-w-2xl flex-col gap-4">
      <Toggle checked={enabled} disabled={!canManage} onCheckedChange={setEnabled} label={t('crm.bitrix24.enabled')} />
      <MaskedSecretField
        label={t('crm.bitrix24.webhookUrl')} hint={t('crm.bitrix24.webhookUrlHint')} setHint={t('crm.bitrix24.webhookUrlSet')}
        isSet={data.config.has_webhook_url} value={webhookUrl} onChange={setWebhookUrl} disabled={!canManage}
        error={errorField === 'webhook_url' ? errorMessage : undefined}
      />
      <Toggle checked={createLead} disabled={!canManage} onCheckedChange={setCreateLead} label={t('crm.bitrix24.createLead')} />
      <Field label={t('crm.bitrix24.popupMaxDelay')} className="max-w-xs">
        {(a) => <Input {...a} mono inputMode="numeric" disabled={!canManage} value={popupDelay} onChange={(e) => setPopupDelay(e.target.value)} />}
      </Field>
      <Field label={t('crm.bitrix24.defaultUserId')} className="max-w-xs">
        {(a) => <Input {...a} mono disabled={!canManage} value={defaultUserId} onChange={(e) => setDefaultUserId(e.target.value)} />}
      </Field>
      <MaskedSecretField
        label={t('crm.bitrix24.appToken')} hint={t('crm.bitrix24.appTokenHint')} setHint={t('crm.bitrix24.appTokenSet')}
        isSet={data.config.application_token_set} value={appToken} onChange={setAppToken} disabled={!canManage}
      />
      <Field label={t('crm.bitrix24.hookUrl')} hint={t('crm.bitrix24.hookUrlHint')}>
        {(a) => <Input {...a} mono readOnly value={bitrixHookUrl(data.config.hook_token, publicBase, window.location.origin)} />}
      </Field>
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

/** Bitrix24/amoCRM — konfiguratsiya, ulanishni tekshirish va foydalanuvchi moslashuvi. Provider bo'yicha parametrlangan. */
export function CrmTab({ provider, canManage }: { provider: CrmProvider; canManage: boolean }) {
  const { t } = useTranslation('integrations');
  const bitrix = useBitrix24Config();
  const amo = useAmoCrmConfig();
  const query = provider === 'bitrix24' ? bitrix : amo;

  if (query.isLoading || !query.data) {
    return <p className="text-sm text-muted">{query.isError ? t('crm.testFail') : '…'}</p>;
  }

  return (
    <section className="flex flex-col gap-5">
      {provider === 'bitrix24'
        ? <Bitrix24Form data={bitrix.data as BitrixConfigResult} canManage={canManage} />
        : <AmoCrmForm data={amo.data as AmoConfigResult} canManage={canManage} />}
      <div><TestConnectionButton provider={provider} /></div>
      <UnmappedBanner list={query.data.status.unmapped_extensions} />
      <div data-testid="crm-usermap">
        <h3 className="mb-1 font-display text-base font-semibold">{t('crm.userMap')}</h3>
        <p className="mb-2 text-sm text-muted">{t('crm.userMapDesc')}</p>
        <UserMapTable provider={provider} entries={query.data.user_map} canManage={canManage} />
      </div>
    </section>
  );
}
