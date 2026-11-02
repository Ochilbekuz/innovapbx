import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useIntegrationsSettings, useRecordingSettings, useUpdateIntegrationsSettings, useUpdateRecordingSettings } from '@/api/queries';
import type { IntegrationsSettings, RecordingSettings } from '@/api/types';
import { Button } from '@/ui/Button';
import { Field, Input } from '@/ui/Field';
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

/** M3b §6 — Integratsiyalar sozlamalari (public_base_url/TTL) + qoʻngʻiroq yozib olish (saqlash muddati/faqat tashqi). */
export function SettingsTab({ canManage }: { canManage: boolean }) {
  const integrations = useIntegrationsSettings();
  const recording = useRecordingSettings();

  if (integrations.isLoading || recording.isLoading || !integrations.data || !recording.data) {
    return <p className="text-sm text-muted">…</p>;
  }

  return (
    <div className="flex flex-col gap-5">
      <IntegrationsSettingsForm data={integrations.data} canManage={canManage} />
      <RecordingSettingsForm data={recording.data} canManage={canManage} />
    </div>
  );
}
