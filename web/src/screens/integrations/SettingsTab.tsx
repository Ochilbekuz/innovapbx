import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  useIntegrationsSettings, useRecordingSettings, useTestTtsSettings, useTtsSettings, useUpdateIntegrationsSettings,
  useUpdateRecordingSettings, useUpdateTtsSettings,
} from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { IntegrationsSettings, RecordingSettings, TtsProvider, TtsSettings, TtsVoices } from '@/api/types';
import { Button } from '@/ui/Button';
import { Field, Input, Select } from '@/ui/Field';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';
import { StaleBanner, useMutationError } from './shared';

function SettingsSection({
  title, children, canManage, pending, onSave,
}: { title: string; children: React.ReactNode; canManage: boolean; pending: boolean; onSave: () => void }) {
  const { t } = useTranslation('integrations');
  return (
    <section className="max-w-2xl rounded-lg border border-line bg-surface p-4 shadow-card">
      <h3 className="mb-3 font-display text-base font-semibold">{title}</h3>
      <div className="flex flex-col gap-4">
        {children}
        {canManage && <div><Button variant="primary" loading={pending} onClick={onSave}>{t('settings.save')}</Button></div>}
      </div>
    </section>
  );
}

function IntegrationsSettingsForm({ data, canManage }: { data: IntegrationsSettings; canManage: boolean }) {
  const { t } = useTranslation('integrations');
  const toast = useToast();
  const updateM = useUpdateIntegrationsSettings();
  const [publicBaseUrl, setPublicBaseUrl] = useState(data.public_base_url ?? '');
  const [ttl, setTtl] = useState(String(data.recording_link_ttl_s));
  const { field: errorField, message: errorMessage, stale } = useMutationError(updateM.error);

  const submit = () => {
    updateM.mutate({ public_base_url: publicBaseUrl.trim() || null, recording_link_ttl_s: Number(ttl) || 0, updated_at: data.updated_at }, {
      onSuccess: () => toast({ kind: 'success', title: t('settings.saved') }),
    });
  };

  return (
    <SettingsSection title={t('settings.integrationsTitle')} canManage={canManage} pending={updateM.isPending} onSave={submit}>
      <StaleBanner stale={stale} message={errorMessage} />
      <Field label={t('settings.publicBaseUrl')} hint={t('settings.publicBaseUrlHint')} error={errorField === 'public_base_url' ? errorMessage : undefined}>
        {(a) => <Input {...a} mono disabled={!canManage} value={publicBaseUrl} onChange={(e) => setPublicBaseUrl(e.target.value)} />}
      </Field>
      <Field label={t('settings.recordingLinkTtl')} className="max-w-xs" error={errorField === 'recording_link_ttl_s' ? errorMessage : undefined}>
        {(a) => <Input {...a} mono inputMode="numeric" disabled={!canManage} value={ttl} onChange={(e) => setTtl(e.target.value)} />}
      </Field>
    </SettingsSection>
  );
}

function RecordingSettingsForm({ data, canManage }: { data: RecordingSettings; canManage: boolean }) {
  const { t } = useTranslation('integrations');
  const toast = useToast();
  const updateM = useUpdateRecordingSettings();
  const [retentionDays, setRetentionDays] = useState(String(data.retention_days));
  const [externalOnly, setExternalOnly] = useState(data.external_only);
  const { field: errorField, message: errorMessage, stale } = useMutationError(updateM.error);

  const submit = () => {
    updateM.mutate({ retention_days: Number(retentionDays) || 0, external_only: externalOnly, updated_at: data.updated_at }, {
      onSuccess: () => toast({ kind: 'success', title: t('settings.saved') }),
    });
  };

  return (
    <SettingsSection title={t('settings.recordingTitle')} canManage={canManage} pending={updateM.isPending} onSave={submit}>
      <StaleBanner stale={stale} message={errorMessage} />
      <Field label={t('settings.retentionDays')} className="max-w-xs" error={errorField === 'retention_days' ? errorMessage : undefined}>
        {(a) => <Input {...a} mono inputMode="numeric" disabled={!canManage} value={retentionDays} onChange={(e) => setRetentionDays(e.target.value)} />}
      </Field>
      <Toggle checked={externalOnly} disabled={!canManage} onCheckedChange={setExternalOnly} label={t('settings.externalOnly')} />
    </SettingsSection>
  );
}

