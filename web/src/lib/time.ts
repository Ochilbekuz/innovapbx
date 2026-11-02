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

/** Asterisk ish vaqti: 90061 → «1 kun 1 soat», 300 → «5 daq». */
export function formatUptime(sec: number): string {
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (d > 0) return h > 0 ? `${d} kun ${h} soat` : `${d} kun`;
  if (h > 0) return `${h} soat ${m} daq`;
  return `${m} daq`;
}

/** Sana filtri input'lari uchun "YYYY-MM-DD" (mahalliy kalendar kuni). Qoʻngʻiroqlar/Audit filtrlarida ishlatiladi. */
export function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Bugundan N kun oldingi sana, "YYYY-MM-DD". Filtr formalarining standart "dan" qiymati. */
export function daysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return isoDate(d);
}
