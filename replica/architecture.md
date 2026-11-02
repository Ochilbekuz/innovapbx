# Arxitektura: Innova PBX (FreePBX + OnlinePBX asosiy funksiyalarining qayta qurilishi)

Sana: 2026-10-27. Manba: `recon.md` (36 ekran, 9 oqim), `features.csv` (87 funksiya). Sxema: `schema.sql`
(sinovdan o'tgan: PostgreSQL 16 da 41 jadval + 7 view; `schema_smoke.sql` — 5 ta cheklov tekshiruvi OK).

## Stack

Bizda allaqachon ishlab chiqarishda ishlayotgan stack (callcenter / Dial Dashboard) — yangisini o'rganmaymiz.
Bulut-SaaS standart stack (Vercel/Supabase) bu yerda TO'G'RI EMAS: mahsulot mijoz serverida, SIP/RTP bilan ishlaydi.

| qatlam | tanlov | nega |
| --- | --- | --- |
| Telefoniya yadrosi | **Asterisk 22 LTS** (o'zgartirilmagan, alohida konteyner, `network_mode: host`) | FreePBX ham shu; LTS 2029 gacha; GPL — alohida jarayon sifatida ishlatamiz |
| Konfiguratsiya → Asterisk | **Gibrid:** PJSIP/navbatlar — Realtime (PostgreSQL view'lar), dialplan — o'z kompilyatorimiz (`extensions_innova.conf` + `dialplan reload`) | pastda «Asosiy qaror» |
| Jonli hodisalar | **AMI** (callcenter'dagi mijoz qayta ishlatiladi) → WebSocket | sinalgan; ARI keyin softfon/kampaniya uchun |
| Backend API | **FastAPI + SQLAlchemy 2 (async) + Alembic + Pydantic 2** (Python 3.12) | callcenter bilan bir xil; RBAC, auth, audit, litsenziya, updater ko'chiriladi |
| Baza | **PostgreSQL 16** — bitta baza: konfiguratsiya + CDR/CEL/queue_log + Asterisk realtime | bitta haqiqat manbai; FreePBX'dagi MySQL + astdb + .conf parchalanishi yo'q |
| Frontend | **React 18 + Vite + TypeScript + Tailwind + TanStack Query + Zustand** | callcenter bilan bir xil (u JS — bu safar TS); dizayn tokenlari `/replica-design` dan |
| i18n | i18next, uz / ru / en | FreePBX'da o'zbek yo'q — ustunlik |
| Fon vazifalari | API ichida `bg_loop` (callcenter) — trunk sog'ligi, saqlash muddati, zaxira, TTS | Celery/Redis kerak emas; navbat — Postgres `LISTEN/NOTIFY` |
| Fayllar | lokal disk (`/var/lib/innova/{recordings,sounds}`), keyin S3/SFTP zaxira | on-prem; yozuvlar mijoz serverida qoladi |
| Auth | o'z JWT + refresh + TOTP 2FA (callcenter `security.py`) | sinalgan, tashqi xizmatsiz ishlaydi |
| Xabarlar | Telegram bot (callcenter `telegram.py`) + SMTP | O'zbekistonda Telegram asosiy kanal |
| TTS | rasmiy API (Yandex SpeechKit — uz/ru/en), kalit mijozniki | B2; o'zbek ovozi uchun ochiq model sifati yetarli emas |
| Tarqatish | bitta `docker compose` (asterisk, api, web+nginx, postgres), `registry.uzmik.uz/innova-pbx`, panel orqali yangilanish | callcenter updater/litsenziya (lic.uzmik.uz) andozasi |
| Testlar | pytest (API), Vitest + Playwright (UI), **SIPp** (haqiqiy qo'ng'iroq stsenariylari Asterisk konteyneriga) | dialplan kompilyatori — eng xavfli joy, haqiqiy qo'ng'iroq bilan sinaladi |

Mikroservislar yo'q: 4 konteyner, bitta baza. Bulut bosqichida (B4) xuddi shu obraz ko'p ijarachili rejimda.

### Asosiy qaror: konfiguratsiya Asterisk'ka qanday yetadi

| variant | + | − |
| --- | --- | --- |
| A. FreePBX kabi: hamma narsa `.conf` ga generatsiya + reload | oddiy, oldindan aytib bo'ladi | «Apply Config», PJSIP reload ba'zan registratsiyalarni uzadi, ko'p ijarachilikda katta fayllar |
| B. Hamma narsa ARI Stasis ilovasida (dialplan kod ichida) | eng moslashuvchan | **API yiqilsa — qo'ng'iroqlar to'xtaydi**; murakkab; FreePBX'dan ko'chirish qiyin |
| **C. Gibrid (tanlandi)** | ichki raqam/trunk/navbat — **darhol** (realtime, reload yo'q); dialplan — kompilyatsiya qilingan, tekshirilgan, **faol qo'ng'iroqlarni uzmaydigan** `dialplan reload`; API yiqilsa ham Asterisk ishlayveradi | kompilyator yozish kerak (lekin u sof funksiya — test qilish oson) |

Qo'llash jarayoni (har «Saqlash»da, foydalanuvchi uchun ko'rinmas, ~200 ms):
1. Tranzaksiyada yozish (baza cheklovlari singan manzil/raqam to'qnashuvini o'zi to'xtatadi).
2. `compile(tenant) -> dialplan` — **sof funksiya** (bazadan o'qilgan snapshot → matn); halqa tekshiruvi
   (IVR → navbat → IVR timeout'siz) shu yerda.
3. Matn sha256 o'zgarmagan bo'lsa — hech narsa qilinmaydi (idempotent).
4. Faylga atomik yozish (`.tmp` + `rename`), AMI `dialplan reload`, `dialplan show <ctx>` bilan tekshirish.
5. Xato → oldingi `config_revisions` matni qaytariladi, status `rolled_back`, UI'da aniq xabar.
6. Trunk registratsiyasi o'zgarsa — qo'shimcha `pjsip send register <id>` (faqat shu trunk).

### Kontekstlar (tenant izolyatsiyasi B1 dan boshlab)
`<code>-from-internal`, `<code>-from-trunk`, `<code>-dest-<target_id>` (har manzil — bitta kichik kontekst),
`<code>-outbound`. Ichki raqam endpoint nomi `<code>-<raqam>`. On-prem'da `tenants` da bitta qator — lekin
sxema va kontekstlar boshidan ko'p ijarachili, B4 da qayta loyihalash shart emas.

## Sxema

`schema.sql` — to'liq SQL. Asosiy g'oyalar:

- **`call_targets` — polimorf manzil registri.** Har obyekt (ichki raqam, guruh, navbat, IVR, ish vaqti, e'lon,
  pochta, konferensiya, tashqi raqam, osish) bitta qatorga ega; obyekt unga `on delete cascade` bilan bog'langan,
  «manzil» ustunlari esa `on delete restrict`. Natija: **singan manzil imkonsiz** (sinovda isbotlandi), o'chirishda
  UI «kim ishlatyapti» ro'yxatini FK'dan oladi.
- **`dial_numbers`** — bitta terish nom maydoni: 101 ichki raqam ham, navbat ham bo'lolmaydi (PK).
- Hamma narsada `tenant_id`, `timestamptz`, CHECK bilan holatlar, FK indekslar, `updated_at` triggeri.
- Maxfiy ma'lumot: SIP/trunk parollari `pgp_sym_encrypt` bilan shifrlangan; Asterisk realtime ochiq parol talab
  qiladi → `ps_auths` view `sip_secret()` orqali ochadi, kalit faqat Asterisk ulanadigan DB rolining sessiya
  sozlamasida (`ALTER ROLE asterisk SET innova.key = ...`), view'larga faqat shu rol SELECT huquqiga ega; API roli
  view'larni o'qimaydi. PIN'lar — hash.
- Asterisk yozadigan jadvallar (`cdr`, `cel`, `queue_log`) — Asterisk talab qilgan ustun nomlari bilan; tenant —
  `accountcode`. Hisobot kodi callcenter'dan (MySQL→Postgres dialekti allaqachon `db/cdr.py` da abstraksiya qilingan).
- Ruxsat: **API ma'lumot qatlamida har so'rovga `tenant_id` filtri** (RLS emas — Asterisk ham shu bazani o'qiydi,
  RLS uning rolini murakkablashtiradi). Bitta `TenantScope` dependency, testi bilan.

Jadvallar (41): tenants, roles, users, refresh_tokens, audit_log, call_targets, dial_numbers, audio_files, moh_classes,
moh_class_files, extensions, voicemail_boxes, devices, trunks, trunk_health, time_groups, time_ranges, holidays,
time_conditions, announcements, ivrs, ivr_options, ring_groups, ring_group_members, queues, queue_members,
conferences, external_numbers, inbound_routes, outbound_routes, outbound_route_patterns, outbound_route_trunks,
extension_outbound_routes, feature_codes, blacklist, system_settings, config_revisions, backups, cdr, cel, queue_log.
View'lar (7): ps_endpoints, ps_auths, ps_aors, ps_endpoint_id_ips, ps_registrations, asterisk_queues, asterisk_queue_members.

B2+ da qo'shiladi: integrations, webhooks, webhook_deliveries, campaigns, campaign_contacts, quality_scores,
provisioning_templates, api_keys; B4: plans, subscriptions, payments (pul — tiyin `bigint` + `currency`).

## API

Hammasi `/api/v1`, JSON, JWT. Ruxsatlar: `pbx.view`, `pbx.manage`, `trunks.manage`, `routes.manage`, `reports.view`,
`calls.recording`, `monitor.view`, `monitor.spy`, `users.manage`, `system.manage`; operator — `self.*`.
Har yozuvchi so'rov: audit + qo'llash jarayoni (yuqorida); javobda `apply: {status, revision}`.

**F01 Onboarding**
| method path | nima qiladi | kim | kirish | chiqish |
| --- | --- | --- | --- | --- |
| GET /setup/state | sehrgar kerakmi | ochiq (faqat admin yo'q bo'lsa) | — | {needed, step} |
| POST /setup | birinchi admin, til, TZ, tashqi IP/NAT, ixtiyoriy trunk | ochiq, bir martalik | forma | tokenlar |
| GET /system/network/detect | tashqi IP va NAT aniqlash (STUN) | system.manage | — | {external_ip, behind_nat} |
| POST /auth/login, /auth/refresh, /auth/2fa/* , /auth/logout | kirish | ochiq / login | — | tokenlar |

**F04 Ichki raqamlar (S04, S05)**
| GET /extensions | ro'yxat + jonli registratsiya | pbx.view | q, sahifa | [] |
| POST /extensions | yaratish (raqam bo'sh joydan avtomatik) | pbx.manage | forma | obyekt + SIP ma'lumot (bir marta) |
| POST /extensions/bulk | CSV import (dry-run rejimi bilan) | pbx.manage | fayl, dry_run | {created, errors[]} |
| GET /extensions/export.csv | eksport (parolsiz) | pbx.view | — | CSV |
| GET/PATCH/DELETE /extensions/{id} | karta / tahrir / o'chirish (409 + «kim ishlatyapti») | pbx.view / pbx.manage | — | — |
| POST /extensions/{id}/rotate-secret | yangi SIP parol | pbx.manage | — | yangi parol (bir marta) |
| GET /extensions/{id}/qr | softfon QR | pbx.manage | — | PNG |

**F01/F09 Trunklar (S06)**
| GET/POST /trunks, GET/PATCH/DELETE /trunks/{id} | CRUD | trunks.manage | — | — |
| GET /trunks/{id}/health | sog'lik tafsiloti (registratsiya, qualify, oxirgi kiruvchi/chiquvchi) | pbx.view | — | trunk_health |
| POST /trunks/{id}/test | OPTIONS + (ixtiyoriy) sinov qo'ng'irog'i | trunks.manage | {number?} | natija |

**F02/F07 Kiruvchi oqim (S07, S08, S09, S10, S21, S11)**
| CRUD /inbound-routes | DID → manzil | routes.manage | — | — |
| CRUD /time-groups, /holidays, /time-conditions | ish vaqti | routes.manage | — | — |
| POST /time-conditions/{id}/override | tungi rejim / majburiy | routes.manage yoki kod | {override} | — |
| POST /holidays/import-uz | O'zbekiston bayramlari shabloni | routes.manage | {year} | [] |
| CRUD /ivrs, /ring-groups, /queues, /announcements, /conferences, /external-numbers | ilovalar | routes.manage | — | — |
| GET /targets?kind= | manzil tanlagich uchun yagona ro'yxat | pbx.view | — | [{id, kind, label, number}] |
| GET /targets/{id}/usages | kim ishlatyapti | pbx.view | — | [] |
| GET /flow/{inbound_route_id} | qo'ng'iroq oqimi grafigi (daraxt, halqa/singan belgisi) | pbx.view | — | graf |
| CRUD /audio, POST /audio/tts, GET /audio/{id}/stream | audio, TTS, tinglash | pbx.manage / pbx.view | multipart | — |
| CRUD /moh-classes | kutish musiqasi | pbx.manage | — | — |

**F03 Chiquvchi (S22)**
| CRUD /outbound-routes, PUT /outbound-routes/order | naqsh + trunk tartibi | routes.manage | — | — |
| POST /outbound-routes/simulate | «0901234567 terilsa qaysi marshrut/trunk?» | pbx.view | {ext, number} | yo'l izi |

**F05/F08 Tarix va analitika (S12, S13, S03)** — callcenter endpointlari ko'chiriladi
| GET /calls, /calls/{uniqueid}, /calls/export.csv, /calls/{uniqueid}/recording | tarix, yozuv (Range) | reports.view / calls.recording |
| GET /reports/*, /dashboard/* | KPI, operator, navbat, soat, SLA | reports.view |

**F06 Jonli (S29)**
| WS /live | kanallar, navbat, agent holati (AMI → WS) | monitor.view |
| POST /live/spy | ChanSpy (tinglash/shivirlash/aralashish) — ichki raqamiga qo'ng'iroq | monitor.spy |
| POST /live/queue-members | agentni navbatga qo'shish/pauza | monitor.view |

**Tizim (S24, S27, S31–S36)**
| CRUD /feature-codes, /blacklist, /users, /roles | | pbx.manage / users.manage |
| GET/PUT /settings/sip, /settings/security, /settings/notifications | | system.manage |
| GET /system/health, /system/info, /system/logs?unit= | Asterisk/disk/xizmatlar, loglar (faqat o'qish) | system.manage |
| GET /config/revisions, POST /config/revisions/{id}/restore | reviziyalar, qaytarish | system.manage |
| POST /backups, GET /backups, POST /backups/{id}/restore | zaxira | system.manage |
| GET /audit | audit jurnali | users.manage |

**Operator portali (S30):** GET/PATCH /me/extension (DND, yo'naltirish, Follow Me), GET /me/calls, /me/voicemail.

Hisob: B1 ≈ 75 endpoint, B2 ≈ +30, B3 ≈ +35 (integratsiyalar, provizioning `GET /provision/{mac}.cfg`, import).

**Kiruvchi webhooklar:** yo'q (B3: CRM OAuth callback'lari — amoCRM/Bitrix24 rasmiy API, mijoz kalitlari).
**Chiquvchi webhooklar (B3):** call.started / answered / ended / recording.ready — imzo (HMAC), qayta urinish, `delivery_id` idempotentlik.

**Fon vazifalari**
| vazifa | jadval | nima qiladi |
| --- | --- | --- |
| trunk_health | 30 s | AMI `PJSIPShowRegistrationsOutbound` + qualify + oxirgi CDR → `trunk_health`; holat o'zgarsa Telegram |
| recording_retention | kuniga 03:00 | muddati o'tgan yozuvlarni o'chirish |
| backup | admin jadvali | pg_dump + sounds + (ixtiyoriy) yozuvlar → local/S3/SFTP |
| toll_fraud_guard | real vaqt (AMI) | chiquvchi limitlar oshsa — bloklash + ogohlantirish |
| sip_attack_guard | 1 daq | Asterisk security log → ko'p muvaffaqiyatsiz urinish → nftables bloklash |
| disk_watch | 5 daq | <10% bo'sh joy → ogohlantirish |
| daily_agg / report_prewarm | callcenter'dagidek | hisobot tezligi |

## Xavfli joylar

- **Vaqt zonasi:** Asterisk `GotoIfTime` server vaqtida ishlaydi → konteyner TZ = tenant TZ (on-prem bitta);
  bulutda tenant TZ dialplan'ga `,${TZ}` parametr bilan (GotoIfTime timezone argumenti). O'zbekistonda DST yo'q, lekin kod uni hisobga oladi.
  CDR `timestamptz` — UTC, UI tenant TZ'da ko'rsatadi (callcenter'dagi «naive UTC» xatosi takrorlanmaydi).
- **Idempotentlik:** qo'llash sha256 bo'yicha; webhook `delivery_id`; CSV import qatorlari raqam bo'yicha upsert; zaxirani tiklash — toza bazaga.
- **Poyga holatlari:** bir vaqtda ikki admin tahriri — `updated_at` bo'yicha optimistik qulf (409); qo'llash — tenant bo'yicha
  `pg_advisory_xact_lock`; raqam to'qnashuvi — PK.
- **Real vaqt:** AMI uzilishi → avtomatik qayta ulanish + holatni to'liq qayta o'qish (callcenter `live_service` saboqlari).
- **SIP/NAT:** `external_media_address`/`local_net` sehrgarda aniqlanadi; `rtp_symmetric`, `force_rport`, `rewrite_contact` standart;
  WebRTC — WSS + DTLS (B3), sertifikat — Let's Encrypt yoki mijozniki.
- **Xavfsizlik:** SIP skaner hujumlari (birinchi kundan), zaif SIP parol imkonsiz (generatsiya, 16+ belgi), toll fraud
  (xalqaro marshrut alohida belgilanadi va standart o'chiq), admin panel 2FA, audit. Ishga tushirishdan oldin security-auditor ko'rigi.
- **Fayl hajmi:** yozuvlar ~1 MB/daq (wav) → saqlash `opus`/`mp3` ga konvertatsiya varianti; audio yuklash ≤ 20 MB, format server tomonda tekshiriladi va konvertatsiya qilinadi (sox/ffmpeg).
- **Qidiruv:** CDR — `calldate`, `src/dst` indekslari; katta hajmda kunlik agregat (callcenter `daily_agg`).
- **Ko'p ijarachilik (B4):** kontekst prefiksi, `accountcode`, endpoint nomi — hammasi tenant `code` bilan; Asterisk bitta, bazada izolyatsiya API qatlamida.
- **FreePBX'dan ko'chirish (B3):** FreePBX `asterisk` MySQL jadvallari (users, devices, sip/pjsip, incoming, outbound_routes, ivr_details,
  ringgroups, queues_config, timeconditions, recordings) → bizning sxema; avval «quruq yugurish» hisobot, keyin import. Bu vosita ham
  faqat ma'lumotni o'qiydi (FreePBX kodi ishlatilmaydi).
- **GPL:** Asterisk o'zgartirilmagan va alohida jarayon — bizning kod yopiq bo'lishi mumkin. FreePBX kodidan hech narsa olinmaydi.
- **O'chirish/GDPR:** yozuvlar va CDR saqlash muddati sozlanadi; foydalanuvchi o'chirilsa audit'da `user_id` → null.

## Qurish tartibi

**M0 — Vertikal kesim (1–2 hafta, xunuk bo'lsa ham):** docker compose (asterisk + api + web + postgres), sehrgar (S01 qisqa),
kirish (S02), 2 ta ichki raqam (S04), bitta IP-trunk (S06), kiruvchi marshrut → ichki raqam (S07), tarix (S12).
Isbot: SIPp bilan trunkdan kiruvchi qo'ng'iroq ichki raqamga yetadi va CDR'da ko'rinadi; ichki raqam paroli o'zgarsa reload'siz ishlaydi.
Jadvallar: tenants, users, roles, call_targets, dial_numbers, extensions, trunks, inbound_routes, config_revisions, cdr. View: ps_*.

**M1 — Asosiy halqa (B1 must, ~4–6 hafta):** S03, S08, S09, S10, S21, S22, S11, S32, manzil tanlagich, qo'llash/rollback, audit,
uz/ru/en. Jadvallar: qolgan B1 jadvallari. Isbot: F01 ≤ 15 bosish; F02/F03/F07 SIPp stsenariylari CI'da.

**M2 — B2 (~4 hafta):** ovozli pochta (S23), kodlar (S24), konferensiya (S25), park/pickup (S26), qora ro'yxat (S27), analitika (S13 —
Dial Dashboard birlashadi), jonli monitoring (S29), operator portali (S30), xavfsizlik (S33), toll fraud, Telegram, TTS, oqim grafigi (ko'rish).

**M3 — B3 (~6 hafta):** WebRTC softfon (S16), CRM (amoCRM, Bitrix24, 1C), webhook/API, provizioning (S35), zaxira (S34),
FreePBX'dan import, kampaniyalar (S18 — freepbx-autodialer).

**M4 — B4:** bulut/ko'p ijarachilik, Payme/Click billing, callback vidjet, mobil.

**M5 — `/replica-entrepreneur` topgan tuzatishlar.**

Har bosqichda ub-mode: Work → Right (crapper < 10, dryer, mutator) → Practice; kompilyator va qo'llash jarayoni — mutatsiya testi bilan.
