import { describe, expect, it, vi } from 'vitest';
import { closeOnOpenChange, fieldError, itemsOrEmpty, otherFieldError } from './formHelpers';

describe('fieldError', () => {
  it('xato shu maydonga tegishli bo\'lsa — xabarni qaytaradi', () => {
    expect(fieldError('mac', 'mac', 'band')).toBe('band');
  });

  it('xato boshqa maydonga tegishli bo\'lsa — undefined', () => {
    expect(fieldError('model', 'mac', 'band')).toBeUndefined();
  });

  it('errorField yo\'q bo\'lsa — undefined', () => {
    expect(fieldError(undefined, 'mac', 'band')).toBeUndefined();
  });
});

describe('otherFieldError', () => {
  it('xabar yo\'q bo\'lsa — null', () => {
    expect(otherFieldError(undefined, false, undefined, [])).toBeNull();
  });

  it('stale bo\'lsa — null (umumiy banner yetarli)', () => {
    expect(otherFieldError('xato', true, undefined, [])).toBeNull();
  });

  it('xato maʼlum maydonga tegishli bo\'lsa — null (maydon o\'zida ko\'rsatiladi)', () => {
    expect(otherFieldError('xato', false, 'mac', ['mac', 'model'])).toBeNull();
  });

  it('xato maʼlum bo\'lmagan maydonga tegishli bo\'lsa — xabarni qaytaradi', () => {
    expect(otherFieldError('xato', false, undefined, ['mac', 'model'])).toBe('xato');
  });
});

describe('closeOnOpenChange', () => {
  it('open=false bo\'lsa — close() chaqiradi', () => {
    const close = vi.fn();
    closeOnOpenChange(false, close);
    expect(close).toHaveBeenCalledOnce();
  });

  it('open=true bo\'lsa — close() chaqirilmaydi', () => {
    const close = vi.fn();
    closeOnOpenChange(true, close);
    expect(close).not.toHaveBeenCalled();
  });
});

describe('itemsOrEmpty', () => {
  it('data mavjud bo\'lsa — items ro\'yxatini qaytaradi', () => {
    expect(itemsOrEmpty({ items: [1, 2, 3] })).toEqual([1, 2, 3]);
  });

  it('data yo\'q bo\'lsa (hali yuklanmagan) — bo\'sh massiv', () => {
    expect(itemsOrEmpty(undefined)).toEqual([]);
  });
});
