// M3a §4 (S16) — qarang ../../../replica/m3a-contract.md §4. Softfon holatlari bu yerda — UI va
// store ikkisi ham shulardan foydalanadi, parallel enum ikki marta yozilmasin (DRY).

/** Ulanish holati — raqam/ro'yxatga olish darajasida. */
export type ConnectionState = 'unavailable' | 'other_tab' | 'connecting' | 'registered' | 'error';

/** Qo'ng'iroq bosqichi — `null` bo'lsa chaqiruv yo'q. */
export type CallPhase = 'incoming' | 'outgoing' | 'talking' | 'hold';

export type CallDirection = 'in' | 'out';

export type ActiveCall = {
  direction: CallDirection;
  phase: CallPhase;
  remoteNumber: string;
  remoteName?: string;
  /** `talking` boshlangan `Date.now()` — taymer hisobi shundan. `hold`da to'xtamaydi (umumiy davomiylik). */
  startedAt: number | null;
  muted: boolean;
};

export type SoftphoneDiagStats = {
  packetsSent: number;
  packetsReceived: number;
  codec: string | null;
  /** Mikrofon treki yoqilganmi (mute isboti: false bo'lsa — jim). */
  micEnabled: boolean;
  /** Kiruvchi audio `totalAudioEnergy` yig'indisi — qarshi tomon mute bo'lsa o'smaydi. */
  audioEnergy: number;
};

/** `window.__innovaSoftphone.state()` (diag) — isbot uchun tilga bog'liq bo'lmagan holat. */
export type SoftphoneDiagState = {
  connection: ConnectionState;
  errorReason: string | null;
  phase: CallPhase | null;
  remoteNumber: string | null;
  muted: boolean;
};
