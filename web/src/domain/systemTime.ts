// Sof sana/vaqt validatsiya mantiqi — M12 B1 (../../replica/m12-contract.md §B1). `src/api/fake.ts` va
// `src/screens/time/*` shu yerdan foydalanadi (dryer). Qoidalar backend `app/netd/systemtime.py::validate_time_config`
// bilan bir xil: IANA vaqt zonasi (`Intl.supportedValuesOf('timeZone')` ↔ `zoneinfo.available_timezones()`),
// NTP server — IPv4 yoki RFC1123 mezbon nomi (`lib/validators.ts`dagi BIR XIL tekshiruv).
import { isValidHost } from '@/lib/validators';
import type { TimeConfigIn, TimeFieldError } from '@/api/types';

export const MAX_NTP_SERVERS = 5;

let cachedZones: Set<string> | null = null;

/** `Intl.supportedValuesOf` eski brauzerda yo'q bo'lishi mumkin — shu holda tekshiruv serverga qoldiriladi (bo'sh ro'yxat emas, cheklov yo'q). */
function availableTimezones(): Set<string> | null {
  if (cachedZones) return cachedZones;
  const supported = (Intl as unknown as { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf;
  if (!supported) return null;
  cachedZones = new Set(supported('timeZone'));
  return cachedZones;
}

export function isValidTimezone(value: string): boolean {
  const zones = availableTimezones();
  return zones ? zones.has(value) : value.trim().length > 0;
}

function isValidNtpServer(value: string): boolean {
  return isValidHost(value);
}

/** To'liq mijoz-tomoni validatsiya (M12 §B1). Backend yana bir bor tekshiradi — bu faqat tezkor fikr uchun. */
export function validateTimeConfig(config: TimeConfigIn): TimeFieldError[] {
  const errors: TimeFieldError[] = [];
  if (!isValidTimezone(config.timezone)) errors.push({ field: 'timezone', message: "Vaqt zonasi IANA ro'yxatida topilmadi" });
  if (config.ntp_servers.length > MAX_NTP_SERVERS) {
    errors.push({ field: 'ntp_servers', message: `Ko'pi bilan ${MAX_NTP_SERVERS} ta NTP server bo'lishi mumkin` });
  } else {
    config.ntp_servers.forEach((server, idx) => {
      if (!isValidNtpServer(server)) errors.push({ field: `ntp_servers[${idx}]`, message: `Yaroqsiz NTP server: ${server}` });
    });
  }
  return errors;
}

export function listTimezones(): string[] {
  return availableTimezones() ? Array.from(availableTimezones()!).sort() : [];
}

// ─────────────── Mintaqaviy NTP pool — backend `app/netd/systemtime.py::default_ntp_servers` aynan nusxasi ───────────────
// Admin ro'yxati bo'sh bo'lsa server shu serverlardan vaqt oladi (`FallbackNTP=`). Sahifa qoralama zonaga ko'ra ko'rsatadi.

const POOL_ZONE_BY_REGION: Record<string, string> = {
  Asia: 'asia', Europe: 'europe', Africa: 'africa', Australia: 'oceania', Pacific: 'oceania', America: 'north-america',
};
const SOUTH_AMERICA = new Set([
  'Argentina', 'Asuncion', 'Bogota', 'Caracas', 'Cayenne', 'Guayaquil', 'La_Paz', 'Lima',
  'Montevideo', 'Paramaribo', 'Punta_Arenas', 'Santiago', 'Sao_Paulo', 'Recife', 'Fortaleza',
  'Belem', 'Manaus', 'Cuiaba', 'Campo_Grande', 'Porto_Velho', 'Boa_Vista', 'Rio_Branco',
  'Maceio', 'Araguaina', 'Bahia', 'Santarem', 'Noronha', 'Eirunepe',
]);
const POOL_SIZE = 4;

function poolZone(tz: string): string | undefined {
  const [region = '', city = ''] = tz.split('/', 2);
  if (region === 'America' && SOUTH_AMERICA.has(city)) return 'south-america';
  return POOL_ZONE_BY_REGION[region];
}

export function defaultNtpServers(tz: string): string[] {
  const zone = poolZone(tz);
  const suffix = zone ? `${zone}.pool.ntp.org` : 'pool.ntp.org';
  return Array.from({ length: POOL_SIZE }, (_, i) => `${i}.${suffix}`);
}

// ─────────────── Zona ko'rinishi: siljish yorlig'i, zonadagi vaqt, qidiruv ───────────────

/** "UTC+05:00". `longOffset` UTC uchun ba'zan faqat "GMT" qaytaradi. */
export function utcOffsetLabel(tz: string, at: Date): string {
  const part = new Intl.DateTimeFormat('en-US', { timeZone: tz, timeZoneName: 'longOffset' })
    .formatToParts(at)
    .find((p) => p.type === 'timeZoneName')?.value ?? 'GMT';
  const offset = part.replace('GMT', '');
  return `UTC${offset || '+00:00'}`;
}

/** "2026-11-04 22:24:05" — `sv-SE` ISO ko'rinishidagi sana beradi. */
export function formatInZone(at: Date, tz: string): string {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: tz, dateStyle: 'short', timeStyle: 'medium' }).format(at);
}

/** O'zbekiston va qo'shnilari — ro'yxat boshida. */
export const POPULAR_TIMEZONES = ['Asia/Tashkent', 'Asia/Samarkand', 'Europe/Moscow', 'Asia/Almaty', 'Asia/Dubai', 'Europe/Istanbul', 'UTC'];

export type TimezoneOption = { zone: string; offset: string };

function popularRank(zone: string): number {
  const i = POPULAR_TIMEZONES.indexOf(zone);
  return i < 0 ? POPULAR_TIMEZONES.length : i;
}

function normalize(text: string): string {
  return text.toLowerCase().replace(/_/g, ' ');
}

export function searchTimezones(zones: string[], query: string, at: Date): TimezoneOption[] {
  const q = normalize(query.trim());
  return zones
    .map((zone) => ({ zone, offset: utcOffsetLabel(zone, at) }))
    .filter((o) => !q || normalize(o.zone).includes(q) || o.offset.toLowerCase().includes(q))
    .sort((a, b) => popularRank(a.zone) - popularRank(b.zone) || a.zone.localeCompare(b.zone));
}
