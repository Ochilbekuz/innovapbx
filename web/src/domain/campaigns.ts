// M6 — kampaniyalar (S18) uchun sof qoidalar: backend `services/campaign_rules.py` (CSV tahlili, ish oynasi)
// va `services/campaigns.py` (`_check_*`, holat o'tishlari) bilan BIR XIL. UI ham, fake API ham shuni ishlatadi.
import type {
  Campaign, CampaignAction, CampaignFields, CampaignStats, CampaignStatus, CreateCampaignPayload, UpdateCampaignPayload,
} from '@/api/types';

export const MAX_INVALID_REPORTED = 50;
export const MAX_CONTACTS = 50_000;
export const MAX_CSV_BYTES = 1_000_000;

const NUMBER_RE = /^[0-9]{3,15}$/;
const NUMBER_CHARS = /^[+0-9 ()\-.]+$/;

export type ParsedCsv = {
  rows: { number: string; name: string | null }[];
  invalid: { line: number; value: string }[];
  invalid_count: number;
  duplicates: number;
};

/** `+998 (90) 111-22-33` → `998901112233`; raqam emas yoki 3..15 dan tashqari → null. */
export function parseNumber(raw: string): string | null {
  const value = raw.trim();
  if (!NUMBER_CHARS.test(value)) return null;
  const digits = value.replace(/[^0-9]/g, '');
  return NUMBER_RE.test(digits) ? digits : null;
}

const count = (line: string, ch: string) => line.split(ch).length - 1;
/** Python `campaign_rules`: `;` ko'p bo'lsa — `;`, aks holda (teng ham) — `,`. */
export const csvDelimiter = (line: string) => (count(line, ';') > count(line, ',') ? ';' : ',');

/** Python `csv.reader` ning bitta qatorli soddalashtirilgani: qo'shtirnoqli katak, `""` — qo'shtirnoq. */
type CsvState = { cells: string[]; cell: string; quoted: boolean };

/** Qo'shtirnoq: `""` qo'shtirnoq ichida — belgi (2 ta iste'mol), katak boshida/ichida — rejim almashadi, o'rtada — oddiy belgi. */
function quoteStep(s: CsvState, next: string): number {
  if (s.quoted && next === '"') { s.cell += '"'; return 2; }
  if (s.quoted || s.cell === '') s.quoted = !s.quoted;
  else s.cell += '"';
  return 1;
}

function csvStep(s: CsvState, ch: string, next: string, delimiter: string): number {
  if (ch === '"') return quoteStep(s, next);
  if (ch === delimiter && !s.quoted) { s.cells.push(s.cell); s.cell = ''; }
  else s.cell += ch;
  return 1;
}

export function splitCsvRow(line: string): string[] {
  const delimiter = csvDelimiter(line);
  const s: CsvState = { cells: [], cell: '', quoted: false };
  for (let i = 0; i < line.length;) i += csvStep(s, line.charAt(i), line.charAt(i + 1), delimiter);
  s.cells.push(s.cell);
  return s.cells;
}

function isHeader(cells: string[]): boolean {
  const first = (cells[0] ?? '').trim();
  return first !== '' && !NUMBER_CHARS.test(first);
}

function cleanName(raw: string | undefined): string | null {
  const name = (raw ?? '').trim().slice(0, 80);
  return name || null;
}

/** 1-ustun raqam, 2-ustun ism. Birinchi qator raqam bo'lmasa — sarlavha. `existing` — kampaniyadagi raqamlar. */
export function parseContactsCsv(text: string, existing: Iterable<string> = []): ParsedCsv {
  const seen = new Set(existing);
  const out: ParsedCsv = { rows: [], invalid: [], invalid_count: 0, duplicates: 0 };
  text.split(/\r\n|\r|\n/).forEach((line, index) => {
    if (!line.trim()) return;
    const cells = splitCsvRow(line);
    if (index === 0 && isHeader(cells)) return;
    const [first = '', name] = cells;
    const number = parseNumber(first);
    if (number === null) {
      out.invalid_count += 1;
      if (out.invalid.length < MAX_INVALID_REPORTED) out.invalid.push({ line: index + 1, value: first.trim().slice(0, 40) });
    } else if (seen.has(number)) {
      out.duplicates += 1;
    } else {
      seen.add(number);
      out.rows.push({ number, name: cleanName(name) });
    }
  });
  return out;
}

const minutes = (hhmm: string) => Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3, 5));
const isoWeekday = (d: Date) => ((d.getUTCDay() + 6) % 7) + 1;

/** `local` — tenant mahalliy vaqti UTC maydonlarida (`TENANT_TZ` siljishi qo'shilgan). Tun oshgan oyna
 * (22:00–02:00): kun — oyna BOSHLANGAN kun. */
export function inWindow(local: Date, start: string, end: string, days: readonly number[]): boolean {
  const now = local.getUTCHours() * 60 + local.getUTCMinutes();
  const [s, e] = [minutes(start), minutes(end)];
  if (s < e) return days.includes(isoWeekday(local)) && s <= now && now < e;
  if (now >= s) return days.includes(isoWeekday(local));
  return now < e && days.includes(isoWeekday(new Date(local.getTime() - 86_400_000)));
}

type ShapeRule = [code: string, field: keyof CampaignFields, broken: (f: CampaignFields) => boolean];

