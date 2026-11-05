// Bitrix24 — xususiy (ichki) host aniqlash va sinxron hisobotini qurish (sof mantiq).
// Qarang CrmTab.tsx — click-to-call ogohlantirishi va sinxron banneri shu yerdan foydalanadi.
import { describe, expect, it } from 'vitest';
import { bitrix24LicenseStateArgs, buildBitrixSyncPlan, cloudCannotReachPrivateHost, computeBitrix24License, isPrivateHost, normalizeBitrixDomain, parseBitrixPortalHost } from './crm';

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

describe('normalizeBitrixDomain', () => {
  it('oddiy hostni oʻzgarishsiz qabul qiladi', () => {
    expect(normalizeBitrixDomain('firma.bitrix24.kz')).toBe('firma.bitrix24.kz');
  });
  it('https:// prefiksini olib tashlaydi', () => {
    expect(normalizeBitrixDomain('https://firma.bitrix24.kz')).toBe('firma.bitrix24.kz');
  });
  it('yoʻl, portni olib tashlaydi, kichik harfga oʻtkazadi', () => {
    expect(normalizeBitrixDomain('HTTPS://Firma.Bitrix24.kz:443/crm/deal/')).toBe('firma.bitrix24.kz');
  });
  it('boʻsh joylarni kesadi', () => {
    expect(normalizeBitrixDomain('  firma.bitrix24.kz  ')).toBe('firma.bitrix24.kz');
  });
  it('boʻsh qiymat — null', () => {
    expect(normalizeBitrixDomain('')).toBeNull();
    expect(normalizeBitrixDomain('   ')).toBeNull();
  });
  it('notoʻgʻri hostname — null', () => {
    expect(normalizeBitrixDomain('not a domain')).toBeNull();
    expect(normalizeBitrixDomain('firma')).toBeNull();
  });
});

describe('computeBitrix24License', () => {
  const base = { domain: 'firma.bitrix24.kz', sinov_boshlandi: '2026-11-01', tolov_tugash: null, blocked: false };
  it("sinov davrida — 'sinov', qolgan kun hisoblanadi", () => {
    const lic = computeBitrix24License({ ...base, today: '2026-11-05' });
    expect(lic.holat).toBe('sinov');
    expect(lic.sinov_tugash).toBe('2026-11-15');
    expect(lic.tugash).toBe('2026-11-15');
    expect(lic.qolgan_kun).toBe(10);
  });
  it("sinov tugagan, toʻlov bo'lmasa, imtiyoz kunida — 'imtiyoz'", () => {
    const lic = computeBitrix24License({ ...base, today: '2026-11-16' });
    expect(lic.holat).toBe('imtiyoz');
  });
  it("imtiyozdan keyin — 'tugagan'", () => {
    const lic = computeBitrix24License({ ...base, today: '2026-11-17' });
    expect(lic.holat).toBe('tugagan');
  });
  it("toʻlov tugash sinovdan uzoqroq va bugun undan oldin boʻlsa — 'faol'", () => {
    const lic = computeBitrix24License({ ...base, tolov_tugash: '2026-12-15', today: '2026-11-20' });
    expect(lic.holat).toBe('faol');
    expect(lic.tugash).toBe('2026-12-15');
  });
  it("bloklangan — dastur holatidan qat'i nazar", () => {
    const lic = computeBitrix24License({ ...base, blocked: true, today: '2026-11-05' });
    expect(lic.holat).toBe('bloklangan');
  });
  it('tariflar roʻyxati shartnomaga mos', () => {
    const lic = computeBitrix24License({ ...base, today: '2026-11-05' });
    expect(lic.tariflar).toEqual([
      { kod: 'sinov', kun: 14 }, { kod: '1oy', oy: 1 }, { kod: '3oy', oy: 3 }, { kod: '6oy', oy: 6 }, { kod: '1yil', oy: 12 },
    ]);
  });
});

describe('bitrix24LicenseStateArgs', () => {
  const base = { domain: 'firma.bitrix24.kz', sinov_boshlandi: '2026-11-01', tolov_tugash: null, blocked: false };
  it("'sinov' — qolgan kunni qaytaradi", () => {
    const lic = computeBitrix24License({ ...base, today: '2026-11-05' });
    expect(bitrix24LicenseStateArgs(lic)).toEqual({ state: 'sinov', days: 10 });
  });
  it("'faol' — tugash sanasini qaytaradi", () => {
    const lic = computeBitrix24License({ ...base, tolov_tugash: '2026-12-15', today: '2026-11-20' });
    expect(bitrix24LicenseStateArgs(lic)).toEqual({ state: 'faol', date: '2026-12-15' });
  });
  it("'imtiyoz'/'tugagan'/'bloklangan' — faqat holatni qaytaradi", () => {
    expect(bitrix24LicenseStateArgs(computeBitrix24License({ ...base, today: '2026-11-16' }))).toEqual({ state: 'imtiyoz' });
    expect(bitrix24LicenseStateArgs(computeBitrix24License({ ...base, today: '2026-11-17' }))).toEqual({ state: 'tugagan' });
    expect(bitrix24LicenseStateArgs(computeBitrix24License({ ...base, blocked: true, today: '2026-11-05' }))).toEqual({ state: 'bloklangan' });
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
