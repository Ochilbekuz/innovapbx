// M6 — fake kampaniya ombori: backend bilan bir xil kodlar, holat o'tishlari, import va dialer simulyatsiyasi.
import { beforeEach, describe, expect, it } from 'vitest';
import { defaultCampaignForm, formToPayload } from '@/domain/campaigns';
import { ApiError } from './errors';
import { createCampaignStore, csvCell } from './fakeCampaigns';
import type { CreateCampaignPayload } from './types';

const audits: string[] = [];
let allowed = true;
const deps = () => ({
  requireManage: () => { if (!allowed) throw new ApiError(403, { code: 'forbidden', message: 'yoʻq' }); },
  audioName: (id: string) => (id === 'au-1' ? 'Eslatma.wav' : undefined),
  dialNumbers: () => new Set(['600', '101']),
  blacklist: () => new Set(['998900000000']),
  audit: (action: string, _id: string, _label: string, diff: Record<string, unknown>) => { audits.push(`${action}:${String(diff.op)}`); },
  now: () => new Date('2026-11-01T10:00:00Z'),
});

const payload = (p: Partial<CreateCampaignPayload> = {}): CreateCampaignPayload => ({
  ...formToPayload({ ...defaultCampaignForm(), name: 'Eslatma', audio_id: 'au-1' }), ...p,
});

async function failure(promise: Promise<unknown>): Promise<{ status: number; code: string; field?: string }> {
  try {
    await promise;
  } catch (e) {
    expect(e).toBeInstanceOf(ApiError);
    const err = e as ApiError;
    return { status: err.status, code: err.code, ...(err.field ? { field: err.field } : {}) };
  }
  throw new Error('xato kutilgan edi');
}

let store = createCampaignStore(deps());
beforeEach(() => { store = createCampaignStore(deps()); audits.length = 0; allowed = true; });

describe('yaratish validatsiyasi', () => {
  it.each<[Partial<CreateCampaignPayload>, number, string, string]>([
    [{ name: '  ' }, 422, 'validation_error', 'name'],
    [{ target_number: '6' }, 422, 'validation_error', 'target_number'],
    [{ callerid: '12' }, 422, 'validation_error', 'callerid'],
    [{ max_concurrent: 31 }, 422, 'validation_error', 'max_concurrent'],
    [{ max_attempts: 0 }, 422, 'validation_error', 'max_attempts'],
    [{ retry_delay_s: 59 }, 422, 'validation_error', 'retry_delay_s'],
    [{ ring_seconds: 31 }, 422, 'validation_error', 'ring_seconds'],
    [{ days: [] }, 422, 'validation_error', 'days'],
    [{ audio_id: null }, 422, 'campaign_audio_required', 'audio_id'],
    [{ audio_id: 'au-x' }, 422, 'campaign_bad_audio', 'audio_id'],
    [{ dtmf_connect: true, target_number: '999' }, 422, 'campaign_bad_target', 'target_number'],
    [{ window_end: '09:00' }, 422, 'campaign_window', 'window_end'],
  ])('%j → %s', async (p, status, code, field) => {
    expect(await failure(store.api.createCampaign(payload(p)))).toEqual({ status, code, field });
  });

  it('nom band — name_taken; ruxsatsiz — 403', async () => {
    await store.api.createCampaign(payload());
    expect(await failure(store.api.createCampaign(payload()))).toMatchObject({ code: 'name_taken', field: 'name' });
    allowed = false;
    expect((await failure(store.api.listCampaigns())).status).toBe(403);
  });

  it('yaratilgan — draft, audio nomi, bo\'sh statistika, audit', async () => {
    const { item } = await store.api.createCampaign(payload({ callerid: '  ' }));
    expect(item).toMatchObject({ status: 'draft', audio_name: 'Eslatma.wav', callerid: null, stats: { total: 0 } });
    expect(audits).toEqual(['create:create']);
  });
});

