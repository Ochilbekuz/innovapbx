// M3a §4 — softfon holat mashinasi. Engine (SIP.js) bilan bog'lanish, `navigator.locks` orqali bitta
// tabda ishlash, ticket eskirishi/uzilishda eksponensial (1→30 s) qayta ulanish shu yerda.
import { create } from 'zustand';
import { apiClient } from '@/api';
import { isApiError } from '@/api/errors';
import { createSoftphoneEngine, type SoftphoneEngine } from './engine';
import { startRingtone } from './ring';
import type { ActiveCall, ConnectionState, SoftphoneDiagStats } from './types';

const LOCK_NAME = 'innova-softphone-tab';
const MIN_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30000;
/** §5.8: admin raqamda webrtc'ni o'chirsa — chip ≤ 60 s ichida yo'qolsin (WS o'zi yopilmaydi). */
export const STATUS_POLL_MS = 30000;
const UNAVAILABLE_CODES = new Set(['no_extension', 'webrtc_disabled', 'extension_disabled']);

type State = {
  connection: ConnectionState;
  errorReason: string | null;
  micDenied: boolean;
  call: ActiveCall | null;
  panelOpen: boolean;
};

type Actions = {
  init: () => void;
  teardown: () => Promise<void>;
  openPanel: () => void;
  closePanel: () => void;
  togglePanel: () => void;
  startCall: (number: string) => void;
  answer: () => void;
  reject: () => void;
  hangup: () => void;
  toggleMute: () => void;
  toggleHold: () => void;
  sendDigit: (digit: string) => void;
  transfer: (number: string) => void;
  attachAudio: (el: HTMLAudioElement | null) => void;
  getStats: () => Promise<SoftphoneDiagStats | null>;
};

// Reaktiv bo'lmagan ("ref") holat — modul darajasida, qayta render qo'zg'atmaydi.
let engine: SoftphoneEngine | null = null;
let releaseLock: (() => void) | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let statusTimer: ReturnType<typeof setInterval> | null = null;
let backoffMs = MIN_BACKOFF_MS;
let ring: { stop: () => void } | null = null;
let audioEl: HTMLAudioElement | null = null;
let initStarted = false;
let shouldStayConnected = false;

function stopRing(): void {
  ring?.stop();
  ring = null;
}

function releaseLockNow(): void {
  releaseLock?.();
  releaseLock = null;
}

/** `navigator.locks` yo'q bo'lsa (eski brauzer/jsdom) — bitta-tab qoidasini tekshirmasdan davom etamiz. */
function acquireLock(): Promise<boolean> {
  if (releaseLock) return Promise.resolve(true);
  const locks = navigator.locks;
  if (!locks?.request) return Promise.resolve(true);
  return new Promise((resolve) => {
    locks
      .request(LOCK_NAME, { ifAvailable: true }, (lock) => {
        if (!lock) {
          resolve(false);
          return Promise.resolve();
        }
        return new Promise<void>((keepHeld) => {
          releaseLock = () => keepHeld();
          resolve(true);
        });
      })
      .catch(() => resolve(false));
  });
}

function stopTimers(): void {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  if (statusTimer) clearInterval(statusTimer);
  reconnectTimer = null;
  statusTimer = null;
}

