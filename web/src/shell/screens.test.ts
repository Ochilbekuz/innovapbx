// Xatti-harakat testi — `byGroup` operator uchun faqat `/me` va qoʻngʻiroqlar tarixini (`cdr`) qoldiradi;
// admin uchun filtrlamaydi (M2b §4, sidebar). Qarang ../../replica/m2b-contract.md §4.
import { describe, expect, it } from 'vitest';
import { byGroup, OPERATOR_VISIBLE_IDS, SCREENS } from './screens';

describe('byGroup — operator sidebar koʻrinishi', () => {
  it('operator roli faqat "portal" (/me) va "cdr" (qoʻngʻiroqlar tarixi) ekranlarini koʻradi', () => {
    const visible = SCREENS.filter((s) => byGroup(s.group, 'operator').some((v) => v.id === s.id));
    expect(visible.map((s) => s.id).sort()).toEqual([...OPERATOR_VISIBLE_IDS].sort());
  });

  it('"users" guruhida operator uchun faqat "portal" qoladi (extensions/devices yashirin)', () => {
    const items = byGroup('users', 'operator');
    expect(items.map((s) => s.id)).toEqual(['portal']);
  });

  it('"overview" guruhida operator uchun hech narsa koʻrinmaydi (dashboard va live yashirin)', () => {
    expect(byGroup('overview', 'operator')).toEqual([]);
  });

  it('admin rolida (va role berilmaganda) filtrlanmaydi — guruhdagi hamma ekran qaytadi', () => {
    const forAdmin = byGroup('users', 'admin');
    const forUndefined = byGroup('users', undefined);
    const all = SCREENS.filter((s) => s.group === 'users');
    expect(forAdmin).toEqual(all);
    expect(forUndefined).toEqual(all);
  });
});
