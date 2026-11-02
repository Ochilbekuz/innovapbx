// M5b — Follow Me raqamlari uchun sof yordamchilar (qarang ../../replica/m5b-contract.md §1).
// UI (darhol ko'rsatish) va fake API (backend `services/follow_me.py` nusxasi) ikkalasi shundan foydalanadi.
import { FOLLOW_ME_MAX_NUMBERS, FOLLOW_ME_RING_MAX, FOLLOW_ME_RING_MIN, type FollowMe } from '@/api/types';

const NUMBER_RE = /^[0-9]{2,15}$/;
/** Backend `EXTERNAL_MIN_DIGITS`: 5+ raqam — tashqi, qisqasi — ichki raqam bo'lishi shart. */
const EXTERNAL_MIN_DIGITS = 5;

export type NumberProblem = 'invalid' | 'self' | 'duplicate' | 'full';

export function defaultFollowMe(): FollowMe {
  return { enabled: false, numbers: [], strategy: 'ring_all', include_extension: true, ring_seconds: 20, confirm: true };
}

/** `+998 (90) 123-45-67` → `998901234567` (backend `normalize_number` kabi). */
export function cleanNumber(raw: string): string {
  return raw.trim().replace(/[\s().-]/g, '').replace(/^\+/, '');
}

export function isExternalNumber(number: string): boolean {
  return number.length >= EXTERNAL_MIN_DIGITS;
}

/** Ro'yxatga qo'shishdan oldingi tekshiruv; `null` — qo'shsa bo'ladi. */
export function numberProblem(number: string, own: string, current: readonly string[]): NumberProblem | null {
  if (!NUMBER_RE.test(number)) return 'invalid';
  if (number === own) return 'self';
  if (current.includes(number)) return 'duplicate';
  return current.length >= FOLLOW_ME_MAX_NUMBERS ? 'full' : null;
}

/** Butun soniya, backend chegarasi ichida (5..120). */
export function isRingSecondsValid(seconds: number): boolean {
  return Number.isInteger(seconds) && seconds >= FOLLOW_ME_RING_MIN && seconds <= FOLLOW_ME_RING_MAX;
}

/** Ro'yxat elementini bir pog'ona siljitadi (`delta` = -1 yuqoriga, +1 pastga); chegaradan chiqsa o'zgarishsiz. */
export function moveItem<T>(items: readonly T[], index: number, delta: -1 | 1): T[] {
  const to = index + delta;
  if (to < 0 || to >= items.length) return [...items];
  const next = [...items];
  next.splice(to, 0, ...next.splice(index, 1));
  return next;
}

export function sameFollowMe(a: FollowMe, b: FollowMe): boolean {
  return a.enabled === b.enabled && a.strategy === b.strategy && a.include_extension === b.include_extension
    && a.ring_seconds === b.ring_seconds && a.confirm === b.confirm
    && a.numbers.length === b.numbers.length && a.numbers.every((n, i) => n === b.numbers[i]);
}
