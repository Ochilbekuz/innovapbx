# M10 — OnlinePBX funksiyalari — 1.0.11

Manba: foydalanuvchi (2026-11-03): «endi online pbxdagi funksiyalarga o'tish kerak». Bo'shliq tahlili (CTO, kodga qarab;
OnlinePBX recon `/root/devteam/workspaces/793156577/onlinepbx-klon/replica/features.csv`):
Sifat baholash (S14) — stub; Callback vidjet (S17) — stub; TTS — faqat `audio_files.tts_text` ustuni bor;
javobsiz qo'ng'iroq xabari (Telegram/e-mail) — yo'q (faqat ovozli pochta xabari bor); 2FA — `users.totp_secret_enc`
ustuni bor, oqim yo'q; tashqi WebSocket hodisalar — yo'q (webhook bor). Navbatdagi o'rin xabari, Follow Me, ko'p qurilma,
click-to-call, amoCRM/Bitrix24/1C, webhook, HTTP API, avtoinformator — ALLAQACHON BOR (tegmang).
Doiradan tashqari (keyingi relizlar): transkripsiya, stereo yozuv, billing/balans, chat, mobil ilova.

Clean-room: OnlinePBX kodi/matni/logosi olinmaydi — faqat funksiya g'oyasi. Barcha UI matni uz/ru/en (i18n).
Konvensiyalar MAVJUD koddan (blacklist/conferences/pinsets/phonebook): `Paged{items,total}`, `*Mutated{item,apply}` (apply
faqat dialplan o'zgarsa), `updated_at` bilan optimistik 409 `stale`, `Target{id,kind,label,number,broken}`, xato
`ApiError(code,field)`, audit yozuvi, `usages` → 409 `in_use`, ruxsat hududi `core/permissions.py` `_PREFIX_REGION` ga
qo'shiladi (aks holda fail-closed `*`). Sirlar `crypto.encrypt_secret` bilan (`crypto_registry` ga ro'yxatga oling),
API javobida HECH QACHON qaytmaydi (`has_key: bool`). Vaqt ko'rsatish — tenant tz (Toshkent).

## 0. Umumiy qoidalar (3 agent parallel ishlaydi — SHART)
- Migratsiyalar (`api/alembic/sql/` + `api/alembic/versions/`, 0032 andozasi): **Bo'lak A = `0033_m10a_*` (down 0032)**,
  **Bo'lak B = `0034_m10b_*` (down 0033)**. A o'z migratsiya faylini BIRINCHI qadamda yaratadi; B 0033 ga zanjirlaydi
  (A fayli hali bo'lmasa ham revision id `0033_m10a` deb yozing — A shu id'ni ishlatadi).
- Umumiy fayllar (models.py, schemas.py, router.py, permissions.py, main.py, crypto_registry.py, backup_parts.py, types.ts,
  router.tsx, screens.ts, i18n): faqat o'z qismingizni `Edit` bilan qo'shing, boshqaning qatorlariga tegmang, faylni to'liq
  qayta yozmang. Yangi jadvallar `backup_parts.py` ro'yxatiga qo'shilsin.
