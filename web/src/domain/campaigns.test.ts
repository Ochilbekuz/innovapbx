// M6 — kampaniya sof qoidalari backend `campaign_rules.py` / `campaigns.py` bilan mos.
import { describe, expect, it } from 'vitest';
import type { Campaign, CampaignFields, CampaignStats } from '@/api/types';
import {
  MAX_INVALID_REPORTED, campaignActions, campaignProgress, campaignShapeError, campaignToForm, canEditCampaign,
  canImportContacts, defaultCampaignForm, formToPayload, formToUpdate, formatDays, hhmm, inWindow, parseContactsCsv,
  parseNumber, splitCsvRow, toggleDay,
} from './campaigns';

const fields = (p: Partial<CampaignFields> = {}): CampaignFields => ({
  ...defaultCampaignForm(), audio_id: 'au-1', target_number: null, callerid: null, ...p,
});
const stats = (p: Partial<CampaignStats> = {}): CampaignStats => ({
  total: 0, pending: 0, dialing: 0, retry: 0, done: 0, failed: 0, skipped: 0, connected: 0, optout: 0, ...p,
});
/** `YYYY-MM-DDTHH:MM` — tenant mahalliy vaqti UTC maydonlarida. 2026-11-02 — dushanba. */
const at = (s: string) => new Date(`${s}:00Z`);

describe('parseNumber', () => {
  it.each([
    ['+998 (90) 111-22-33', '998901112233'],
    ['  101 ', '101'],
    ['12', null],
    ['1234567890123456', null],
    ['90x1112233', null],
    ['', null],
  ])('%j → %j', (raw, out) => expect(parseNumber(raw)).toBe(out));
});

describe('splitCsvRow', () => {
  it('vergul va nuqtali vergulni aniqlaydi', () => {
    expect(splitCsvRow('901;Ali;Toshkent, Chilonzor')).toEqual(['901', 'Ali', 'Toshkent, Chilonzor']);
    expect(splitCsvRow('901;Ali, Vali')).toEqual(['901;Ali', ' Vali']); // teng — vergul (Python bilan bir xil)
    expect(splitCsvRow('901,Ali')).toEqual(['901', 'Ali']);
  });
  it('qo\'shtirnoqli katak va "" ni ochadi', () => {
    expect(splitCsvRow('"901","Ali ""Aka"", Toshkent"')).toEqual(['901', 'Ali "Aka", Toshkent']);
  });
  it('katak o\'rtasidagi qo\'shtirnoq — oddiy belgi', () => {
    expect(splitCsvRow('901,Ali"s')).toEqual(['901', 'Ali"s']);
  });
});

describe('parseContactsCsv', () => {
  it('sarlavha, takror, yaroqsiz, bo\'sh qator va mavjud raqamlar', () => {
    const r = parseContactsCsv('raqam;ism\n998901112233;Aziz\n\n+998 90 111 22 33;Takror\nabc;X\n101\n555', ['555']);
    expect(r.rows).toEqual([{ number: '998901112233', name: 'Aziz' }, { number: '101', name: null }]);
    expect(r.duplicates).toBe(2);
    expect(r.invalid).toEqual([{ line: 5, value: 'abc' }]);
    expect(r.invalid_count).toBe(1);
  });
  it('birinchi qator raqam bo\'lsa — sarlavha emas', () => {
    expect(parseContactsCsv('101\n102').rows.map((x) => x.number)).toEqual(['101', '102']);
  });
  it('yaroqsizlar ro\'yxati cheklangan, hisob — to\'liq', () => {
    const r = parseContactsCsv(Array.from({ length: MAX_INVALID_REPORTED + 5 }, () => 'x1').join('\n').replace(/^/, '100\n'));
    expect(r.invalid).toHaveLength(MAX_INVALID_REPORTED);
    expect(r.invalid_count).toBe(MAX_INVALID_REPORTED + 5);
  });
  it('ism 80 belgigacha qisqartiriladi, CRLF qabul qilinadi', () => {
    const r = parseContactsCsv(`101,${'a'.repeat(100)}\r\n102,  `);
    expect(r.rows[0]?.name).toHaveLength(80);
    expect(r.rows[1]?.name).toBeNull();
  });
});

describe('inWindow', () => {
  const week = [1, 2, 3, 4, 5];
  it('kunduzgi oyna: chegaralar [start, end)', () => {
    expect(inWindow(at('2026-11-02T09:00'), '09:00', '18:00', week)).toBe(true);
    expect(inWindow(at('2026-11-02T08:59'), '09:00', '18:00', week)).toBe(false);
    expect(inWindow(at('2026-11-02T18:00'), '09:00', '18:00', week)).toBe(false);
  });
  it('ruxsat etilmagan kun', () => {
    expect(inWindow(at('2026-11-08T10:00'), '09:00', '18:00', week)).toBe(false);
  });
  it('tun oshgan oyna — kun oyna boshlangan kun', () => {
    expect(inWindow(at('2026-11-06T23:00'), '22:00', '02:00', week)).toBe(true); // juma kechasi
    expect(inWindow(at('2026-11-07T01:00'), '22:00', '02:00', week)).toBe(true); // shanba tongi — juma oynasi
    expect(inWindow(at('2026-11-07T23:00'), '22:00', '02:00', week)).toBe(false); // shanba kechasi
    expect(inWindow(at('2026-11-02T01:00'), '22:00', '02:00', week)).toBe(false); // dushanba tongi — yakshanba oynasi
    expect(inWindow(at('2026-11-02T02:00'), '22:00', '02:00', [7])).toBe(false);
  });
});

