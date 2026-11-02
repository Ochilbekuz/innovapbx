import { describe, expect, it } from 'vitest';
import { findDuplicateDigit, findIvrLoop, type IvrEdgeLookup, type IvrOption } from './ivr';

describe('findDuplicateDigit', () => {
  it("takrorlanish yo'q bo'lsa — null", () => {
    const options: IvrOption[] = [{ digit: '1', targetId: 'q1' }, { digit: '2', targetId: 'q2' }];
    expect(findDuplicateDigit(options)).toBeNull();
  });

  it('bir xil tugma ikki marta — takrorlangan raqamni qaytaradi', () => {
    const options: IvrOption[] = [
      { digit: '1', targetId: 'q1' },
      { digit: '2', targetId: 'q2' },
      { digit: '1', targetId: 'e101' },
    ];
    expect(findDuplicateDigit(options)).toBe('1');
  });

  it("bo'sh ro'yxat — null", () => {
    expect(findDuplicateDigit([])).toBeNull();
  });
});

describe('findIvrLoop', () => {
  it("timeout boshqa turga chiqsa — halqa yo'q", () => {
    const lookup: IvrEdgeLookup = (id) =>
      id === 'ivr1' ? { timeout: { kind: 'ring_group', id: 'rg1' }, invalid: null } : null;
    expect(findIvrLoop('ivr1', lookup)).toBeNull();
  });

  it('IVR o\'ziga timeout bilan qaytsa — halqa (shartnoma 4-stsenariy)', () => {
    const lookup: IvrEdgeLookup = (id) =>
      id === 'ivr1' ? { timeout: { kind: 'ivr', id: 'ivr1' }, invalid: null } : null;
    expect(findIvrLoop('ivr1', lookup)).toEqual({ edge: 'timeout', path: ['ivr1', 'ivr1'] });
  });

  it('IVR → IVR → birinchisiga (zanjir orqali) — halqa, yo\'l to\'liq', () => {
    const lookup: IvrEdgeLookup = (id) => {
      if (id === 'ivr1') return { timeout: { kind: 'ivr', id: 'ivr2' }, invalid: null };
      if (id === 'ivr2') return { timeout: { kind: 'ivr', id: 'ivr1' }, invalid: null };
      return null;
    };
    expect(findIvrLoop('ivr1', lookup)).toEqual({ edge: 'timeout', path: ['ivr1', 'ivr2', 'ivr1'] });
  });

  it('invalid yo\'lida chiqish bor — timeout halqa bo\'lsa ham invalid tekshiriladi mustaqil', () => {
    const lookup: IvrEdgeLookup = (id) =>
      id === 'ivr1' ? { timeout: { kind: 'ivr', id: 'ivr1' }, invalid: { kind: 'extension', id: 'e101' } } : null;
    expect(findIvrLoop('ivr1', lookup)).toEqual({ edge: 'timeout', path: ['ivr1', 'ivr1'] });
  });

  it("tugma orqali o'z-o'ziga qaytish bu funksiyada tekshirilmaydi (faqat timeout/invalid)", () => {
    const lookup: IvrEdgeLookup = () => ({ timeout: null, invalid: null });
    expect(findIvrLoop('ivr1', lookup)).toBeNull();
  });
});
