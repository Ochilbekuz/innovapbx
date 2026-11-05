import { describe, expect, it } from 'vitest';
import {
  buildSshLoginCommand, buildWebAddress, buildWebConfirmUrl, isReservedPort, ROOT_LOGIN_FIX_COMMAND, sshLoginAdvice, sshLoginUser, sshNeedsAttention, showRootLoginNote, validateSshApply, validateWebApply,
} from './access';
import type { AccessSshApplyIn, AccessSshOut, AccessWebApplyIn } from '@/api/types';

function sshIn(overrides: Partial<AccessSshApplyIn> = {}): AccessSshApplyIn {
  return { port: 2222, ...overrides };
}
function webIn(overrides: Partial<AccessWebApplyIn> = {}): AccessWebApplyIn {
  return { http_port: 8080, https_port: 8443, ...overrides };
}

describe('access — isReservedPort', () => {
  it.each([5060, 5061, 5038, 8088, 5432, 8710, 8711, 8712, 10000, 15000, 20000])(
    '%d — band (band xizmatlar/diapazon)',
    (port) => expect(isReservedPort(port)).toBe(true),
  );
  it.each([22, 80, 443, 2222, 9999, 20001])('%d — band emas', (port) => expect(isReservedPort(port)).toBe(false));
});

describe('access — validateSshApply', () => {
  it("to'g'ri port — xatosiz", () => {
    expect(validateSshApply(sshIn())).toEqual([]);
  });
  it('diapazondan tashqari port — rad', () => {
    expect(validateSshApply(sshIn({ port: 0 }))).toContainEqual({ field: 'port', message: "1..65535 oralig'ida butun son bo'lishi kerak" });
    expect(validateSshApply(sshIn({ port: 65536 }))).toContainEqual({ field: 'port', message: "1..65535 oralig'ida butun son bo'lishi kerak" });
  });
  it('butun son emas — rad', () => {
    expect(validateSshApply(sshIn({ port: 22.5 }))).toContainEqual({ field: 'port', message: "1..65535 oralig'ida butun son bo'lishi kerak" });
  });
  it('band port — rad', () => {
    expect(validateSshApply(sshIn({ port: 5060 }))).toContainEqual({ field: 'port', message: 'Bu port boshqa xizmat uchun band: 5060' });
  });
  it('timeout_s diapazondan tashqari — rad', () => {
    expect(validateSshApply(sshIn({ timeout_s: 10 }))).toContainEqual({ field: 'timeout_s', message: "30..600 oralig'ida butun son bo'lishi kerak" });
  });
});

describe('access — validateWebApply', () => {
  it("to'g'ri portlar — xatosiz", () => {
    expect(validateWebApply(webIn())).toEqual([]);
  });
  it('http_port band — rad', () => {
    expect(validateWebApply(webIn({ http_port: 5432 }))).toContainEqual({ field: 'http_port', message: 'Bu port boshqa xizmat uchun band: 5432' });
  });
  it('https_port diapazondan tashqari — rad', () => {
    expect(validateWebApply(webIn({ https_port: 70000 }))).toContainEqual({ field: 'https_port', message: "1..65535 oralig'ida butun son bo'lishi kerak" });
  });
  it('http_port va https_port bir xil — rad', () => {
    expect(validateWebApply(webIn({ http_port: 8080, https_port: 8080 }))).toContainEqual({
      field: 'https_port',
      message: "HTTP va HTTPS port bir xil bo'lmasligi kerak",
    });
  });
});

function sshOut(overrides: Partial<AccessSshOut> = {}): AccessSshOut {
  return {
    port: 22, active: true, listening_ports: [22], password_auth: true,
    root_login: 'prohibit-password', login_users: ['innova'], host_firewall: 'innova', ...overrides,
  };
}

describe('access — buildSshLoginCommand', () => {
  it("login buyrug'ini to'g'ri quradi", () => {
    expect(buildSshLoginCommand(2222, 'innova', 'pbx1.example.com')).toBe('ssh -p 2222 innova@pbx1.example.com');
  });
});

