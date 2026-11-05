import { afterEach, describe, expect, it } from 'vitest';
import { useSession } from '@/api/session';
import type { User } from '@/api/types';
import { formatDateTime, formatTime, formatUptime, tenantDate, tenantDateTimeIso, tzOffsetLabel } from './time';

const SOME_USER: User = { id: 'u1', login: 'admin', full_name: 'Admin', role: 'admin', permissions: ['*'], language: 'uz', timezone: 'Asia/Tashkent' };

describe('time', () => {
  it.each([
    ['Asia/Tashkent', 'UTC+5'],
    ['Asia/Kolkata', 'UTC+5:30'],
    ['America/New_York', 'UTC-4'],
    ['UTC', 'UTC'],
  ])('vaqt zonasi siljishi: %s → %s', (tz, label) => {
    expect(tzOffsetLabel('2026-10-27T13:19:31Z', tz)).toBe(label);
  });

  it('siljish sukut boʻyicha panel zonasida (Toshkent)', () => {
    expect(tzOffsetLabel('2026-10-27T13:19:31Z')).toBe('UTC+5');
  });

  it('UTC vaqtni brauzer zonasidan qat\'i nazar Toshkent vaqtida ko\'rsatadi', () => {
    expect(formatTime('2026-10-27T13:19:31Z')).toContain('18:19');
    expect(formatDateTime('2026-10-27T13:19:31Z')).toContain('18:19:31');
  });

  it('Toshkent yarim tunidan keyingi UTC kechqurunni ertangi sana deb ko\'rsatadi', () => {
    expect(formatDateTime('2026-10-27T19:30:00Z')).toContain('28');
  });

  it.each([
    [0, '0 daq'],
    [59, '0 daq'],
    [300, '5 daq'],
    [3600, '1 soat 0 daq'],
    [3660, '1 soat 1 daq'],
    [86400, '1 kun'],
    [90061, '1 kun 1 soat'],
  ])('formatUptime(%i) = %s', (sec, want) => {
    expect(formatUptime(sec)).toBe(want);
  });

  it('formatUptime — interfeys tili birliklari bilan', () => {
    expect(formatUptime(90061, { d: 'д', h: 'ч', m: 'мин' })).toBe('1 д 1 ч');
    expect(formatUptime(3660, { d: 'd', h: 'h', m: 'min' })).toBe('1 h 1 min');
  });

  it('tenantDate — Toshkent kalendari kuni (UTC 19:00 dan keyin ertangi kun)', () => {
    expect(tenantDate(new Date('2026-11-02T18:59:00Z'))).toBe('2026-11-02');
    expect(tenantDate(new Date('2026-11-02T19:00:00Z'))).toBe('2026-11-03');
    expect(tenantDate(new Date('2026-11-03T10:00:00Z'), 7)).toBe('2026-10-27');
  });

  it('tenantDateTimeIso — Toshkent sana+soat:daqiqa → UTC, oxiri daqiqa oxirigacha', () => {
    expect(tenantDateTimeIso('2026-11-03', '00:00')).toBe('2026-11-02T19:00:00.000Z');
    expect(tenantDateTimeIso('2026-11-03', '23:59', true)).toBe('2026-11-03T18:59:59.999Z');
    expect(tenantDateTimeIso('2026-11-03', '')).toBe('2026-11-02T19:00:00.000Z');
  });

  describe('yozgi vaqtli zona (DST) — har qanday zona uchun to\'g\'ri, doimiy +05:00 taxmin qilinmaydi', () => {
    it('tenantDateTimeIso — New York yozda (EDT, UTC-4) va qishda (EST, UTC-5) har xil siljish bilan hisoblaydi', () => {
      expect(tenantDateTimeIso('2026-07-01', '09:00', false, 'America/New_York')).toBe('2026-07-01T13:00:00.000Z');
      expect(tenantDateTimeIso('2026-01-15', '09:00', false, 'America/New_York')).toBe('2026-01-15T14:00:00.000Z');
    });

    it('tzOffsetLabel — New York yozda UTC-4, qishda UTC-5', () => {
      expect(tzOffsetLabel('2026-07-01T12:00:00Z', 'America/New_York')).toBe('UTC-4');
      expect(tzOffsetLabel('2026-01-15T12:00:00Z', 'America/New_York')).toBe('UTC-5');
    });
  });

  describe('tenantTz — sessiyadagi foydalanuvchi zonasidan dinamik o\'qiydi', () => {
    afterEach(() => useSession.setState({ user: null }));

    it('sessiyada boshqa zona bo\'lsa — shu zonada ko\'rsatadi (Toshkent qattiq yozilmagan)', () => {
      useSession.setState({ user: { ...SOME_USER, timezone: 'America/New_York' } });
      expect(formatTime('2026-01-15T14:00:00Z')).toContain('09:00');
    });

    it('sessiya hali yuklanmagan bo\'lsa — xavfsiz sukut (Asia/Tashkent)', () => {
      expect(formatTime('2026-10-27T13:19:31Z')).toContain('18:19');
    });
  });
});
