// M6 — fake API uchun kampaniyalar ombori (xotirada). Backend `api/v1/campaigns.py` bilan bir xil kodlar,
// `field` va holat o'tishlari; dialer simulyatsiyasi — har o'qishda ishlayotgan kampaniya bir qadam oldinga.
import {
  MAX_CONTACTS, MAX_CSV_BYTES, campaignShapeError, canEditCampaign, canImportContacts, parseContactsCsv,
} from '@/domain/campaigns';
import { ApiError } from './errors';
import type {
  Campaign, CampaignAction, CampaignContact, CampaignFields, CampaignStats, CampaignStatus, CreateCampaignPayload,
  ImportCampaignContactsPayload, ImportCampaignContactsResult, ListCampaignContactsParams, UpdateCampaignPayload,
} from './types';

export type CampaignStoreDeps = {
  /** Ruxsat (`pbx.manage`) — yo'q bo'lsa 403 tashlaydi. */
  requireManage: () => void;
  /** Audio nomi; topilmasa — `undefined`. */
  audioName: (id: string) => string | undefined;
  /** Ichki raqam / navbat / guruh raqamlari (`target_number` uchun). */
  dialNumbers: () => ReadonlySet<string>;
  blacklist: () => ReadonlySet<string>;
  audit: (action: 'create' | 'update' | 'delete', id: string, label: string, diff: Record<string, unknown>) => void;
  now?: () => Date;
};

type Row = Omit<Campaign, 'stats' | 'audio_name'>;

const EDITABLE: (keyof CampaignFields)[] = [
  'name', 'mode', 'audio_id', 'target_number', 'dtmf_connect', 'dtmf_optout', 'callerid', 'max_concurrent',
  'max_attempts', 'retry_delay_s', 'ring_seconds', 'window_start', 'window_end', 'days',
];

const TRANSITIONS: Record<CampaignAction, [CampaignStatus[], CampaignStatus]> = {
  start: [['draft', 'paused'], 'running'],
  pause: [['running'], 'paused'],
  stop: [['draft', 'running', 'paused'], 'stopped'],
};

const OPEN = new Set(['pending', 'retry', 'dialing']);
const NOT_FOUND = 'Kampaniya topilmadi';

function fail(status: number, code: string, message: string, field?: string): never {
  throw new ApiError(status, { code, message, ...(field ? { field } : {}) });
}

const NUMBER_PATTERNS: [keyof CampaignFields, RegExp][] = [['target_number', /^[0-9]{2,15}$/], ['callerid', /^[0-9]{3,15}$/]];
const RANGES: [keyof CampaignFields, number, number][] = [
  ['max_concurrent', 1, 30], ['max_attempts', 1, 5], ['retry_delay_s', 60, 86400], ['ring_seconds', 10, 30],
];

const validName = (name: string) => name.trim() !== '' && name.trim().length <= 80;
const inRange = (v: unknown, min: number, max: number) => Number.isInteger(v) && Number(v) >= min && Number(v) <= max;

/** Pydantic `CampaignFields` cheklovlari — birinchi buzilgan maydon yoki null. */
function typeErrorField(f: CampaignFields): string | null {
  if (!validName(f.name)) return 'name';
  const pattern = NUMBER_PATTERNS.find(([key, re]) => f[key] !== null && !re.test(String(f[key])));
  const range = RANGES.find(([key, min, max]) => !inRange(f[key], min, max));
  const field = pattern?.[0] ?? range?.[0] ?? null;
  return field ?? (inRange(f.days.length, 1, 7) ? null : 'days');
}

/** 422 `validation_error`, `field` — maydon nomi. */
function checkTypes(f: CampaignFields): void {
  const field = typeErrorField(f);
  if (field) fail(422, 'validation_error', 'Soʻrov maʼlumotlari yaroqsiz', field);
}

const blank = (v: string | null | undefined) => (v ?? '').trim() || null;

function normalized(f: CampaignFields): CampaignFields {
  return { ...f, name: f.name.trim(), audio_id: blank(f.audio_id), target_number: blank(f.target_number), callerid: blank(f.callerid) };
}

function emptyStats(): CampaignStats {
  return { total: 0, pending: 0, dialing: 0, retry: 0, done: 0, failed: 0, skipped: 0, connected: 0, optout: 0 };
}