describe('campaignShapeError', () => {
  it.each<[Partial<CampaignFields>, string | null, string?]>([
    [{}, null],
    [{ audio_id: null }, 'campaign_audio_required', 'audio_id'],
    [{ mode: 'connect', audio_id: null, dtmf_optout: false }, 'campaign_target_required', 'target_number'],
    [{ mode: 'connect', target_number: '600', dtmf_optout: true }, 'campaign_dtmf_mode', 'dtmf_connect'],
    [{ dtmf_connect: true }, 'campaign_target_required', 'target_number'],
    [{ window_start: '09:00', window_end: '09:00:00' }, 'campaign_window', 'window_end'],
    [{ days: [1, 1] }, 'campaign_days', 'days'],
    [{ days: [0] }, 'campaign_days', 'days'],
    [{ days: [8] }, 'campaign_days', 'days'],
  ])('%j → %s', (p, code, field) => {
    const err = campaignShapeError(fields(p));
    expect(err).toEqual(code ? { code, field } : null);
  });
});

describe('holat qoidalari', () => {
  it('progress — hal bo\'lganlar ulushi, pastga yaxlitlanadi', () => {
    expect(campaignProgress(stats())).toBe(0);
    expect(campaignProgress(stats({ total: 3, done: 1, failed: 0, skipped: 1 }))).toBe(66);
    expect(campaignProgress(stats({ total: 4, done: 2, failed: 1, skipped: 1 }))).toBe(100);
  });
  it('amallar holatga qarab', () => {
    expect(campaignActions('draft')).toEqual(['start', 'stop']);
    expect(campaignActions('running')).toEqual(['pause', 'stop']);
    expect(campaignActions('paused')).toEqual(['start', 'stop']);
    expect(campaignActions('completed')).toEqual([]);
    expect(campaignActions('stopped')).toEqual([]);
  });
  it('tahrirlash va import ruxsati', () => {
    expect(['draft', 'running', 'paused', 'completed', 'stopped'].map((s) => canEditCampaign(s as never))).toEqual([true, false, true, true, true]);
    expect(['draft', 'running', 'paused', 'completed', 'stopped'].map((s) => canImportContacts(s as never))).toEqual([true, true, true, false, false]);
  });
});

describe('formatDays / hhmm / toggleDay', () => {
  const L = ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'];
  it.each([
    [[1, 2, 3, 4, 5], 'Du–Ju'],
    [[1, 2], 'Du, Se'],
    [[7, 1, 3, 4, 5], 'Du, Ch–Ju, Ya'],
    [[6], 'Sh'],
    [[], ''],
  ])('%j → %s', (days, out) => expect(formatDays(days, L)).toBe(out));
  it('yorliq bo\'lmasa — raqam', () => expect(formatDays([1, 2], ['Du'])).toBe('Du, 2'));
  it('hhmm', () => expect(hhmm('09:30:00')).toBe('09:30'));
  it('toggleDay tartibni saqlaydi', () => {
    expect(toggleDay([1, 5], 3)).toEqual([1, 3, 5]);
    expect(toggleDay([1, 3, 5], 3)).toEqual([1, 5]);
  });
});

describe('forma ↔ payload', () => {
  it('message, «1» o\'chiq — yashirin ulash raqami yuborilmaydi', () => {
    const p = formToPayload({ ...defaultCampaignForm(), name: '  Eslatma ', audio_id: 'au-1', target_number: '600', days: [3, 1] });
    expect(p).toMatchObject({ name: 'Eslatma', audio_id: 'au-1', target_number: null, callerid: null, dtmf_connect: false, dtmf_optout: true, days: [1, 3] });
  });
  it('message + «1» — ulash raqami yuboriladi', () => {
    expect(formToPayload({ ...defaultCampaignForm(), dtmf_connect: true, target_number: '600' }).target_number).toBe('600');
  });
  it('connect — audio va DTMF tozalanadi', () => {
    const p = formToPayload({ ...defaultCampaignForm(), mode: 'connect', audio_id: 'au-1', target_number: ' 600 ', dtmf_connect: true, callerid: '712000000' });
    expect(p).toMatchObject({ audio_id: null, target_number: '600', dtmf_connect: false, dtmf_optout: false, callerid: '712000000' });
  });
  it('campaignToForm → formToUpdate aylanma', () => {
    const c = {
      ...fields({ name: 'A', window_start: '08:00:00', window_end: '21:30:00', callerid: null }),
      id: 'c1', status: 'paused', audio_name: 'x', started_at: null, finished_at: null, created_at: 't0', updated_at: 't1', stats: stats(),
    } as Campaign;
    const form = campaignToForm(c);
    expect(form).toMatchObject({ window_start: '08:00', window_end: '21:30', callerid: '', audio_id: 'au-1' });
    expect(formToUpdate(form, c.updated_at)).toMatchObject({ updated_at: 't1', name: 'A', audio_id: 'au-1', callerid: null });
  });
});
