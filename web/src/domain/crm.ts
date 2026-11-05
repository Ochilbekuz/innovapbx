// Bitrix24 — sof mantiq: xususiy (ichki) host aniqlash (click-to-call ogohlantirishi) va
// "Bitrix'dan sinxronlash" natijasidan avto-moslashuv/hisobot qurish (M3b §5). `CrmTab.tsx` va
// `src/api/fake.ts` (mock backend) shu yerdan foydalanadi — qoida bitta joyda yashaydi (dryer).
import type { Bitrix24License, Bitrix24LicenseState, CrmSyncConflict, CrmSyncReport, CrmUnknownInnerEntry, CrmUser } from '@/api/types';

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

/**
 * OAuth «Ulash» maydoniga kiritilgan portal domenini broker kutgan shaklga keltiradi (shartnoma §1:
 * `https://`, yo'l, port, oxirgi `/` olib tashlanadi, kichik harf). Notoʻgʻri hostname — `null`.
 */
export function normalizeBitrixDomain(input: string): string | null {
  const trimmed = input.trim();
  if (!trimmed) return null;
  const withScheme = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
  let host: string;
  try {
    host = new URL(withScheme).hostname.toLowerCase();
  } catch {
    return null;
  }
  if (!/^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$/.test(host)) return null;
  return host;
}

function addDays(dateStr: string, days: number): string {
  const d = new Date(`${dateStr}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** Kun farqi (`b - a`), ikkisi ham `YYYY-MM-DD`. */
function diffDays(a: string, b: string): number {
  return Math.round((new Date(`${b}T00:00:00Z`).getTime() - new Date(`${a}T00:00:00Z`).getTime()) / 86_400_000);
}

export const BITRIX24_TARIFLAR: Bitrix24License['tariflar'] = [
  { kod: 'sinov', kun: 14 },
  { kod: '1oy', oy: 1 },
  { kod: '3oy', oy: 3 },
  { kod: '6oy', oy: 6 },
  { kod: '1yil', oy: 12 },
];

/**
 * Shartnoma §1 — `litsenziya` obyektini sanalardan hisoblaydi (Asia/Tashkent sanasi deb qaraladi,
 * barcha sanalar `YYYY-MM-DD`). Fake backend (`src/api/fake.ts`) va shu qoidaga tayanadigan
 * UI testlari shu funksiyadan foydalanadi — qoida bitta joyda (dryer).
 */
export function computeBitrix24License(params: { domain: string; sinov_boshlandi: string; tolov_tugash: string | null; blocked: boolean; today: string }): Bitrix24License {
  const sinov_tugash = addDays(params.sinov_boshlandi, 14);
  const tugash = params.tolov_tugash && params.tolov_tugash > sinov_tugash ? params.tolov_tugash : sinov_tugash;
  const graceEnd = addDays(tugash, 1);
  let holat: Bitrix24LicenseState;
  if (params.blocked) holat = 'bloklangan';
  else if (params.today <= tugash) holat = params.tolov_tugash && params.today <= params.tolov_tugash ? 'faol' : 'sinov';
  else if (params.today <= graceEnd) holat = 'imtiyoz';
  else holat = 'tugagan';
  const qolgan_kun = Math.max(diffDays(params.today, tugash), 0);
  return { holat, tugash, qolgan_kun, sinov_tugash, tolov_tugash: params.tolov_tugash, domain: params.domain, tariflar: BITRIX24_TARIFLAR };
}

/**
 * Litsenziya holatini i18n interpolyatsiya parametrlariga aylantiradi — `CrmTab`dagi qisqa
 * belgi (`integrations:crm.bitrix24.oauth.license.*`) va Litsenziya sahifasi (`license:card.state.*`)
 * bir xil holat-filiallarini ishlatadi, shu sabab bitta joyda (dryer). Sana formatlash chaqiruvchida
 * (`formatDateShort` — joriy tilga bog'liq, domain sof funksiyasi emas).
 */
export function bitrix24LicenseStateArgs(license: Bitrix24License): { state: Bitrix24LicenseState; days?: number; date?: string } {
  if (license.holat === 'sinov') return { state: 'sinov', days: license.qolgan_kun };
  if (license.holat === 'faol') return { state: 'faol', date: license.tugash ?? license.sinov_tugash };
  return { state: license.holat };
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
