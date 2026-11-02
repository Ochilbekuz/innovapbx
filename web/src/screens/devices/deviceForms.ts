// `DevicesTab.tsx` dagi modal formalarning holati/validatsiyasi/submit logikasi — sof funksiyalar
// va kichik hook'larga ajratilgan, shu bilan komponent funksiyalari faqat JSX'ni tutadi
// (qarang `formHelpers.ts` izohi — nested callback'lar CRAP'ga qoʻshilib hisoblanadi).
import { useState } from 'react';
import type { Device, DeviceKey, DeviceKeyType, DeviceModel, DeviceVendor, DiscoveredDevice } from '@/api/types';
import type { SelectOption } from '@/ui/Field';

export function macValid(raw: string): boolean {
  return /^[0-9a-f]{12}$/.test(raw.toLowerCase().replace(/[:\-\s]/g, ''));
}

export function extensionOptions(extensions: { id: string; number: string; name: string; webrtc: boolean }[], keepId?: string): SelectOption[] {
  return extensions
    .filter((e) => !e.webrtc || e.id === keepId)
    .map((e) => ({ value: e.id, label: `${e.number} — ${e.name}` }));
}

export function deviceModelOptions(models: DeviceModel[]): SelectOption[] {
  return models.map((m) => ({ value: m.model, label: `${m.model} (${m.keys})` }));
}

export function modelsForVendor(models: DeviceModel[], vendor: DeviceVendor): DeviceModel[] {
  return models.filter((m) => m.vendor === vendor);
}

// ── «Topilgan qurilma»ni ichki raqamga biriktirish ──────────────────────────────────────────

export type AssignFormState = { extensionId: string; model: string; label: string };
const EMPTY_ASSIGN_FORM: AssignFormState = { extensionId: '', model: '', label: '' };

export function effectiveVendor(device: DiscoveredDevice | null): DeviceVendor {
  return device?.vendor ?? 'yealink';
}

export function assignModalDescription(
  t: (key: string, options?: Record<string, unknown>) => string, device: DiscoveredDevice | null,
): string | undefined {
  if (!device) return undefined;
  return t('discovered.assignModalDesc', { mac: device.mac, model: device.model ?? effectiveVendor(device) });
}

export function canSubmitAssign(device: DiscoveredDevice | null, state: AssignFormState): boolean {
  return !!device && !!state.extensionId && !!state.model;
}

export function assignPayload(state: AssignFormState): { extension_id: string; model: string; label: string | undefined } {
  return { extension_id: state.extensionId, model: state.model, label: state.label.trim() || undefined };
}

/** `device` (topilgan MAC) har ochilishda oʻzgarishi mumkin — formani shunga moslab qayta ishga tushiradi. */
export function useAssignForm(device: DiscoveredDevice | null) {
  const [state, setState] = useState<AssignFormState>(EMPTY_ASSIGN_FORM);
  const [lastMac, setLastMac] = useState<string | undefined>(undefined);
  if (device && device.mac !== lastMac) {
    setLastMac(device.mac);
    setState({ ...EMPTY_ASSIGN_FORM, model: device.model ?? '' });
  }
  const reset = () => { setState(EMPTY_ASSIGN_FORM); setLastMac(undefined); };
  const setExtensionId = (v: string) => setState((prev) => ({ ...prev, extensionId: v }));
  const setModel = (v: string) => setState((prev) => ({ ...prev, model: v }));
  const setLabel = (v: string) => setState((prev) => ({ ...prev, label: v }));
  return { state, setExtensionId, setModel, setLabel, reset };
}

// ── Yangi apparat qoʻshish ───────────────────────────────────────────────────────────────────

export type DeviceFormState = { vendor: DeviceVendor; model: string; mac: string; extensionId: string; label: string };
export function emptyForm(fixedExtensionId?: string): DeviceFormState {
  return { vendor: 'yealink', model: '', mac: '', extensionId: fixedExtensionId ?? '', label: '' };
}

export function createDeviceValid(form: DeviceFormState, macOk: boolean): boolean {
  return macOk && !!form.model && !!form.extensionId;
}

