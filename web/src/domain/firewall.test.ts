import { describe, expect, it } from 'vitest';
import { buildFirewallDiff, checkFirewallSelfLockout, parseFirewallFieldPath, validateFirewallConfig } from './firewall';
import type { FirewallConfigIn, FirewallServiceIn } from '@/api/types';

function cfg(overrides: Partial<FirewallConfigIn> = {}): FirewallConfigIn {
  const services: FirewallServiceIn[] = [
    { name: 'ssh', mode: 'all', allow: [] },
    { name: 'web', mode: 'all', allow: [] },
    { name: 'sip', mode: 'all', allow: [] },
    { name: 'rtp', mode: 'all', allow: [] },
  ];
  return { services, blocked_cidrs: [], timeout_s: 120, ...overrides };
}

describe('firewall — validateFirewallConfig', () => {
  it("to'liq to'g'ri konfiguratsiya — xatosiz", () => {
    expect(validateFirewallConfig(cfg())).toEqual([]);
  });
  it("yetishmayotgan xizmat — 'services' xatosi", () => {
    const errors = validateFirewallConfig(cfg({ services: cfg().services.filter((s) => s.name !== 'rtp') }));
    expect(errors).toEqual([{ field: 'services', message: "Xizmat ko'rsatilmagan: rtp" }]);
  });
  it("noma'lum xizmat nomi — rad", () => {
    const services = cfg().services.map((s) => (s.name === 'rtp' ? { ...s, name: 'ftp' as never } : s));
    const errors = validateFirewallConfig(cfg({ services }));
    expect(errors).toContainEqual({ field: 'services[3].name', message: "Noma'lum xizmat: ftp" });
  });
  it('takroriy xizmat nomi — rad', () => {
    const services: FirewallServiceIn[] = [...cfg().services, { name: 'ssh', mode: 'all', allow: [] }];
    const errors = validateFirewallConfig(cfg({ services }));
    expect(errors).toContainEqual({ field: 'services[4].name', message: 'Xizmat takrorlangan: ssh' });
  });
  it("allowlist rejimida bo'sh ro'yxat — rad", () => {
    const services = cfg().services.map((s) => (s.name === 'ssh' ? { ...s, mode: 'allowlist' as const } : s));
    const errors = validateFirewallConfig(cfg({ services }));
    expect(errors).toContainEqual({ field: 'services[0].allow', message: "allowlist rejimida kamida bitta CIDR kerak" });
  });
  it('allowlist CIDR yaroqsiz — indeks bilan xato', () => {
    const services = cfg().services.map((s) => (s.name === 'ssh' ? { ...s, mode: 'allowlist' as const, allow: ['bad'] } : s));
    const errors = validateFirewallConfig(cfg({ services }));
    expect(errors).toContainEqual({ field: 'services[0].allow[0]', message: 'Yaroqsiz IPv4 CIDR: bad' });
  });
  it("0.0.0.0/0 ni bloklash — taqiqlangan", () => {
    const errors = validateFirewallConfig(cfg({ blocked_cidrs: ['0.0.0.0/0'] }));
    expect(errors).toContainEqual({ field: 'blocked_cidrs[0]', message: "0.0.0.0/0 ni bloklash taqiqlangan — butun tarmoqni uzadi" });
  });
  it('yaroqsiz bloklangan CIDR — indeks bilan xato', () => {
    const errors = validateFirewallConfig(cfg({ blocked_cidrs: ['nope'] }));
    expect(errors).toContainEqual({ field: 'blocked_cidrs[0]', message: 'Yaroqsiz IPv4 CIDR: nope' });
  });
  it('timeout_s diapazondan tashqari — rad', () => {
    expect(validateFirewallConfig(cfg({ timeout_s: 10 }))).toContainEqual(
      { field: 'timeout_s', message: "30..600 oralig'ida butun son bo'lishi kerak" },
    );
    expect(validateFirewallConfig(cfg({ timeout_s: 1000 }))).toContainEqual(
      { field: 'timeout_s', message: "30..600 oralig'ida butun son bo'lishi kerak" },
    );
  });
});