- Jonli stek bitta (`docker compose -p innova-m0`, `deploy/`). Stekni o'zgartiradigan yoki jonli test qiladigan HAR buyruq:
  `flock /tmp/innova-stack.lock -c '<buyruq>'` (build/up/restart, proof skriptlar, live pytest, real-check).
  API kodi OBRAZ ichida → tuzatishdan keyin `docker compose -p innova-m0 build api && ... up -d api` (worker konteynerlari
  ham shu obrazdan — kerak bo'lsa ularni ham `up -d`).
- `ub-mode` (`~/.claude/skills/ub-mode/SKILL.md`) — Work → Right → Practice; CRAP < 10. Har o'zgarishdan oldin muhim
  faylga `.bak-$(date +%Y%m%d-%H%M%S)`. git commit/push QILMANG (CTO qiladi).
- Test parallelini cheklang: `VITEST_MAX_FORKS=2 VITEST_MIN_FORKS=1`, pytest `-q`, mutator ishlatmang.
- Tashqi xizmatlar (Yandex, Telegram, SMTP) testda — faqat soxta server/mock; base URL env bilan almashtiriladi.

## Bo'lak A — qo'ng'iroq oqimi funksiyalari (asterisk-engineer)
### A1. Callback vidjet (S17) — hudud `connect`
Jadvallar (0033):
```
callback_widgets(id uuid pk, tenant_id fk cascade, name text, public_key text unique (24+ belgi url-safe, tasodifiy),
  target_id fk call_targets RESTRICT  -- operator tomoni: ext/queue/ring_group/ivr
  allowed_origins text[] not null default '{}'  -- 'https://site.uz' ko'rinishida; bo'sh = vidjet ishlamaydi
  time_group_id fk null, offhours_mode text check in ('reject','schedule') default 'schedule',
  max_attempts int 1..5 default 2, retry_interval_s int 60..1800 default 120,
  callerid_prefix text null (operator telefonida ko'rinadi, masalan «Sayt:»), allow_international bool default false,
  appearance jsonb  -- {color '#RRGGBB', position 'right'|'left', title{uz,ru,en}, button{uz,ru,en}, success{uz,ru,en}}
  enabled bool default true, created_at, updated_at)
callback_requests(id uuid pk, tenant_id, widget_id fk cascade, phone text (normalizatsiyalangan), name text null,
  page_url text null, ip inet null, status text check in ('pending','dialing','connected','failed','rejected','cancelled'),
  attempts int default 0, next_attempt_at timestamptz null, linkedid text null, last_error text null, created_at, updated_at)
  index (tenant_id, created_at desc), index (status, next_attempt_at)
```
Admin API (`/callback-widgets`, `/callback-requests`):
```
Widget = {id, name, public_key, target: Target, allowed_origins: string[], time_group_id, time_group_name, offhours_mode,
          max_attempts, retry_interval_s, callerid_prefix, allow_international, appearance, enabled, embed_snippet, updated_at}
embed_snippet = '<script async src="{public_base_url}/widget/{public_key}.js"></script>' (public_base_url yo'q → 409 public_base_url_missing emas, snippet null + UI ogohlantiradi)
GET /callback-widgets (Paged) · POST · GET/{id} · PATCH/{id} (updated_at) · DELETE/{id}
POST /callback-widgets/{id}/rotate-key → Widget
GET /callback-requests?widget_id&status&from&to&page&page_size (Paged; CallbackRequest = {id, widget_id, widget_name, phone,
    name, page_url, status, attempts, next_attempt_at, linkedid, last_error, created_at})
POST /callback-requests/{id}/cancel (faqat pending/dialing emas → 409 invalid_state)
```
Ochiq qism (auth yo'q; nginx `/widget/` va `/api/public/widget/` ni api'ga uzatadi — `deploy/web-nginx.conf` ni A tahrirlaydi):
```
GET  /widget/{public_key}.js            → vanilla JS (tashqi kutubxonasiz, Shadow DOM, ≤ 15 KB), Cache-Control 300s
GET  /api/public/widget/{public_key}/config → {appearance, open_now: bool, languages}
POST /api/public/widget/{public_key}/callback  {phone, name?, page_url?, hp?}  → 202 {status:'accepted'|'scheduled'}
```
Xavfsizlik (SHART): `Origin` sarlavhasi `allowed_origins` da bo'lmasa 403 (CORS faqat shu origin'ga); `hp` (honeypot)
to'ldirilgan → 202 qaytariladi, lekin hech narsa terilmaydi; rate limit (mavjud `rate_limit.py`): IP 3/10 daq, telefon
2/soat, vidjet 60/soat → 429; telefon `number_normalize` bilan, xalqaro faqat `allow_international`; toll-fraud
(`toll_fraud.py`) va qora ro'yxat tekshiruvi; bir telefon uchun ochiq so'rov bo'lsa — yangisi yaratilmaydi (o'shasini
qaytaradi); enabled=false/vidjet yo'q → 404.
Terish: worker (mavjud kampaniya worker'i andozasida, `job_lock`) `pending` + `next_attempt_at<=now` ni oladi → AMI Originate:
avval operator tomoni (`target` dialplan'i, CallerID = `callerid_prefix + phone`), operator javob bergach mijoz raqami
tenantning chiquvchi marshruti orqali teriladi (yangi kontekst `innova-callback-<tenant>` yoki mavjud originate yo'li —
o'zingiz tanlang). Operator javob bermasa/mijoz javob bermasa → attempts++, `retry_interval_s` dan keyin qayta, `max_attempts`
dan keyin `failed`. Ish vaqtidan tashqari: `reject` → 202 emas, 409 `closed`; `schedule` → `next_attempt_at` = vaqt guruhi
keyingi ochilishi (`time_eval.py`), 24 soatdan uzoq bo'lsa `rejected`. CDR'da qo'ng'iroq vidjetdan ekani ko'rinsin
(`cdr.userfield`ga `callback:<widget_id>` yoki mavjud usul).

### A2. Javobsiz qo'ng'iroq xabari — hudud `apps`
Jadvallar (0033):
```
missed_call_rules(id, tenant_id, name, scope_kind text check in ('any','did','queue','ring_group','extension'),
  scope_value text null (did raqami yoki uuid), telegram_chat_ids text[] default '{}', emails text[] default '{}',
  include_internal bool default false, enabled bool default true, created_at, updated_at)
missed_call_notices(id bigserial, tenant_id, rule_id fk cascade, call_id text, status text ('sent','failed'),
  attempts int, last_error text null, created_at, sent_at null, unique(rule_id, call_id))
missed_notify_cursor(tenant_id pk, last_seq bigint)
```
Manba: `integration_events` (type `call.ended`, payload `call.status='missed'`; hodisa obunasiz ham yoziladi — tekshirildi),
`seq` kursori bilan; `internal` hodisa faqat `include_internal`. Mos qoida: `any` / DID / navbat / guruh / ichki raqam
(payload'dagi maydonlar bo'yicha — `call_events.py` / `ended_call` ga qarang). Yuborish — mavjud `vm_notify`
(`send_telegram`, e-mail, `NotifyConfig` = `/settings/notify`). Xabar tenant tilida: raqam, CID nomi (bo'lsa), qayerga
qo'ng'iroq qilgan (DID/navbat/raqam), vaqt (tenant tz), oxirgi jiringlagan raqam. Xato → 3 marta qayta urinish, sirlar
log/xatoga tushmaydi (`alerts._safe_error` andozasi).
API: `/missed-call-rules` GET (Paged) · POST · GET/{id} · PATCH/{id} · DELETE/{id}; `POST /missed-call-rules/{id}/test`
→ {ok, error?} (soxta qo'ng'iroq bilan xabar yuboradi); `GET /missed-call-notices?rule_id&status&page` (Paged; {id, rule_id,
rule_name, call_id, status, attempts, last_error, created_at, sent_at}).

### A3. Matndan nutq (TTS) — hudud `apps` (audio), sozlama — admin
0033: `tts_settings(tenant_id pk, provider text check in ('none','yandex') default 'none', api_key_enc text null,
folder_id text null, voices jsonb default '{"uz":"nigora","ru":"alena","en":"john"}', updated_at)`.
Yandex SpeechKit v1 REST: `POST {TTS_YANDEX_BASE|https://tts.api.cloud.yandex.net}/speech/v1/tts:synthesize`,
`Authorization: Api-Key <key>`, form: text, lang (uz-UZ|ru-RU|en-US), voice, speed, format=lpcm, sampleRateHertz=8000
(yoki 16000 + mavjud `audio_tools` konvertatsiyasi) → WAV (Asterisk uchun mavjud audio formatiga moslang). Base URL faqat
env'dan (foydalanuvchi kiritmaydi — SSRF yo'q). Timeout 20 s.
```
GET   /settings/tts → {provider, has_key, folder_id, voices, updated_at}
PATCH /settings/tts {provider?, api_key? (bo'sh satr = o'chirish), folder_id?, voices?, updated_at}
POST  /settings/tts/test → {ok, error?}
POST  /audio/tts {name, text (1..2000), language 'uz'|'ru'|'en', voice?, speed 0.5..2.0 = 1.0} → AudioFile (source='tts', tts_text)
POST  /audio/tts/preview {text (≤ 500), language, voice?, speed?} → audio/wav (saqlanmaydi; rate limit 20/daq/foydalanuvchi)
```
provider='none' → 409 `tts_not_configured`; provayder xatosi → 502 `tts_failed` (javob tanasi/kalit logga to'liq emas).

## Bo'lak B — ma'lumot va xavfsizlik funksiyalari (python-engineer)
### B1. Sifat baholash (S14) — hudud `reports` (`view` — ko'rish, `edit` — baholash)
Jadvallar (0034):
```
qa_checklists(id, tenant_id, name, description text null, is_active bool default true, created_at, updated_at)
qa_criteria(id, checklist_id fk cascade, position int, title text, description text null, weight int 1..10 default 1,
  kind text check in ('yesno','scale5'), critical bool default false)
qa_evaluations(id, tenant_id, call_id text (linkedid), checklist_id fk RESTRICT, checklist_snapshot jsonb,
  agent_number text null, agent_name text null, evaluator_user_id fk users set null, answers jsonb, score_pct numeric(5,2),
  comment text null, status text check in ('draft','final') default 'final', created_at, updated_at,
  unique(tenant_id, call_id, checklist_id))
```
Ball (sof funksiya, unit-test SHART): yesno → 1/0 × weight; scale5 → (v−1)/4 × weight; foiz = Σ/Σweight × 100 (2 xona);
`critical` mezon yiqilsa (yesno=0 yoki scale5=1) → 0. Javob berilmagan mezon → `final` da 422 `incomplete`, `draft` da mumkin.
Baholashda mezonlar snapshot qilinadi — chek-list keyin o'zgarsa eski baho buzilmaydi. `agent_number` sukut — CDR'dagi
javob bergan ichki raqam.
```
Checklist = {id, name, description, is_active, criteria: [{id, position, title, description, weight, kind, critical}],
             evaluations_count, updated_at}
GET /qa/checklists (Paged; ?active) · POST (criteria massiv bilan) · GET/{id} · PATCH/{id} (criteria to'liq almashtiriladi)
DELETE /qa/checklists/{id} (bahosi bor → 409 in_use; UI arxivlashni taklif qiladi)
Evaluation = {id, call_id, call: {started_at, src, dst, duration, recording_id|null}, checklist_id, checklist_name,
              checklist_snapshot, agent_number, agent_name, evaluator: {id, name}|null, answers: [{criterion_id, value,
              comment|null}], score_pct, comment, status, created_at, updated_at}
GET /qa/evaluations?from&to&agent&checklist_id&evaluator_id&min_score&max_score&status&page&page_size (Paged)
POST /qa/evaluations {call_id, checklist_id, answers, comment?, status?, agent_number?}
GET/PATCH/DELETE /qa/evaluations/{id} (PATCH — updated_at; DELETE — admin yoki o'zi yaratgan)
GET /qa/summary?from&to&group_by=agent|checklist|criterion&checklist_id → {rows: [{key, label, count, avg_pct, min_pct,
    max_pct}]}  (criterion — faqat checklist_id bilan; mezon bo'yicha o'rtacha bajarilish %)
GET /calls/{linkedid}/evaluations → Evaluation[]
GET /me/evaluations (operator: o'zining ichki raqamiga oid, faqat o'qish, Paged)
```
`/calls` ro'yxati elementiga `qa: {evaluation_id, score_pct}|null` qo'shilsin (bitta qo'shimcha so'rov, N+1 emas).

### B2. Ikki bosqichli kirish (2FA, TOTP)
0034: `users.totp_enabled_at timestamptz null`, `users.totp_recovery_hashes text[] default '{}'`, `users.totp_last_step
bigint null`; tenant xavfsizlik sozlamasi `require_2fa text check in ('off','admins','all') default 'off'` (mavjud S33
xavfsizlik sozlamalari joyiga — `security_config.py`/`/settings/security` ga qarang).
TOTP — RFC 6238 (SHA1, 30 s, 6 raqam, ±1 qadam), faqat stdlib; secret 20 bayt base32, `totp_secret_enc` (shifrlangan).
Takror ishlatish himoyasi: `totp_last_step` dan kichik/teng qadam rad etiladi. Recovery kodlar: 10 ta `xxxx-xxxx`, bcrypt/
sha256+salt hash, bir martalik.
```
POST /auth/login → 2FA yoqilgan bo'lsa tokenlar O'RNIGA {status:'totp_required', challenge} (imzolangan, 5 daq, bir martalik)
                    (AuthResult kengaytiriladi: status 'ok'|'totp_required'; eski mijozlar uchun 'ok' da shakl o'zgarmaydi)
POST /auth/login/totp {challenge, code} → AuthResult(status 'ok'); code = 6 raqam yoki recovery kod;
     5 xato → challenge bekor, `failed_logins`++ (mavjud bloklash qoidasi), audit
POST /me/2fa/setup → {secret, otpauth_uri}   (issuer «Innova PBX», label tenant:username; enabled_at hali null)
POST /me/2fa/enable {code} → {recovery_codes: string[]} (bir marta ko'rsatiladi)
POST /me/2fa/disable {password, code}  (require_2fa siyosati bu foydalanuvchini qamrasa → 409 policy_required)
POST /me/2fa/recovery-codes {code} → {recovery_codes}
POST /users/{id}/2fa/reset (admin, audit) — foydalanuvchining 2FA'sini o'chiradi
UserOut / me: totp_enabled: bool, must_enroll_2fa: bool
```
Siyosat talab qilsa va foydalanuvchi ro'yxatdan o'tmagan bo'lsa — login tokenlar beradi, lekin `must_enroll_2fa=true` va
backend `deps` boshqa barcha so'rovlarga 403 `2fa_enrollment_required` qaytaradi (ruxsat: `/auth/*`, `GET /me`,
`/me/2fa/*`, `/me/password`). `must_change_password` mantig'iga o'xshash.

### B3. Tashqi WebSocket hodisalar — ochiq API
`api_keys.SCOPES` ga `events:read` qo'shiladi.
```
WS /api/public/v1/events/ws
  auth: `Authorization: Bearer ipk_...` sarlavhasi YOKI 5 s ichida birinchi xabar {"type":"auth","token":"ipk_..."}
        (query string'da token QABUL QILINMAYDI — loglarga tushadi); scope yo'q → close 4403, yaroqsiz → 4401
  mijoz → {"type":"subscribe","events":["call.ringing","call.answered","call.ended"] | ["*"], "since_seq": 123?}
  server → {"type":"ready","seq":<oxirgi seq>} ; {"type":"event","seq":..,"event":"call.ended","data":<webhook bilan
           bir xil envelope>} ; har 25 s {"type":"ping"} (mijoz {"type":"pong"} yoki istalgan xabar)
```
Tenant bo'yicha cheklangan; `internal` hodisalar — webhook'dagi kabi faqat so'ralsa (`subscribe.include_internal`).
`since_seq` bilan qayta ulanishda o'tkazib yuborilgan hodisalar (≤ 1000 ta, ≤ 24 soat). Amalga oshirish: PG
LISTEN/NOTIFY yoki 1 s polling (bitta umumiy o'quvchi + ulanishlarga tarqatish afzal); limit 5 ulanish/kalit,
50/tenant → close 4429. nginx: `deploy/web-nginx.conf` ga shu yo'l uchun Upgrade/Connection sarlavhali location (B tahrirlaydi;
A ham shu faylga `/widget/` qo'shadi — faqat o'z blokingizni qo'shing). Hujjat: mavjud ochiq API hujjatiga (bo'lsa) bo'lim.

## Bo'lak C — frontend (react-engineer)
Mavjud qoliplar: `screens/pinsets`, `screens/phonebook`, `screens/campaigns`, `screens/integrations`, DestinationPicker,
`api/` hooklar, `ScreenStub`/`ExtraScreenStub` → to'liq sahifa (`FULL_PAGES` + `screens.ts full:true`), i18n uz/ru/en,
ruxsatlar (`useCanEdit/useCanView(hudud)`). Dizayn — mavjud tokenlar/primitivlar; yangi rang/shrift kiritilmaydi.
TUZOQ: `cn` = faqat clsx (twMerge YO'Q) — Input/Select kengligini o'ram div'ga bering.
- **Sifat (`/quality`, S14 stub → to'liq)**: tablar «Baholashlar» (jadval + filtrlar: sana, operator, chek-list, ball
  oralig'i; ball rangli belgi) / «Chek-listlar» (CRUD, mezonlarni sudrab tartiblash yoki ↑↓, og'irlik, tur, «muhim») /
  «Hisobot» (`/qa/summary` — operator bo'yicha o'rtacha ball jadvali + gorizontal bar; `dataviz` skilini o'qing).
  Baholash oynasi (drawer): qo'ng'iroq ma'lumoti + yozuv pleeri (mavjud AudioPlayer) + mezonlar (ha/yo'q yoki 1–5) +
  jonli hisoblanayotgan ball + izoh; «Qoralama» / «Saqlash». `/cdr` qatorida «Baholash» tugmasi (reports:edit) va `qa`
  ball belgisi. `/me` da «Mening baholarim» kartasi.
- **Callback vidjet (`/settings/integrations/widget`, S17 ExtraScreenStub → to'liq; Integratsiyalar sahifasidan havola)**:
  vidjetlar ro'yxati, forma (nom, manzil — DestinationPicker, ruxsat etilgan saytlar — chip input, vaqt guruhi,
  ish vaqtidan tashqari rejimi, urinishlar, CallerID prefiksi, xalqaro, ko'rinish: rang, joy, matnlar uz/ru/en) +
  JONLI KO'RINISH (vidjet tugmasi va oynasi namunasi), «Kodni nusxalash», «Kalitni yangilash» (tasdiq bilan),
  so'rovlar jurnali jadvali (holat, urinishlar, bekor qilish).
- **Javobsiz qo'ng'iroq xabari**: `/settings/alerts` sahifasiga yangi tab yoki `apps` guruhida alohida ekran
  (`missedcalls`, yo'l `/missed-calls`) — qoidalar CRUD (qamrov turi + qiymat tanlagich: DID/navbat/guruh/raqam ro'yxatidan),
  Telegram chat ID va e-mail chip input, «Sinash» tugmasi, yuborishlar jurnali.
- **TTS**: `/audio` sahifasida «Matndan yaratish» dialogi (matn, til, ovoz, tezlik, «Tinglab ko'rish» — preview blob,
  «Saqlash»); sozlanmagan bo'lsa — admin uchun sozlash havolasi. Sozlama: `/settings/integrations` da «Nutq sintezi
  (Yandex SpeechKit)» kartasi (provayder, API kalit — faqat yozish, `has_key` belgisi, folder_id, ovozlar, «Sinash»).
- **2FA**: login sahifasida 2-qadam (6 xonali kod kiritish, «Zaxira kod bilan kirish» havolasi); `/me` da «Ikki bosqichli
  kirish» kartasi: yoqish (QR — mavjud QR kutubxonasi, Linphone QR andozasi; secret qo'lda kiritish uchun ham), kodni
  tasdiqlash, recovery kodlarni ko'rsatish (nusxalash/yuklab olish, «saqladim» tasdig'i), o'chirish, kodlarni yangilash;
  `must_enroll_2fa` → majburiy ro'yxatdan o'tish sahifasi (must_change_password andozasi); `/settings/security` da
  `require_2fa` tanlovi; `/settings/users` da «2FA'ni tiklash» amali va `totp_enabled` belgisi.
- **API kalitlar**: `events:read` scope tanlovi + WebSocket ulanish namunasi (kod parchasi) integratsiyalar sahifasida.
- vitest har yangi ekran/dialog uchun. Backend tayyor bo'lmaguncha shartnoma shakllariga qarab yozing (fake), keyin real API
  bilan tekshiring.

## Isbot (DoD)
- `scripts/m10a-proof.sh` (A) — jonli: vidjet config/CORS (ruxsatsiz Origin → 403), honeypot, rate limit 429, so'rov →
  SIPp operator javob beradi → mijoz raqami trunk (soxta SIPp trunk) orqali teriladi, holat `connected`; operator javob
  bermasa qayta urinish/`failed`; ish vaqtidan tashqari `schedule`/`reject`; javobsiz kiruvchi qo'ng'iroq → soxta Telegram
  serverga xabar (qoida mosligi, include_internal), takror yuborilmaydi; TTS soxta Yandex server bilan → audio fayl yaratiladi
  va IVR'da o'ynaydi, `none` → 409.
- `scripts/m10b-proof.sh` (B) — QA ball (critical, snapshot), summary; TOTP: setup→enable→login 2 bosqich, takror kod rad,
  recovery bir martalik, siyosat `admins` → 403 2fa_enrollment_required, admin reset; WS: header va first-message auth,
  scope yo'q 4403, since_seq qayta ijro, jonli qo'ng'iroq hodisasi WS'ga keladi, nginx orqali (443) ham ishlaydi.
- `web/scripts/m10-real-check.mjs` (C, Playwright, jonli stek) — har yangi ekran ochiladi, asosiy amal bajariladi, 390px'da
  buzilmaydi.
- Eski isbotlar regressiyasiz: m0, m2a (`--fresh`), m3b, m6, m9a, m9b 0 FAIL. pytest/vitest hammasi yashil.
