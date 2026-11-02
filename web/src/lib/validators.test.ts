import { describe, expect, it } from 'vitest';
import { isValidCidr, isValidHost, isValidIPv4, splitList } from './validators';

describe('isValidIPv4', () => {
  it("to'g'ri IPv4 manzillarni qabul qiladi", () => {
    expect(isValidIPv4('10.0.0.1')).toBe(true);
    expect(isValidIPv4('255.255.255.255')).toBe(true);
    expect(isValidIPv4('0.0.0.0')).toBe(true);
  });
  it("256 dan katta oktetni rad etadi", () => {
    expect(isValidIPv4('10.0.0.256')).toBe(false);
  });
  it("noto'g'ri formatni rad etadi", () => {
    expect(isValidIPv4('10.0.0')).toBe(false);
    expect(isValidIPv4('misol.uz')).toBe(false);
  });
});

describe('isValidCidr', () => {
  it("to'g'ri CIDR'ni qabul qiladi", () => {
    expect(isValidCidr('10.0.0.0/8')).toBe(true);
    expect(isValidCidr('192.168.1.0/24')).toBe(true);
    expect(isValidCidr('0.0.0.0/0')).toBe(true);
  });
  it("prefiks 32'dan katta bo'lsa rad etadi", () => {
    expect(isValidCidr('10.0.0.0/33')).toBe(false);
  });
  it("prefikssiz yoki yaroqsiz IP qismini rad etadi", () => {
    expect(isValidCidr('10.0.0.0')).toBe(false);
    expect(isValidCidr('10.0.0.256/8')).toBe(false);
  });
});

describe('isValidHost', () => {
  it('IPv4 va hostname ikkisini ham qabul qiladi', () => {
    expect(isValidHost('203.0.113.10')).toBe(true);
    expect(isValidHost('sip.uztelecom.uz')).toBe(true);
    expect(isValidHost('trunk-1')).toBe(true);
  });
  it("bo'sh joy yoki noto'g'ri belgili qatorni rad etadi", () => {
    expect(isValidHost('sip host.uz')).toBe(false);
    expect(isValidHost('')).toBe(false);
  });
});

describe('splitList', () => {
  it('vergul va qator bilan ajratilgan qiymatlarni ajratadi', () => {
    expect(splitList('10.0.0.0/8, 192.168.0.0/16\n172.16.0.0/12')).toEqual(['10.0.0.0/8', '192.168.0.0/16', '172.16.0.0/12']);
  });
  it("bo'sh qatorlarni va ortiqcha bo'shliqlarni olib tashlaydi", () => {
    expect(splitList(' 10.0.0.0/8 ,\n\n , 192.168.0.0/16')).toEqual(['10.0.0.0/8', '192.168.0.0/16']);
  });
  it("bo'sh satr uchun bo'sh ro'yxat qaytaradi", () => {
    expect(splitList('')).toEqual([]);
  });
});
