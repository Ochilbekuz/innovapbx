import { describe, expect, it } from 'vitest';
import {
  defaultNtpServers, formatInZone, isValidTimezone, MAX_NTP_SERVERS, searchTimezones, utcOffsetLabel, validateTimeConfig,
} from './systemTime';

describe('systemTime — isValidTimezone', () => {
  it("to'g'ri IANA zona — rozi", () => {
    expect(isValidTimezone('Asia/Tashkent')).toBe(true);
    expect(isValidTimezone('Europe/London')).toBe(true);
  });
  it("yolg'on/bo'sh zona — rad", () => {
    expect(isValidTimezone('Mars/Phobos')).toBe(false);
    expect(isValidTimezone('')).toBe(false);
  });
});

describe('systemTime — validateTimeConfig', () => {
  const base = { timezone: 'Asia/Tashkent', ntp_servers: ['0.uz.pool.ntp.org'], ntp_enabled: true };

  it("to'g'ri konfiguratsiya — xatosiz", () => {
    expect(validateTimeConfig(base)).toEqual([]);
  });
  it("yaroqsiz vaqt zonasi — 'timezone' xatosi", () => {
    const errors = validateTimeConfig({ ...base, timezone: 'Nowhere/Here' });
    expect(errors).toEqual([{ field: 'timezone', message: "Vaqt zonasi IANA ro'yxatida topilmadi" }]);
  });
  it('NTP server soni limitdan oshsa — umumiy xato, har birini tekshirmaydi', () => {
    const many = Array.from({ length: MAX_NTP_SERVERS + 1 }, (_, i) => `ntp${i}.example.com`);
    const errors = validateTimeConfig({ ...base, ntp_servers: many });
    expect(errors).toEqual([{ field: 'ntp_servers', message: `Ko'pi bilan ${MAX_NTP_SERVERS} ta NTP server bo'lishi mumkin` }]);
  });
  it('yaroqsiz NTP server (IPv4 ham, hostname ham emas) — indeks bilan xato', () => {
    const errors = validateTimeConfig({ ...base, ntp_servers: ['not a host!!'] });
    expect(errors).toEqual([{ field: 'ntp_servers[0]', message: 'Yaroqsiz NTP server: not a host!!' }]);
  });
  it('IPv4 NTP server — yaroqli', () => {
    expect(validateTimeConfig({ ...base, ntp_servers: ['1.1.1.1'] })).toEqual([]);
  });
  it("bo'sh NTP ro'yxati — yaroqli (NTP o'chirilgan bo'lishi mumkin)", () => {
    expect(validateTimeConfig({ ...base, ntp_servers: [] })).toEqual([]);
  });
});

// Backend `app/netd/systemtime.py::default_ntp_servers` bilan bir xil — admin ro'yxati bo'sh bo'lsa shu serverlar ishlaydi.
describe('systemTime — defaultNtpServers (mintaqaviy pool)', () => {
  it('Osiyo zonasi — asia.pool.ntp.org', () => {
    expect(defaultNtpServers('Asia/Tashkent')).toEqual([
      '0.asia.pool.ntp.org', '1.asia.pool.ntp.org', '2.asia.pool.ntp.org', '3.asia.pool.ntp.org',
    ]);
  });
  it('Janubiy Amerika shahri — south-america, boshqasi — north-america', () => {
    expect(defaultNtpServers('America/Sao_Paulo')[0]).toBe('0.south-america.pool.ntp.org');
    expect(defaultNtpServers('America/Argentina/Buenos_Aires')[0]).toBe('0.south-america.pool.ntp.org');
    expect(defaultNtpServers('America/New_York')[0]).toBe('0.north-america.pool.ntp.org');
  });
  it('Pacific/Australia — oceania; Europe, Africa — o\'z nomi', () => {
    expect(defaultNtpServers('Pacific/Auckland')[0]).toBe('0.oceania.pool.ntp.org');
    expect(defaultNtpServers('Australia/Sydney')[0]).toBe('0.oceania.pool.ntp.org');
    expect(defaultNtpServers('Europe/Moscow')[0]).toBe('0.europe.pool.ntp.org');
    expect(defaultNtpServers('Africa/Cairo')[0]).toBe('0.africa.pool.ntp.org');
  });
  it('mintaqasiz zona (UTC, Etc/*, Atlantic/*) — global pool', () => {
    expect(defaultNtpServers('UTC')).toEqual(['0.pool.ntp.org', '1.pool.ntp.org', '2.pool.ntp.org', '3.pool.ntp.org']);
    expect(defaultNtpServers('Atlantic/Reykjavik')[0]).toBe('0.pool.ntp.org');
  });
});

describe('systemTime — utcOffsetLabel / formatInZone', () => {
  const at = new Date('2026-11-04T17:24:05Z');
  it('zona siljishi UTC±HH:MM koʻrinishida', () => {
    expect(utcOffsetLabel('Asia/Tashkent', at)).toBe('UTC+05:00');
    expect(utcOffsetLabel('America/New_York', at)).toBe('UTC-05:00');
    expect(utcOffsetLabel('Asia/Kolkata', at)).toBe('UTC+05:30');
    expect(utcOffsetLabel('UTC', at)).toBe('UTC+00:00');
  });
  it('vaqtni tanlangan zonada YYYY-MM-DD HH:MM:SS qilib chiqaradi', () => {
    expect(formatInZone(at, 'Asia/Tashkent')).toBe('2026-11-04 22:24:05');
    expect(formatInZone(at, 'UTC')).toBe('2026-11-04 17:24:05');
  });
});

describe('systemTime — searchTimezones', () => {
  const zones = ['Africa/Cairo', 'America/New_York', 'Asia/Almaty', 'Asia/Tashkent', 'Asia/Samarkand', 'Europe/Moscow', 'UTC'];
  const at = new Date('2026-11-04T17:24:05Z');
  it("bo'sh qidiruv — mashhur zonalar birinchi, keyin qolgani alifbo tartibida", () => {
    const names = searchTimezones(zones, '', at).map((o) => o.zone);
    expect(names).toEqual(['Asia/Tashkent', 'Asia/Samarkand', 'Europe/Moscow', 'Asia/Almaty', 'UTC', 'Africa/Cairo', 'America/New_York']);
  });
  it('har variantda siljish yorligʻi bor', () => {
    expect(searchTimezones(zones, 'tashkent', at)).toEqual([{ zone: 'Asia/Tashkent', offset: 'UTC+05:00' }]);
  });
  it('qidiruv katta-kichik harfga va bo\'shliq/pastki chiziqqa befarq', () => {
    expect(searchTimezones(zones, 'new york', at).map((o) => o.zone)).toEqual(['America/New_York']);
  });
  it('siljish boʻyicha ham topadi (mashhuri birinchi)', () => {
    const found = searchTimezones(zones, '+05:00', at);
    expect(found[0]?.zone).toBe('Asia/Tashkent');
    expect(found.map((o) => o.zone)).toContain('Asia/Samarkand');
    expect(found.every((o) => o.offset === 'UTC+05:00')).toBe(true);
  });
});
