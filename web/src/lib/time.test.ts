import { describe, expect, it } from 'vitest';
import { formatDateTime, formatTime, formatUptime } from './time';

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
});
