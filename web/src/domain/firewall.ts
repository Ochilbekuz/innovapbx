// Sof firewall validatsiya/diff mantiqi — M12 B3 (../../replica/m12-contract.md §B3). `src/api/fake.ts`
// (netd'ni simulyatsiya qiladi) va `src/screens/firewall/*` shu yerdan foydalanadi — qoida bitta joyda
// yashaydi (dryer). Maydon nomlari backend `app/netd/firewall.py::validate_firewall_config`/`check_self_lockout`
// bilan BIR XIL ("services[idx].allow[j]" / "blocked_cidrs[idx]" / "services.<nom>.allow").
import { isValidCidr, isValidIPv4 } from '@/lib/validators';
import type { FirewallConfigIn, FirewallFieldError, FirewallServiceIn, FirewallServiceOut } from '@/api/types';

export const FIREWALL_SERVICE_NAMES = ['ssh', 'web', 'sip', 'rtp'] as const;
const SELF_LOCKOUT_SERVICES = ['ssh', 'web'] as const;
const MAX_ALLOW_ENTRIES = 50;
const MAX_BLOCKED_ENTRIES = 100;
export const MIN_TIMEOUT_S = 30;
export const MAX_TIMEOUT_S = 600;

function ipInCidr(ip: string, cidr: string): boolean {
  if (!isValidIPv4(ip) || !isValidCidr(cidr)) return false;
  const [netAddr, prefixRaw] = cidr.split('/');
  const prefix = Number(prefixRaw);
  const toInt = (addr: string) => addr.split('.').reduce((acc, octet) => (acc << 8) + Number(octet), 0) >>> 0;
  const mask = prefix === 0 ? 0 : (0xffffffff << (32 - prefix)) >>> 0;
  return (toInt(ip) & mask) === (toInt(netAddr!) & mask);
}

function ipInAnyCidr(ip: string, cidrs: string[]): boolean {
  return cidrs.some((cidr) => ipInCidr(ip, cidr));
}

function validateService(idx: number, svc: FirewallServiceIn, seen: Set<string>, errors: FirewallFieldError[]): void {
  const prefix = `services[${idx}]`;
  if (!(FIREWALL_SERVICE_NAMES as readonly string[]).includes(svc.name)) {
    errors.push({ field: `${prefix}.name`, message: `Noma'lum xizmat: ${svc.name}` });
    return;
  }
  if (seen.has(svc.name)) { errors.push({ field: `${prefix}.name`, message: `Xizmat takrorlangan: ${svc.name}` }); return; }
  seen.add(svc.name);
  if (svc.mode !== 'all' && svc.mode !== 'allowlist') {
    errors.push({ field: `${prefix}.mode`, message: 'mode "all" yoki "allowlist" bo\'lishi kerak' });
    return;
  }
  if (svc.mode !== 'allowlist') return;
  if (svc.allow.length === 0) { errors.push({ field: `${prefix}.allow`, message: "allowlist rejimida kamida bitta CIDR kerak" }); return; }
  if (svc.allow.length > MAX_ALLOW_ENTRIES) { errors.push({ field: `${prefix}.allow`, message: `Ko'pi bilan ${MAX_ALLOW_ENTRIES} ta CIDR bo'lishi mumkin` }); return; }
  svc.allow.forEach((cidr, j) => {
    if (!isValidCidr(cidr)) errors.push({ field: `${prefix}.allow[${j}]`, message: `Yaroqsiz IPv4 CIDR: ${cidr}` });
  });
}

function validateBlockedCidrs(blocked: string[], errors: FirewallFieldError[]): void {
  if (blocked.length > MAX_BLOCKED_ENTRIES) {
    errors.push({ field: 'blocked_cidrs', message: `Ko'pi bilan ${MAX_BLOCKED_ENTRIES} ta bloklangan CIDR bo'lishi mumkin` });
    return;
  }
  blocked.forEach((cidr, idx) => {
    if (!isValidCidr(cidr)) errors.push({ field: `blocked_cidrs[${idx}]`, message: `Yaroqsiz IPv4 CIDR: ${cidr}` });
    else if (cidr === '0.0.0.0/0') errors.push({ field: `blocked_cidrs[${idx}]`, message: "0.0.0.0/0 ni bloklash taqiqlangan — butun tarmoqni uzadi" });
  });
}

