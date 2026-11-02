// `ExtensionsPage.tsx` dagi modal/drawer formalarning holati/validatsiyasi/submit logikasi — sof
// funksiyalar va kichik hook'larga ajratilgan, shu bilan komponent funksiyalari faqat JSX'ni tutadi
// (qarang `../devices/deviceForms.ts` izohi — bir xil naqsh).
import { useState } from 'react';
import type { CreateExtensionPayload, Extension, RecordingPolicy, UpdateExtensionPayload } from '@/api/types';
import { validateSipPassword } from '@/domain/sipPassword';

// M2a — qarang ../../../replica/m2a-contract.md §1
export const FORWARD_NUMBER_RE = /^\+?[0-9]{2,15}$/;
export const PICKUP_GROUP_RE = /^[a-z0-9_-]{1,32}$/;

export function forwardNumberValid(v: string): boolean {
  return v.trim() === '' || FORWARD_NUMBER_RE.test(v.trim());
}

export function pickupGroupValid(v: string): boolean {
  return v.trim() === '' || PICKUP_GROUP_RE.test(v.trim());
}

// ── Qo'ng'iroq sozlamalari (DND/yo'naltirish/pickup/chiquvchi) — Yaratish VA Tahrirlashda bitta komponent ──

export type CallSettingsState = {
  dnd: boolean; forwardAlways: string; forwardBusy: string; pickupGroup: string;
  outboundAllowed: boolean; outboundCallerid: string;
};

export const DEFAULT_CALL_SETTINGS: CallSettingsState = {
  dnd: false, forwardAlways: '', forwardBusy: '', pickupGroup: '', outboundAllowed: true, outboundCallerid: '',
};

export function callSettingsFromExtension(ext: Extension): CallSettingsState {
  return {
    dnd: ext.dnd, forwardAlways: ext.forward_always ?? '', forwardBusy: ext.forward_busy ?? '',
    pickupGroup: ext.pickup_group ?? '', outboundAllowed: ext.outbound_allowed, outboundCallerid: ext.outbound_callerid ?? '',
  };
}

export function callSettingsValid(s: CallSettingsState): boolean {
  return forwardNumberValid(s.forwardAlways) && forwardNumberValid(s.forwardBusy) && pickupGroupValid(s.pickupGroup) && forwardNumberValid(s.outboundCallerid);
}

/** Bitta obyekt holatidagi qo'ng'iroq sozlamalari — har bir maydon uchun alohida `useState` yozishdan qochish uchun. */
export function useCallSettings(initial: CallSettingsState) {
  const [state, setState] = useState<CallSettingsState>(initial);
  return {
    state,
    setState,
    setDnd: (v: boolean) => setState((p) => ({ ...p, dnd: v })),
    setForwardAlways: (v: string) => setState((p) => ({ ...p, forwardAlways: v })),
    setForwardBusy: (v: string) => setState((p) => ({ ...p, forwardBusy: v })),
    setPickupGroup: (v: string) => setState((p) => ({ ...p, pickupGroup: v })),
    setOutboundAllowed: (v: boolean) => setState((p) => ({ ...p, outboundAllowed: v })),
    setOutboundCallerid: (v: string) => setState((p) => ({ ...p, outboundCallerid: v })),
  };
}

// ── Yangi ichki raqam yaratish ────────────────────────────────────────────────────────────────

// M3c §1 — kiruvchi/chiquvchi yozib olish siyosati MUSTAQIL (shu raqamga kelgan / shu raqamdan
// chiqqan qo'ng'iroq); backend `recording_in`/`recording_out`ga mos.
export type CreateExtensionFields = {
  number: string; name: string; password: string; webrtc: boolean;
  recordingIn: RecordingPolicy; recordingOut: RecordingPolicy; calls: CallSettingsState;
};

export function createExtensionValid(f: CreateExtensionFields): boolean {
  return f.name.trim().length > 0 && validateSipPassword(f.password, f.number.trim()) === null && callSettingsValid(f.calls);
}