/** To'xtatish yakuniy — terilmagan (pending/retry) kontaktlar skipped/STOPPED bo'ladi (backend bilan bir xil). */
function closeOpen(list: readonly CampaignContact[]): CampaignContact[] {
  return list.map((c) => (c.status === 'pending' || c.status === 'retry'
    ? { ...c, status: 'skipped', result: 'STOPPED', next_attempt_at: null }
    : c));
}

function statsOf(contacts: readonly CampaignContact[]): CampaignStats {
  const s = emptyStats();
  contacts.forEach((c) => {
    s[c.status] += 1;
    s.total += 1;
    if (c.key === '1') s.connected += 1;
    if (c.key === '9') s.optout += 1;
  });
  return s;
}

/** Deterministik «natija»: raqamning oxirgi raqami bo'yicha (sinovda takrorlanadi). */
function simulatedResult(number: string): { result: string; billsec: number; key: string | null } {
  const last = Number(number.slice(-1));
  if (last === 3) return { result: 'BUSY', billsec: 0, key: null };
  if (last === 7) return { result: 'NOANSWER', billsec: 0, key: null };
  return { result: 'ANSWER', billsec: 8 + last * 3, key: last === 1 ? '1' : last === 9 ? '9' : null };
}

type SeedInput = { fields: CampaignFields; status: CampaignStatus; csv: string; ticks: number; at: string };
type ImportReport = Omit<ImportCampaignContactsResult, 'item'>;

function settled(row: Row, c: CampaignContact, at: string): CampaignContact {
  const r = simulatedResult(c.number);
  const attempts = c.attempts + 1;
  const answered = r.result === 'ANSWER';
  const retry = attempts < row.max_attempts ? 'retry' : 'failed';
  const status = !answered ? retry : r.key === '9' ? 'skipped' : 'done';
  return {
    ...c, attempts, status, last_attempt_at: at, next_attempt_at: status === 'retry' ? at : null,
    result: r.key === '9' ? 'OPTOUT' : r.result, billsec: answered ? r.billsec : null, key: r.key,
  };
}

/** Xotiradagi ombor: har metod — backend endpoint'i (ruxsat, 404/409/422 kodlari bir xil). */
class CampaignStore {
  private rows: Row[] = [];
  private readonly contacts = new Map<string, CampaignContact[]>();
  private readonly optouts = new Set<string>();
  private seq = 0;
  private contactSeq = 0;
  private readonly now: () => Date;

  constructor(private readonly deps: CampaignStoreDeps) {
    this.now = deps.now ?? (() => new Date());
  }

  private listOf(id: string): CampaignContact[] {
    return this.contacts.get(id) ?? [];
  }

  private out(row: Row): Campaign {
    const audioName = row.audio_id ? this.deps.audioName(row.audio_id) ?? null : null;
    return { ...row, audio_name: audioName, stats: statsOf(this.listOf(row.id)) };
  }

  private find(id: string): Row {
    return this.rows.find((r) => r.id === id) ?? fail(404, 'not_found', NOT_FOUND);
  }

  private validate(f: CampaignFields, excludeId?: string): void {
    checkTypes(f);
    const shape = campaignShapeError(f);
    if (shape) fail(422, shape.code, 'Kampaniya sozlamasi notoʻgʻri', shape.field);
    if (f.audio_id && this.deps.audioName(f.audio_id) === undefined) fail(422, 'campaign_bad_audio', 'Audio topilmadi', 'audio_id');
    if (f.target_number && !this.deps.dialNumbers().has(f.target_number)) {
      fail(422, 'campaign_bad_target', 'Bunday ichki raqam/navbat/guruh raqami yoʻq', 'target_number');
    }
    if (this.rows.some((r) => r.name === f.name && r.id !== excludeId)) fail(422, 'name_taken', 'Bu nomli kampaniya bor', 'name');
  }

  private save(row: Row): Row {
    const exists = this.rows.some((r) => r.id === row.id);
    this.rows = exists ? this.rows.map((r) => (r.id === row.id ? row : r)) : [row, ...this.rows];
    return row;
  }

  private requireEditable(row: Row): void {
    if (!canEditCampaign(row.status)) fail(409, 'campaign_running', 'Kampaniya ishlayapti — avval toʻxtatib turing');
  }