/** M10 C A3 — Nutq sintezi (Yandex SpeechKit): provayder, API kalit (faqat yozish), katalog ID, ovozlar, sinash. */
function SpeechKitSettingsForm({ data, canManage }: { data: TtsSettings; canManage: boolean }) {
  const { t } = useTranslation('integrations');
  const toast = useToast();
  const updateM = useUpdateTtsSettings();
  const testM = useTestTtsSettings();
  const [provider, setProvider] = useState<TtsProvider>(data.provider);
  const [apiKey, setApiKey] = useState('');
  const [voices, setVoices] = useState<TtsVoices>(data.voices);
  const { field: errorField, message: errorMessage, stale } = useMutationError(updateM.error);

  const setVoice = (lang: keyof TtsVoices, v: string) => setVoices((prev) => ({ ...prev, [lang]: v }));
  // Sinov SAQLANGAN sozlamani tekshiradi — saqlanmagan o'zgarish bilan bosilsa chalg'ituvchi natija beradi.
  const dirty = apiKey !== '' || provider !== data.provider || JSON.stringify(voices) !== JSON.stringify(data.voices);

  const submit = () => {
    // Bo'sh qoldirilsa — mavjud kalitga tegilmaydi (faqat qayta kiritilganda almashtiriladi/o'chiriladi — "" bilan).
    updateM.mutate({ provider, ...(apiKey !== '' ? { api_key: apiKey } : {}), voices, updated_at: data.updated_at }, {
      onSuccess: () => { toast({ kind: 'success', title: t('settings.saved') }); setApiKey(''); },
    });
  };

  const runTest = () => {
    testM.mutate(undefined, {
      onSuccess: (res) => toast(res.ok ? { kind: 'success', title: t('settings.speechkit.testOk') } : { kind: 'error', title: t('settings.speechkit.testFail', { message: res.message }) }),
      onError: (e) => toast({ kind: 'error', title: t('settings.speechkit.testFail', { message: isApiError(e) ? e.message : String(e) }) }),
    });
  };

  return (
    <SettingsSection title={t('settings.speechkit.title')} canManage={canManage} pending={updateM.isPending} onSave={submit}>
      <StaleBanner stale={stale} message={errorMessage} />
      <Field label={t('settings.speechkit.providerLabel')} className="max-w-xs">
        {(a) => (
          <Select
            {...a} disabled={!canManage} value={provider} onValueChange={(v) => setProvider(v as TtsProvider)}
            options={[{ value: 'none', label: t('settings.speechkit.provider.none') }, { value: 'yandex', label: t('settings.speechkit.provider.yandex') }]}
          />
        )}
      </Field>
      {provider === 'yandex' && (
        <>
          <Field
            label={t('settings.speechkit.apiKeyLabel')} hint={data.has_api_key ? t('settings.speechkit.apiKeySetHint') : undefined}
            error={errorField === 'api_key' ? errorMessage : undefined}
          >
            {(a) => <Input {...a} mono disabled={!canManage} type="password" placeholder={t('settings.speechkit.apiKeyPlaceholder')} value={apiKey} onChange={(e) => setApiKey(e.target.value)} />}
          </Field>
          <div>
            <p className="mb-2 text-sm font-medium text-fg">{t('settings.speechkit.voicesTitle')}</p>
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label={t('settings.speechkit.voiceUz')}>{(a) => <Input {...a} mono disabled={!canManage} value={voices.uz} onChange={(e) => setVoice('uz', e.target.value)} />}</Field>
              <Field label={t('settings.speechkit.voiceRu')}>{(a) => <Input {...a} mono disabled={!canManage} value={voices.ru} onChange={(e) => setVoice('ru', e.target.value)} />}</Field>
              <Field label={t('settings.speechkit.voiceEn')}>{(a) => <Input {...a} mono disabled={!canManage} value={voices.en} onChange={(e) => setVoice('en', e.target.value)} />}</Field>
            </div>
          </div>
          {canManage && (
            <div className="flex items-center gap-3">
              <Button variant="secondary" loading={testM.isPending} disabled={dirty} onClick={runTest}>{t('settings.speechkit.test')}</Button>
              {dirty && <span className="text-sm text-muted">{t('settings.speechkit.saveBeforeTest')}</span>}
            </div>
          )}
        </>
      )}
    </SettingsSection>
  );
}

/** M3b §6 — Integratsiyalar sozlamalari (public_base_url/TTL) + qoʻngʻiroq yozib olish (saqlash muddati/faqat tashqi) + TTS. */
export function SettingsTab({ canManage }: { canManage: boolean }) {
  const integrations = useIntegrationsSettings();
  const recording = useRecordingSettings();
  const tts = useTtsSettings();

  if (integrations.isLoading || recording.isLoading || tts.isLoading || !integrations.data || !recording.data || !tts.data) {
    return <p className="text-sm text-muted">…</p>;
  }

  return (
    <div className="flex flex-col gap-5">
      <IntegrationsSettingsForm data={integrations.data} canManage={canManage} />
      <RecordingSettingsForm data={recording.data} canManage={canManage} />
      <SpeechKitSettingsForm data={tts.data} canManage={canManage} />
    </div>
  );
}
