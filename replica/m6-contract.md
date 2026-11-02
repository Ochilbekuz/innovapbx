# M6 kontrakt — Kampaniyalar: avtoinformator / avtoterish (2026-11-01)

Manba: recon S18 «Avtoinformator / avtoterish | Ilovalar → Kampaniyalar | ro'yxatga xabar / operatorga ulash
(freepbx-autodialer asos) | CSV, natijalar». Web sidebar'da «Kampaniyalar» joyi bor (placeholder).

## 1. Ma'lumot (migratsiya 0025)
- `campaigns`: `id, tenant_id, name (1..80, tenant ichida yagona), mode ('message'|'connect'), status
  ('draft'|'running'|'paused'|'completed'|'stopped'), audio_id → audio_files (message'da SHART, connect'da ixtiyoriy
  e'lon), target_number (connect'da SHART: ichki raqam yoki dial_numbers raqami — navbat/guruh/IVR),
  dtmf_connect (message: «1» → target_number), dtmf_optout (message: «9» → raqam kampaniyalardan chiqariladi),
  callerid (ixtiyoriy, 3..15 raqam — trunk/marshrut CID ustun bo'lsa o'sha), max_concurrent 1..30,
  max_attempts 1..5, retry_delay_s 60..86400, ring_seconds 10..30 (marshrut Dial 30 s), window_start/window_end (time, tenant
  timezone), days int[] (1=Du..7=Ya, bo'sh emas), created_at, updated_at, started_at, finished_at`.
- `campaign_contacts`: `id bigserial, campaign_id, number (normalize_number, 3..15), name (≤80), status
  ('pending'|'dialing'|'retry'|'done'|'failed'|'skipped'), result (oxirgi: ANSWER|BUSY|NOANSWER|CHANUNAVAIL|
  CONGESTION|NOROUTE|LOST|BLACKLIST|OPTOUT), attempts, next_attempt_at, last_attempt_at, billsec, key`.
  `(campaign_id, number)` yagona. Kampaniyada ≤ 50 000 kontakt.
- `campaign_attempts`: `id bigserial, contact_id, campaign_id, started_at, ended_at, dial_status, billsec, key`.
- `campaign_optouts (tenant_id, number, campaign_id, created_at)` — «9» bosganlar; hamma kampaniyada o'tkaziladi.

## 2. API (`/api/v1/campaigns`, faqat admin; jurnal `campaign.*`)
- `GET /campaigns` → `{items:[CampaignOut]}`; `CampaignOut` = maydonlar + `stats {total,pending,dialing,retry,
  done,failed,skipped,answered,optout}`.
- `POST /campaigns` (201), `PATCH /campaigns/{id}` (`updated_at` → 409 `stale`; running'da 409 `campaign_running`),
  `DELETE /campaigns/{id}` (running'da 409 `campaign_running`; 204).
- 422 kodlari: `name_taken`, `campaign_audio_required`, `campaign_target_required`, `campaign_bad_target`
  (raqam topilmadi), `campaign_bad_audio`, `campaign_dtmf_mode` (DTMF faqat message'da), `campaign_window`
  (start == end), `campaign_days`, validation.
- `POST /campaigns/{id}/contacts/import` `{csv, replace?:false}` → `{added, duplicates, invalid:[{line, value}]
  (≤50 ta), skipped}`. CSV: 1-ustun raqam, 2-ustun ism (ixtiyoriy); sarlavha qatori avtomatik tashlanadi;
  ajratgich `,` yoki `;`; ≤ 1 MB, ≤ 50 000 qator. running'da import mumkin (yangi kontaktlar `pending`).
  Qora ro'yxat / opt-out raqami → `skipped` (result BLACKLIST/OPTOUT) — import paytida ham, terishdan oldin ham.
- `GET /campaigns/{id}/contacts?status=&q=&page=&page_size=` → `{items, total}`.
- `GET /campaigns/{id}/export.csv` → `number,name,status,result,attempts,billsec,key,last_attempt_at`.
- `POST /campaigns/{id}/start|pause|stop` → `{item}`. start: draft/paused → running (kontakt yo'q → 409
  `campaign_empty`); pause: running → paused; stop: draft/running/paused → stopped (tugatilgan, qayta start yo'q
  → 409 `campaign_bad_state`). Barcha kontakt done/failed/skipped → dialer `completed` qiladi.

## 3. Dialer (fon vazifa `campaign_dialer`, `CAMPAIGN_DIALER_ENABLED`, har 2 s)
- running kampaniya, oyna ichida (tenant timezone, `days`): bo'sh joy = max_concurrent − dialing;
  `pending` yoki `retry` (next_attempt_at ≤ now) kontaktlar `FOR UPDATE SKIP LOCKED` → attempt + `dialing`.
- AMI Originate: `Channel Local/<number>@<code>-campaign-dial/n`, `Context <code>-campaign-answer`, `Exten s`,
  `Timeout ring_seconds*1000`, `Async true`, `CallerID` = callerid, `Variable` — faqat oq ro'yxat belgilari
  (raqam, UUID, audio yo'li `[A-Za-z0-9/_.-]`). AMI xato → attempt o'chiriladi, kontakt avvalgi holatiga.
- `<code>-campaign-dial`: hangup handler qo'yadi → `<code>-outbound-rg` (mavjud chiquvchi marshrut/trunk
  failover/toll-limit qayta ishlatiladi; ichki raqam filtri yo'q).
- Hangup handler → `GET /internal/campaigns/result?token&attempt&status=${DIALSTATUS}&answered=${ANSWEREDTIME}`.
  ANSWER → `done`; boshqasi (CANCEL = ring_seconds tugadi → NOANSWER; bo'sh → NOROUTE) → attempts <
  max_attempts bo'lsa `retry` (+retry_delay_s), aks holda `failed`. Takroriy natija e'tiborsiz (idempotent).
- `<code>-campaign-answer`: message — audio (DTMF yoqilgan bo'lsa `Read` 2 marta, 6 s) → `GET
  /internal/campaigns/key?attempt&key` → `connect` | `optout` | `none`; connect → `Goto(<code>-from-internal,
  target_number)`. Mijoz CallerID'si operatorga ko'rinadi.
- Supurgich: 3 soatdan eski `dialing` attempt → LOST (retry qoidasi bilan).

## 4. Web — «Kampaniyalar» sahifasi
Ro'yxat (holat belgisi, progress bar, javob berganlar), yaratish/tahrirlash drawer (rejim, audio, maqsad, DTMF,
oyna, kunlar, limitlar), batafsil: start/pause/stop, statistika kartalari, CSV yuklash (fayl yoki matn,
natija: qo'shildi/takror/xato qatorlar), kontaktlar jadvali (holat filtri, qidiruv), CSV eksport.
Running'da avtoyangilanish (5 s). uz/ru/en, qorong'i rejim, 390 px mobil.

## 5. Isbot (`scripts/m6-proof.sh --fresh`)
Trunk UAS (`m2a_phone.py serve trunk`): answer / busy / ring rejimlari, `answer:9` (opt-out), `answer:1`
(→ ichki raqam 201 javob beradi). Tekshiruv: API 422/409, CSV import hisobotlari, qora ro'yxat skip,
max_concurrent hurmati, busy → retry → failed, answer → done + billsec, ring → NOANSWER, opt-out → keyingi
kampaniyada skipped, connect, oyna tashqarisida terilmaydi, pause/stop, export CSV.
