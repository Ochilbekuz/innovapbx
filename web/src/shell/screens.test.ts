// Xatti-harakat testi — `isScreenVisible`/`byGroup` ekranlarni `permissions`ga ko'ra filtrlaydi
// (M7 kontrakti §1/§4). Qarang ../../replica/m7-roles-contract.md.
import { describe, expect, it } from 'vitest';
import { byGroup, isScreenVisible, OPERATOR_VISIBLE_IDS, SCREENS } from './screens';
import * as shellLocales from '@/i18n/shell';

const OPERATOR_PERMISSIONS = ['calls:read:own'];

describe('isScreenVisible / byGroup — ruxsat boʻyicha koʻrinish', () => {
  it('"*" bor foydalanuvchiga HAMMA ekran koʻrinadi (tizim guruhi ham)', () => {
    const visible = SCREENS.filter((s) => isScreenVisible(s, ['*']));
    expect(visible).toEqual(SCREENS);
  });

  it('`calls:read:own` bilan faqat "portal" va "cdr" koʻrinadi (operatorning haqiqiy ruxsati)', () => {
    const visible = SCREENS.filter((s) => isScreenVisible(s, OPERATOR_PERMISSIONS));
    expect(visible.map((s) => s.id).sort()).toEqual([...OPERATOR_VISIBLE_IDS].sort());
  });

  it('"users" guruhida `calls:read:own` bilan faqat "portal" qoladi (extensions/devices yashirin)', () => {
    const items = byGroup('users', OPERATOR_PERMISSIONS);
    expect(items.map((s) => s.id)).toEqual(['portal']);
  });

  it('"overview" guruhida `calls:read:own` bilan hech narsa koʻrinmaydi (dashboard va live yashirin)', () => {
    expect(byGroup('overview', OPERATOR_PERMISSIONS)).toEqual([]);
  });

  it('`system` guruhi faqat "*" bilan koʻrinadi — hudud ruxsatlari (hammasi birga) yetarli emas', () => {
    const allHududs = ['monitor:edit', 'extensions:edit', 'connect:edit', 'routing:edit', 'apps:edit', 'reports:edit'];
    expect(byGroup('system', allHududs)).toEqual([]);
  });

  it('ruxsat berilmagan (undefined) boʻlsa — faqat "portal" koʻrinadi', () => {
    expect(SCREENS.filter((s) => isScreenVisible(s, undefined)).map((s) => s.id)).toEqual(['portal']);
  });

  it('`monitor:view` bilan "dashboard"/"live" koʻrinadi, boshqa hududlar koʻrinmaydi', () => {
    const items = byGroup('overview', ['monitor:view']);
    expect(items.map((s) => s.id).sort()).toEqual(['dashboard', 'live']);
    expect(byGroup('connect', ['monitor:view'])).toEqual([]);
  });

  it('`<hudud>:edit` `<hudud>:view`ni ham qamraydi (edit ⇒ view)', () => {
    expect(isScreenVisible({ id: 'trunks', group: 'connect' }, ['connect:edit'])).toBe(true);
  });

  it('`reports:view` bilan "cdr" koʻrinadi (hammaning qoʻngʻiroqlari)', () => {
    expect(isScreenVisible({ id: 'cdr', group: 'reports' }, ['reports:view'])).toBe(true);
  });
});

describe('menyu nomlari — har ekranning har tilda tarjimasi bor', () => {
  it.each(Object.entries(shellLocales))('%s: SCREENS dagi har id uchun nav kaliti bor', (_lang, locale) => {
    const nav = locale.nav as Record<string, string>;
    const missing = SCREENS.map((s) => s.id).filter((id) => !nav[id]);
    expect(missing).toEqual([]);
  });
});