export function createExtensionPayload(f: CreateExtensionFields): CreateExtensionPayload {
  return {
    number: f.number.trim() || undefined,
    name: f.name.trim(),
    password: f.password,
    webrtc: f.webrtc,
    recording_in: f.recordingIn,
    recording_out: f.recordingOut,
    dnd: f.calls.dnd,
    forward_always: f.calls.forwardAlways.trim() || undefined,
    forward_busy: f.calls.forwardBusy.trim() || undefined,
    pickup_group: f.calls.pickupGroup.trim() || undefined,
    outbound_allowed: f.calls.outboundAllowed,
    outbound_callerid: f.calls.outboundCallerid.trim() || undefined,
  };
}

// ── Mavjud ichki raqamni tahrirlash ──────────────────────────────────────────────────────────

export type EditExtensionFields = {
  name: string; enabled: boolean; webrtc: boolean;
  recordingIn: RecordingPolicy; recordingOut: RecordingPolicy; calls: CallSettingsState;
};

export function editExtensionFieldsFromExtension(ext: Extension): EditExtensionFields {
  return {
    name: ext.name, enabled: ext.enabled, webrtc: ext.webrtc,
    recordingIn: ext.recording_in, recordingOut: ext.recording_out, calls: callSettingsFromExtension(ext),
  };
}

export function editExtensionValid(f: EditExtensionFields): boolean {
  return f.name.trim().length > 0 && callSettingsValid(f.calls);
}

export function editExtensionDirty(f: EditExtensionFields, ext: Extension): boolean {
  const base = editExtensionFieldsFromExtension(ext);
  return f.name !== base.name || f.enabled !== base.enabled || f.webrtc !== base.webrtc
    || f.recordingIn !== base.recordingIn || f.recordingOut !== base.recordingOut
    || (Object.keys(f.calls) as (keyof CallSettingsState)[]).some((k) => f.calls[k] !== base.calls[k]);
}

function trimmedOrNull(v: string): string | null {
  return v.trim() || null;
}

/** `payload[key]` faqat `next` qiymat `prev`dan farq qilsa yoziladi — o'zgarmagan maydonlar yuborilmaydi. */
function setIfChanged<K extends keyof UpdateExtensionPayload>(
  payload: UpdateExtensionPayload, key: K, next: UpdateExtensionPayload[K], prev: UpdateExtensionPayload[K],
): void {
  if (next !== prev) payload[key] = next;
}

// Faqat haqiqatan o'zgargan maydonlar yuboriladi — §1: agar FAQAT dnd/forward/pickup/chiquvchi o'zgarsa,
// backend realtime-only apply qaytaradi (name/enabled bo'lmasa). To'liq payload yuborish bu holatni yo'qqa chiqarardi.
export function updateExtensionPayload(f: EditExtensionFields, ext: Extension): UpdateExtensionPayload {
  const payload: UpdateExtensionPayload = { updated_at: ext.updated_at };
  setIfChanged(payload, 'name', f.name.trim(), ext.name);
  setIfChanged(payload, 'enabled', f.enabled, ext.enabled);
  setIfChanged(payload, 'webrtc', f.webrtc, ext.webrtc);
  setIfChanged(payload, 'recording_in', f.recordingIn, ext.recording_in);
  setIfChanged(payload, 'recording_out', f.recordingOut, ext.recording_out);
  setIfChanged(payload, 'dnd', f.calls.dnd, ext.dnd);
  setIfChanged(payload, 'forward_always', trimmedOrNull(f.calls.forwardAlways), ext.forward_always ?? null);
  setIfChanged(payload, 'forward_busy', trimmedOrNull(f.calls.forwardBusy), ext.forward_busy ?? null);
  setIfChanged(payload, 'pickup_group', trimmedOrNull(f.calls.pickupGroup), ext.pickup_group ?? null);
  setIfChanged(payload, 'outbound_allowed', f.calls.outboundAllowed, ext.outbound_allowed);
  setIfChanged(payload, 'outbound_callerid', trimmedOrNull(f.calls.outboundCallerid), ext.outbound_callerid ?? null);
  return payload;
}
