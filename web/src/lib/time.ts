import i18n from './i18n';

/**
 * Vaqtni ko'rsatish — HAR DOIM tenant vaqt zonasida (brauzer zonasida emas).
 * API vaqtlari UTC (`...Z`); M0 da tenant bitta — Asia/Tashkent.
 */
export const TENANT_TZ = 'Asia/Tashkent';

const DEFAULT_LOCALE = 'uz-UZ';
const INTL_LOCALE: Record<string, string> = { uz: DEFAULT_LOCALE, ru: 'ru-RU', en: 'en-US' };

/** Joriy panel tiliga mos Intl locale — sana/vaqt formatlash shunga qarab o'zgaradi. */
function currentLocale(): string {
  return INTL_LOCALE[i18n.language] ?? DEFAULT_LOCALE;
}

const fmt = (opts: Intl.DateTimeFormatOptions) => (iso: string) =>
  new Date(iso).toLocaleString(currentLocale(), { timeZone: TENANT_TZ, ...opts });

export const formatDateTime = fmt({ day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
export const formatDateTimeShort = fmt({ day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' });
export const formatTime = fmt({ hour: '2-digit', minute: '2-digit' });

/** Vaqt zonasi siljishi shu lahzada: «UTC+5», «UTC+5:30», «UTC» (yozgi vaqt bo'lsa sanaga qarab to'g'ri chiqadi). */
export function tzOffsetLabel(iso: string, tz: string = TENANT_TZ): string {
  const name = new Intl.DateTimeFormat('en-US', { timeZone: tz, timeZoneName: 'shortOffset' })
    .formatToParts(new Date(iso))
    .find((p) => p.type === 'timeZoneName')?.value;
  // ICU nol siljishni «GMT» yoki «GMT+0» deb beradi — ikkalasi ham «UTC».
  return (name ?? 'GMT').replace(/^GMT(\+0$)?/, 'UTC');
}

/** Sana-only maydonlar uchun (bayram kuni, "YYYY-MM-DD") — vaqt zonasiz, chunki kalendar kuni, lahza emas. */
export const formatDateShort = (day: string) => new Date(`${day}T00:00:00Z`).toLocaleDateString(currentLocale(), { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'UTC' });

/** Audio uzunligi: 4200 (ms) → «0:04». Audio kutubxona/IVR salomlashuv tanlagichida ishlatiladi. */
export function formatDurationMs(ms: number): string {
  const s = Math.round(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

/** Qoʻngʻiroq davomiyligi, soniyada: 75 → «1:15». CDR va jonli qoʻngʻiroqlarda ishlatiladi. */
export function formatDurationSec(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

export type UptimeUnits = { d: string; h: string; m: string };

/** Asterisk ish vaqti: 90061 → «1 kun 1 soat», 300 → «5 daq». Birliklar — interfeys tilidan (`shell:uptimeUnits`). */
export function formatUptime(sec: number, u: UptimeUnits = { d: 'kun', h: 'soat', m: 'daq' }): string {
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (d > 0) return h > 0 ? `${d} ${u.d} ${h} ${u.h}` : `${d} ${u.d}`;
  if (h > 0) return `${h} ${u.h} ${m} ${u.m}`;
  return `${m} ${u.m}`;
}

/** Sana filtri input'lari uchun "YYYY-MM-DD" (mahalliy kalendar kuni). Qoʻngʻiroqlar/Audit filtrlarida ishlatiladi. */
export function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Tenant (Asia/Tashkent) kalendaridagi kun, "YYYY-MM-DD" — UTC'dagi `isoDate`dan farqli, 00:00–05:00 da ham to'g'ri. */
export function tenantDate(d: Date, daysBack = 0): string {
  return new Date(d.getTime() - daysBack * 86_400_000).toLocaleDateString('en-CA', { timeZone: TENANT_TZ });
}

/** Tenant vaqtidagi kun + "HH:MM" → UTC ISO. `endOfMinute` — oraliq oxiri (shu daqiqaning 59.999 s gacha).
 * Asia/Tashkent'da yozgi vaqt yo'q — doimiy +05:00. */
export function tenantDateTimeIso(day: string, hhmm: string, endOfMinute = false): string {
  const base = Date.parse(`${day}T${hhmm || '00:00'}:00+05:00`);
  return new Date(base + (endOfMinute ? 59_999 : 0)).toISOString();
}

/** Bugundan N kun oldingi sana, "YYYY-MM-DD". Filtr formalarining standart "dan" qiymati. */
export function daysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return isoDate(d);
}
