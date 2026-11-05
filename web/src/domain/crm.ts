// Bitrix24 — sof mantiq: xususiy (ichki) host aniqlash (click-to-call ogohlantirishi) va
// "Bitrix'dan sinxronlash" natijasidan avto-moslashuv/hisobot qurish (M3b §5). `CrmTab.tsx` va
// `src/api/fake.ts` (mock backend) shu yerdan foydalanadi — qoida bitta joyda yashaydi (dryer).
import type { CrmSyncConflict, CrmSyncReport, CrmUnknownInnerEntry, CrmUser } from '@/api/types';

const PRIVATE_HOST_PATTERNS: RegExp[] = [
  /^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/,
  /^172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}$/,
  /^192\.168\.\d{1,3}\.\d{1,3}$/,
  /^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$/,
  /^localhost$/i,
];

/** Hostname xususiy (ichki) tarmoqdami — Bitrix24 bulut portali bu manzilga tashqaridan yeta olmaydi. */
export function isPrivateHost(hostname: string): boolean {
  return PRIVATE_HOST_PATTERNS.some((re) => re.test(hostname));
}

function hostOf(url: string): string | null {
  try {
    return new URL(url).hostname;
  } catch {
    return null;
  }
}

/** Bitrix24 bulutdan click-to-call manziliga yeta olmasligi mumkinmi (portal bulutda + manzil xususiy). */
export function cloudCannotReachPrivateHost(portalCloud: boolean, hookUrl: string): boolean {
  if (!portalCloud) return false;
  const host = hostOf(hookUrl);
  return host !== null && isPrivateHost(host);
}

/** Vebhuk manzilidan portal hosti va u bulutda (*.bitrix24.*) ekanligini ajratadi — notoʻgʻri URL boʻlsa `null`. */
export function parseBitrixPortalHost(webhookUrl: string): { host: string; cloud: boolean } | null {
  const host = hostOf(webhookUrl);
  if (!host) return null;
  return { host, cloud: /\.bitrix24\.[a-z]+$/i.test(host) };
}

export type BitrixAutoMapEntry = { crm_user_id: string; crm_user_name: string };
export type BitrixSyncPlan = { report: Omit<CrmSyncReport, 'last_at'>; autoMap: Map<string, BitrixAutoMapEntry> };

/**
 * Bitrix portalidan olingan foydalanuvchilar (`UF_PHONE_INNER`) PBX ichki raqamlariga qanday mos kelishini
 * hisoblaydi: bitta-bittaga mos — avto-moslashuv; PBX'da yoʻq ichki raqam — `unknown_inner`; bir ichki
 * raqamda bir nechta foydalanuvchi — `conflicts` (hal qilinmaydi). Qoʻlda moslangan ichki raqamlar
 * (`manualExtensions`) avto-moslashuv bilan ustiga yozilmaydi.
 */
export function buildBitrixSyncPlan(portalUsers: CrmUser[], extensionNumbers: string[], manualExtensions: string[]): BitrixSyncPlan {
  const extSet = new Set(extensionNumbers);
  const manualSet = new Set(manualExtensions);
  const byPhone = new Map<string, CrmUser[]>();
  const unknown_inner: CrmUnknownInnerEntry[] = [];

  for (const user of portalUsers) {
    if (!user.inner_phone) continue;
    if (!extSet.has(user.inner_phone)) {
      unknown_inner.push({ user_id: user.id, user_name: user.name, inner_phone: user.inner_phone });
      continue;
    }
    byPhone.set(user.inner_phone, [...(byPhone.get(user.inner_phone) ?? []), user]);
  }

  const conflicts: CrmSyncConflict[] = [];
  const autoMap = new Map<string, BitrixAutoMapEntry>();
  let mapped = 0;
  for (const [phone, users] of byPhone) {
    if (users.length > 1) { conflicts.push({ inner_phone: phone, user_names: users.map((u) => u.name) }); continue; }
    mapped += 1;
    if (manualSet.has(phone)) continue;
    autoMap.set(phone, { crm_user_id: users[0]!.id, crm_user_name: users[0]!.name });
  }

  return { report: { users_total: portalUsers.length, mapped, unknown_inner, conflicts }, autoMap };
}
