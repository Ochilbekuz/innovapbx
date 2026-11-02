# M3b shartnomasi — qo'ng'iroq yozuvlari, hodisalar, webhook, REST API kalitlari, CRM (Bitrix24, amoCRM, 1C), integratsiyalar sahifasi (S15)

M0–M3a shartnomalari amalda qoladi: xato formati `{"error":{"code","message","field"?,"details"?}}`, `apply` bloki, `updated_at` → 409 `stale`,
vaqt UTC ISO, ro'yxat `{"items":[...]}`, yaratish/tahrir `{"item","apply"?}`, payload YASSI. Sirlar (API kalit, webhook secret, CRM token)
javobda FAQAT yaratilganda bir marta, keyin `has_secret`/`prefix`; auditda, logda, `last_error`da — `***`. Admin bo'limlari faqat `admin` (operator → 403).
M3b DAN TASHQARI: amoCRM popup (widget kerak), Bitrix24 «ilova» (marketplace) rejimi, stereo yozuv, yozuvni S3 ga ko'chirish, zaxira (S34), provizioning (S35),
FreePBX importi, kampaniyalar — keyingi bosqichlar.

VoxBridge saboqlari (`/root/devteam/workspaces/6199793291/voxbridge`, `docs/ADR-00{2,3,4}*.md`, `internal/crm/bitrix24/`, `internal/ami/`) MAJBURIY o'qiladi:
sekin iste'molchi AMI o'qishni bloklamasin; Originate — OQ RO'YXAT belgilar + `Async: true`; tugagan qo'ng'iroq holati TTL bilan saqlanadi (kech hodisa
qayta tiriltirmasin); osilib qolgan qo'ng'iroq majburan yopiladi (CRM kartasi ham); ichki (xodim↔xodim) qo'ng'iroq CRM'ga yuborilmaydi; bo'sh xarita = WARN + sabab.

## 0. Tamoyillar (CTO qarorlari)
- **Yagona hodisa manbai → outbox → yetkazuvchilar.** `call_events` fon vazifasi hodisa yaratadi (`integration_events` jadvali), har faol obuna
  (webhook / bitrix24 / amocrm) uchun `integration_deliveries` qatori yoziladi (bitta tranzaksiyada). `integration_dispatch` fon vazifasi
  (`FOR UPDATE SKIP LOCKED`, alert_dispatch qolipi) yetkazadi. API restartidan keyin `pending` davom etadi; `(subscription_id, event_id)` UNIQUE.
- **Tartib:** bitta `(subscription_id, call_id)` uchun yetkazish QAT'IY tartibda (oldingisi `delivered`/`dead` bo'lmaguncha keyingisi olinmaydi) —
  CRM'da `register` dan oldin `finish` hech qachon ketmaydi.
- **Real vaqt hodisalari AMI'dan** (alohida event-ulanish, `Events: call`): `call.ringing` (DialBegin → ichki raqam), `call.answered` (DialEnd ANSWER).
  Eng yaxshi harakat (best-effort). **`call.ended` CDR'dan** (haqiqat manbai): linkedid'ning oxirgi kanali yopilgach ≥ 2 s kutib, `cdr` qatorlari
  `cdr_grouping` bilan yig'iladi. Bardoshlilik: `call_event_state(linkedid PK, ringing_sent, answered_sent, ended_sent, ...)`; har 30 s supurgich
  oxirgi 6 soatdagi CDR linkedid'larini tekshiradi — `ended_sent=false` va kanal yo'q → `call.ended` (API o'chib turganda bo'lgan qo'ng'iroq ham yetadi).
  AMI uzilsa — qayta ulanish + `CoreShowChannels` bilan holatni tiklash. Tugagan holat 10 daqiqa TTL.
- **Ichki qo'ng'iroqlar** (ikkala tomon ichki raqam) — webhook'ga faqat `include_internal=true` bo'lsa; CRM'ga HECH QACHON.
- **Yozuvlar** — Asterisk `MixMonitor`, fayl `recordings` volume'da (Asterisk rw, API rw — saqlash muddati tozalashi uchun).

## 1. Qo'ng'iroq yozuvlari (features.csv «must B1»)
- Siyosat: `extensions.recording` (`always|never|on_demand`, ustun bor) + `tenants.recording_retention_days` (bor). Yangi
  `system_settings.recording = {"external_only": false, "format": "wav"}` (sukut). Qoida: qo'ng'iroq yoziladi, agar qatnashgan ichki raqam `always`
  (kiruvchi — javob bergan raqam; chiquvchi — chaqirgan raqam). `never` — yozilmaydi. `on_demand` — suhbat paytida `*1` (features.conf `automixmon`,
  DYNAMIC_FEATURES) yoqadi/o'chiradi. `external_only=true` → ichki qo'ng'iroqlar yozilmaydi.
