// Sof draft<->kontrakt aylanish funksiyalari — Firewall GUI (M12 B3, ../../replica/m12-contract.md §B3).
// React'siz — testlash va CRAP past ushlab turish uchun (`networkDraft.ts` bilan bir xil naqsh, dryer).
import { splitList } from '@/lib/validators';
import { FIREWALL_SERVICE_NAMES, MAX_TIMEOUT_S, MIN_TIMEOUT_S } from '@/domain/firewall';
import type { FirewallConfigIn, FirewallServiceIn, FirewallServiceName, FirewallStateOut } from '@/api/types';

export type FirewallServiceDraft = { name: FirewallServiceName; mode: 'all' | 'allowlist'; allowText: string };
export type FirewallDraft = { services: FirewallServiceDraft[]; blockedText: string };

export const TIMEOUT_OPTIONS = [60, 120, 300, 600] as const;
export const DEFAULT_TIMEOUT_S = 120;

/** `MIN_TIMEOUT_S..MAX_TIMEOUT_S` qarang `domain/firewall.ts` — shu yerda qayta ishlatiladi (dryer). */
export const FIREWALL_TIMEOUT_RANGE = { min: MIN_TIMEOUT_S, max: MAX_TIMEOUT_S };

/** Xizmatlar HAR DOIM shartnomadagi 4 nomda, shu tartibda yuboriladi — netd shuni talab qiladi. */
export function stateToDraft(state: FirewallStateOut): FirewallDraft {
  const services = FIREWALL_SERVICE_NAMES.map((name) => {
    const found = state.services.find((s) => s.name === name);
    const mode: 'all' | 'allowlist' = found?.mode === 'allowlist' ? 'allowlist' : 'all';
    return { name, mode, allowText: (found?.allow ?? []).join('\n') };
  });
  return { services, blockedText: state.blocked_cidrs.join('\n') };
}

function serviceDraftToConfig(s: FirewallServiceDraft): FirewallServiceIn {
  return { name: s.name, mode: s.mode, allow: s.mode === 'allowlist' ? splitList(s.allowText) : [] };
}

export function draftToConfig(draft: FirewallDraft, timeoutS: number): FirewallConfigIn {
  return {
    services: draft.services.map(serviceDraftToConfig),
    blocked_cidrs: splitList(draft.blockedText),
    timeout_s: timeoutS,
  };
}

export function updateServiceDraft(draft: FirewallDraft, name: string, patch: Partial<FirewallServiceDraft>): FirewallDraft {
  return { ...draft, services: draft.services.map((s) => (s.name === name ? { ...s, ...patch } : s)) };
}
