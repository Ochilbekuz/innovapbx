import { describe, expect, it } from 'vitest';
import type { AdvancedSearchForm } from './advancedSearch';
import { buildAdvancedParams, countActiveFilters, EMPTY_ADVANCED_SEARCH } from './advancedSearch';

describe('buildAdvancedParams', () => {
  it('boʻsh forma — boʻsh parametr (hech narsa yuborilmaydi)', () => {
    expect(buildAdvancedParams(EMPTY_ADVANCED_SEARCH)).toEqual({});
  });

  it('sukut rejim (contains) yuborilmaydi, boshqa rejim yuboriladi', () => {
    expect(buildAdvancedParams({ ...EMPTY_ADVANCED_SEARCH, src: '101', srcMode: 'contains' })).toEqual({ src: '101' });
    expect(buildAdvancedParams({ ...EMPTY_ADVANCED_SEARCH, src: '101', srcMode: 'begins' })).toEqual({ src: '101', src_mode: 'begins' });
  });

  it('inkor (_not) faqat true boʻlsa qoʻshiladi', () => {
    expect(buildAdvancedParams({ ...EMPTY_ADVANCED_SEARCH, dst: '202', dstNot: true })).toEqual({ dst: '202', dst_not: true });
    expect(buildAdvancedParams({ ...EMPTY_ADVANCED_SEARCH, dst: '202', dstNot: false })).toEqual({ dst: '202' });
  });

  it('qiymat boʻlmasa rejim/inkor ham yuborilmaydi', () => {
    expect(buildAdvancedParams({ ...EMPTY_ADVANCED_SEARCH, srcMode: 'exact', srcNot: true })).toEqual({});
  });

  it('boʻsh joylar olib tashlanadi (trim)', () => {
    expect(buildAdvancedParams({ ...EMPTY_ADVANCED_SEARCH, trunk: '  ', name: '   ' })).toEqual({});
    expect(buildAdvancedParams({ ...EMPTY_ADVANCED_SEARCH, trunk: '  Beeline  ' })).toEqual({ trunk: 'Beeline' });
  });

  it('disposition — tanlanganlar vergul bilan birlashtiriladi', () => {
    const form: AdvancedSearchForm = { ...EMPTY_ADVANCED_SEARCH, disposition: ['answered', 'busy'] };
    expect(buildAdvancedParams(form)).toEqual({ disposition: 'answered,busy' });
  });

  it('davomiylik — faqat butun, manfiy boʻlmagan son qabul qilinadi', () => {
    expect(buildAdvancedParams({ ...EMPTY_ADVANCED_SEARCH, minDuration: '30', maxDuration: '90' })).toEqual({ min_duration: 30, max_duration: 90 });
    expect(buildAdvancedParams({ ...EMPTY_ADVANCED_SEARCH, minDuration: 'abc' })).toEqual({});
    expect(buildAdvancedParams({ ...EMPTY_ADVANCED_SEARCH, minDuration: '-5' })).toEqual({});
    expect(buildAdvancedParams({ ...EMPTY_ADVANCED_SEARCH, minDuration: '1.5' })).toEqual({});
  });

  it('recording — sukut (any) yuborilmaydi, boshqasi yuboriladi', () => {
    expect(buildAdvancedParams({ ...EMPTY_ADVANCED_SEARCH, recording: 'any' })).toEqual({});
    expect(buildAdvancedParams({ ...EMPTY_ADVANCED_SEARCH, recording: 'with' })).toEqual({ recording: 'with' });
  });

  it('bir nechta maydon birga — hammasi mavjud', () => {
    const form = { ...EMPTY_ADVANCED_SEARCH, src: '998901234567', srcMode: 'exact' as const, name: 'Anvar', ext: '101' };
    expect(buildAdvancedParams(form)).toEqual({ src: '998901234567', src_mode: 'exact', name: 'Anvar', ext: '101' });
  });
});

describe('countActiveFilters', () => {
  it('boʻsh forma — 0', () => {
    expect(countActiveFilters(EMPTY_ADVANCED_SEARCH)).toBe(0);
  });

  it('har mustaqil filtr guruhi bittadan hisoblanadi', () => {
    const form: AdvancedSearchForm = { ...EMPTY_ADVANCED_SEARCH, src: '101', dst: '202', disposition: ['answered', 'busy'], recording: 'with' };
    expect(countActiveFilters(form)).toBe(4);
  });

  it('rejim/inkor alohida hisoblanmaydi — bitta maydon baribir 1', () => {
    expect(countActiveFilters({ ...EMPTY_ADVANCED_SEARCH, src: '101', srcMode: 'exact', srcNot: true })).toBe(1);
  });
});