describe('firewall — checkFirewallSelfLockout', () => {
  it("admin IP allowlistda yo'q — rad (o'zini qulflash)", () => {
    const services = cfg().services.map((s) => (s.name === 'ssh' ? { ...s, mode: 'allowlist' as const, allow: ['10.0.0.0/24'] } : s));
    const errors: { field: string; message: string }[] = [];
    checkFirewallSelfLockout(cfg({ services }), '192.168.1.5', errors);
    expect(errors).toContainEqual({ field: 'services.ssh.allow', message: "Joriy admin IP (192.168.1.5) ssh ruxsat ro'yxatida emas — o'zini qulflash oldini olinadi" });
  });
  it('admin IP allowlistda bor — rozi', () => {
    const services = cfg().services.map((s) => (s.name === 'ssh' ? { ...s, mode: 'allowlist' as const, allow: ['192.168.1.0/24'] } : s));
    const errors: { field: string; message: string }[] = [];
    checkFirewallSelfLockout(cfg({ services }), '192.168.1.5', errors);
    expect(errors).toEqual([]);
  });
  it('admin IP bloklangan CIDRga tushadi — rad', () => {
    const errors: { field: string; message: string }[] = [];
    checkFirewallSelfLockout(cfg({ blocked_cidrs: ['192.168.1.0/24'] }), '192.168.1.5', errors);
    expect(errors).toContainEqual({ field: 'blocked_cidrs', message: "Joriy admin IP (192.168.1.5) bloklangan CIDR qatoriga tushadi — o'zini qulflash oldini olinadi" });
  });
  it("requestHost noma'lum/IPv6 — o'tkazib yuboriladi", () => {
    const errors: { field: string; message: string }[] = [];
    checkFirewallSelfLockout(cfg({ blocked_cidrs: ['0.0.0.0/0'] }), null, errors);
    checkFirewallSelfLockout(cfg({ blocked_cidrs: ['0.0.0.0/0'] }), '::1', errors);
    expect(errors).toEqual([]);
  });
});

describe('firewall — buildFirewallDiff', () => {
  it("rejim o'zgarsa — satr qo'shiladi", () => {
    const current = { services: cfg().services.map((s) => ({ name: s.name, mode: s.mode, allow: s.allow })), blocked_cidrs: [] };
    const next = cfg({ services: cfg().services.map((s) => (s.name === 'ssh' ? { ...s, mode: 'allowlist' as const, allow: ['10.0.0.0/24'] } : s)) });
    const diff = buildFirewallDiff(next, current);
    expect(diff).toContainEqual('ssh: hammaga ochiq → allowlist (10.0.0.0/24)');
  });
  it("bloklangan CIDR qo'shilsa/olib tashlansa — satrlar", () => {
    const current = { services: [], blocked_cidrs: ['1.2.3.0/24'] };
    const next = cfg({ services: [], blocked_cidrs: ['5.6.7.0/24'] });
    const diff = buildFirewallDiff(next, current);
    expect(diff).toContain('+ bloklangan 5.6.7.0/24');
    expect(diff).toContain('− bloklangan 1.2.3.0/24');
  });
  it("o'zgarish yo'q — bo'sh ro'yxat", () => {
    const state = { services: cfg().services, blocked_cidrs: [] };
    expect(buildFirewallDiff(cfg(), state)).toEqual([]);
  });
});

describe('firewall — parseFirewallFieldPath', () => {
  const services = cfg().services;
  it('services[idx].allow[...] — xizmat nomi bilan', () => {
    expect(parseFirewallFieldPath('services[0].allow[1]', services)).toEqual({ kind: 'service', name: 'ssh', sub: 'allow' });
  });
  it('services.<nom>.allow — xizmat nomi bilan', () => {
    expect(parseFirewallFieldPath('services.web.allow', services)).toEqual({ kind: 'service', name: 'web', sub: 'allow' });
  });
  it('blocked_cidrs[idx] — indeks bilan', () => {
    expect(parseFirewallFieldPath('blocked_cidrs[2]', services)).toEqual({ kind: 'blocked', index: 2 });
  });
  it('timeout_s — timeout', () => {
    expect(parseFirewallFieldPath('timeout_s', services)).toEqual({ kind: 'timeout' });
  });
  it('tanimadi — other', () => {
    expect(parseFirewallFieldPath('services', services)).toEqual({ kind: 'other' });
  });
});
