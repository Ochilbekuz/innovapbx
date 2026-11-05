import { describe, expect, it } from 'vitest';
import { buildPingPresets, isValidPingHost } from './ping';

describe('isValidPingHost', () => {
  it.each(['1.1.1.1', 'google.com', 'sip.uztelecom.uz', 'localhost', '2001:db8::1', ' 8.8.8.8 '])('qabul qiladi: %s', (h) => {
    expect(isValidPingHost(h)).toBe(true);
  });

  it.each(['', '   ', '-oProxy', 'a b', '$(id)', 'a;b', 'fe80::1%eth0', 'a..b', '.a', 'x'.repeat(64), 'a_b.com'])(
    'rad etadi: %s',
    (h) => {
      expect(isValidPingHost(h)).toBe(false);
    },
  );
});

describe('buildPingPresets', () => {
  it('shlyuz, SIP trunk hostlari (takrorsiz), internet va DNS — shu tartibda', () => {
    const presets = buildPingPresets('192.168.10.1', [
      { name: 'Uztelecom', host: 'sip.uztelecom.uz' },
      { name: 'Zaxira', host: 'sip.uztelecom.uz' },
      { name: 'Beeline', host: '10.0.0.7' },
    ]);
    expect(presets.map((p) => [p.kind, p.host])).toEqual([
      ['gateway', '192.168.10.1'],
      ['sip', 'sip.uztelecom.uz'],
      ['sip', '10.0.0.7'],
      ['internet', '1.1.1.1'],
      ['internet', '8.8.8.8'],
      ['dns', 'google.com'],
    ]);
    expect(presets[1]?.name).toBe('Uztelecom');
  });

  it('shlyuz yoʻq va yaroqsiz trunk host — tashlab yuboriladi', () => {
    const presets = buildPingPresets(null, [{ name: 'Yomon', host: 'a b' }]);
    expect(presets.map((p) => p.kind)).toEqual(['internet', 'internet', 'dns']);
  });
});