/** MAC maydonining xatosi — mutatsiyadan kelgan maydon xatosi birinchi, aks holda mahalliy format tekshiruvi. */
export function macFieldError(
  errorField: string | undefined, errorMessage: string | undefined, mac: string, macOk: boolean, hint: string,
): string | undefined {
  if (errorField === 'mac') return errorMessage;
  if (mac && !macOk) return hint;
  return undefined;
}

export function createDevicePayload(form: DeviceFormState): {
  mac: string; vendor: DeviceVendor; model: string; extension_id: string; label: string | undefined;
} {
  return { mac: form.mac, vendor: form.vendor, model: form.model, extension_id: form.extensionId, label: form.label.trim() || undefined };
}

// ── Apparatni tahrirlash ─────────────────────────────────────────────────────────────────────

export type EditDeviceFormState = { label: string; extensionId: string; enabled: boolean };

function editDeviceFormState(device: Device | null): EditDeviceFormState {
  return { label: device?.label ?? '', extensionId: device?.extension?.id ?? '', enabled: device?.enabled ?? true };
}

export function currentExtensionId(device: Device | null): string | undefined {
  return device?.extension?.id;
}

export function editDevicePayload(form: EditDeviceFormState, device: Device): {
  label: string; extension_id: string; enabled: boolean; updated_at: string;
} {
  return { label: form.label.trim(), extension_id: form.extensionId, enabled: form.enabled, updated_at: device.updated_at };
}

/** `device` prop har ochilishda boshqa apparatga almashishi mumkin — formani shunga moslab qayta ishga tushiradi. */
export function useEditDeviceForm(device: Device | null) {
  const [state, setState] = useState<EditDeviceFormState>(() => editDeviceFormState(device));
  const [lastId, setLastId] = useState(device?.id);
  if (device?.id !== lastId) {
    setLastId(device?.id);
    setState(editDeviceFormState(device));
  }
  const setLabel = (v: string) => setState((prev) => ({ ...prev, label: v }));
  const setExtensionId = (v: string) => setState((prev) => ({ ...prev, extensionId: v }));
  const setEnabled = (v: boolean) => setState((prev) => ({ ...prev, enabled: v }));
  return { state, setLabel, setExtensionId, setEnabled };
}

// ── BLF/dastur tugmalari (KeysModal) ─────────────────────────────────────────────────────────

export function nextIdx(rows: DeviceKey[]): number {
  return rows.length + 1;
}

export function updateKeyRow(rows: DeviceKey[], i: number, patch: Partial<DeviceKey>): DeviceKey[] {
  return rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r));
}

export function addKeyRow(rows: DeviceKey[], limit: number): DeviceKey[] {
  if (rows.length >= limit) return rows;
  return [...rows, { idx: nextIdx(rows), type: 'blf', value: '', label: '' }];
}

export function removeKeyRow(rows: DeviceKey[], i: number): DeviceKey[] {
  return rows.filter((_, idx) => idx !== i).map((r, idx) => ({ ...r, idx: idx + 1 }));
}

export function normalizeKeysForSubmit(rows: DeviceKey[]): DeviceKey[] {
  return rows.map((r) => ({ ...r, value: r.value?.trim() || null, label: r.label?.trim() || null }));
}

export function keysLimitFor(models: DeviceModel[], device: Device | null): number {
  if (!device) return 0;
  const match = models.find((m) => m.vendor === device.vendor && m.model === device.model);
  return match?.keys ?? 0;
}

export function keysModalTitle(t: (key: string, options?: Record<string, unknown>) => string, device: Device | null): string {
  if (!device) return '';
  return t('keysModal.title', { label: device.label ?? device.mac });
}

export function keyTypeOptions(t: (key: string) => string, keyTypes: DeviceKeyType[]): SelectOption[] {
  return keyTypes.map((kt) => ({ value: kt, label: t(`keysModal.typeOption.${kt}`) }));
}

/** Modal `device` oʻzgarganda (va kalitlar soʻrovi tayyor boʻlganda) qatorlarni serverdan qayta yuklaydi. */
export function useKeysForm(device: Device | null, items: DeviceKey[] | undefined) {
  const [rows, setRows] = useState<DeviceKey[]>([]);
  const [lastId, setLastId] = useState<string | undefined>(undefined);
  if (device && device.id !== lastId && items) {
    setLastId(device.id);
    setRows(items);
  }
  const reset = () => setLastId(undefined);
  return { rows, setRows, reset };
}
