// CDR kengaytirilgan qidiruv — forma holati (UI) va `ListCallsParams` (API) orasidagi sof aylanma.
// Hech qanday React/DOM yo'q — `CallsPage.tsx` va `AdvancedSearchPanel.tsx` shu yerdan foydalanadi.
import type { CallDisposition, CallRecordingFilter, CallTextMatchMode, ListCallsParams } from '@/api/types';

export type { CallRecordingFilter, CallTextMatchMode };

export type AdvancedSearchForm = {
  src: string; srcMode: CallTextMatchMode; srcNot: boolean;
  dst: string; dstMode: CallTextMatchMode; dstNot: boolean;
  did: string; didMode: CallTextMatchMode; didNot: boolean;
  name: string;
  ext: string;
  trunk: string;
  account: string;
  disposition: CallDisposition[];
  minDuration: string;
  maxDuration: string;
  recording: CallRecordingFilter;
};

export const EMPTY_ADVANCED_SEARCH: AdvancedSearchForm = {
  src: '', srcMode: 'contains', srcNot: false,
  dst: '', dstMode: 'contains', dstNot: false,
  did: '', didMode: 'contains', didNot: false,
  name: '', ext: '', trunk: '', account: '',
  disposition: [], minDuration: '', maxDuration: '', recording: 'any',
};

type TextFieldKey = 'src' | 'dst' | 'did';

/** `src`/`dst`/`did` uchun umumiy: qiymat + rejim (sukut `contains` yuborilmaydi) + inkor. */
function applyTextField(out: Partial<ListCallsParams>, key: TextFieldKey, value: string, mode: CallTextMatchMode, not: boolean): void {
  const trimmed = value.trim();
  if (!trimmed) return;
  const bag = out as unknown as Record<string, unknown>;
  bag[key] = trimmed;
  if (mode !== 'contains') bag[`${key}_mode`] = mode;
  if (not) bag[`${key}_not`] = true;
}

/** Butun, manfiy bo'lmagan soniya — bo'sh yoki yaroqsiz matn `undefined` qaytaradi. */
function parseDurationSec(raw: string): number | undefined {
  const trimmed = raw.trim();
  if (!trimmed) return undefined;
  const n = Number(trimmed);
  return Number.isInteger(n) && n >= 0 ? n : undefined;
}

/** Forma holatidan `ListCallsParams`ga — bo'sh maydonlar va sukut qiymatlar YUBORILMAYDI. */
export function buildAdvancedParams(form: AdvancedSearchForm): Partial<ListCallsParams> {
  const out: Partial<ListCallsParams> = {};
  applyTextField(out, 'src', form.src, form.srcMode, form.srcNot);
  applyTextField(out, 'dst', form.dst, form.dstMode, form.dstNot);
  applyTextField(out, 'did', form.did, form.didMode, form.didNot);

  const name = form.name.trim();
  if (name) out.name = name;
  const ext = form.ext.trim();
  if (ext) out.ext = ext;
  const trunk = form.trunk.trim();
  if (trunk) out.trunk = trunk;
  const account = form.account.trim();
  if (account) out.account = account;

  if (form.disposition.length > 0) out.disposition = form.disposition.join(',');

  const minDuration = parseDurationSec(form.minDuration);
  if (minDuration !== undefined) out.min_duration = minDuration;
  const maxDuration = parseDurationSec(form.maxDuration);
  if (maxDuration !== undefined) out.max_duration = maxDuration;

  if (form.recording !== 'any') out.recording = form.recording;

  return out;
}

/** Tugmadagi badge uchun — nechta mustaqil filtr guruhi faol (rejim/inkor alohida hisoblanmaydi). */
export function countActiveFilters(form: AdvancedSearchForm): number {
  let n = 0;
  if (form.src.trim()) n += 1;
  if (form.dst.trim()) n += 1;
  if (form.did.trim()) n += 1;
  if (form.name.trim()) n += 1;
  if (form.ext.trim()) n += 1;
  if (form.trunk.trim()) n += 1;
  if (form.account.trim()) n += 1;
  if (form.disposition.length > 0) n += 1;
  if (parseDurationSec(form.minDuration) !== undefined) n += 1;
  if (parseDurationSec(form.maxDuration) !== undefined) n += 1;
  if (form.recording !== 'any') n += 1;
  return n;
}
