import { afterEach, describe, expect, it } from 'vitest';
import { EMPTY_ADVANCED_SEARCH } from './advancedSearch';
import { addSearchTemplate, loadSearchTemplates, removeSearchTemplate, saveSearchTemplates } from './searchTemplates';

afterEach(() => localStorage.clear());

describe('addSearchTemplate / removeSearchTemplate (sof funksiyalar)', () => {
  it('yangi shablonni roʻyxatga qoʻshadi, id generatsiya qiladi', () => {
    const next = addSearchTemplate([], 'VIP mijoz', { ...EMPTY_ADVANCED_SEARCH, src: '101' });
    expect(next).toHaveLength(1);
    expect(next[0]?.name).toBe('VIP mijoz');
    expect(next[0]?.form.src).toBe('101');
    expect(next[0]?.id).toBeTruthy();
  });

  it('bir xil nom bilan saqlasa — eskisini almashtiradi, nusxalanmaydi', () => {
    const first = addSearchTemplate([], 'Kunlik', { ...EMPTY_ADVANCED_SEARCH, src: '101' });
    const second = addSearchTemplate(first, 'Kunlik', { ...EMPTY_ADVANCED_SEARCH, src: '202' });
    expect(second).toHaveLength(1);
    expect(second[0]?.form.src).toBe('202');
  });

  it('removeSearchTemplate — faqat berilgan id ni olib tashlaydi', () => {
    const withTwo = [
      ...addSearchTemplate([], 'A', EMPTY_ADVANCED_SEARCH),
      ...addSearchTemplate([], 'B', EMPTY_ADVANCED_SEARCH),
    ];
    const removed = removeSearchTemplate(withTwo, withTwo[0]!.id);
    expect(removed).toHaveLength(1);
    expect(removed[0]?.name).toBe('B');
  });
});

describe('loadSearchTemplates / saveSearchTemplates (localStorage)', () => {
  it('hech narsa saqlanmagan boʻlsa — boʻsh roʻyxat', () => {
    expect(loadSearchTemplates()).toEqual([]);
  });

  it('saqlangan shablonlarni oʻqib qaytaradi', () => {
    const templates = addSearchTemplate([], 'Kunlik', { ...EMPTY_ADVANCED_SEARCH, src: '101' });
    saveSearchTemplates(templates);
    expect(loadSearchTemplates()).toEqual(templates);
  });

  it('buzilgan JSON — xato otmaydi, boʻsh roʻyxat', () => {
    localStorage.setItem('innova.cdr.searchTemplates', '{not json');
    expect(loadSearchTemplates()).toEqual([]);
  });

  it('notoʻgʻri shaklga ega elementlarni filtrlaydi', () => {
    localStorage.setItem('innova.cdr.searchTemplates', JSON.stringify([{ id: '1' }, { id: '2', name: 'X', form: EMPTY_ADVANCED_SEARCH }]));
    const loaded = loadSearchTemplates();
    expect(loaded).toHaveLength(1);
    expect(loaded[0]?.name).toBe('X');
  });
});