- Barcha dial nuqtalari (to'g'ridan ichki raqam, RG, navbat `Queue(...,b(...))`, follow/forward, chiquvchi trunk, transferdan keyin) — BITTA dialplan
  subroutine orqali (`innova-rec`), compiler'da bitta yordamchi. Fayl: `/var/spool/asterisk/monitor/innova/YYYY/MM/DD/<linkedid>-<uniqueid>.wav`,
  `CDR(recordingfile)` ga nisbiy yo'l. Bir qo'ng'iroqda bir nechta fayl bo'lishi mumkin (transfer) — `call_recordings` jadvali
  (`id, tenant_id, linkedid, uniqueid, path, extension, started_at, duration_s, size_bytes, deleted_at`), API fayl yopilgach to'ldiradi.
- `GET /calls?...` → har qo'ng'iroqda `recordings: [{id, duration_s}]`. `GET /recordings/{id}/audio` (admin — hammasi; operator — faqat o'z raqami
  qatnashgan qo'ng'iroq) → `audio/wav`, `Range` qo'llab-quvvatlanadi; `DELETE /recordings/{id}` (admin, audit). `/me/calls` da ham.
- **Imzoli havola** (CRM/webhook uchun, autentifikatsiyasiz): `GET /api/public/v1/recordings/{id}?exp=<unix>&sig=<hmac>` — HMAC-SHA256
  (`SECRET_KEY`dan domen-ajratilgan kalit), TTL `integrations.recording_link_ttl_s` (sukut 7 kun). Eskirgan/buzilgan → 403.