describe('holat o\'tishlari va tahrirlash', () => {
  it('bo\'sh kampaniya boshlanmaydi; start → pause → start → stop', async () => {
    const { item } = await store.api.createCampaign(payload());
    expect(await failure(store.api.campaignAction(item.id, 'start'))).toMatchObject({ status: 409, code: 'campaign_empty' });
    expect(await failure(store.api.campaignAction(item.id, 'pause'))).toMatchObject({ status: 409, code: 'campaign_bad_state' });
    await store.api.importCampaignContacts(item.id, { csv: '901112230\n901112237', replace: false });
    const started = (await store.api.campaignAction(item.id, 'start')).item;
    expect(started).toMatchObject({ status: 'running', started_at: '2026-11-01T10:00:00.000Z' });
    expect(await failure(store.api.updateCampaign(item.id, { name: 'B', updated_at: started.updated_at }))).toMatchObject({ code: 'campaign_running' });
    expect(await failure(store.api.deleteCampaign(item.id))).toMatchObject({ code: 'campaign_running' });
    expect(await failure(store.api.importCampaignContacts(item.id, { csv: '101', replace: true }))).toMatchObject({ code: 'campaign_running' });
    expect((await store.api.campaignAction(item.id, 'pause')).item.status).toBe('paused');
    expect((await store.api.campaignAction(item.id, 'stop')).item).toMatchObject({
      status: 'stopped', finished_at: '2026-11-01T10:00:00.000Z', stats: { total: 2, pending: 0, retry: 0, skipped: 2 },
    });
    expect(await failure(store.api.importCampaignContacts(item.id, { csv: '101', replace: false }))).toMatchObject({ code: 'campaign_bad_state' });
    expect(audits).toEqual(['create:create', 'update:import', 'update:start', 'update:pause', 'update:stop']);
  });

  it('eskirgan updated_at — stale; to\'g\'risi saqlanadi va qayta tekshiriladi', async () => {
    const { item } = await store.api.createCampaign(payload());
    expect(await failure(store.api.updateCampaign(item.id, { name: 'B', updated_at: 'eski' }))).toMatchObject({ code: 'stale' });
    expect(await failure(store.api.updateCampaign(item.id, { audio_id: null, updated_at: item.updated_at }))).toMatchObject({ code: 'campaign_audio_required' });
    expect((await store.api.updateCampaign(item.id, { name: 'B', updated_at: item.updated_at })).item.name).toBe('B');
  });

  it('o\'chirish; topilmagan — 404', async () => {
    const { item } = await store.api.createCampaign(payload());
    await store.api.deleteCampaign(item.id);
    expect((await store.api.listCampaigns()).items).toEqual([]);
    expect(await failure(store.api.getCampaign(item.id))).toMatchObject({ status: 404, code: 'not_found' });
  });
});

describe('import va dialer simulyatsiyasi', () => {
  it('qora ro\'yxat o\'tkaziladi, replace eskisini o\'chiradi, 1 MB cheklov', async () => {
    const { item } = await store.api.createCampaign(payload());
    const r = await store.api.importCampaignContacts(item.id, { csv: 'raqam,ism\n998900000000,Qora\n901112230,Ali\n901112230\nxx', replace: false });
    expect(r).toMatchObject({ added: 1, skipped: 1, duplicates: 1, invalid_count: 1, item: { stats: { total: 2, skipped: 1, pending: 1 } } });
    const again = await store.api.importCampaignContacts(item.id, { csv: '901112230\n101', replace: true });
    expect(again.item.stats.total).toBe(2);
    expect(await failure(store.api.importCampaignContacts(item.id, { csv: '1'.repeat(1_000_001), replace: false }))).toMatchObject({ code: 'csv_too_large' });
  });

  it('natijalar raqam oxiriga qarab; «9» rad etganlar keyingi kampaniyada o\'tkaziladi; oxirida completed', async () => {
    const { item } = await store.api.createCampaign(payload({ dtmf_connect: true, target_number: '600', max_concurrent: 5, max_attempts: 2 }));
    await store.api.importCampaignContacts(item.id, { csv: '901112230\n901112231\n901112233\n901112239', replace: false });
    await store.api.campaignAction(item.id, 'start');
    const first = await store.api.getCampaign(item.id);
    expect(first.item.stats).toMatchObject({ done: 2, skipped: 1, retry: 1, connected: 1, optout: 1 });
    const done = await store.api.getCampaign(item.id);
    expect(done.item).toMatchObject({ status: 'completed', stats: { failed: 1 } });
    const busy = await store.api.listCampaignContacts(item.id, { status: 'failed' });
    expect(busy.items[0]).toMatchObject({ number: '901112233', result: 'BUSY', attempts: 2, billsec: null });

    const second = (await store.api.createCampaign(payload({ name: 'Ikkinchi' }))).item;
    const r = await store.api.importCampaignContacts(second.id, { csv: '901112239', replace: false });
    expect(r).toMatchObject({ added: 0, skipped: 1 });
    expect((await store.api.listCampaignContacts(second.id, {})).items[0]?.result).toBe('OPTOUT');
  });

  it('sahifalash, qidiruv va CSV eksport (formula himoyasi)', async () => {
    const { item } = await store.api.createCampaign(payload());
    await store.api.importCampaignContacts(item.id, { csv: '101,=HYPERLINK("x")\n102,Vali\n103,Ali', replace: false });
    expect(await store.api.listCampaignContacts(item.id, { page: 2, page_size: 2 })).toMatchObject({ total: 3, items: [{ number: '103' }] });
    expect((await store.api.listCampaignContacts(item.id, { q: 'ali' })).items.map((c) => c.number)).toEqual(['102', '103']);
    const csv = await (await store.api.exportCampaignCsv(item.id)).text();
    expect(csv.split('\r\n')[0]).toBe('number,name,status,result,attempts,billsec,key,last_attempt_at');
    expect(csv).toContain('101,"\'=HYPERLINK(""x"")",pending,,0,,,');
  });
});

describe('csvCell', () => {
  it.each([[null, ''], ['-1', "'-1"], ['@a', "'@a"], ['a,b', '"a,b"'], [5, '5']])('%j → %j', (v, out) => expect(csvCell(v)).toBe(out));
});
