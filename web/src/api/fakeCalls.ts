// Fake klient uchun CDR kengaytirilgan qidiruv filtri — `fake.ts`dagi `listCalls`/`exportCallsCsv`
// ikkisi ham shu sof funksiyadan foydalanadi (bitta joyda — laziness protocol).
import type { Call, CallTextMatchMode, ListCallsParams } from './types';
import { csvCell } from './fakeCampaigns';

function textMatches(value: string, needle: string, mode: CallTextMatchMode): boolean {
  const v = value.toLowerCase();
  const n = needle.toLowerCase();
  if (mode === 'begins') return v.startsWith(n);
  if (mode === 'ends') return v.endsWith(n);
  if (mode === 'exact') return v === n;
  return v.includes(n);
}

/** `src`/`dst`/`did` uchang umumiy: qiymat + rejim + inkor (`_not`). Bo'sh needle — filtr yo'q. */
function textFieldOk(value: string, needle: string | undefined, mode: CallTextMatchMode | undefined, not: boolean | undefined): boolean {
  if (!needle) return true;
  const hit = textMatches(value, needle, mode ?? 'contains');
  return not ? !hit : hit;
}

/** Qo'ng'iroq berilgan CDR filtriga mos keladimi — sana/yo'nalish/qidiruv allaqachon chaqiruvchida tekshirilgan. */
export function matchesCallFilters(c: Call, p: ListCallsParams): boolean {
  if (!textFieldOk(c.src, p.src, p.src_mode, p.src_not)) return false;
  if (!textFieldOk(c.dst, p.dst, p.dst_mode, p.dst_not)) return false;
  if (!textFieldOk(c.did ?? '', p.did, p.did_mode, p.did_not)) return false;
  if (p.name && !(c.src_name ?? '').toLowerCase().includes(p.name.toLowerCase())) return false;
  if (p.ext && c.src !== p.ext && c.dst !== p.ext) return false;
  if (p.trunk && c.trunk !== p.trunk) return false;
  if (p.account && !(c.pin_label ?? '').toLowerCase().includes(p.account.toLowerCase())) return false;
  if (p.disposition) {
    const allowed = p.disposition.split(',').map((d) => d.trim()).filter(Boolean);
    if (allowed.length > 0 && !allowed.includes(c.disposition)) return false;
  }
  if (p.min_duration !== undefined && c.duration < p.min_duration) return false;
  if (p.max_duration !== undefined && c.duration > p.max_duration) return false;
  if (p.recording === 'with' && c.recordings.length === 0) return false;
  if (p.recording === 'without' && c.recordings.length > 0) return false;
  return true;
}

const CSV_HEADER = ['started_at', 'direction', 'src', 'src_name', 'dst', 'did', 'disposition', 'duration', 'trunk', 'pin_label'];

/** Qo'ng'iroqlar roʻyxatini `export.csv` javobidagi kabi matnga aylantiradi (bitta joyda — haqiqiy backend ham shu ustunlarni beradi). */
export function callsToCsv(items: Call[]): string {
  const rows = items.map((c) => [
    c.started_at, c.direction, c.src, c.src_name, c.dst, c.did, c.disposition, c.duration, c.trunk, c.pin_label,
  ].map(csvCell).join(','));
  return [CSV_HEADER.join(','), ...rows].join('\n') + '\n';
}
