import { afterEach, describe, expect, it } from 'vitest';
import { accordionNext, isNavToggleShortcut, loadNavMode, parseNavMode, saveNavMode } from './navMode';

describe('navMode — sidebar rejimi', () => {
  afterEach(() => localStorage.clear());

  it.each([
    ['pinned', 'pinned'],
    ['rail', 'rail'],
    [null, 'pinned'],
    ['', 'pinned'],
    ['RAIL', 'pinned'],
    ['{"x":1}', 'pinned'],
  ])('parseNavMode(%j) → %s', (raw, want) => {
    expect(parseNavMode(raw)).toBe(want);
  });

  it('saqlangan rejim qayta oʻqiladi', () => {
    saveNavMode('rail');
    expect(localStorage.getItem('innova.nav.mode')).toBe('rail');
    expect(loadNavMode()).toBe('rail');
  });

  it('localStorage boʻsh — sukut «pinned»', () => {
    expect(loadNavMode()).toBe('pinned');
  });
});

describe('accordionNext — bitta guruh ochiq', () => {
  it('yopiq guruh bosilsa — u ochiladi (oldingisi oʻrniga)', () => {
    expect(accordionNext('users', 'system')).toBe('system');
    expect(accordionNext(null, 'system')).toBe('system');
  });

  it('ochiq guruh bosilsa — hammasi yopiladi', () => {
    expect(accordionNext('system', 'system')).toBeNull();
  });
});

describe('isNavToggleShortcut — Ctrl/⌘+B', () => {
  const ev = (init: KeyboardEventInit, target: EventTarget = document.body) => {
    const e = new KeyboardEvent('keydown', init);
    Object.defineProperty(e, 'target', { value: target });
    return e;
  };

  it('Ctrl+B va ⌘+B — ha', () => {
    expect(isNavToggleShortcut(ev({ key: 'b', ctrlKey: true }))).toBe(true);
    expect(isNavToggleShortcut(ev({ key: 'B', metaKey: true }))).toBe(true);
  });

  it('rus tartibida ham (code=KeyB)', () => {
    expect(isNavToggleShortcut(ev({ key: 'и', code: 'KeyB', ctrlKey: true }))).toBe(true);
  });

  it('modifikatorsiz, Shift/Alt bilan yoki boshqa tugma — yoʻq', () => {
    expect(isNavToggleShortcut(ev({ key: 'b' }))).toBe(false);
    expect(isNavToggleShortcut(ev({ key: 'b', ctrlKey: true, shiftKey: true }))).toBe(false);
    expect(isNavToggleShortcut(ev({ key: 'b', ctrlKey: true, altKey: true }))).toBe(false);
    expect(isNavToggleShortcut(ev({ key: 'k', ctrlKey: true }))).toBe(false);
  });

  it('matn kiritish maydonida — yoʻq', () => {
    const input = document.createElement('input');
    const area = document.createElement('textarea');
    const editable = document.createElement('div');
    editable.setAttribute('contenteditable', 'true'); // jsdom'da `contentEditable` IDL yo'q
    expect(isNavToggleShortcut(ev({ key: 'b', ctrlKey: true }, input))).toBe(false);
    expect(isNavToggleShortcut(ev({ key: 'b', ctrlKey: true }, area))).toBe(false);
    expect(isNavToggleShortcut(ev({ key: 'b', ctrlKey: true }, editable))).toBe(false);
  });
});
