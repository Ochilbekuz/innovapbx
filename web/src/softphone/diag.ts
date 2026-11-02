// M3a §4 — isbot (Playwright) uchun diagnostika. Faqat dev rejimida yoki `?diag=1` bilan ochiq.
import { useSoftphoneStore } from './store';
import type { SoftphoneDiagState, SoftphoneDiagStats } from './types';

declare global {
  interface Window {
    __innovaSoftphone?: {
      stats: () => Promise<SoftphoneDiagStats | null>;
      /** Mashina o'qiydigan holat (UI matni tilga bog'liq — isbot shu bilan tekshiradi). */
      state: () => SoftphoneDiagState;
    };
  }
}

export function diagState(): SoftphoneDiagState {
  const s = useSoftphoneStore.getState();
  return {
    connection: s.connection,
    errorReason: s.errorReason,
    phase: s.call?.phase ?? null,
    remoteNumber: s.call?.remoteNumber ?? null,
    muted: s.call?.muted ?? false,
  };
}

export function installSoftphoneDiagnostics(): void {
  const diagRequested = new URLSearchParams(location.search).get('diag') === '1';
  if (!import.meta.env.DEV && !diagRequested) return;
  window.__innovaSoftphone = {
    stats: () => useSoftphoneStore.getState().getStats(),
    state: diagState,
  };
}
