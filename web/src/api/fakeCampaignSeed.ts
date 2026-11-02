// M6 — fake API boshlang'ich kampaniyalari: bittasi tugagan, bittasi yarim yo'lda (pauza).
import type { CampaignFields, CampaignStatus } from './types';

type SeedFn = (input: { fields: CampaignFields; status: CampaignStatus; csv: string; ticks: number; at: string }) => void;

const BASE: Omit<CampaignFields, 'name' | 'mode'> = {
  audio_id: 'au-notice', target_number: '600', dtmf_connect: true, dtmf_optout: true, callerid: '712000000',
  max_concurrent: 3, max_attempts: 2, retry_delay_s: 900, ring_seconds: 25,
  window_start: '09:00', window_end: '19:00', days: [1, 2, 3, 4, 5],
};

const DEBTORS = `raqam;ism
+998 90 111-22-30;Aziz Karimov
+998 91 222-33-41;Dilnoza Rahimova
998935550012;Bekzod Tursunov
998977771239;Malika Yusupova
998946660015;Sardor Aliyev
998998887766;Spam raqam
`;

const TARIFF = Array.from({ length: 24 }, (_, i) => `99890${String(3_100_000 + i * 137).padStart(7, '0')},Mijoz ${i + 1}`).join('\n');

export function seedCampaigns(seed: SeedFn): void {
  seed({ fields: { ...BASE, name: 'Qarzdorlik eslatmasi — oktyabr', mode: 'message' }, status: 'completed', csv: DEBTORS, ticks: 6, at: '2026-10-28T05:10:00Z' });
  seed({
    fields: { ...BASE, name: 'Yangi tarif — sodiq mijozlar', mode: 'connect', audio_id: null, dtmf_connect: false, dtmf_optout: false, max_concurrent: 4 },
    status: 'paused', csv: TARIFF, ticks: 3, at: '2026-10-31T06:00:00Z',
  });
}
