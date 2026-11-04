import { describe, expect, it } from 'vitest';
import { isValidTimezone, MAX_NTP_SERVERS, validateTimeConfig } from './systemTime';

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
