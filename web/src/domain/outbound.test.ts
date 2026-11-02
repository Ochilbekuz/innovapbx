import { describe, expect, it } from 'vitest';
import { isInternationalNumber, simulateOutbound, validateOutboundForm, type OutboundFormDraft, type SimRoute } from './outbound';

const VALID_DRAFT: OutboundFormDraft = {
  name: 'UZ', patternCount: 1, everyPatternFilled: true, chainLength: 1,
  pinOn: false, pin: '', hasExistingPin: false, extensionsMode: 'all', selectedExtensionCount: 0,
};

const UZ_ROUTE: SimRoute = {
  id: 'r1',
  name: 'Mahalliy va mobil (UZ)',
  priority: 1,
  enabled: true,
  patterns: [
    { strip_prefix: null, pattern: '998XXXXXXXXX', add_prefix: null, callerid_match: null },
    { strip_prefix: null, pattern: 'XXXXXXXXX', add_prefix: '998', callerid_match: null },
  ],
  trunks: [{ id: 't1', name: 'Trunk A', health_state: 'ok' }],
  callerid: null,
  override_extension_callerid: false,
  international: false,
  extensions: 'all',
};

const INTL_ROUTE: SimRoute = { ...UZ_ROUTE, id: 'r2', name: 'Xalqaro', priority: 2, international: true, patterns: [{ strip_prefix: '00', pattern: '.', add_prefix: '', callerid_match: null }] };

describe('isInternationalNumber', () => {
  it('00 va + bilan boshlanib 998 bilan boshlanmasa — xalqaro', () => {
    expect(isInternationalNumber('0044201234567')).toBe(true);
    expect(isInternationalNumber('+44201234567')).toBe(true);
  });
  it('998 bilan boshlansa xalqaro emas', () => {
    expect(isInternationalNumber('998901234567')).toBe(false);
    expect(isInternationalNumber('00998901234567')).toBe(false);
  });
  it('oddiy mahalliy raqam xalqaro emas', () => {
    expect(isInternationalNumber('901234567')).toBe(false);
  });
});

describe('simulateOutbound', () => {
  it('mobil raqamga 998 qoʻshib UZ marshrutdan oʻtkazadi', () => {
    const r = simulateOutbound([UZ_ROUTE], '101', '901234567');
    expect(r.allowed).toBe(true);
    expect(r.dialed).toBe('998901234567');
    expect(r.route?.id).toBe('r1');
    expect(r.trunks).toEqual(UZ_ROUTE.trunks);
    expect(r.steps[0]).toMatchObject({ route: UZ_ROUTE.name, result: 'match' });
  });

  it('xalqaro raqamni international=false marshrutda rad etadi va keyingisiga oʻtadi', () => {
    const r = simulateOutbound([UZ_ROUTE, INTL_ROUTE], '101', '0044201234567');
    expect(r.allowed).toBe(true);
    expect(r.route?.id).toBe('r2');
    const first = r.steps.find((s) => s.route === UZ_ROUTE.name);
    expect(first?.result).toBe('no_pattern');
  });

  it('hech bir marshrut mos kelmasa allowed=false va sabab beradi', () => {
    const r = simulateOutbound([UZ_ROUTE], '101', '0044201234567');
    expect(r.allowed).toBe(false);
    expect(r.reason).toBeTruthy();
    expect(r.steps[0]?.result).toBe('no_pattern');
  });

  it('ichki raqam ruxsat etilmagan marshrutni oʻtkazib yuboradi', () => {
    const restricted: SimRoute = { ...UZ_ROUTE, extensions: ['102'] };
    const r = simulateOutbound([restricted], '101', '901234567');
    expect(r.allowed).toBe(false);
    expect(r.steps[0]?.result).toBe('ext_not_allowed');
  });

  it("o'chirilgan marshrutni sinamaydi", () => {
    const disabled: SimRoute = { ...UZ_ROUTE, enabled: false };
    const r = simulateOutbound([disabled], '101', '901234567');
    expect(r.allowed).toBe(false);
    expect(r.steps[0]?.result).toBe('disabled');
  });

  it('override_extension_callerid false bo‘lsa ext callerid ustunlik qiladi', () => {
    const r = simulateOutbound([{ ...UZ_ROUTE, callerid: '998711234567' }], '101', '901234567', '998900001122');
    expect(r.callerid).toBe('998900001122');
  });

  it('override_extension_callerid true bo‘lsa route callerid ustunlik qiladi', () => {
    const r = simulateOutbound([{ ...UZ_ROUTE, callerid: '998711234567', override_extension_callerid: true }], '101', '901234567', '998900001122');
    expect(r.callerid).toBe('998711234567');
  });

  it('priority tartibida birinchi mosini tanlaydi', () => {
    const second: SimRoute = { ...UZ_ROUTE, id: 'r3', name: 'Ikkinchi', priority: 0 };
    const r = simulateOutbound([UZ_ROUTE, second], '101', '901234567');
    expect(r.route?.id).toBe('r3');
  });
});

describe('validateOutboundForm', () => {
  it('to‘liq to‘ldirilgan forma — valid', () => {
    expect(validateOutboundForm(VALID_DRAFT)).toEqual({ valid: true, pinError: null });
  });
  it('nom bo‘sh bo‘lsa — invalid', () => {
    expect(validateOutboundForm({ ...VALID_DRAFT, name: '  ' }).valid).toBe(false);
  });
  it('naqsh yo‘q yoki to‘ldirilmagan bo‘lsa — invalid', () => {
    expect(validateOutboundForm({ ...VALID_DRAFT, patternCount: 0 }).valid).toBe(false);
    expect(validateOutboundForm({ ...VALID_DRAFT, everyPatternFilled: false }).valid).toBe(false);
  });
  it('trunk zanjiri bo‘sh bo‘lsa — invalid', () => {
    expect(validateOutboundForm({ ...VALID_DRAFT, chainLength: 0 }).valid).toBe(false);
  });
  it('PIN yoqilgan, lekin 4 raqamdan kam bo‘lsa — xato va invalid', () => {
    const r = validateOutboundForm({ ...VALID_DRAFT, pinOn: true, pin: '12' });
    expect(r.valid).toBe(false);
    expect(r.pinError).toMatch(/4–8/);
  });
  it('PIN yoqilgan, yangi va eski PIN yo‘q bo‘lsa — invalid (pinMissing)', () => {
    expect(validateOutboundForm({ ...VALID_DRAFT, pinOn: true, pin: '' }).valid).toBe(false);
  });
  it('PIN yoqilgan, eski PIN mavjud va yangisi kiritilmagan bo‘lsa — valid (eskisi qoladi)', () => {
    expect(validateOutboundForm({ ...VALID_DRAFT, pinOn: true, pin: '', hasExistingPin: true }).valid).toBe(true);
  });
  it('tanlangan rejimda hech bo‘lmaganda bitta ichki raqam kerak', () => {
    expect(validateOutboundForm({ ...VALID_DRAFT, extensionsMode: 'selected', selectedExtensionCount: 0 }).valid).toBe(false);
    expect(validateOutboundForm({ ...VALID_DRAFT, extensionsMode: 'selected', selectedExtensionCount: 2 }).valid).toBe(true);
  });
});