/** To'liq mijoz-tomoni validatsiya — backend `validate_firewall_config` bilan bir xil qoidalar (serverga yuborishdan oldin tezkor fikr). */
export function validateFirewallConfig(config: FirewallConfigIn): FirewallFieldError[] {
  const errors: FirewallFieldError[] = [];
  const seen = new Set<string>();
  config.services.forEach((svc, idx) => validateService(idx, svc, seen, errors));
  FIREWALL_SERVICE_NAMES.filter((name) => !seen.has(name)).forEach((name) => {
    errors.push({ field: 'services', message: `Xizmat ko'rsatilmagan: ${name}` });
  });
  validateBlockedCidrs(config.blocked_cidrs, errors);
  if (!Number.isInteger(config.timeout_s) || config.timeout_s < MIN_TIMEOUT_S || config.timeout_s > MAX_TIMEOUT_S) {
    errors.push({ field: 'timeout_s', message: `${MIN_TIMEOUT_S}..${MAX_TIMEOUT_S} oralig'ida butun son bo'lishi kerak` });
  }
  return errors;
}

/** Joriy admin o'zini qulflab qolmasligi — backend `check_self_lockout` bilan bir xil (faqat IPv4 `requestHost`da tekshiradi). */
export function checkFirewallSelfLockout(config: FirewallConfigIn, requestHost: string | null, errors: FirewallFieldError[]): void {
  if (!requestHost || !isValidIPv4(requestHost)) return;
  for (const name of SELF_LOCKOUT_SERVICES) {
    const svc = config.services.find((s) => s.name === name);
    if (!svc || svc.mode !== 'allowlist') continue;
    if (ipInAnyCidr(requestHost, svc.allow)) continue;
    errors.push({ field: `services.${name}.allow`, message: `Joriy admin IP (${requestHost}) ${name} ruxsat ro'yxatida emas — o'zini qulflash oldini olinadi` });
  }
  if (ipInAnyCidr(requestHost, config.blocked_cidrs)) {
    errors.push({ field: 'blocked_cidrs', message: `Joriy admin IP (${requestHost}) bloklangan CIDR qatoriga tushadi — o'zini qulflash oldini olinadi` });
  }
}

/** Yuborilayotgan konfiguratsiya bilan joriy holat orasidagi inson-o'qiydigan farq roʻyxati (confirm modal + sticky bar). */
export function buildFirewallDiff(next: FirewallConfigIn, current: { services: FirewallServiceOut[]; blocked_cidrs: string[] }): string[] {
  const lines: string[] = [];
  const describe = (svc: { mode: string; allow: string[] }) => (svc.mode === 'allowlist' ? `allowlist (${svc.allow.join(', ') || '—'})` : 'hammaga ochiq');
  for (const svc of next.services) {
    const cur = current.services.find((c) => c.name === svc.name);
    if (!cur) continue;
    if (describe(cur) !== describe(svc)) lines.push(`${svc.name}: ${describe(cur)} → ${describe(svc)}`);
  }
  const curBlocked = new Set(current.blocked_cidrs);
  const nextBlocked = new Set(next.blocked_cidrs);
  next.blocked_cidrs.forEach((c) => { if (!curBlocked.has(c)) lines.push(`+ bloklangan ${c}`); });
  current.blocked_cidrs.forEach((c) => { if (!nextBlocked.has(c)) lines.push(`− bloklangan ${c}`); });
  return lines;
}

export type FirewallFieldPath =
  | { kind: 'service'; name: string; sub: 'allow' }
  | { kind: 'blocked'; index: number }
  | { kind: 'timeout' }
  | { kind: 'other' };

/** Server xato maydonini ("services[0].allow[1]" / "blocked_cidrs[2]" / "services.ssh.allow") UI tegishli inputga bog'lash uchun ajratadi. */
export function parseFirewallFieldPath(field: string, services: FirewallServiceIn[]): FirewallFieldPath {
  if (field === 'timeout_s') return { kind: 'timeout' };
  const byIndex = /^services\[(\d+)\]\.allow/.exec(field);
  if (byIndex) {
    const svc = services[Number(byIndex[1])];
    if (svc) return { kind: 'service', name: svc.name, sub: 'allow' };
  }
  const byName = /^services\.([^.]+)\.allow$/.exec(field);
  if (byName) return { kind: 'service', name: byName[1]!, sub: 'allow' };
  const blocked = /^blocked_cidrs\[(\d+)\]$/.exec(field);
  if (blocked) return { kind: 'blocked', index: Number(blocked[1]) };
  return { kind: 'other' };
}