describe('access — showRootLoginNote', () => {
  it.each(['no', 'prohibit-password'] as const)('%s uchun eslatma koʻrsatiladi', (v) => expect(showRootLoginNote(v)).toBe(true));
  it.each(['yes', 'without-password', 'forced-commands-only', null] as const)('%s uchun eslatma koʻrsatilmaydi', (v) => expect(showRootLoginNote(v)).toBe(false));
});

describe('access — sshLoginUser / sshLoginAdvice', () => {
  it('oddiy foydalanuvchi bor (ISO: innova) — u bilan kiriladi, «sudo -i» eslatmasi', () => {
    expect(sshLoginUser(sshOut())).toBe('innova');
    expect(sshLoginAdvice(sshOut())).toBe('sudo');
  });
  it('Proxmox LXC shabloni: foydalanuvchi yoʻq, root faqat kalit bilan — hech kim parol bilan kira olmaydi', () => {
    const lxc = sshOut({ login_users: [] });
    expect(sshLoginUser(lxc)).toBe('root');
    expect(sshLoginAdvice(lxc)).toBe('no-login');
  });
  it.each(['no', 'without-password', null] as const)('foydalanuvchisiz, root_login=%s — ham kirib boʻlmaydi', (v) => {
    expect(sshLoginAdvice(sshOut({ login_users: [], root_login: v }))).toBe('no-login');
  });
  it('foydalanuvchisiz, lekin root parol bilan kira oladi — eslatma kerak emas', () => {
    expect(sshLoginAdvice(sshOut({ login_users: [], root_login: 'yes' }))).toBeNull();
  });
  it('tuzatish buyrugʻi drop-in orqali root kirishini yoqadi va sshd ni qayta ishga tushiradi', () => {
    expect(ROOT_LOGIN_FIX_COMMAND).toContain('PermitRootLogin yes');
    expect(ROOT_LOGIN_FIX_COMMAND).toContain('/etc/ssh/sshd_config.d/');
    expect(ROOT_LOGIN_FIX_COMMAND).toContain('systemctl restart ssh');
  });
});

describe('access — sshNeedsAttention', () => {
  it("ishlab turgan, portda tinglayotgan bo'lsa — ogohlantirish yoʻq", () => {
    expect(sshNeedsAttention(sshOut())).toBe(false);
  });
  it('active=false boʻlsa — ogohlantirish', () => {
    expect(sshNeedsAttention(sshOut({ active: false }))).toBe(true);
  });
  it('port listening_ports ichida boʻlmasa — ogohlantirish', () => {
    expect(sshNeedsAttention(sshOut({ port: 2222, listening_ports: [22] }))).toBe(true);
  });
});

describe('access — buildWebAddress', () => {
  it('https, nostandart port — porti koʻrsatiladi', () => {
    expect(buildWebAddress({ protocol: 'https:', hostname: 'pbx1', httpPort: 80, httpsPort: 8443 })).toBe('https://pbx1:8443');
  });
  it('http, standart 80 — port yashirin', () => {
    expect(buildWebAddress({ protocol: 'http:', hostname: 'pbx1', httpPort: 80, httpsPort: 443 })).toBe('http://pbx1');
  });
});

describe('access — buildWebConfirmUrl', () => {
  it('http, nostandart port — porti koʻrsatiladi', () => {
    expect(buildWebConfirmUrl({ protocol: 'http:', hostname: 'pbx1', httpPort: 8080, httpsPort: 8443, pendingId: 'p1' }))
      .toBe('http://pbx1:8080/access-confirm#p1');
  });
  it('https, standart 443 — port yashirin', () => {
    expect(buildWebConfirmUrl({ protocol: 'https:', hostname: 'pbx1', httpPort: 80, httpsPort: 443, pendingId: 'p1' }))
      .toBe('https://pbx1/access-confirm#p1');
  });
  it('http, standart 80 — port yashirin', () => {
    expect(buildWebConfirmUrl({ protocol: 'http:', hostname: 'pbx1', httpPort: 80, httpsPort: 443, pendingId: 'p1' }))
      .toBe('http://pbx1/access-confirm#p1');
  });
});
