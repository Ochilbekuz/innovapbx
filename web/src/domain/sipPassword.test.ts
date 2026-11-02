import { describe, expect, it } from 'vitest';
import { generateSipPassword, validateSipPassword } from './sipPassword';

describe('validateSipPassword', () => {
  it('kamida 8 belgi talab qiladi', () => {
    expect(validateSipPassword('Ab1', '100')).toBe('too_short');
    expect(validateSipPassword('Abcdefg1', '100')).toBeNull();
  });

  it("64 belgidan uzun bo'lsa rad etadi", () => {
    expect(validateSipPassword(`A1${'a'.repeat(63)}`, '100')).toBe('too_long');
  });

  it('ruxsat etilmagan belgilarni rad etadi', () => {
    expect(validateSipPassword('Abcdef1 2', '100')).toBe('bad_chars');
    expect(validateSipPassword('Abcdef1<2', '100')).toBe('bad_chars');
  });

  it('ruxsat etilgan maxsus belgilarni qabul qiladi', () => {
    expect(validateSipPassword('Ab1!@#$%^*_+=.,:-', '100')).toBeNull();
  });

  it('kamida bitta harf talab qiladi', () => {
    expect(validateSipPassword('12345678', '100')).toBe('no_letter');
    expect(validateSipPassword('1234567!', '100')).toBe('no_letter');
  });

  it('kamida bitta raqam talab qiladi', () => {
    expect(validateSipPassword('abcdefgh', '100')).toBe('no_digit');
  });

  it("ichki raqam parol ichida bo'lishiga ruxsat bermaydi", () => {
    expect(validateSipPassword('secret100pass', '100')).toBe('contains_number');
    expect(validateSipPassword('secret999pass', '100')).toBeNull();
  });

  it("ichki raqam bo'sh bo'lsa (hali tayinlanmagan) tekshirmaydi", () => {
    expect(validateSipPassword('secretpass1', '')).toBeNull();
  });
});

describe('generateSipPassword', () => {
  it('siyosatga mos, ichki raqamni o\'z ichiga olmaydigan kuchli parol yaratadi', () => {
    for (let i = 0; i < 50; i++) {
      const password = generateSipPassword('100');
      expect(validateSipPassword(password, '100')).toBeNull();
      expect(password.length).toBeGreaterThanOrEqual(16);
    }
  });

  it('ichki raqam bo\'sh bo\'lganda ham yaroqli parol beradi', () => {
    const password = generateSipPassword('');
    expect(validateSipPassword(password, '')).toBeNull();
  });

  it('har chaqiruvda boshqa parol beradi', () => {
    const a = generateSipPassword('100');
    const b = generateSipPassword('100');
    expect(a).not.toBe(b);
  });
});
