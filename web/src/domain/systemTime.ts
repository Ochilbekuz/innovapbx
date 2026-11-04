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
