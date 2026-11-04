import { describe, expect, it } from 'vitest';
import { formatDateTime, formatTime, formatUptime, tenantDate, tenantDateTimeIso } from './time';

describe('time', () => {
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
});
