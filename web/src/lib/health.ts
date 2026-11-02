// Sogʻlik darajasi qoidalari — Dashboard (S03) va Tizim holati (S36) ikkisi ham shu yerdan foydalanadi (DRY).
import type { TrunkHealthState } from '@/api/types';
import type { HealthLevel } from '@/ui/Health';

/** Disk toʻlganlik darajasi: 85% — ogohlantirish, 95% — kritik (Dashboard va Status sahifasida bir xil qoida). */
export function diskLevel(usedPct: number): HealthLevel {
  return usedPct >= 95 ? 'crit' : usedPct >= 85 ? 'warn' : 'ok';
}

/** Trankning `state` maydonidan sogʻlik darajasi: `ok` — ok, `unreachable` — kritik, qolgani (`unknown`/`disabled`) — ogohlantirish. */
export function trunkHealthLevel(state: TrunkHealthState): HealthLevel {
  return state === 'ok' ? 'ok' : state === 'unreachable' ? 'crit' : 'warn';
}
