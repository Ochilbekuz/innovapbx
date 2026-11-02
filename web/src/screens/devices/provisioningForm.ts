// `SettingsTab.tsx` dagi provizioning sozlamalari formasining holati/submit payload'i — sof
// funksiyalar va bitta hook'ga ajratilgan (qarang `formHelpers.ts` izohi).
import { useState } from 'react';
import type { ProvisioningExtra, ProvisioningSettings, SipTransport, UpdateProvisioningSettingsPayload } from '@/api/types';

export function networksToText(items: string[]): string { return items.join('\n'); }
export function textToNetworks(text: string): string[] { return text.split('\n').map((l) => l.trim()).filter(Boolean); }

export type ProvisioningFormState = {
  language: ProvisioningSettings['language'];
  timezone: string;
  ntpServer: string;
  sipTransport: SipTransport;
  sipServerHost: string;
  allowedNetworks: string;
  adminPassword: string;
  extra: ProvisioningExtra;
};

function provisioningFormState(data: ProvisioningSettings): ProvisioningFormState {
  return {
    language: data.language,
    timezone: data.timezone,
    ntpServer: data.ntp_server,
    sipTransport: data.sip_transport,
    sipServerHost: data.sip_server_host ?? '',
    allowedNetworks: networksToText(data.allowed_networks),
    adminPassword: '',
    extra: data.extra,
  };
}

export function provisioningPayload(state: ProvisioningFormState, updatedAt: string): UpdateProvisioningSettingsPayload {
  return {
    language: state.language,
    timezone: state.timezone.trim(),
    ntp_server: state.ntpServer.trim(),
    sip_transport: state.sipTransport,
    sip_server_host: state.sipServerHost.trim() || null,
    allowed_networks: textToNetworks(state.allowedNetworks),
    extra: state.extra,
    ...(state.adminPassword ? { admin_password: state.adminPassword } : {}),
    updated_at: updatedAt,
  };
}

export function adminPasswordHint(t: (key: string) => string, hasAdminPassword: boolean): string {
  return hasAdminPassword ? t('settings.adminPasswordSet') : t('settings.adminPasswordHint');
}

export function extraFieldError(errorField: string | undefined, stale: boolean, errorMessage: string | undefined): string | undefined {
  return errorField === 'extra' && !stale ? errorMessage : undefined;
}

/** Forma `data` ishga tushgandagi qiymatlardan boshlanadi; keyingi `data` yangilanishlari (masalan
 * saqlashdan keyingi yangi `updated_at`) formani qayta ishga tushirmaydi — faqat parol tozalanadi. */
export function useProvisioningForm(data: ProvisioningSettings) {
  const [state, setState] = useState<ProvisioningFormState>(() => provisioningFormState(data));
  const setLanguage = (v: ProvisioningSettings['language']) => setState((prev) => ({ ...prev, language: v }));
  const setTimezone = (v: string) => setState((prev) => ({ ...prev, timezone: v }));
  const setNtpServer = (v: string) => setState((prev) => ({ ...prev, ntpServer: v }));
  const setSipTransport = (v: SipTransport) => setState((prev) => ({ ...prev, sipTransport: v }));
  const setSipServerHost = (v: string) => setState((prev) => ({ ...prev, sipServerHost: v }));
  const setAllowedNetworks = (v: string) => setState((prev) => ({ ...prev, allowedNetworks: v }));
  const setAdminPassword = (v: string) => setState((prev) => ({ ...prev, adminPassword: v }));
  const setExtraField = (vendor: keyof ProvisioningExtra, v: string) => setState((prev) => ({ ...prev, extra: { ...prev.extra, [vendor]: v } }));
  const clearAdminPassword = () => setState((prev) => ({ ...prev, adminPassword: '' }));
  return {
    state, setLanguage, setTimezone, setNtpServer, setSipTransport, setSipServerHost,
    setAllowedNetworks, setAdminPassword, setExtraField, clearAdminPassword,
  };
}
