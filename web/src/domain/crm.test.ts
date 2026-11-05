// Bitrix24 — xususiy (ichki) host aniqlash va sinxron hisobotini qurish (sof mantiq).
// Qarang CrmTab.tsx — click-to-call ogohlantirishi va sinxron banneri shu yerdan foydalanadi.
import { describe, expect, it } from 'vitest';
import { buildBitrixSyncPlan, cloudCannotReachPrivateHost, isPrivateHost, parseBitrixPortalHost } from './crm';

describe('isPrivateHost', () => {
  it.each([
    ['10.0.0.5', true],
    ['172.16.0.1', true],
    ['172.31.255.255', true],
    ['172.32.0.1', false],
    ['192.168.1.10', true],
    ['localhost', true],
    ['127.0.0.1', true],
    ['pbx.firma.uz', false],
    ['bitrix24.ru', false],
  ])('%s → %s', (host, expected) => expect(isPrivateHost(host)).toBe(expected));
});

describe('cloudCannotReachPrivateHost', () => {
  it('portal bulutda emas boʻlsa — ogohlantirish yoʻq', () => {
    expect(cloudCannotReachPrivateHost(false, 'http://10.0.0.5:8080/call')).toBe(false);
  });
  it('portal bulutda va manzil xususiy boʻlsa — ogohlantirish bor', () => {
    expect(cloudCannotReachPrivateHost(true, 'http://10.0.0.5:8080/call')).toBe(true);
  });
  it('portal bulutda va manzil ochiq (public) boʻlsa — ogohlantirish yoʻq', () => {
    expect(cloudCannotReachPrivateHost(true, 'https://pbx.firma.uz/call')).toBe(false);
  });
  it('notoʻgʻri URL boʻlsa — ogohlantirish koʻrsatmaydi', () => {
    expect(cloudCannotReachPrivateHost(true, 'not-a-url')).toBe(false);
  });
});

describe('parseBitrixPortalHost', () => {
  it('bulut portalini aniqlaydi', () => {
    expect(parseBitrixPortalHost('https://firma.bitrix24.ru/rest/1/abc/')).toEqual({ host: 'firma.bitrix24.ru', cloud: true });
  });
  it('oʻz serveridagi (on-prem) portalni aniqlaydi', () => {
    expect(parseBitrixPortalHost('https://crm.firma.uz/rest/1/abc/')).toEqual({ host: 'crm.firma.uz', cloud: false });
  });
  it("notoʻgʻri URL boʻlsa — null", () => {
    expect(parseBitrixPortalHost('notaurl')).toBeNull();
  });
});

describe('buildBitrixSyncPlan', () => {
  const extensions = ['101', '102', '103'];
  it('ichki raqami mos keladigan foydalanuvchini "auto" qilib moslaydi', () => {
    const plan = buildBitrixSyncPlan([{ id: 'u1', name: 'Ali', inner_phone: '101' }], extensions, []);
    expect(plan.report.mapped).toBe(1);
    expect(plan.report.unknown_inner).toEqual([]);
    expect(plan.report.conflicts).toEqual([]);
    expect(plan.autoMap.get('101')).toEqual({ crm_user_id: 'u1', crm_user_name: 'Ali' });
  });

  it('PBX\'da yoʻq ichki raqamni "unknown_inner" ga yozadi', () => {
    const plan = buildBitrixSyncPlan([{ id: 'u1', name: 'Ali', inner_phone: '199' }], extensions, []);
    expect(plan.report.unknown_inner).toEqual([{ user_id: 'u1', user_name: 'Ali', inner_phone: '199' }]);
    expect(plan.autoMap.has('199')).toBe(false);
  });

  it('bitta ichki raqamda ikki foydalanuvchi boʻlsa — "conflicts" ga yozadi, avto-moslamaydi', () => {
    const plan = buildBitrixSyncPlan(
      [{ id: 'u1', name: 'Ali', inner_phone: '101' }, { id: 'u2', name: 'Vali', inner_phone: '101' }],
      extensions, [],
    );
    expect(plan.report.conflicts).toEqual([{ inner_phone: '101', user_names: ['Ali', 'Vali'] }]);
    expect(plan.autoMap.has('101')).toBe(false);
  });

  it('qoʻlda moslangan ichki raqamni avto-sinxron ustiga yozmaydi', () => {
    const plan = buildBitrixSyncPlan([{ id: 'u1', name: 'Ali', inner_phone: '101' }], extensions, ['101']);
    expect(plan.autoMap.has('101')).toBe(false);
  });

  it('inner_phone yoʻq foydalanuvchini eʼtiborsiz qoldiradi', () => {
    const plan = buildBitrixSyncPlan([{ id: 'u1', name: 'Ali', inner_phone: null }], extensions, []);
    expect(plan.report.unknown_inner).toEqual([]);
    expect(plan.report.mapped).toBe(0);
  });
});