  /** Bir qadam: `max_concurrent` tagacha ochiq kontakt yakunlanadi; ochiq qolmasa — `completed`. */
  private tick(row: Row): Row {
    if (row.status !== 'running') return row;
    const at = this.now().toISOString();
    const open = this.listOf(row.id).filter((c) => OPEN.has(c.status)).slice(0, row.max_concurrent);
    const next = new Map(open.map((c) => [c.id, settled(row, c, at)]));
    next.forEach((c) => { if (c.key === '9') this.optouts.add(c.number); });
    const list = this.listOf(row.id).map((c) => next.get(c.id) ?? c);
    this.contacts.set(row.id, list);
    if (list.some((c) => OPEN.has(c.status))) return row;
    return this.save({ ...row, status: 'completed', finished_at: at, updated_at: at });
  }

  private skipReason(number: string): string | null {
    if (this.deps.blacklist().has(number)) return 'BLACKLIST';
    return this.optouts.has(number) ? 'OPTOUT' : null;
  }

  private addContacts(row: Row, csv: string): ImportReport {
    const list = this.listOf(row.id);
    const parsed = parseContactsCsv(csv, list.map((c) => c.number));
    if (list.length + parsed.rows.length > MAX_CONTACTS) {
      fail(422, 'csv_too_many', `Kampaniyada ${MAX_CONTACTS} dan ortiq kontakt boʻlmaydi`, 'csv');
    }
    const added = parsed.rows.map(({ number, name }): CampaignContact => {
      const reason = this.skipReason(number);
      this.contactSeq += 1;
      return {
        id: this.contactSeq, number, name, status: reason ? 'skipped' : 'pending', result: reason, attempts: 0,
        billsec: null, key: null, next_attempt_at: null, last_attempt_at: null,
      };
    });
    this.contacts.set(row.id, [...list, ...added]);
    const skipped = added.filter((c) => c.status === 'skipped').length;
    return { added: added.length - skipped, duplicates: parsed.duplicates, skipped, invalid_count: parsed.invalid_count, invalid: parsed.invalid };
  }

  private insert(fields: CampaignFields, at: string): Row {
    this.seq += 1;
    return this.save({ ...fields, id: `cmp-${this.seq}`, status: 'draft', started_at: null, finished_at: null, created_at: at, updated_at: at });
  }

  seed(input: SeedInput): void {
    const row = this.insert(input.fields, input.at);
    this.addContacts(row, input.csv);
    let cur = this.save({ ...row, status: 'running', started_at: input.at });
    for (let i = 0; i < input.ticks; i += 1) cur = this.tick(cur);
    if (cur.status === 'running' && input.status !== 'running') this.save({ ...cur, status: input.status });
  }

  async listCampaigns(): Promise<{ items: Campaign[] }> {
    this.deps.requireManage();
    this.rows.forEach((r) => this.tick(r));
    return { items: this.rows.map((r) => this.out(r)) };
  }

  async getCampaign(id: string): Promise<{ item: Campaign }> {
    this.deps.requireManage();
    return { item: this.out(this.tick(this.find(id))) };
  }

  async createCampaign(payload: CreateCampaignPayload): Promise<{ item: Campaign }> {
    this.deps.requireManage();
    const f = normalized(payload);
    this.validate(f);
    const row = this.insert(f, this.now().toISOString());
    this.deps.audit('create', row.id, row.name, { op: 'create', name: row.name });
    return { item: this.out(row) };
  }

  async updateCampaign(id: string, payload: UpdateCampaignPayload): Promise<{ item: Campaign }> {
    this.deps.requireManage();
    const row = this.find(id);
    this.requireEditable(row);
    if (payload.updated_at !== row.updated_at) fail(409, 'stale', 'Kampaniya boshqa joyda oʻzgartirilgan');
    const { updated_at: _ignored, ...changes } = payload;
    const f = normalized({ ...fieldsOf(row), ...changes });
    this.validate(f, id);
    const next = this.save({ ...row, ...f, updated_at: this.now().toISOString() });
    this.deps.audit('update', id, next.name, { op: 'update', name: next.name });
    return { item: this.out(next) };
  }

  async deleteCampaign(id: string): Promise<void> {
    this.deps.requireManage();
    const row = this.find(id);
    this.requireEditable(row);
    this.rows = this.rows.filter((r) => r.id !== id);
    this.contacts.delete(id);
    this.deps.audit('delete', id, row.name, { op: 'delete', name: row.name });
  }