/** Backend `_check_mode/_check_dtmf/_check_schedule` tartibi bilan. */
const SHAPE_RULES: ShapeRule[] = [
  ['campaign_audio_required', 'audio_id', (f) => f.mode === 'message' && !f.audio_id],
  ['campaign_target_required', 'target_number', (f) => f.mode === 'connect' && !f.target_number],
  ['campaign_dtmf_mode', 'dtmf_connect', (f) => f.mode !== 'message' && (f.dtmf_connect || f.dtmf_optout)],
  ['campaign_target_required', 'target_number', (f) => f.dtmf_connect && !f.target_number],
  ['campaign_window', 'window_end', (f) => minutes(f.window_start) === minutes(f.window_end)],
  ['campaign_days', 'days', (f) => new Set(f.days).size !== f.days.length || f.days.some((d) => d < 1 || d > 7)],
];

/** Birinchi buzilgan qoida `{code, field}` yoki null. */
export function campaignShapeError(f: CampaignFields): { code: string; field: string } | null {
  const rule = SHAPE_RULES.find(([, , broken]) => broken(f));
  return rule ? { code: rule[0], field: rule[1] } : null;
}

/** Hal bo'lgan kontaktlar ulushi (0..100); bo'sh kampaniya — 0. */
export function campaignProgress(stats: CampaignStats): number {
  if (stats.total === 0) return 0;
  return Math.floor(((stats.done + stats.failed + stats.skipped) * 100) / stats.total);
}

const ACTIONS_BY_STATUS: Record<CampaignStatus, CampaignAction[]> = {
  draft: ['start', 'stop'],
  running: ['pause', 'stop'],
  paused: ['start', 'stop'],
  completed: [],
  stopped: [],
};

export const campaignActions = (status: CampaignStatus): CampaignAction[] => ACTIONS_BY_STATUS[status];
/** Tahrirlash/o'chirish — ishlayotganida emas (409 `campaign_running`). */
export const canEditCampaign = (status: CampaignStatus) => status !== 'running';
/** Kontakt qo'shish — tugagan/to'xtatilganga emas; `replace` — ishlayotganiga ham emas. */
export const canImportContacts = (status: CampaignStatus) => status !== 'completed' && status !== 'stopped';

/** `[1,2,3,4,5]` → `Du–Ju`; uzilgan bo'lsa vergul bilan. `labels[0]` — dushanba. */
export function formatDays(days: readonly number[], labels: readonly string[]): string {
  const label = (d: number) => labels[d - 1] ?? String(d);
  const groups: { from: number; to: number }[] = [];
  [...days].sort((a, b) => a - b).forEach((d) => {
    const last = groups[groups.length - 1];
    if (last && d === last.to + 1) last.to = d;
    else groups.push({ from: d, to: d });
  });
  return groups
    .map(({ from, to }) => {
      if (to - from >= 2) return `${label(from)}–${label(to)}`;
      return from === to ? label(from) : `${label(from)}, ${label(to)}`;
    })
    .join(', ');
}

export const hhmm = (time: string) => time.slice(0, 5);

export type CampaignForm = Omit<CampaignFields, 'audio_id' | 'target_number' | 'callerid'> & {
  audio_id: string;
  target_number: string;
  callerid: string;
};

export function defaultCampaignForm(): CampaignForm {
  return {
    name: '', mode: 'message', audio_id: '', target_number: '', dtmf_connect: false, dtmf_optout: true, callerid: '',
    max_concurrent: 2, max_attempts: 3, retry_delay_s: 600, ring_seconds: 25,
    window_start: '09:00', window_end: '20:00', days: [1, 2, 3, 4, 5, 6],
  };
}

export function campaignToForm(c: Campaign): CampaignForm {
  return {
    name: c.name, mode: c.mode, audio_id: c.audio_id ?? '', target_number: c.target_number ?? '',
    dtmf_connect: c.dtmf_connect, dtmf_optout: c.dtmf_optout, callerid: c.callerid ?? '',
    max_concurrent: c.max_concurrent, max_attempts: c.max_attempts, retry_delay_s: c.retry_delay_s,
    ring_seconds: c.ring_seconds, window_start: hhmm(c.window_start), window_end: hhmm(c.window_end), days: [...c.days],
  };
}

const blankToNull = (v: string) => v.trim() || null;

/** Forma → POST tanasi. `connect` rejimida audio/DTMF, «1» o'chiq xabarda — ulash raqami yuborilmaydi
 * (yashirin maydon backend 422 bermasin). */
export function formToPayload(form: CampaignForm): CreateCampaignPayload {
  const message = form.mode === 'message';
  return {
    ...form,
    name: form.name.trim(),
    audio_id: message ? blankToNull(form.audio_id) : null,
    target_number: message && !form.dtmf_connect ? null : blankToNull(form.target_number),
    callerid: blankToNull(form.callerid),
    dtmf_connect: message && form.dtmf_connect,
    dtmf_optout: message && form.dtmf_optout,
    days: [...form.days].sort((a, b) => a - b),
  };
}

export function formToUpdate(form: CampaignForm, updatedAt: string): UpdateCampaignPayload {
  return { ...formToPayload(form), updated_at: updatedAt };
}

/** Kun belgisini almashtirish (forma chiplari). */
export function toggleDay(days: readonly number[], day: number): number[] {
  return days.includes(day) ? days.filter((d) => d !== day) : [...days, day].sort((a, b) => a - b);
}
