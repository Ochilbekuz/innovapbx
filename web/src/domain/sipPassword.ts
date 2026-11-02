// SIP parol siyosati — FreePBX-dek ichki raqam yaratish/parol almashtirish oqimi.
// BITTA sof funksiya: formada jonli xato koʻrsatish HAM, fake API 422 qaytarishi HAM shundan foydalanadi.
// Siyosat: 8-64 belgi, faqat [A-Za-z0-9!@#$%^*_+=.,:-], kamida 1 harf + 1 raqam, ichki raqamni oʻz ichiga olmasin.

export type SipPasswordIssue = 'too_short' | 'too_long' | 'bad_chars' | 'no_letter' | 'no_digit' | 'contains_number';

const CHARSET_RE = /^[A-Za-z0-9!@#$%^*_+=.,:-]+$/;
const MIN_LENGTH = 8;
const MAX_LENGTH = 64;

/** `null` — parol yaroqli; aks holda birinchi topilgan muammo kodi. */
export function validateSipPassword(password: string, extensionNumber: string): SipPasswordIssue | null {
  if (password.length < MIN_LENGTH) return 'too_short';
  if (password.length > MAX_LENGTH) return 'too_long';
  if (!CHARSET_RE.test(password)) return 'bad_chars';
  if (!/[A-Za-z]/.test(password)) return 'no_letter';
  if (!/[0-9]/.test(password)) return 'no_digit';
  const number = extensionNumber.trim();
  if (number && password.includes(number)) return 'contains_number';
  return null;
}

const GEN_LENGTH = 18;
const GEN_LETTERS = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz';
const GEN_DIGITS = '23456789';
const GEN_SYMBOLS = '!@#$%^*_+=.,:-';
const GEN_ALL = GEN_LETTERS + GEN_DIGITS + GEN_SYMBOLS;

function randomFrom(pool: string): string {
  const bytes = new Uint32Array(1);
  crypto.getRandomValues(bytes);
  return pool[bytes[0]! % pool.length]!;
}

function shuffled(chars: string[]): string[] {
  const bytes = new Uint32Array(chars.length);
  crypto.getRandomValues(bytes);
  return chars.map((c, i) => [c, bytes[i]!] as const).sort((a, b) => a[1] - b[1]).map(([c]) => c);
}

/**
 * Kuchli, siyosatga mos tasodifiy parol — bitta harf va bitta raqam qurilish orqali kafolatlanadi
 * (ehtimollikka tayanmaydi), `crypto.getRandomValues` orqali (UUID generatori emas — qarang `lib/browser.ts`).
 */
export function generateSipPassword(extensionNumber: string): string {
  const required = [randomFrom(GEN_LETTERS), randomFrom(GEN_DIGITS)];
  const rest = Array.from({ length: GEN_LENGTH - required.length }, () => randomFrom(GEN_ALL));
  const candidate = shuffled([...required, ...rest]).join('');
  // Ichki raqam tasodifan parol ichida chiqib qolishi juda kam ehtimol — chekka holatda bitta raqam qo'shib yetarli.
  const number = extensionNumber.trim();
  return number && candidate.includes(number) ? candidate + randomFrom(GEN_DIGITS) : candidate;
}
