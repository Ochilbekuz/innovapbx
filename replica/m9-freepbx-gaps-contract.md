# M9 — FreePBX bo'shliqlari — 1.0.9

Manba: foydalanuvchi (2026-11-03): «avval freepbxdagi qo'shilmaganlarni qo'sh». Bo'shliq tahlili (CTO, kodga qarab):
E'lon UI/API yo'q, ichki raqam CSV yo'q, parkovka sahifasi stub, Misc destinations stub, PIN to'plamlari yo'q (faqat
marshrutga bitta PIN), CID Lookup yo'q, Paging/Intercom yo'q, Call Waiting yo'q, `inbound_routes.callerid_name_prefix`
ustuni bor lekin API/kompilyator ishlatmaydi, Alert-Info yo'q.

Clean-room: FreePBX kodi/matni olinmaydi — faqat funksiya g'oyasi. Barcha UI matni uz/ru/en (i18n).
Konvensiyalar MAVJUD koddan (blacklist/conferences/ring-groups): `Paged{items,total}`, `*Mutated{item,apply}`,
`updated_at` bilan optimistik 409 `stale`, `Target{id,kind,label,number,broken}`, xato `ApiError(code,field)`,
audit yozuvi, `usages` («kim ishlatyapti» — o'chirishda 409 `in_use`), ruxsat hududi `core/permissions.py` PREFIX
jadvaliga qo'shiladi (aks holda fail-closed `*`).

## 0. Umumiy qoidalar (3 agent parallel ishlaydi — SHART)
- Migratsiyalar: **Bo'lak A = `0031_m9a_*.sql/py` (down 0030)**, **Bo'lak B = `0032_m9b_*.sql/py` (down 0031)**.
  A o'z migratsiya faylini BIRINCHI qadamda yaratadi. B o'zinikini 0031 ga zanjirlaydi.
- Umumiy fayllar (models.py, schemas.py, compiler.py, router.py, permissions.py, types.ts, router.tsx, screens.ts,
  i18n/shell.ts): faqat o'z qismingizni `Edit` bilan qo'shing, boshqaning qatorlariga tegmang, faylni to'liq qayta yozmang.
- Jonli stek bitta (`docker compose -p innova-m0`, `deploy/`). Stekni o'zgartiradigan yoki jonli test qiladigan HAR
  buyruq: `flock /tmp/innova-stack.lock -c '<buyruq>'` (build/up/restart, proof skriptlar, live pytest, real-check).
  API kodi OBRAZ ichida → tuzatishdan keyin `docker compose -p innova-m0 build api && ... up -d api`.
- `ub-mode` (`~/.claude/skills/ub-mode/SKILL.md`) — Work → Right → Practice; CRAP < 10. Har o'zgarishdan oldin
  muhim faylga `.bak-$(date +%Y%m%d-%H%M%S)`. git commit/push QILMANG (CTO qiladi).
- Test parallelini cheklang: `VITEST_MAX_FORKS=2 VITEST_MIN_FORKS=1`, pytest `-q`, mutator ishlatmang.

## Bo'lak A — dialplan funksiyalari (asterisk-engineer)
### A1. E'lon (Announcements) — hudud `routing`
Jadval `announcements` bor (0001; ORM `Announcement`), `call_targets.kind='announcement'` bor, kompilyator esa
«qo'llab-quvvatlanmagan» deydi. 0031: `allow_skip bool default false`, `repeat_key text null` (0-9*#),
`answer bool default true`.
API `/announcements`: GET (Paged), POST, GET/{id}, PATCH/{id} (updated_at), DELETE/{id} (usages → 409 in_use).
```
Announcement = {id, name, audio_file_id, audio_name, next_target: Target, allow_skip, repeat_key: string|null,
                answer, target_id, updated_at}
Create = {name, audio_file_id, next_target_id, allow_skip?, repeat_key?, answer?}
```
Dialplan: Answer (agar answer) → allow_skip bo'lsa `Background`+`WaitExten(1)` (har tugma → next), aks holda
`Playback`; repeat_key → qayta o'ynash; keyin next_target. Sikl tekshiruvi (`_detect_target_cycle`) qamrab olsin.

### A2. Boshqa manzillar (Misc Destinations) + Maxsus kodlar (Misc Applications) — hudud `routing`
- `call_targets.kind` CHECK ga `'misc'` qo'shiladi (0031). Jadval `misc_destinations(id, tenant_id, target_id unique,
  name, dial text)` — `dial`: `^[0-9*#+]{1,32}$`. Dialplan: ichki abonent tergandek `{code}-outbound`/from-internal
  kontekstiga Goto — barcha chiquvchi marshrut, toll-fraud va PIN qoidalari AYNAN qo'llanadi (aylanib o'tish YO'Q).
  Agar `dial` ichki raqam/xizmat kodiga teng bo'lsa — o'sha ham ishlaydi (from-internal mantig'i).
- Jadval `misc_applications(id, tenant_id, name, code, target_id → call_targets RESTRICT, enabled)` — ichki abonent
  `code` (`^\*[0-9*#]{1,6}$` yoki oddiy raqam) tersa → target. Xizmat kodlari va `dial_numbers` bilan to'qnashuv
  (prefiks ham) → 409 `code_taken` (feature_codes.py qolipi).
API: `/misc-destinations` va `/misc-applications` — CRUD, bir xil konvensiya.
```
MiscDestination = {id, name, dial, target_id, updated_at}
MiscApplication = {id, name, code, target: Target, enabled, updated_at}
```

### A3. Parkovka sozlamalari — hudud `apps`
Hozir `dialplan_features.PARK_*` doimiy (lot 700, 701–720, 60 s). `system_settings` (yoki yangi jadval) ga:
```
ParkingSettings = {lot_number:"700", first_slot:701, slot_count:20 (1..100), timeout_s:60 (10..3600),
                   on_timeout:"origin"|"target", timeout_target: Target|null, moh_class_id: string|null, updated_at}
GET/PUT /parking/settings ; GET /parking/calls  (bor bo'lsa — mavjudini ishlating)
ParkedCall = {slot, caller_num, caller_name, parked_by, parked_seconds, timeout_s}
```
Raqamlar `dial_numbers`/ichki raqamlar bilan to'qnashsa → 409 `number_taken` (field). `##700` blind transfer va
`*70` ishlashda davom etsin. `res_parking` lot fayli + dialplan sozlamadan; o'zgarganda apply (reload'siz bo'lsa yaxshi).

### A4. Paging / Intercom — hudud `apps`
Jadval `page_groups(id, tenant_id, name, number unique (dial_numbers ga ham), duplex bool, skip_busy bool default true,
beep bool default true)` + `page_group_members(page_group_id, extension_id)`.
API `/page-groups` CRUD: `PageGroup = {id, name, number, duplex, skip_busy, beep, members:[{id, number, name}], updated_at}`.
Dialplan: `Page()` (duplex → `d`, skip_busy → band kanal o'tkazib yuboriladi, `i` forward'larni e'tiborsiz) +
avto-javob sarlavhalari. Intercom xizmat kodi `intercom` sukut `*80` (feature_code_defaults seed, prefiks
to'qnashuvini tekshiring): `*80<raqam>` → bitta ichki raqamga avto-javob bilan.
**Umumiy predial sarlavha gosub (A egasi, B ham ishlatadi):** `[innova-predial-hdr]` — ichki raqamga Dial qilinganda
`b(innova-predial-hdr^s^1)` orqali: `INNOVA_ALERT_INFO` bo'sh bo'lmasa → `PJSIP_HEADER(add,Alert-Info)`;
`INNOVA_AUTOANSWER=1` → `Call-Info: <sip:x>;answer-after=0` + `Alert-Info: info=alert-autoanswer` (Yealink/
Grandstream/Fanvil). Ichki raqam Dial'larida mavjud `b()`/`U()` bo'lsa — buzmasdan birlashtiring.

### A5. Call Waiting — hudud `extensions`
`extensions.call_waiting bool default true` (0031). API ichki raqam DTO/PATCH ga `call_waiting` qo'shiladi.
Xizmat kodlari `cw_on` `*56`, `cw_off` `*57` (seed). O'chiq va `DEVICE_STATE` INUSE/BUSY/RINGINUSE → band
(ichki raqamning «band» manziliga / ovozli pochtaga — mavjud no-answer/busy mantig'i bilan bir xil).
Navbat a'zolari uchun ham qo'llang (navbat `ringinuse`) — agar arzon bo'lsa; bo'lmasa hisobotda yozing.

## Bo'lak B — ma'lumot funksiyalari (python-engineer)
### B1. PIN to'plamlari (PIN Sets) — hudud `connect`
Mavjud: marshrutga bitta PIN (`outbound_routes.pin_hash`, `_route_pin_lines`, `/internal/outbound-routes/{id}/pin-check`).
0032: `pin_sets(id, tenant_id, name unique, record_in_cdr bool default true, updated_at)`,
`pin_set_pins(id, pin_set_id cascade, pin_hmac text, label text)` — PIN `HMAC-SHA256(server sirri, pin)` (bcrypt
emas — aniq qidirish kerak; PIN hech qachon ochiq saqlanmaydi/qaytarilmaydi), `outbound_routes.pin_set_id null`
(RESTRICT). Mavjud yakka PIN saqlanadi: ikkalasi bo'lsa — istalgani yetadi.
pin-check: to'plamdagi PIN mos kelsa va record_in_cdr → CDR `accountcode` = label (dialplan `Set(CDR(accountcode)=..)`);
javob formati — o'zingiz tanlang, lekin dialplan va endpoint mos, label sanitarlangan. Brute-force: chaqiruvchi
bo'yicha limit (`rate_limit.py`), xato urinishlar `security_events` ga.
```
PinSet = {id, name, record_in_cdr, pin_count, used_by:[{id,name}], updated_at}
GET/POST /pin-sets ; GET/PATCH/DELETE /pin-sets/{id} ; GET /pin-sets/{id}/pins → [{id,label}]
POST /pin-sets/{id}/pins {pins:[{pin, label}]} (4–12 raqam, takror → 409 pin_taken) ; DELETE /pin-sets/{id}/pins/{pin_id}
Outbound route DTO: + pin_set: {id,name}|null ; payload + pin_set_id
```

### B2. Telefon kitobi + CID Lookup — hudud `apps` (kitob), `connect` (manbalar)
0032: `phonebook_contacts(id, tenant_id, name, company, note, updated_at)` + `phonebook_numbers(contact_id cascade,
number_norm, label)` (index tenant+number_norm; `number_normalize.py` ishlatiladi).
`cid_lookup_sources(id, tenant_id, name, kind 'phonebook'|'crm'|'http', http_url (`{number}` shabloni), http_json_path
null, timeout_ms 300..3000 default 1500, cache_ttl_s default 3600, enabled, updated_at)`;
`inbound_routes.cid_lookup_source_id null`.
```
Contact = {id, name, company, note, numbers:[{number, label}], updated_at}
GET /phonebook?q=&page=&page_size= (Paged) ; POST/PATCH/DELETE ; GET /phonebook/export.csv ;
POST /phonebook/import (multipart file, dry_run=bool) → {created, updated, skipped, errors:[{row, message}]}
CidSource = {id, name, kind, http_url, http_json_path, timeout_ms, cache_ttl_s, enabled, used_by:[{id,name}], updated_at}
GET/POST /cid-sources ; PATCH/DELETE /cid-sources/{id} ; POST /cid-sources/{id}/test {number} → {name|null, ms, error|null}
```
HTTP manba URL — mavjud SSRF tekshiruvi (integrations `url_forbidden`). CRM — mavjud amoCRM/Bitrix24 kontakt
qidiruvidan (bo'lsa; bo'lmasa kind 'crm' ni hisobotda yozing). Ichki endpoint `/internal/cid-lookup?...&num=` →
ism (≤ 40 belgi, faqat xavfsiz belgilar — `"`, `;`, `,`, `\n` tozalanadi). Dialplan kiruvchi marshrutda: manba bor
va CALLERID(name) bo'sh/raqamga teng bo'lsa → `CURLOPT` timeout + `CURL()`; javob bo'lmasa — o'zgarishsiz.
Kesh: jarayon ichida TTL.

### B3. Kiruvchi marshrut: CID nomi prefiksi + Alert-Info — hudud `connect`
`callerid_name_prefix` (bor ustun) + 0032 `alert_info text null` (`^[A-Za-z0-9=<>:;/._@-]{1,128}$`).
Inbound DTO/payload: `cid_name_prefix`, `alert_info`, `cid_lookup_source_id` (+ DTO `cid_lookup_source:{id,name}|null`).
Dialplan: lookup → keyin `Set(CALLERID(name)=${prefix}${CALLERID(name)})`; `Set(__INNOVA_ALERT_INFO=..)` (A ning
`innova-predial-hdr` gosub'i sarlavhani qo'shadi).

### B4. Ichki raqamlar CSV import/eksport — hudud `extensions`
```
GET /extensions/export.csv — ustunlar: number,name,email,outbound_cid,language,voicemail,record_in,record_out,
    max_contacts,call_waiting,enabled (SIR/PAROL HECH QACHON eksport qilinmaydi)
POST /extensions/import (multipart file, dry_run=bool) →
    {rows:[{row, number, action:'create'|'update'|'skip'|'error', message|null}], created, updated, errors,
     secrets_csv: string|null}   # faqat dry_run=false va yangi yaratilganlarda: number,sip_password — BIR MARTA
```
Chegaralar: ≤ 2000 qator, ≤ 1 MB, UTF-8 (BOM ok), `;` yoki `,` ajratgich. Formula-inyeksiya himoyasi eksportda
(`=+-@` boshidagi qiymat → `'`). Apply — bitta tranzaksiya (birorta xato → hech narsa yozilmaydi) va bitta apply_config.
Audit. Mavjud ichki raqam yaratish validatsiyasi/servisi QAYTA ishlatiladi (dublikat mantiq yozilmasin).

## Bo'lak C — frontend (react-engineer)
Mavjud qoliplar: `screens/blacklist`, `screens/conferences`, `screens/ringgroups`, DestinationPicker, `api/` hooklar,
`ScreenStub` → to'liq sahifa (`FULL_PAGES` + `screens.ts full:true`), i18n uz/ru/en, ruxsatlar (`auth/permissions.ts`).
- Yangi/stub→to'liq ekranlar: `announcements` (routing), `misc` (routing; tablar: Manzillar / Maxsus kodlar),
  `parking` (apps; sozlama formasi + jonli park ro'yxati, 5 s yangilanish), `paging` (apps), `phonebook` (apps; CSV
  import/eksport), `pinsets` (connect; PIN qo'shish — ommaviy textarea «pin;label» har qatorda), `cidsources` (connect;
  «Sinash» tugmasi).
- Ichki raqamlar: `call_waiting` kaliti; «CSV import» dialogi (fayl → dry-run ko'rinishi jadvali → «Qo'llash»;
  `secrets_csv` bo'lsa «Parollarni yuklab olish» — bir marta, ogohlantirish bilan) + «CSV eksport».
- Chiquvchi marshrut formasi: PIN to'plami tanlagich. Kiruvchi marshrut formasi: CID manbasi, nom prefiksi, Alert-Info.
- DestinationPicker / `TARGET_KINDS`: `announcement`, `misc` qo'shiladi.
- Dizayn mavjud tizimda (tokens, primitivlar) — yangi rang/shrift kiritilmaydi. vitest har ekran uchun.
- Backend tayyor bo'lmaguncha shartnomadagi shakllarga qarab yozing (MSW/fake), keyin real API bilan tekshiring.

## Isbot (DoD)
- `scripts/m9-proof.sh [--fresh]` (A va B o'z bo'limlarini yozadi: A → `scripts/m9a-proof.sh`, B → `scripts/m9b-proof.sh`)
  — SIPp bilan jonli: e'lon o'ynab next ga o'tadi; misc → chiquvchi trunk; park sozlamasi (slot soni) o'zgaradi;
  page guruh 2 a'zoga avto-javob sarlavhasi bilan; CW o'chiq → ikkinchi qo'ng'iroq band; PIN to'plami + accountcode;
  CID lookup ismi INVITE From display'da; prefiks; CSV import dry-run/apply.
- Eski isbotlar regressiyasiz: m0, m1a, m1b, m2a, m6 0 FAIL. pytest/vitest hammasi yashil.
