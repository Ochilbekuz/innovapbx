// M10 B2 — TOTP (RFC 6238): SHA1, 30s qadam, 6 raqam, ±1 qadam tolerantlik.
// Fake klient (demo/vitest) uchun — haqiqiy backend shu algoritmni serverda qaytaradi, bu yerda faqat
// UI/test oqimlari mustaqil ishlashi uchun (masalan 2FA yoqishda darhol to'g'ri kod hosil qilish).

const BASE32_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
const STEP_SECONDS = 30;
const DIGITS = 6;

/** 20 baytlik tasodifiy sirni base32'ga o'giradi (RFC 4648, padding'siz). */
export function generateTotpSecret(randomBytes: Uint8Array = cryptoRandomBytes(20)): string {
  let bits = '';
  for (const b of randomBytes) bits += b.toString(2).padStart(8, '0');
  let out = '';
  for (let i = 0; i + 5 <= bits.length; i += 5) out += BASE32_ALPHABET[parseInt(bits.slice(i, i + 5), 2)];
  return out;
}

function cryptoRandomBytes(n: number): Uint8Array {
  const arr = new Uint8Array(n);
  globalThis.crypto.getRandomValues(arr);
  return arr;
}

function base32Decode(secret: string): Uint8Array {
  const clean = secret.replace(/=+$/, '').toUpperCase();
  let bits = '';
  for (const ch of clean) {
    const idx = BASE32_ALPHABET.indexOf(ch);
    if (idx < 0) continue;
    bits += idx.toString(2).padStart(5, '0');
  }
  const bytes: number[] = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2));
  return new Uint8Array(bytes);
}

async function hmacSha1(keyBytes: Uint8Array, msgBytes: Uint8Array): Promise<Uint8Array> {
  // TS 7 — `Uint8Array<ArrayBufferLike>` `BufferSource`ga mos kelmaydi (SharedArrayBuffer ehtimoli tufayli);
  // runtime xatti-harakati o'zgarmaydi, faqat toza ArrayBuffer-qolipga aylantiramiz.
  const key = await globalThis.crypto.subtle.importKey('raw', keyBytes as BufferSource, { name: 'HMAC', hash: 'SHA-1' }, false, ['sign']);
  const sig = await globalThis.crypto.subtle.sign('HMAC', key, msgBytes as BufferSource);
  return new Uint8Array(sig);
}

function stepToCounterBytes(step: number): Uint8Array {
  const buf = new ArrayBuffer(8);
  const view = new DataView(buf);
  // 32-bitgacha yetadi, yuqori 32 bit doim 0 (amaliyotda yetarli: 2^32 qadam ≈ 4 ming yil).
  view.setUint32(4, step, false);
  return new Uint8Array(buf);
}

/** Berilgan vaqt qadami (epoch sekund / 30) uchun 6 xonali TOTP kodni hisoblaydi. */
export async function totpAt(secret: string, step: number): Promise<string> {
  const key = base32Decode(secret);
  const hmac = await hmacSha1(key, stepToCounterBytes(step));
  const offset = hmac[hmac.length - 1]! & 0x0f;
  const code = ((hmac[offset]! & 0x7f) << 24) | ((hmac[offset + 1]! & 0xff) << 16) | ((hmac[offset + 2]! & 0xff) << 8) | (hmac[offset + 3]! & 0xff);
  return String(code % 10 ** DIGITS).padStart(DIGITS, '0');
}

export function stepOf(epochSeconds: number): number {
  return Math.floor(epochSeconds / STEP_SECONDS);
}

export async function currentTotpCode(secret: string, nowMs: number = Date.now()): Promise<string> {
  return totpAt(secret, stepOf(nowMs / 1000));
}

/**
 * Kodni ±1 qadam tolerantlik bilan tekshiradi; qayta ishlatishdan himoya uchun `lastStep`dan
 * KATTA bo'lgan qadamni qaytaradi (muvaffaqiyatsiz bo'lsa — null).
 */
export async function verifyTotp(secret: string, code: string, nowMs: number = Date.now(), lastStep: number | null = null): Promise<number | null> {
  const centerStep = stepOf(nowMs / 1000);
  for (const delta of [0, -1, 1]) {
    const step = centerStep + delta;
    if (lastStep !== null && step <= lastStep) continue;
    if ((await totpAt(secret, step)) === code) return step;
  }
  return null;
}

export function otpauthUri(secret: string, tenantLabel: string, username: string): string {
  const label = encodeURIComponent(`Innova PBX:${tenantLabel}:${username}`);
  return `otpauth://totp/${label}?secret=${secret}&issuer=${encodeURIComponent('Innova PBX')}&digits=${DIGITS}&period=${STEP_SECONDS}`;
}

/** 10 ta tiklash kodi `xxxx-xxxx` formatida (demo/fake uchun — haqiqiy backend o'zi hash'laydi). */
export function generateRecoveryCodes(count = 10): string[] {
  const out: string[] = [];
  for (let i = 0; i < count; i += 1) {
    const bytes = cryptoRandomBytes(5);
    const hex = Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('');
    out.push(`${hex.slice(0, 4)}-${hex.slice(4, 8)}`);
  }
  return out;
}