  async campaignAction(id: string, action: CampaignAction): Promise<{ item: Campaign }> {
    this.deps.requireManage();
    const row = this.find(id);
    const [allowed, status] = TRANSITIONS[action] ?? fail(404, 'not_found', 'Amal topilmadi');
    if (!allowed.includes(row.status)) fail(409, 'campaign_bad_state', `Bu holatda (${row.status}) amal bajarilmaydi`);
    if (action === 'start' && !this.listOf(id).some((c) => OPEN.has(c.status))) {
      fail(409, 'campaign_empty', 'Teriladigan kontakt yoʻq — CSV yuklang');
    }
    const at = this.now().toISOString();
    const next = this.save({
      ...row, status, updated_at: at,
      started_at: row.started_at ?? (action === 'start' ? at : null),
      finished_at: status === 'stopped' ? at : row.finished_at,
    });
    if (status === 'stopped') this.contacts.set(id, closeOpen(this.listOf(id)));
    this.deps.audit('update', id, next.name, { op: action, name: next.name });
    return { item: this.out(next) };
  }

  async importCampaignContacts(id: string, payload: ImportCampaignContactsPayload): Promise<ImportCampaignContactsResult> {
    this.deps.requireManage();
    const row = this.find(id);
    if (!canImportContacts(row.status)) fail(409, 'campaign_bad_state', 'Tugagan kampaniyaga kontakt qoʻshilmaydi');
    if (new TextEncoder().encode(payload.csv).length > MAX_CSV_BYTES) fail(422, 'csv_too_large', 'CSV 1 MB dan katta', 'csv');
    if (payload.replace) {
      this.requireEditable(row);
      this.contacts.set(id, []);
    }
    const report = this.addContacts(row, payload.csv);
    this.deps.audit('update', id, row.name, { op: 'import', added: report.added, replace: payload.replace });
    return { ...report, item: this.out(row) };
  }

  async listCampaignContacts(id: string, params: ListCampaignContactsParams): Promise<{ items: CampaignContact[]; total: number }> {
    this.deps.requireManage();
    this.tick(this.find(id));
    const filtered = this.listOf(id).filter(contactFilter(params));
    const size = params.page_size ?? 50;
    const start = ((params.page ?? 1) - 1) * size;
    return { items: filtered.slice(start, start + size), total: filtered.length };
  }

  async exportCampaignCsv(id: string): Promise<Blob> {
    this.deps.requireManage();
    this.find(id);
    const lines = this.listOf(id).map((c) => EXPORT_COLUMNS.map((k) => csvCell(c[k])).join(','));
    return new Blob([[EXPORT_COLUMNS.join(','), ...lines].join('\r\n') + '\r\n'], { type: 'text/csv' });
  }
}

const EXPORT_COLUMNS: (keyof CampaignContact)[] = ['number', 'name', 'status', 'result', 'attempts', 'billsec', 'key', 'last_attempt_at'];

const fieldsOf = (row: Row) => Object.fromEntries(EDITABLE.map((k) => [k, row[k]])) as CampaignFields;

function contactFilter(params: ListCampaignContactsParams): (c: CampaignContact) => boolean {
  const q = (params.q ?? '').trim().toLowerCase();
  const byStatus = (c: CampaignContact) => !params.status || c.status === params.status;
  const byText = (c: CampaignContact) => !q || c.number.includes(q) || (c.name ?? '').toLowerCase().includes(q);
  return (c) => byStatus(c) && byText(c);
}

const API_METHODS = [
  'listCampaigns', 'getCampaign', 'createCampaign', 'updateCampaign', 'deleteCampaign', 'campaignAction',
  'importCampaignContacts', 'listCampaignContacts', 'exportCampaignCsv',
] as const;

type CampaignApi = Pick<CampaignStore, (typeof API_METHODS)[number]>;

export function createCampaignStore(deps: CampaignStoreDeps): { api: CampaignApi; seed: (input: SeedInput) => void } {
  const store = new CampaignStore(deps);
  const api = Object.fromEntries(API_METHODS.map((m) => [m, store[m].bind(store)])) as CampaignApi;
  return { api, seed: (input) => store.seed(input) };
}

/** Backend `csv_cell` — formula in'ektsiyasidan himoya (`=`, `+`, `-`, `@` bilan boshlansa `'`). */
export function csvCell(value: unknown): string {
  let s = value === null || value === undefined ? '' : String(value);
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}
