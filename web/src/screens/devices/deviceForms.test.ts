import { describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import type { Device, DeviceKey, DeviceModel, DiscoveredDevice } from '@/api/types';
import {
  addKeyRow, assignModalDescription, assignPayload, canSubmitAssign, createDevicePayload, createDeviceValid,
  currentExtensionId, deviceModelOptions, editDevicePayload, effectiveVendor, emptyForm, extensionOptions,
  keyTypeOptions, keysLimitFor, keysModalTitle, macFieldError, macValid, modelsForVendor, nextIdx,
  normalizeKeysForSubmit, removeKeyRow, updateKeyRow, useAssignForm, useEditDeviceForm, useKeysForm,
} from './deviceForms';

const t = (key: string, options?: Record<string, unknown>) => (options ? `${key}:${JSON.stringify(options)}` : key);

const DISCOVERED: DiscoveredDevice = {
  mac: 'aabbccddeeff', vendor: 'grandstream', model: 'GXP2135', ip: '10.0.0.5', user_agent: 'x',
  firmware: null, first_seen_at: '2026-01-01T00:00:00Z', last_seen_at: '2026-01-01T00:00:00Z', requests: 1,
};

const DEVICE: Device = {
  id: 'd-1', mac: 'aabbccddeeff', vendor: 'yealink', model: 'T31P', label: 'Hol A', enabled: true,
  extension: { id: 'e-1', number: '101', name: 'Ali' }, status: 'registered', provisioned_at: null,
  last_seen_at: null, last_ip: null, firmware: null, registered: true, keys_count: 0, updated_at: '2026-01-01T00:00:00Z',
};

const YEALINK_T31P: DeviceModel = { vendor: 'yealink', model: 'T31P', keys: 2, family: 'T3' };
const GRANDSTREAM_GXP2135: DeviceModel = { vendor: 'grandstream', model: 'GXP2135', keys: 4, family: 'GXP' };
const MODELS: DeviceModel[] = [YEALINK_T31P, GRANDSTREAM_GXP2135];

describe('macValid', () => {
  it('12 ta hex belgi (ayiruvchilarsiz) — valid', () => { expect(macValid('AA:BB:CC:DD:EE:FF')).toBe(true); });
  it('qisqa yoki notoʻgʻri belgilar — invalid', () => { expect(macValid('aabbcc')).toBe(false); });
});

describe('extensionOptions', () => {
  const extensions = [
    { id: 'e-1', number: '101', name: 'Ali', webrtc: false },
    { id: 'e-2', number: '102', name: 'Vali', webrtc: true },
  ];
  it('webrtc ichki raqamlarni chiqarib tashlaydi', () => {
    expect(extensionOptions(extensions)).toEqual([{ value: 'e-1', label: '101 — Ali' }]);
  });
  it('keepId berilsa — webrtc bo\'lsa ham shu bittasi qoladi', () => {
    expect(extensionOptions(extensions, 'e-2')).toEqual([
      { value: 'e-1', label: '101 — Ali' }, { value: 'e-2', label: '102 — Vali' },
    ]);
  });
});

describe('deviceModelOptions / modelsForVendor', () => {
  it('vendor boʻyicha filtrlaydi', () => { expect(modelsForVendor(MODELS, 'yealink')).toEqual([YEALINK_T31P]); });
  it('model + tugmalar sonini label qiladi', () => {
    expect(deviceModelOptions([YEALINK_T31P])).toEqual([{ value: 'T31P', label: 'T31P (2)' }]);
  });
});

describe('Assign discovered form', () => {
  it('effectiveVendor — device yo\'q bo\'lsa yealink', () => { expect(effectiveVendor(null)).toBe('yealink'); });
  it('effectiveVendor — device vendor\'ini qaytaradi', () => { expect(effectiveVendor(DISCOVERED)).toBe('grandstream'); });

  it('assignModalDescription — device yo\'q bo\'lsa undefined', () => { expect(assignModalDescription(t, null)).toBeUndefined(); });
  it('assignModalDescription — model mavjud bo\'lsa shuni ishlatadi', () => {
    expect(assignModalDescription(t, DISCOVERED)).toContain('"model":"GXP2135"');
  });

  it('canSubmitAssign — extension/model tanlanmaguncha false', () => {
    expect(canSubmitAssign(DISCOVERED, { extensionId: '', model: '', label: '' })).toBe(false);
    expect(canSubmitAssign(DISCOVERED, { extensionId: 'e-1', model: 'GXP2135', label: '' })).toBe(true);
  });
  it('canSubmitAssign — device yo\'q bo\'lsa false', () => {
    expect(canSubmitAssign(null, { extensionId: 'e-1', model: 'GXP2135', label: '' })).toBe(false);
  });

  it('assignPayload — label trim qilinadi, boʻsh boʻlsa undefined', () => {
    expect(assignPayload({ extensionId: 'e-1', model: 'GXP2135', label: '  ' })).toEqual({ extension_id: 'e-1', model: 'GXP2135', label: undefined });
    expect(assignPayload({ extensionId: 'e-1', model: 'GXP2135', label: ' Hol B ' })).toEqual({ extension_id: 'e-1', model: 'GXP2135', label: 'Hol B' });
  });

  it('useAssignForm — device MAC boʻyicha qayta ishga tushadi, model device.model bilan boshlanadi', () => {
    const { result, rerender } = renderHook(({ device }) => useAssignForm(device), { initialProps: { device: null as DiscoveredDevice | null } });
    expect(result.current.state).toEqual({ extensionId: '', model: '', label: '' });

    rerender({ device: DISCOVERED });
    expect(result.current.state.model).toBe('GXP2135');

    act(() => result.current.setExtensionId('e-1'));
    expect(result.current.state.extensionId).toBe('e-1');

    act(() => result.current.reset());
    rerender({ device: DISCOVERED });
    expect(result.current.state).toEqual({ extensionId: '', model: 'GXP2135', label: '' });
  });
});

describe('Create device form', () => {
  it('emptyForm — fixedExtensionId berilsa shu bilan boshlanadi', () => {
    expect(emptyForm('e-9')).toEqual({ vendor: 'yealink', model: '', mac: '', extensionId: 'e-9', label: '' });
  });

  it('createDeviceValid — mac/model/extension kerak', () => {
    const base = emptyForm();
    expect(createDeviceValid(base, false)).toBe(false);
    expect(createDeviceValid({ ...base, model: 'T31P', extensionId: 'e-1' }, true)).toBe(true);
  });

  it('macFieldError — mutatsiya xatosi birinchi', () => {
    expect(macFieldError('mac', 'band', 'aabbccddeeff', true, 'hint')).toBe('band');
  });
  it('macFieldError — format notoʻgʻri boʻlsa hint', () => {
    expect(macFieldError(undefined, undefined, 'xx', false, 'hint')).toBe('hint');
  });
  it('macFieldError — boʻsh yoki toʻgʻri boʻlsa undefined', () => {
    expect(macFieldError(undefined, undefined, '', false, 'hint')).toBeUndefined();
    expect(macFieldError(undefined, undefined, 'aabbccddeeff', true, 'hint')).toBeUndefined();
  });

  it('createDevicePayload — label trim qilinadi', () => {
    expect(createDevicePayload({ vendor: 'yealink', model: 'T31P', mac: 'aabbccddeeff', extensionId: 'e-1', label: '  ' }))
      .toEqual({ mac: 'aabbccddeeff', vendor: 'yealink', model: 'T31P', extension_id: 'e-1', label: undefined });
  });
});

describe('Edit device form', () => {
  it('currentExtensionId — device yo\'q bo\'lsa undefined', () => { expect(currentExtensionId(null)).toBeUndefined(); });
  it('currentExtensionId — biriktirilgan ichki raqamni qaytaradi', () => { expect(currentExtensionId(DEVICE)).toBe('e-1'); });

  it('editDevicePayload — label trim, updated_at saqlanadi', () => {
    expect(editDevicePayload({ label: ' Hol B ', extensionId: 'e-2', enabled: false }, DEVICE))
      .toEqual({ label: 'Hol B', extension_id: 'e-2', enabled: false, updated_at: '2026-01-01T00:00:00Z' });
  });

  it('useEditDeviceForm — device id oʻzgarganda formani qayta initsializatsiya qiladi', () => {
    const { result, rerender } = renderHook(({ device }) => useEditDeviceForm(device), { initialProps: { device: null as Device | null } });
    expect(result.current.state).toEqual({ label: '', extensionId: '', enabled: true });

    rerender({ device: DEVICE });
    expect(result.current.state).toEqual({ label: 'Hol A', extensionId: 'e-1', enabled: true });

    act(() => result.current.setLabel('Yangi'));
    expect(result.current.state.label).toBe('Yangi');

    // Bir xil device qayta berilsa — qoʻlda kiritilgan qiymat saqlanadi (qayta initsializatsiya boʻlmaydi).
    rerender({ device: DEVICE });
    expect(result.current.state.label).toBe('Yangi');
  });
});

describe('Keys form', () => {
  const rows: DeviceKey[] = [
    { idx: 1, type: 'blf', value: '101', label: 'Ali' },
    { idx: 2, type: 'line', value: null, label: null },
  ];

  it('nextIdx — keyingi tartib raqami', () => { expect(nextIdx(rows)).toBe(3); });

  it('updateKeyRow — faqat koʻrsatilgan qatorni oʻzgartiradi', () => {
    expect(updateKeyRow(rows, 0, { value: '102' })[0]).toEqual({ idx: 1, type: 'blf', value: '102', label: 'Ali' });
    expect(updateKeyRow(rows, 0, { value: '102' })[1]).toEqual(rows[1]);
  });

  it('addKeyRow — limitga yetganda qo\'shmaydi', () => {
    expect(addKeyRow(rows, 2)).toBe(rows);
    expect(addKeyRow(rows, 3)).toHaveLength(3);
  });

  it('removeKeyRow — qatorni olib tashlab, idx\'larni qayta raqamlaydi', () => {
    expect(removeKeyRow(rows, 0)).toEqual([{ idx: 1, type: 'line', value: null, label: null }]);
  });

  it('normalizeKeysForSubmit — boʻsh qiymat/yorliqni null qiladi', () => {
    const withSpaces: DeviceKey[] = [{ idx: 1, type: 'blf', value: '  ', label: '  ' }];
    expect(normalizeKeysForSubmit(withSpaces)).toEqual([{ idx: 1, type: 'blf', value: null, label: null }]);
  });

  it('keysLimitFor — model boʻyicha tugmalar sonini topadi', () => {
    expect(keysLimitFor(MODELS, DEVICE)).toBe(2);
    expect(keysLimitFor(MODELS, null)).toBe(0);
    expect(keysLimitFor([], DEVICE)).toBe(0);
  });

  it('keysModalTitle — device yo\'q bo\'lsa boʻsh satr', () => { expect(keysModalTitle(t, null)).toBe(''); });
  it('keysModalTitle — label boʻlmasa mac ishlatiladi', () => {
    const noLabel: Device = { ...DEVICE, label: null };
    expect(keysModalTitle(t, noLabel)).toContain(DEVICE.mac);
  });

  it('keyTypeOptions — har bir tur uchun tarjima kaliti', () => {
    expect(keyTypeOptions(t, ['blf', 'none'])).toEqual([
      { value: 'blf', label: 'keysModal.typeOption.blf' }, { value: 'none', label: 'keysModal.typeOption.none' },
    ]);
  });

  it('useKeysForm — device id oʻzgarganda va kalitlar kelganda qatorlarni yuklaydi', () => {
    const { result, rerender } = renderHook(
      ({ device, items }) => useKeysForm(device, items),
      { initialProps: { device: null as Device | null, items: undefined as DeviceKey[] | undefined } },
    );
    expect(result.current.rows).toEqual([]);

    rerender({ device: DEVICE, items: rows });
    expect(result.current.rows).toEqual(rows);

    act(() => result.current.reset());
    rerender({ device: DEVICE, items: rows });
    expect(result.current.rows).toEqual(rows);
  });
});
