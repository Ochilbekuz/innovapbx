import { describe, expect, it } from 'vitest';
import type { Extension } from '@/api/types';
import {
  DEFAULT_CALL_SETTINGS, callSettingsFromExtension, callSettingsValid, createExtensionPayload, createExtensionValid,
  editExtensionDirty, editExtensionFieldsFromExtension, editExtensionValid, forwardNumberValid, pickupGroupValid,
  updateExtensionPayload, type CreateExtensionFields, type EditExtensionFields,
} from './extensionForms';

function makeExt(patch: Partial<Extension> = {}): Extension {
  return {
    id: 'e-1', number: '100', name: 'Test', enabled: true, status: 'unknown', contact: null, user_agent: null,
    dnd: false, forward_always: null, forward_busy: null, pickup_group: null,
    outbound_allowed: true, outbound_callerid: null,
    updated_at: '2026-01-01T00:00:00Z', toll_blocked_at: null, toll_block_reason: null, webrtc: false, codecs: [],
    recording: 'never',
    ...patch,
  };
}

describe('forwardNumberValid / pickupGroupValid', () => {
  it('bo\'sh qiymat — yaroqli (yo\'naltirish o\'chiq)', () => {
    expect(forwardNumberValid('')).toBe(true);
    expect(pickupGroupValid('')).toBe(true);
  });
  it('notoʻgʻri formatlar rad etiladi', () => {
    expect(forwardNumberValid('abc')).toBe(false);
    expect(pickupGroupValid('Sales!')).toBe(false);
  });
  it('toʻgʻri formatlar qabul qilinadi', () => {
    expect(forwardNumberValid('998712345678')).toBe(true);
    expect(pickupGroupValid('sales-1')).toBe(true);
  });
});

describe('callSettingsFromExtension / callSettingsValid', () => {
  it('ichki raqamdan holatni to\'g\'ri o\'qiydi', () => {
    const ext = makeExt({ dnd: true, forward_always: '101', outbound_allowed: false, outbound_callerid: '998712345678' });
    expect(callSettingsFromExtension(ext)).toEqual({
      dnd: true, forwardAlways: '101', forwardBusy: '', pickupGroup: '', outboundAllowed: false, outboundCallerid: '998712345678',
    });
  });
  it('notoʻgʻri forward_busy bo\'lsa — yaroqsiz', () => {
    expect(callSettingsValid({ ...DEFAULT_CALL_SETTINGS, forwardBusy: 'xyz' })).toBe(false);
  });
});

describe('createExtensionValid / createExtensionPayload', () => {
  function fields(patch: Partial<CreateExtensionFields> = {}): CreateExtensionFields {
    return { number: '', name: 'Yangi', password: 'Secret123', webrtc: false, recording: 'never', calls: DEFAULT_CALL_SETTINGS, ...patch };
  }

  it('bo\'sh nom — yaroqsiz', () => {
    expect(createExtensionValid(fields({ name: '' }))).toBe(false);
  });
  it('zaif parol — yaroqsiz', () => {
    expect(createExtensionValid(fields({ password: '1234567' }))).toBe(false);
  });
  it('parol ichki raqamni o\'z ichiga olsa — yaroqsiz', () => {
    expect(createExtensionValid(fields({ number: '150', password: 'abc150xyz' }))).toBe(false);
  });
  it('to\'g\'ri forma — yaroqli', () => {
    expect(createExtensionValid(fields())).toBe(true);
  });

  it('payload — bo\'sh maydonlar undefined/true bilan to\'g\'ri quriladi', () => {
    const payload = createExtensionPayload(fields({ number: '150', calls: { ...DEFAULT_CALL_SETTINGS, dnd: true, outboundCallerid: '998712345678' } }));
    expect(payload).toEqual({
      number: '150', name: 'Yangi', password: 'Secret123', webrtc: false, recording: 'never',
      dnd: true, forward_always: undefined, forward_busy: undefined, pickup_group: undefined,
      outbound_allowed: true, outbound_callerid: '998712345678',
    });
  });
});

describe('editExtensionFieldsFromExtension / editExtensionDirty / editExtensionValid', () => {
  function fields(ext: Extension, patch: Partial<EditExtensionFields> = {}): EditExtensionFields {
    return { ...editExtensionFieldsFromExtension(ext), ...patch };
  }

  it('o\'zgarishsiz — dirty emas', () => {
    const ext = makeExt();
    expect(editExtensionDirty(fields(ext), ext)).toBe(false);
  });
  it('faqat dnd o\'zgarsa — dirty', () => {
    const ext = makeExt();
    const f = fields(ext, { calls: { ...DEFAULT_CALL_SETTINGS, dnd: true } });
    expect(editExtensionDirty(f, ext)).toBe(true);
  });
  it('bo\'sh nom — yaroqsiz', () => {
    const ext = makeExt();
    expect(editExtensionValid(fields(ext, { name: '' }))).toBe(false);
  });
});

describe('updateExtensionPayload', () => {
  it('faqat dnd o\'zgarsa — faqat shu maydon va updated_at yuboriladi', () => {
    const ext = makeExt();
    const f: EditExtensionFields = { ...editExtensionFieldsFromExtension(ext), calls: { ...DEFAULT_CALL_SETTINGS, dnd: true } };
    expect(updateExtensionPayload(f, ext)).toEqual({ updated_at: ext.updated_at, dnd: true });
  });

  it('outbound_callerid tozalanishi — bo\'sh satr `null`ga aylanadi', () => {
    const ext = makeExt({ outbound_callerid: '998712345678' });
    const f: EditExtensionFields = { ...editExtensionFieldsFromExtension(ext), calls: { ...callSettingsFromExtension(ext), outboundCallerid: '' } };
    expect(updateExtensionPayload(f, ext)).toEqual({ updated_at: ext.updated_at, outbound_callerid: null });
  });

  it('nom va yoqilganlik birga o\'zgarsa — ikkisi ham payloadda', () => {
    const ext = makeExt();
    const f: EditExtensionFields = { ...editExtensionFieldsFromExtension(ext), name: 'Yangi nom', enabled: false };
    expect(updateExtensionPayload(f, ext)).toEqual({ updated_at: ext.updated_at, name: 'Yangi nom', enabled: false });
  });
});
