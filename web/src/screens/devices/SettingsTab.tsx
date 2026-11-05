import { useTranslation } from 'react-i18next';
import { useProvisioningSettings, useUpdateProvisioningSettings } from '@/api/queries';
import type { ProvisioningExtra, ProvisioningSettings, SipTransport } from '@/api/types';
import { TimezonePicker } from '@/screens/time/TimezonePicker';
import { Button } from '@/ui/Button';
import { Field, Input, Select, Textarea } from '@/ui/Field';
import { useToast } from '@/ui/Toast';
import { OtherFormError, StaleBanner, useMutationError } from '@/screens/integrations/shared';
import { fieldError, otherFieldError } from '@/lib/formHelpers';
import { adminPasswordHint, extraFieldError, provisioningPayload, useProvisioningForm } from './provisioningForm';

const LANGS = ['uz', 'ru', 'en'] as const;
const TRANSPORTS: SipTransport[] = ['udp', 'tcp', 'tls'];
const VENDOR_EXTRA = ['yealink', 'grandstream', 'fanvil'] as const;

/** Bitta vendor uchun qoʻlda kiritish konfiguratsiyasi maydoni — xato va qiymat sof funksiyadan keladi. */
function ExtraField({
  vendor, value, error, canManage, onChange,
}: { vendor: (typeof VENDOR_EXTRA)[number]; value: string; error: string | undefined; canManage: boolean; onChange: (v: string) => void }) {
  const { t } = useTranslation('devices');
  return (
    <Field label={t(`settings.extra.${vendor}`)} error={error}>
      {(a) => <Textarea {...a} disabled={!canManage} className="num" rows={2} value={value} onChange={(e) => onChange(e.target.value)} />}
    </Field>
  );
}

function ProvisioningSettingsForm({ data, canManage }: { data: ProvisioningSettings; canManage: boolean }) {
  const { t } = useTranslation('devices');
  const toast = useToast();
  const updateM = useUpdateProvisioningSettings();
  const {
    state, setLanguage, setTimezone, setNtpServer, setSipTransport, setSipServerHost,
    setAllowedNetworks, setAdminPassword, setExtraField, clearAdminPassword,
  } = useProvisioningForm(data);
  const { field: errorField, message: errorMessage, stale } = useMutationError(updateM.error);

  const submit = () => {
    updateM.mutate(provisioningPayload(state, data.updated_at), {
      onSuccess: () => { toast({ kind: 'success', title: t('saved') }); clearAdminPassword(); },
    });
  };

  return (
    <section className="max-w-2xl rounded-lg border border-line bg-surface p-4 shadow-card">
      <h3 className="mb-3 font-display text-base font-semibold">{t('settings.title')}</h3>
      <div className="flex flex-col gap-4">
        <StaleBanner stale={stale} message={errorMessage} />
        <Field label={t('settings.language')}>
          {(a) => (
            <Select
              {...a} disabled={!canManage} value={state.language}
              onValueChange={(v) => setLanguage(v as ProvisioningSettings['language'])}
              options={LANGS.map((l) => ({ value: l, label: l.toUpperCase() }))}
            />
          )}
        </Field>
        <Field label={t('settings.timezone')} hint={t('settings.timezoneHint')}>
          {(a) => (
            <TimezonePicker
              {...a}
              disabled={!canManage}
              value={state.timezone}
              onChange={setTimezone}
              searchPlaceholder={t('settings.timezoneSearchPlaceholder')}
              noMatch={t('settings.timezoneNoMatch')}
            />
          )}
        </Field>
        <Field label={t('settings.ntpServer')}>
          {(a) => <Input {...a} disabled={!canManage} mono value={state.ntpServer} onChange={(e) => setNtpServer(e.target.value)} />}
        </Field>
        <Field label={t('settings.sipTransport')}>
          {(a) => (
            <Select
              {...a} disabled={!canManage} value={state.sipTransport} onValueChange={(v) => setSipTransport(v as SipTransport)}
              options={TRANSPORTS.map((v) => ({ value: v, label: v.toUpperCase() }))}
            />
          )}
        </Field>
        <Field label={t('settings.sipServerHost')} hint={t('settings.sipServerHostHint')} error={fieldError(errorField, 'sip_server_host', errorMessage)}>
          {(a) => <Input {...a} disabled={!canManage} mono value={state.sipServerHost} onChange={(e) => setSipServerHost(e.target.value)} />}
        </Field>
        <Field label={t('settings.allowedNetworks')} hint={t('settings.allowedNetworksHint')} error={fieldError(errorField, 'allowed_networks', errorMessage)}>
          {(a) => <Textarea {...a} disabled={!canManage} className="num" rows={3} value={state.allowedNetworks} onChange={(e) => setAllowedNetworks(e.target.value)} />}
        </Field>
        <Field label={t('settings.adminPassword')} hint={adminPasswordHint(t, data.has_admin_password)}>
          {(a) => <Input {...a} disabled={!canManage} type="password" autoComplete="new-password" value={state.adminPassword} onChange={(e) => setAdminPassword(e.target.value)} />}
        </Field>
        <div>
          <p className="mb-1.5 text-sm font-medium text-fg">{t('settings.extraTitle')}</p>
          <p className="mb-2 text-sm text-muted">{t('settings.extraHint')}</p>
          <div className="flex flex-col gap-3">
            {VENDOR_EXTRA.map((v) => (
              <ExtraField
                key={v} vendor={v} value={state.extra[v]} canManage={canManage}
                error={extraFieldError(errorField, stale, errorMessage)}
                onChange={(value: string) => setExtraField(v as keyof ProvisioningExtra, value)}
              />
            ))}
          </div>
        </div>
        <OtherFormError message={otherFieldError(errorMessage, stale, errorField, ['sip_server_host', 'allowed_networks', 'extra'])} />
        {canManage && <div><Button variant="primary" loading={updateM.isPending} onClick={submit}>{t('save')}</Button></div>}
      </div>
    </section>
  );
}

/** Provizioning sozlamalari (shartnoma §3-4) — til/vaqt zonasi/NTP/transport/server/ruxsat etilgan tarmoqlar/admin parol/vendor extra. */
export function SettingsTab({ canManage }: { canManage: boolean }) {
  const { data } = useProvisioningSettings();
  if (!data) return <p className="text-sm text-muted">…</p>;
  return <ProvisioningSettingsForm data={data} canManage={canManage} />;
}