export const useSoftphoneStore = create<State & Actions>((set, get) => {
  function ensureEngine(): SoftphoneEngine {
    if (engine) return engine;
    engine = createSoftphoneEngine({
      onRegistered: () => {
        backoffMs = MIN_BACKOFF_MS;
        set({ connection: 'registered', errorReason: null });
      },
      onUnregistered: () => undefined,
      onRegistrationFailed: (reason) => {
        set({ connection: 'error', errorReason: reason });
        scheduleReconnect();
      },
      onDisconnected: () => {
        if (!shouldStayConnected) return;
        set({ connection: 'connecting' });
        scheduleReconnect();
      },
      onIncoming: (info) => {
        stopRing();
        ring = startRingtone();
        set({
          call: { direction: 'in', phase: 'incoming', remoteNumber: info.remoteNumber, remoteName: info.remoteName, startedAt: null, muted: false },
          panelOpen: true,
        });
      },
      onOutgoingProgress: () => {
        set((s) => (s.call ? { call: { ...s.call, phase: 'outgoing' } } : {}));
      },
      onEstablished: () => {
        stopRing();
        engine?.attachRemoteAudio(audioEl);
        set((s) => ({
          call: s.call
            ? { ...s.call, phase: 'talking', startedAt: s.call.startedAt ?? Date.now() }
            : { direction: 'out', phase: 'talking', remoteNumber: '', startedAt: Date.now(), muted: false },
        }));
      },
      onEnded: () => {
        stopRing();
        set({ call: null });
      },
      onFailed: (reason) => {
        stopRing();
        const micDenied = /notallowed|permission/i.test(reason);
        set({ call: null, micDenied, errorReason: micDenied ? null : reason });
      },
    });
    return engine;
  }

  function scheduleReconnect(): void {
    if (!shouldStayConnected || reconnectTimer) return;
    const delay = backoffMs;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      void connectFlow();
    }, delay);
    backoffMs = Math.min(backoffMs * 2, MAX_BACKOFF_MS);
  }

  // Ticket faqat WS OCHILISHIDA tekshiriladi (nginx auth_request) — ochiq ulanishni uning muddati
  // tugaganda qayta ulash SHART EMAS (avvalgi variant har ~9.5 daqiqada qayta ulanib, faol
  // qo'ng'iroqni uzardi). Uzilishda `connectFlow` baribir yangi ticket oladi. Bu yerda faqat
  // raqam holati kuzatiladi: webrtc o'chirilsa/raqam o'chsa — ulanish yopiladi.
  async function checkStatus(): Promise<void> {
    if (!shouldStayConnected || get().connection !== 'registered') return;
    try {
      await apiClient.meSoftphoneStatus();
    } catch (e) {
      if (isApiError(e) && UNAVAILABLE_CODES.has(e.code)) await goUnavailable();
    }
  }

  function startStatusWatch(): void {
    if (statusTimer) clearInterval(statusTimer);
    statusTimer = setInterval(() => void checkStatus(), STATUS_POLL_MS);
  }

  async function goUnavailable(): Promise<void> {
    shouldStayConnected = false;
    initStarted = false;
    stopTimers();
    stopRing();
    const e = engine;
    engine = null;
    if (e) await e.disconnect().catch(() => undefined);
    releaseLockNow();
    set({ connection: 'unavailable', call: null, panelOpen: false, errorReason: null });
  }

  async function connectFlow(): Promise<void> {
    if (!shouldStayConnected) return;
    set({ connection: 'connecting', errorReason: null });
    const gotLock = await acquireLock();
    if (!gotLock) {
      set({ connection: 'other_tab' });
      return;
    }
    try {
      const info = await apiClient.meSoftphone();
      await ensureEngine().connect(info);
      startStatusWatch();
    } catch (e) {
      releaseLockNow();
      if (isApiError(e) && UNAVAILABLE_CODES.has(e.code)) {
        set({ connection: 'unavailable' });
      } else {
        set({ connection: 'error', errorReason: isApiError(e) ? e.code : 'network' });
        scheduleReconnect();
      }
    }
  }

  return {
    connection: 'unavailable',
    errorReason: null,
    micDenied: false,
    call: null,
    panelOpen: false,

    init: () => {
      if (initStarted) return;
      initStarted = true;
      shouldStayConnected = true;
      void connectFlow();
    },

    teardown: async () => {
      await goUnavailable();
      backoffMs = MIN_BACKOFF_MS;
      set({ micDenied: false });
    },

    openPanel: () => set({ panelOpen: true }),
    closePanel: () => set({ panelOpen: false }),
    togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),

    startCall: (number) => {
      const num = number.trim();
      if (!num || get().connection !== 'registered' || get().call) return;
      set({ call: { direction: 'out', phase: 'outgoing', remoteNumber: num, startedAt: null, muted: false }, panelOpen: true });
      ensureEngine().call(num);
    },

    answer: () => {
      if (get().call?.phase !== 'incoming') return;
      ensureEngine().answer();
    },

    reject: () => {
      stopRing();
      ensureEngine().reject();
      set({ call: null });
    },

    hangup: () => {
      stopRing();
      ensureEngine().hangup();
      set({ call: null });
    },

    toggleMute: () => {
      const call = get().call;
      if (!call) return;
      const muted = !call.muted;
      ensureEngine().mute(muted);
      set({ call: { ...call, muted } });
    },

    toggleHold: () => {
      const call = get().call;
      if (!call || (call.phase !== 'talking' && call.phase !== 'hold')) return;
      const held = call.phase !== 'hold';
      ensureEngine().hold(held);
      set({ call: { ...call, phase: held ? 'hold' : 'talking' } });
    },

    sendDigit: (digit) => {
      const phase = get().call?.phase;
      if (phase === 'talking' || phase === 'hold') ensureEngine().sendDtmf(digit);
    },

    transfer: (number) => {
      const num = number.trim();
      if (!num || !get().call) return;
      ensureEngine().transfer(num);
    },

    attachAudio: (el) => {
      audioEl = el;
      engine?.attachRemoteAudio(el);
    },

    getStats: () => (engine ? engine.getStats() : Promise.resolve(null)),
  };
});
