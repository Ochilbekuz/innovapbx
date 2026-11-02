import { describe, expect, it } from 'vitest';
import { applyRoute, canonicalPattern, describePattern, matchPattern, parsePattern } from './pattern';

describe('parsePattern', () => {
  it('oddiy mobil naqshni qabul qiladi va uzunligini hisoblaydi', () => {
    const r = parsePattern('998XXXXXXXXX');
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.minLength).toBe(12);
      expect(r.maxLength).toBe(12);
    }
  });

  it("boshidagi '_' va kichik harflarni qabul qiladi", () => {
    const r = parsePattern('_9nxx');
    expect(r.ok && r.normalized).toBe('9NXX');
  });

  it("'.' va '!' cheksiz uzunlik beradi, faqat oxirida", () => {
    const dot = parsePattern('00.');
    expect(dot.ok && dot.maxLength).toBe(null);
    expect(dot.ok && dot.minLength).toBe(3);
    const bang = parsePattern('8!');
    expect(bang.ok && bang.minLength).toBe(1);
    const mid = parsePattern('9.1');
    expect(mid.ok).toBe(false);
    if (!mid.ok) expect(mid.error).toMatchObject({ code: 'wildcard-not-last', at: 1 });
  });

  it('noto‘g‘ri belgining o‘rnini ko‘rsatadi', () => {
    const r = parsePattern('99A1');
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toMatchObject({ code: 'bad-char', at: 2 });
  });

  it('qavslar: yopilmagan, bo‘sh, teskari oraliq', () => {
    const open = parsePattern('9[1-3');
    expect(!open.ok && open.error.code).toBe('unclosed-class');
    const empty = parsePattern('9[]');
    expect(!empty.ok && empty.error.code).toBe('empty-class');
    const rev = parsePattern('[7-2]');
    expect(!rev.ok && rev.error.code).toBe('bad-range');
  });

  it("bo'sh naqsh — xato", () => {
    const r = parsePattern('  ');
    expect(!r.ok && r.error.code).toBe('empty');
  });
});

describe('canonicalPattern', () => {
  it("API'ga yuboriladigan shakl: '_' siz, katta harf, bo'shliqsiz", () => {
    expect(canonicalPattern(' _998xxxxxxxxx ')).toBe('998XXXXXXXXX');
    expect(canonicalPattern('8!')).toBe('8!');
  });

  it("yaroqsiz naqshni o'zgartirmaydi — xatoni server aniq ko'rsatadi", () => {
    expect(canonicalPattern(' 9.1 ')).toBe('9.1');
  });
});

describe('matchPattern', () => {
  it('X Z N va sinflar', () => {
    expect(matchPattern('998XXXXXXXXX', '998901234567')).toBe(true);
    expect(matchPattern('998XXXXXXXXX', '99890123456')).toBe(false);
    expect(matchPattern('NXX', '199')).toBe(false);
    expect(matchPattern('NXX', '299')).toBe(true);
    expect(matchPattern('Z0', '00')).toBe(false);
    expect(matchPattern('[15-7]X', '62')).toBe(true);
    expect(matchPattern('[15-7]X', '42')).toBe(false);
  });

  it("'.' kamida bitta, '!' nol yoki ko'p belgi", () => {
    expect(matchPattern('00.', '00')).toBe(false);
    expect(matchPattern('00.', '001')).toBe(true);
    expect(matchPattern('8!', '8')).toBe(true);
    expect(matchPattern('8!', '8123')).toBe(true);
  });

  it('yaroqsiz naqsh hech narsaga mos kelmaydi', () => {
    expect(matchPattern('9[', '91')).toBe(false);
  });
});

describe('applyRoute', () => {
  it('prefiksni kesadi, oldiga qo‘shadi', () => {
    expect(applyRoute({ prepend: '998', prefix: '8', pattern: 'XXXXXXXXX' }, '8901234567')).toEqual({
      matched: true,
      dialed: '998901234567',
    });
  });

  it('prefiks mos kelmasa — mos emas', () => {
    expect(applyRoute({ prepend: '', prefix: '0', pattern: 'X.' }, '9123')).toEqual({ matched: false });
  });
});

describe('describePattern', () => {
  const d = (s: string) => describePattern(parsePattern(s));
  it('belgilangan uzunlik va boshlanish', () => {
    expect(d('998XXXXXXXXX')).toEqual({ ok: true, minLength: 12, open: false, prefix: '998' });
  });
  it('prefikssiz naqsh', () => {
    expect(d('XXXXXXXXX')).toEqual({ ok: true, minLength: 9, open: false, prefix: '' });
  });
  it('wildcard — ochiq uzunlik', () => {
    expect(d('00[1-9].')).toEqual({ ok: true, minLength: 4, open: true, prefix: '00' });
  });
  it('faqat literal — hammasi prefiks', () => {
    expect(d('112')).toEqual({ ok: true, minLength: 3, open: false, prefix: '112' });
  });
  it('xato — xato kodi', () => {
    expect(d('9[2-7.')).toEqual({ ok: false, code: 'unclosed-class' });
  });
});