- Saqlash muddati: kunlik tozalovchi `retention_days` dan eski fayllarni o'chiradi, `call_recordings.deleted_at` qo'yadi; disk xatosi → alert.
- Ichki raqam formasi: «Yozib olish» select; `/settings/recording` (yoki mavjud sozlamalar sahifasida bo'lim): retention, external_only.

## 2. Hodisalar (webhook payload — barcha yetkazuvchilar uchun yagona model)
```
{ "id": "<event uuid>", "type": "call.ringing|call.answered|call.ended|test.ping", "occurred_at": "...Z",
  "call": { "id": "<linkedid>", "direction": "inbound|outbound|internal", "from": "998901234567", "to": "101",
            "did": "712000000"|null, "extension": "101"|null, "queue": {"id","name"}|null,
            -- faqat ended: "status": "answered|missed|busy|failed", "started_at", "answered_at"|null, "ended_at",
            "duration_s", "billsec", "answered_by": "103"|null, "recordings": [{"id","duration_s","url"}] } }
```
`url` — §1 imzoli havola (`integrations.public_base_url` bo'sh bo'lsa `url: null` va UI'da ogohlantirish). Raqamlar `normalize_number` bilan.

## 3. Webhook'lar — `/integrations/webhooks` (admin)
- `GET` ro'yxat, `POST {name, url, events[], include_internal=false, enabled=true}` → `{item, secret}` (secret bir marta), `PATCH`, `DELETE`,
  `POST /{id}/rotate-secret` → yangi secret, `POST /{id}/test` → `test.ping` navbatga, `GET /{id}/deliveries?status=&limit=` (oxirgi 200),
  `POST /deliveries/{id}/replay`.
- So'rov: `POST url`, `Content-Type: application/json`, sarlavhalar `X-Innova-Event`, `X-Innova-Delivery` (delivery uuid — qabul qiluvchi uchun
  idempotentlik), `X-Innova-Signature: t=<unix>,v1=<hex HMAC-SHA256(secret, "<t>.<body>")>`. Timeout 10 s, redirect'lar kuzatilmaydi,
  2xx = muvaffaqiyat, javob tanasi ≤ 1 KB saqlanadi.
- Qayta urinish: 30 s, 2 m, 10 m, 30 m, 1 h, 3 h, 6 h, 12 h (8 urinish) → `dead`. Uzluksiz 24 soat muvaffaqiyatsiz → obuna avtomatik `enabled=false`
  (`disabled_reason`) + alert (M2c `raise_alert`, kind `webhook_disabled`).
- URL tekshiruvi: faqat http/https; loopback, link-local (169.254/16, fe80::/10), 0.0.0.0, metadata va PBX'ning o'z konteynerlari (api, postgres,
  asterisk, web nomlari va ularning IP'lari) → 422 `url_forbidden`. LAN (10/8, 172.16/12, 192.168/16) RUXSAT (on-prem 1C/CRM serverlari).
  Tekshiruv yuborish paytida ham (DNS rebinding) takrorlanadi.

## 4. REST API kalitlari va ochiq API — `/integrations/api-keys` (admin), `/api/public/v1/*` (kalit bilan)
- `POST {name, scopes[], expires_at?}` → `{item, key}`; kalit `ipk_<prefix8>_<secret32>`, bazada faqat sha256 + prefix. `GET`, `DELETE` (bekor qilish =
  `revoked_at`). `last_used_at` (≤ 1 daqiqada bir yangilanadi).
- Scope'lar: `calls:read`, `recordings:read`, `calls:originate`, `extensions:read`. `Authorization: Bearer ipk_...`. Yo'q/bekor/muddati o'tgan → 401
  `invalid_api_key`; scope yo'q → 403 `insufficient_scope`. Rate limit 120/daq kalitga → 429.
- Endpointlar: `GET /api/public/v1/calls?from=&to=&number=&limit=&cursor=` (M2 `/calls` modeli + recordings), `GET /api/public/v1/calls/{linkedid}`,
  `GET /api/public/v1/recordings/{id}` (kalit bilan YOKI imzoli havola), `GET /api/public/v1/extensions` (raqam, ism, holat — sirlarsiz),
  `POST /api/public/v1/calls/originate {"extension":"101","to":"+998 90 123-45-67","external_id"?}` → 202 `{"request_id"}`:
  avval ichki raqam jiringlaydi (webrtc ham), javob bergach `to` odatiy chiquvchi qoidalar (toll-fraud, xalqaro blok) bilan teriladi.
  `to` `normalize_number`, faqat `[0-9+*#]`, ≤ 32; ichki raqam mavjud va `enabled` → aks holda 422. Hodisalarda `call.origin = {"source":"api","external_id"}`.
  Audit `api.originate`.

## 5. CRM yetkazuvchilari — `/integrations/crm/{bitrix24|amocrm}` (admin)
Umumiy: `GET` → `{enabled, config (sirsiz, has_token), status: {state: ok|error|disabled, last_ok_at, last_error}, user_map:[{extension, crm_user_id,
crm_user_name, source: auto|manual}]}`; `PUT {enabled, config..., updated_at}`; `POST /test` (ulanishni tekshirish + foydalanuvchilarni yuklash);
`PUT /user-map`. Xarita bo'sh / raqam topilmasa → `default_user_id` + WARN status (`unmapped_extensions: [...]`). Hammasi outbox orqali (§0 tartib, qayta urinish).
Rate limit (Bitrix 2 req/s, amo 6 req/s). Yetkazuvchi obuna jadvali bilan bir xil (`kind`).
- **Bitrix24** (kiruvchi webhook URL `https://<portal>/rest/<user>/<code>/`, huquqlar telephony, user, crm):
  - `call.ringing` (tashqi) → `telephony.externalcall.register` (TYPE 2 kiruvchi / 1 chiquvchi, PHONE_NUMBER, USER_ID, LINE_NUMBER=DID,
    CALL_START_DATE, CRM_CREATE=`config.create_lead`, SHOW=1; kechikkan bo'lsa (`> popup_max_delay_s`, sukut 20) SHOW=0). `CALL_ID` →
    `crm_call_links(provider, linkedid, external_call_id)`. Shu qo'ng'iroqda keyingi jiringlagan raqamlar → `telephony.externalcall.show`.
  - `call.answered` → boshqa foydalanuvchilar uchun `telephony.externalcall.hide`.
  - `call.ended` → `telephony.externalcall.finish` (USER_ID = answered_by yoki oxirgi jiringlagan/default, DURATION=billsec,
    STATUS_CODE 200 javob / 304 javobsiz / 486 band / 603 rad, RECORD_URL = birinchi yozuv havolasi). Register yetkazilmagan bo'lsa — avval register.
  - Click-to-call: `POST /api/hooks/bitrix24/{hook_token}` (Bitrix «исходящий вебхук» `ONEXTERNALCALLSTART`, form-encoded; `auth[application_token]`
    config bilan solishtiriladi → aks holda 403) → USER_ID → ichki raqam → §4 originate; Bitrix `CALL_ID` linkka yoziladi (ikkinchi register YO'Q).
- **amoCRM / Kommo** (`base_url` `https://<sub>.amocrm.ru`, uzoq muddatli token):
  - Faqat `call.ended` (tashqi): `POST /api/v4/calls` `[{direction, uniq: linkedid, duration, source:"Innova PBX", link, phone, call_result,
    call_status (4 suhbat bo'ldi / 6 javob yo'q / 7 band), responsible_user_id, created_at}]`. Kontakt topilmasa (javob xatosi) va
    `config.unsorted_for_unknown` → `POST /api/v4/leads/unsorted/sip` (`source_uid` linkedid, metadata from/phone/called_at/duration/link/service_code).
  - Foydalanuvchilar `GET /api/v4/users` (xarita faqat qo'lda — amo'da ichki raqam maydoni yo'q). 401 → status error (token).
- **1C** — alohida yetkazuvchi YO'Q: «1C» kartasi = webhook + API kalit tayyor to'plami + yuklab olinadigan namunalar `docs/integrations/1c/`
  (BSL: HTTP-servis moduli webhook qabul qiladi va HMAC'ni tekshiradi, `ВызватьИзPBX(Номер)` — `/calls/originate`, `ЗаписьРазговора(id)` yuklab olish;
  o'rnatish yo'riqnomasi o'zbek/rus). Sinov: BSL sintaksis jihatdan ko'rib chiqiladi (1C platforma serverda yo'q — bu aniq aytilsin).

## 6. Integratsiyalar sahifasi (S15) — `/integrations` (admin)
Kartalar: REST API, Webhook'lar, Bitrix24, amoCRM, 1C — har birida holat (Ulanmagan / Ishlayapti / Xato + sabab), «Sozlash». Ichida:
API kalitlar jadvali + yaratish (kalit bir marta, nusxa olish), webhook'lar + yetkazishlar jurnali (status, kod, urinish, «Qayta yuborish»), test tugmasi,
CRM forma + «Ulanishni tekshirish» + foydalanuvchi xaritasi jadvali (WARN: xaritasiz raqamlar), 1C — yo'riqnoma + yuklab olish.
`/settings` da `integrations.public_base_url` (CRM/webhook yozuv havolalari uchun) va yozuv sozlamalari. `/calls` va `/me` da yozuvni tinglash (mavjud
`AudioPlayer`, `fetchAudio` Blob — M1a saboq), yuklab olish. uz/ru/en.

## 7. Isbot (`scripts/m3b-proof.sh --fresh`)
Soxta serverlar proof tarmog'ida: webhook qabul qiluvchi (HMAC tekshiradi, N marta 500 qaytara oladi), soxta Bitrix24 REST, soxta amoCRM — har biri
olgan so'rovlarni JSON'da saqlaydi. SIP — `tests/sipp/*.py` qolipi (RTP yuboradigan UA kerak — yozuv davomiyligini tekshirish uchun).
1. Yozuv: 101 `always` — trunk→101 javob, 6 s gaplashuv → `call_recordings` 1 ta, fayl davomiyligi ≥ 5 s (sox/ffprobe), `/calls` da recordings, audio 200
   (operator-egasi 200, boshqa operator 403), imzoli havola 200, eskirgan/buzilgan 403. 102 `never` → yozuv yo'q. 103 `on_demand` + `*1` → yozuv bor.
   Navbat orqali javob berilgan `always` raqam → yozuv bor. Chiquvchi (101→trunk) → yozuv bor. Muddati o'tgan fayl tozalovchi bilan o'chadi.
2. Webhook: kiruvchi qo'ng'iroq → qabul qiluvchida `call.ringing` → `call.answered` → `call.ended` (shu tartibda), HMAC to'g'ri, ended'da recordings url.
   Ichki qo'ng'iroq `include_internal=false` → hodisa yo'q. Qabul qiluvchi 2 marta 500 → 3-urinishda 2xx, `X-Innova-Delivery` bir xil, jurnalda attempts=3.
3. Bardoshlilik: qo'ng'iroq paytida `docker stop api` → qo'ng'iroq tugaydi → `docker start api` → ≤ 60 s ichida `call.ended` yetadi (bir marta).
4. API kalit: scope'siz 403, bekor qilingan 401, `GET /calls` va yozuvni yuklash 200; originate → 101 jiringlaydi, javob → trunk UAS `to` raqamli INVITE
   oladi; `to` ichida `\r\n` → 422; mavjud bo'lmagan raqam → 422.
5. Bitrix24: navbat (101, 103) ga kiruvchi → register (USER_ID 101 xaritasi) + show 103, 103 javob → hide, ended → finish USER_ID(103), STATUS 200,
   DURATION ≈ billsec, RECORD_URL. Javobsiz → 304. Chiquvchi → TYPE 1. Ichki → 0 so'rov. Soxta Bitrix 1 marta 503 → qayta urinish, tartib buzilmaydi.
   `ONEXTERNALCALLSTART` (to'g'ri token) → xaritadagi raqam jiringlaydi, ikkinchi register yo'q; noto'g'ri token → 403.
6. amoCRM: ma'lum kontakt → `/api/v4/calls` maydonlari to'g'ri; noma'lum → `unsorted/sip`; 429 → kechiktirib qayta urinish.
7. Integratsiyalar sahifasi real API bilan (`web/scripts/m3b-real-check.mjs`): API kalit yaratish/bekor qilish, webhook yaratish + test + jurnal,
   Bitrix forma + test, yozuvni tinglash; skrinshotlar `replica/clone-screens/m3b-*.png` (light+dark).
Barcha oldingi isbotlar (m0, m1a, m1b, m1c, m2a, m2b, m2c, m3a) `--fresh` 0 FAIL; pytest, vitest, tsc toza; ub-mode (crapper < 10, dryer, mutator) yangi kodda.
