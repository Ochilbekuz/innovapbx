import { describe, expect, it } from 'vitest';
import i18n from '@/lib/i18n';
import { parsePattern, describePattern } from '@/domain/pattern';
import { dayLabels, patternText } from './domainText';

const tFor = (lng: string) => i18n.getFixedT(lng);
const text = (lng: string, pattern: string) => patternText(describePattern(parsePattern(pattern)), tFor(lng));

describe('patternText — domen tavsifini tanlangan tilda matnga aylantiradi', () => {
  it('uz: belgilangan uzunlik va prefiks', () => {
    expect(text('uz', '998XXXXXXXXX')).toBe('12 xonali raqam, «998» bilan boshlanadi');
  });
  it('uz: ochiq uzunlik, prefikssiz', () => {
    expect(text('uz', 'X.')).toBe('2 va undan koʻp belgili raqam');
  });
  it('ru va en: o\'sha naqsh boshqa tilda', () => {
    expect(text('ru', '998XXXXXXXXX')).toBe('12-значный номер, начинается с «998»');
    expect(text('en', 'XXXXXXXXX')).toBe('9-digit number');
  });
  it('har bir xato kodi uchun tarjima bor (kalit nomi emas)', () => {
    for (const bad of ['', '9a', '9[2-7', '9[]', '9[7-2]', '9.X']) {
      const desc = describePattern(parsePattern(bad));
      expect(desc.ok, bad).toBe(false);
      for (const lng of ['uz', 'ru', 'en']) expect(patternText(desc, tFor(lng))).not.toMatch(/^common:|pattern\.error/);
    }
  });
  it('ru: xato matni', () => {
    expect(text('ru', '9[2-7')).toBe('«[» открыта, но не закрыта «]».');
  });
});

describe('dayLabels — hafta dushanbadan, 7 kun', () => {
  it('uz qisqa va toʻliq', () => {
    expect(dayLabels(tFor('uz'), 'short')).toEqual(['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya']);
    expect(dayLabels(tFor('uz'), 'long')[6]).toBe('Yakshanba');
  });
  it('ru va en qisqa', () => {
    expect(dayLabels(tFor('ru'), 'short')).toEqual(['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']);
    expect(dayLabels(tFor('en'), 'long')[0]).toBe('Monday');
  });
});
