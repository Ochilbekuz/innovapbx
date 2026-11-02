# M5a shartnomasi — FreePBX'dan ko'chirish (S36 «Ko'chirish», `/settings/migration`)

M0–M4b shartnomalari amalda qoladi: xato formati `{"error":{"code","message","field"?,"details"?}}`, ro'yxat `{"items":[...]}`, vaqt UTC ISO,
faqat `admin` (operator → 403), audit (sirlar `***`), uz/ru/en, light+dark. Manba faktlari: `replica/freepbx-source-notes.md` (haqiqiy FreePBX
stendidan, `tests/freepbx-fixture/`). Clean-room: FreePBX kodi ishlatilmaydi — faqat uning ma'lumotlari o'qiladi.
M5a DAN TASHQARI: CDR/qo'ng'iroq yozuvlari tarixini ko'chirish (M5b), FreePBX native Backup&Restore faylini to'g'ridan-to'g'ri o'qish (M5b — agar
§1 da formati barqaror deb topilmasa), ko'p ijarachiga import, Innova'dan FreePBX'ga qaytarish, `extensions_custom.conf` ni tarjima qilish.

## 0. Tamoyillar (CTO qarorlari)
- **Manba = eksport to'plami** `fpbx-export-<host>-<YYYYmmdd-HHMMSS>.tar.gz` — bizning `api/app/resources/freepbx/innova-fpbx-export.sh`
  (FreePBX serverda root; FAQAT o'qiydi; haqiqiy FreePBX 17.0.33.2 stendida sinalgan, 19 MB). Ichida bitta ildiz papka `fpbx-export-*/`:
  `meta.json` (`format: INNOVA-FPBX-EXPORT/1`, `freepbx_version`, `asterisk_version`, `db_version`, `host`, `created_at`, `tables[]`,
  `ignored_tables[]`, `vm_messages`), `tables/<jadval>.tsv` (`mysql -B`: 1-qator sarlavha, `NULL` so'zi = NULL, `\t \n \\ \0` escape),
  `astdb/astdb.txt` (`database show`: `/<OILA>/<kalit...>   : <qiymat>`, oxiridagi bo'shliqlar kesiladi; `N results found.` qatori e'tiborsiz),
  `conf/voicemail.conf` + `conf/*_custom*.conf`, `files/sounds/[<til>/]custom/*`, `files/moh/<kategoriya>/*` (ildizdagi fayllar = `default`),
  `files/voicemail/<kontekst>/<mailbox>/{greet,unavail,busy,temp}.*`. Format/versiya noto'g'ri → 422 `bundle_invalid` (sabab bilan).
  Test to'plami: `tests/freepbx-fixture/bundle/fpbx-export-fixture.tar.gz` (stenddan shu skript bilan olingan — sintetik EMAS).
  ⚠️ To'plamda SIP parollari bor → UI ogohlantiradi; import tugagach `DELETE /jobs/{id}` to'plamni o'chiradi; diskda `0600`.
  Skript UI'dan yuklab olinadi (`GET /migration/freepbx/export-script`) — bitta buyruq: `bash innova-fpbx-export.sh`.
- **Ikki yo'l bir xil kod yo'liga tushadi**: (a) to'plamni yuklash; (b) **SSH orqali avtomatik** — host, port, user, parol YOKI kalit; host kaliti
  pin (M4b SFTP kabi: barmoq izi ko'rsatiladi → admin tasdiqlaydi; jim qabul YO'Q); API skriptni masofada ishga tushirib to'plamni tortib oladi.
  SSH sirlari saqlanmaydi (bir martalik, xotirada; audit'da `***`).
- **Ikki bosqich, M4b tiklash kabi**: (1) `analyze` — to'plamni ochadi, normallashtirilgan reja quradi, Innova'da HECH NARSA o'zgarmaydi;
  (2) `apply {confirm:"KOCHIRISH", options}` — avtomatik `pre_import` zaxira (M4b mexanizmi, lokal) → BITTA DB tranzaksiya (hammasi yoki
  hech narsa) → audio fayllar (vaqtinchalik papka → almashtirish; xatoda tozalanadi) → bitta dialplan kompilyatsiya + apply (reviziya
  «FreePBX importi») → audit. Bir vaqtda bitta ish (M4b `job_lock`, 409 `job_running`).
- **Reja elementi** (har FreePBX obyekti uchun): `{kind, source_ref, name, number?, action: create|skip|conflict|unsupported, reason?,
  warnings[], depends_on[]}`. `unsupported` — sabab bilan (masalan maxsus kontekst manzili → manzil «Qo'ng'iroqni tugatish» bilan almashtiriladi
  va ogohlantirish). Jim tushib qolish YO'Q: manbadagi har jadval qatori rejada yoki `ignored` ro'yxatida (sabab bilan) — test bilan.
- **To'qnashuv**: Innova'da raqam/nom band (`dial_numbers`, unique nomlar) → `conflict`; variantlar `skip` (sukut) yoki `replace` (faqat
  avvalgi importdan kelgan obyekt bo'lsa — `migration_items` orqali; qo'lda yaratilganni ustidan yozish YO'Q).
- **Idempotentlik**: `migration_items(job_id, kind, source_ref, innova_kind, innova_id)` — qayta import avval import qilinganni taniydi
  (`skip`/`replace`); ikki marta yuritilgan import dublikat yaratmaydi.
- **Bog'liqlik tartibi**: audio/MOH → vaqt guruhlari → ichki raqamlar (+ovozli pochta, DND/yo'naltirish) → trunklar → ring group, navbat,
  konferensiya, e'lon → IVR, vaqt sharti → kiruvchi/chiquvchi marshrutlar → qora ro'yxat, xususiyat kodlari. Sikl bo'lishi mumkin (IVR → TC → IVR)
  → avval barcha `call_targets` yaratiladi, keyin manzillar ulanadi (ikki o'tish).
- **Sirlar**: SIP/trunk parollari o'zgarmay ko'chadi (telefonlar qayta sozlashsiz ishlaydi) → `encrypt_secret`. Zaif parollar (< 12 belgi yoki
  oddiy) — rejada ogohlantirish + `options.rotate_weak_secrets` (sukut `false`; yoqilsa yangi parol, provizioning bilan telefon o'zi oladi).
  Ovozli pochta PIN → xesh. Sirlar rejada, javobda, logda YO'Q (`has_secret: true`).
- **Audio**: `sox` bilan bizning formatga konvertatsiya (M1a audio yo'li); fayl yo'q bo'lsa — obyekt yaratiladi, audio bo'sh, ogohlantirish.

## 1. Moslik jadvali (FreePBX → Innova)
Manba faktlari — `replica/freepbx-source-notes.md` (haqiqiy stend). `source_ref` = `<jadval>:<kalit>` (masalan `users:101`, `trunks:1`).
Har bir `.tsv` qatori yo rejada (`kind`), yo `ignored[]` da (`{table, key, reason}`); quyida sanalmagan jadval butunligicha
`ignored` (`reason: "table_not_supported"`, qator soni bilan) — **jim yo'qolish testi** shuni tekshiradi.

### 1.1 Manzil satri (destination) → `call_targets` (resolver, ikkinchi o'tishda)
`<kontekst>,<exten>,<pri>` → Innova target. Topilmasa yoki noma'lum → `hangup` target + ogohlantirish `dest_unsupported` (asl satr bilan).
| FreePBX satri | Innova |
|---|---|
| `ext-local,<N>,1`, `from-did-direct,<N>,1` | `extension` N |
| `ext-local,vmu<N>,1` / `vmb<N>` / `vms<N>` / `vmi<N>` | `voicemail` N (yo'q bo'lsa → ext N + ogohl.) |
| `ext-group,<N>,1` | `ring_group` N |
| `ext-queues,<N>,1` | `queue` N |
| `ivr-<id>,s,1` | `ivr` (ivr_details.id) |
| `timeconditions,<id>,1` | `time_condition` |
| `app-announcement-<id>,s,1` | `announcement` |
| `ext-meetme,<N>,1`, `ext-conference,<N>,1` | `conference` N (stendda sinalmagan — unit test bilan) |
| `ext-findmefollow,FM<N>,1` | `extension` N (Follow Me o'sha raqamda) |
| `ext-miscdests,<id>,1` | `destdial` ichki raqam bo'lsa — o'sha target; aks holda `external` |
| `app-blackhole,hangup\|congestion\|zapateller\|no-service,1` | `hangup` |
| `app-blackhole,busy,1` | `busy` |
| `app-blackhole,ring\|musiconhold,1` | `hangup` + ogohl. |
| `from-internal,<raqam>,1`, `from-trunk,…`, boshqa har qanday | raqam ichki bo'lsa o'sha; aks holda `hangup` + `dest_unsupported` |

### 1.2 Obyektlar
| FreePBX | Innova | Qoidalar |
|---|---|---|
| `recordings` + `files/sounds/[til/]custom/<fayl>.*` | `audio_files` (source `upload`, language: papka tili `uz/ru/en` bo'lsa o'sha, aks holda `uz`) | `filename` (`custom/x`, `&` bilan bir nechta → birinchisi + ogohl.) bo'yicha fayl qidiriladi; formatlar ustuvorligi `wav > sln* > ulaw > alaw > gsm > g722 > mp3`; sox bilan bizning formatga. Fayl yo'q → `skip` + `audio_missing`. Nom: `displayname`. |
| `music` + `files/moh/<category>/*` | `moh_classes` + `moh_class_files` (`random`→`shuffle`) | `default` kategoriyasi → Innova `default` sinfi (fayllari QO'SHILMAYDI, `skip`, sabab `builtin`). `type!='custom'` (streaming) → `unsupported`. |
| `timegroups_groups` + `timegroups_details.time` (`HH:MM-HH:MM\|dow-dow\|dom-dom\|mon-mon`, `*` joker) | `time_groups` + `time_ranges` | dom/mon `*` → time_range (weekdays dan; `mon-fri`→[1..5]; `*` vaqt → 00:00-23:59). dom+mon aniq (`*\|*\|1\|jan`) → `holidays` (recurring_yearly, sana o'sha yil), ogohl. `holiday_from_timegroup`; dom/mon oraliq → har kun alohida bayram (≤ 31), aks holda `unsupported`. |
| `users` + `devices` + `sip` (EAV, PJSIP ham shu yerda!) + astdb `AMPUSER/<N>/*` | `extensions` + `dial_numbers` + `call_targets(extension)` | `name`; `sip.secret` → `sip_password_enc` (o'zgarmaydi); `allow` → `codecs` (Innova bilmagani tashlanadi + ogohl.); `max_contacts` 1–10; `outboundcid` (`"Ism" <num>` yoki raqam) → `outbound_callerid` raqami; `ringtimer` 0 → 25, aks holda 5–120 ga qisilib ogohl.; `recording` astdb `recording/{in,out}/{internal,external}`: birortasi `force`/`yes` → `always`, hammasi `never`/`no` → `never`, aks holda `on_demand`. `devices.tech` ≠ `pjsip`/`sip` (iax2, dahdi, custom, virtual) → `unsupported`. Zaif sir (< 12 belgi, faqat raqam, ext raqamiga teng) → `weak_secret`. |
| astdb `CF/<N>`, `CFB/<N>`, `CFU/<N>`, `DND/<N>`=`YES` | `forward_always`, `forward_busy`, `no_answer_target_id` (CFU raqami ichki → o'sha target, aks holda `external`), `dnd` | `^[0-9]{2,15}$` emas (`+` olib tashlanadi) → ogohl. va o'tkazib yuboriladi. `CW` — `ignored` (Innova'da sozlanmaydi). |
| `users.noanswer_dest` / `busy_dest` / `chanunavail_dest` | `no_answer_target_id` (CFU bo'lmasa) | busy/unavail → ogohl. `partial_mapping` |
| `findmefollow` (+ astdb `AMPUSER/<N>/followme/ddial` = `DIRECT` yoqiq) | `extensions.follow_me = {enabled, numbers[], ring_seconds}` | `grplist` `-` bilan; `#` tashqi raqam belgisi olib tashlanadi; o'z raqami tashlanadi; `grptime` 5–120; `pre_ring`, `strategy` — ogohl. `partial_mapping`. |
| `conf/voicemail.conf` `[default]` `<mb>=<PIN>,<ism>,<email>,<pager>,<opts>` | `voicemail_boxes` (+ target) | Faqat `users` da mavjud va `users.voicemail != 'novm'` bo'lgan mailbox; boshqalar (masalan namunaviy `1234`, `[other]`) → `ignored` `vm_without_extension`. PIN → `pin_hash`; email → `email`+`email_notify`; `attach=yes` → `attach_audio`; salomlashuv `files/voicemail/default/<mb>/unavail.*`→`greeting_audio_id`. |
| `trunks` + `pjsip` (EAV, id=`trunkid`) | `trunks` | `tech != 'pjsip'` (sip/iax2/dahdi/custom) → `unsupported`. `registration=send` → `register` (`sip_server`→host, `sip_server_port`→port, `username`/`auth_username`, `secret`, `from_domain`); `registration=none` + `identify_by=ip` yoki `match` bor → `ip` (`match` vergulli → `match_ips`; host = `sip_server` yoki birinchi match IP). `transport` `*-udp\|tcp\|tls` → mos; `codecs`; `maxchans`→`max_channels`; `outcid`→`outbound_callerid`; `disabled=on` → `enabled=false`. Nomi `name`. |
| `incoming` | `inbound_routes` | `extension` (DID) bo'sh → «har qanday DID»; `cidnum` → `callerid_pattern`; `grppre` → `callerid_name_prefix`; `destination` → 1.1. `privacyman`, `alertinfo`, `delay_answer`, `fanswer` → ogohl. agar standartdan farqli. |
| `outbound_routes` + `_patterns` + `_trunks(seq)` | `outbound_routes` + `outbound_route_patterns` + `outbound_route_trunks(position=seq)` | `seq` tartibi = failover tartibi; `match_pattern_prefix` → `strip_prefix`, `match_pattern_pass` → `pattern`, `prepend_digits` → `add_prefix`, `match_cid` → `callerid_match`; `outcid` → `callerid`; `outcid_mode` `override_extension` → `override_extension_callerid`; `password` → `pin_hash`; `emergency_route`, `time_group_id≠0` → ogohl. Mavjud bo'lmagan trunk → shu trunk tashlanadi + ogohl.; trunk qolmasa → `skip`. Tartib — `outbound_route_sequence`. |
| `ringgroups` | `ring_groups` + `ring_group_members` | `strategy`: `ringall*`→`ringall`, `hunt*`→`hunt`, `memoryhunt*`→`memoryhunt`, boshqalar → `ringall` + ogohl.; `grptime` 5–300; `grplist`: ichki → `extension_id`, `#` yoki ichki emas → `external_number`; `postdest` → `no_answer_target_id`; `grppre` → `callerid_prefix`. |
| `queues_config` + `queues_details` (EAV) + astdb `QPENALTY/<N>/agents/<a>` | `queues` + `queue_members` | `strategy` mos (Innova to'plamida bo'lmasa → `ringall` + ogohl.); `timeout`→`agent_ring_seconds`, `retry`, `wrapuptime`→`wrapup`, `maxwait`→`max_wait` (0 → cheksiz), `maxlen`→`max_callers`, `music`→`moh_class_id` (nom bo'yicha), `servicelevel`→`sla`, `joinempty`, `dest`→`timeout_target_id`. `member` `Local/<N>@from-queue/n,<penalty>` yoki `PJSIP/<N>` → statik (`dynamic=false`); astdb QPENALTY → dinamik (`dynamic=true`). |
| `ivr_details` + `ivr_entries` | `ivrs` + `ivr_options` | `announcement` (recording id) → `greeting`; `invalid_recording`/`timeout_recording` id → audio (`default`/bo'sh → yo'q); `timeout_time`, `invalid_loops`/`timeout_loops` → `repeats` (kattasi); `directdial` (`ext-local` yoki bo'sh emas) → `direct_dial`; `invalid_destination`/`timeout_destination` → targetlar; `ivr_entries.selection` (0–9, `*`, `#`) → `digit`, boshqa (`i`,`t`, ko'p xonali) → ogohl. |
| `timeconditions` | `time_conditions` | `time` → time_group; `truegoto` → **open** target, `falsegoto` → **closed** target (UI kirish formati teskari bo'lsa ham SXEMA ustunlari aniq — test majburiy); `mode='calendar'` → `unsupported`. Bayram bo'lsa `honor_holidays=true`. |
| `announcement` | `announcements` | `recording_id` → `audio_file_id` (yo'q → `skip` `audio_missing`); `post_dest` → `next_target_id`; `allow_skip`/`repeat_msg`/`return_ivr` → ogohl. agar ≠ 0. |
| `meetme` (+ astdb `CONFERENCE/<N>/*`) | `conferences` (+ `dial_numbers` N) | `userpin`/`adminpin` → xesh; `users` 0 → `max_members` NULL. `conferences_*` (confbridge 17) jadvali bo'lsa shu qoida. |
| `miscdests` | — (`ignored`, `reason: resolved_inline`) | 1.1 orqali manzil sifatida ishlatiladi. |
| astdb `blacklist/<raqam>` = izoh (`blacklist/dest`, `blockunknown` — kalit emas) | `blacklist(number, reason)` | raqam `number_normalize` bilan; mavjud bo'lsa `skip` `exists`. |
| `featurecodes` (`customcode` bo'sh emas va ≠ `defaultcode`) | `feature_codes` | Moslik: `voicemail.myvoicemail`→`voicemail`, `voicemail.dialvoicemail`→`voicemail_other`, `donotdisturb.dnd_toggle`→`dnd_toggle`, `callforward.cfon`→`cf_always_on`, `callforward.cfoff`→`cf_always_off`, `callforward.cfbon`→`cf_busy_on`, `callforward.cfboff`→`cf_busy_off`, `core.pickup`→`pickup_direct`, `core.pickupexten`→`pickup_group`, `parking.parkedcall`→`park`, `infoservices.calltrace`… (moslik yo'q) → `ignored` `no_innova_feature`. `enabled=0` → `enabled=false`. Kod to'qnashuvi → `conflict`. |
| `admin`, `freepbx_settings`, `module_xml`, `modules`, `kvstore*`, `cron*`, `notifications`, `certman_*`, `sipsettings`, `logfile_*`, `dahdi*` va h.k. | — | `ignored` (`reason: system_table`) |
| `conf/*_custom*.conf` (bo'sh emas) | — | `warnings[]` `custom_dialplan_present` (fayl nomi, kontekstlar ro'yxati) — tarjima qilinmaydi. |

### 1.3 To'qnashuv va nomlar
- Raqam: Innova `dial_numbers` da band → `conflict` (`reason: number_taken`, kim band qilgani). Feature kodi bilan to'qnashuv ham `conflict`.
- Unique nomlar (trunk, ring group, IVR, …) band bo'lsa — nomga ` (FreePBX)`, keyin ` (FreePBX 2)` qo'shiladi (ogohl.), bu `conflict` EMAS.
- Avvalgi importdan kelgan (`migration_items` da bor) → sukut `skip` (`reason: already_imported`), `replace` mumkin.

## 2. Ma'lumotlar (migratsiya `0022_m5a_migration`)
- `migration_jobs(id, tenant_id, source upload|ssh, status uploaded|analyzing|analyzed|applying|ok|failed, step, progress, source_meta jsonb,
  plan jsonb, options jsonb, result jsonb, error, pre_import_backup_id → backups, bundle_path, created_by, created_at, finished_at)`.
- `migration_items(job_id → migration_jobs ON DELETE CASCADE, kind, source_ref, innova_kind, innova_id uuid)`, unique `(tenant_id?, kind, source_ref)`.
- `migration_jobs` va `migration_items` zaxiraga (`config`) KIRADI.

## 3. API — `/api/v1/migration/freepbx` (admin)
- `GET /export-script` — skript (text/x-shellscript). `POST /upload` (multipart, oqimli; ≤ 20 GB) → `{item: job}`.
- `POST /ssh/test {host, port, username, password?|private_key?}` → `{ok, host_key_fp, error?}`; `POST /ssh/fetch {..., host_key_fp}` → 202 `{job}`
  (barmoq izi mos kelmasa 422 `host_key_mismatch`).
- `POST /jobs/{id}/analyze` → 202; `GET /jobs/{id}` → `{status, step, progress, source_meta, summary, plan?}`; `GET /jobs/{id}/plan?kind=&action=`
  (sahifalangan). `PATCH /jobs/{id}/plan {items:[{source_ref, kind, action}]}` (faqat conflict → skip|replace, create → skip).
- `POST /jobs/{id}/apply {confirm:"KOCHIRISH", options:{rotate_weak_secrets}}` → 202; 422 `confirm_required`, 409 `job_running`,
  409 `plan_stale` (analyze'dan keyin Innova'da to'qnashuv paydo bo'lsa — qayta analyze).
- `GET /jobs` (tarix), `DELETE /jobs/{id}` (to'plam fayli o'chadi; import natijasi qoladi). `GET /jobs/{id}/report` — CSV (nima, qayerga, ogohlantirish).

## 4. UI — `/settings/migration` (S36), uz/ru/en, light+dark
- Bosqichli sehrgar: **1 Manba** (to'plam yuklash yoki SSH; skriptni yuklab olish + bitta buyruq nusxalash) → **2 Tahlil** (progress) →
  **3 Ko'rib chiqish** (turlar bo'yicha kartalar: yaratiladi / o'tkaziladi / to'qnashuv / qo'llab-quvvatlanmaydi; jadval filtr bilan, har element
  sababi, to'qnashuvda skip/replace; zaif parollar bloki + «yangi parol yaratish» tanlovi) → **4 Qo'llash** (`KOCHIRISH` yozib tasdiqlash,
  `pre_import` zaxira haqida aniq matn, progress) → **5 Natija** (hisobot, CSV, «bekor qilish» = pre_import zaxirani tiklash havolasi).
- Ko'chirish tarixi jadvali.

## 5. Isbot (`scripts/m5a-proof.sh --fresh`)
Toza stek (`--fresh`) → admin → `tests/freepbx-fixture/bundle/fpbx-export-fixture.tar.gz`:
1. RBAC: operator → 403; yaroqsiz to'plam (tasodifiy tar, `meta.format` noto'g'ri, `../` yo'l) → 422 `bundle_invalid`; `export-script` `bash -n` dan o'tadi.
2. upload → analyze → plan: aniq sonlar — extensions 6 (101,102,103,105,106,107), trunks 2 (register + ip), inbound 3 (biri catch-all),
   outbound 2 (Mobil: 2 trunk tartib 1→2), ring group 600 (3 ichki + 1 tashqi), queue 700 (2 statik + 1 dinamik), IVR 1 (3 variant),
   time group 1 (+ 1 bayram 1-yanvar), time condition 1, announcement 1, audio 1, MOH 1 (`sinov-moh`; `default` → skip), konferensiya 8000,
   voicemail 105 (namunaviy 1234 → ignored), blacklist 1, feature code `voicemail`→`*970`, `custom_dialplan_present` ogohlantirishi.
   Rejada va javobda sir YO'Q (`SinovSecret`, `SinovTrunkSecret`, `1105`, `1234`, `4321` grep → 0). Manbadagi har qator rejada yoki `ignored` da.
3. `apply` confirm'siz → 422; to'g'ri → 202 → `ok`; `pre_import` zaxira yaratilgan; dialplan reviziya «FreePBX importi».
4. Innova'da jonli: ext 102 `forward_always=106`, `forward_busy=106`, no-answer → ext 105; ext 106 `dnd=true`, outbound CID `+998901110106`;
   ext 107 follow_me `["0991234567"]`; TC 1 open → IVR, closed → e'lon (TESKARI EMAS); IVR 1→101, 2→RG 600, 3→Q 700; DID 998712345601 → IVR;
   outbound Mobil: `strip 0`, `add +998`, trunklar [register, ip]; ip trunk `match_ips=[203.0.113.10/32]`.
5. Asterisk: `pjsip show endpoint 101` bor; SIP REGISTER `101 / SinovSecret101!` bilan (sipp yoki `pjsip` test klient) → 200 OK — parol o'zgarmay
   ko'chgani isboti; DID 998712345601 ga kiruvchi qo'ng'iroq IVR greeting'ini o'ynaydi (CDR/`core show channels`).
6. Idempotentlik: shu to'plamni qayta analyze → hammasi `skip already_imported`, apply → yangi qator 0.
7. To'qnashuv: qo'lda ext 101 yaratilgan toza tenantda → 101 `conflict`, `replace` taqiqlangan (422), qolganlari import bo'ladi; 101 ga
   bog'liq manzillar mavjud 101 ga ulanadi (ogohl.).
8. Atomarlik: apply o'rtasida xato (test hook `INNOVA_TEST_FAIL_AT=routes`) → DB o'zgarmagan, audio fayllar tozalangan, status `failed`.
9. Bekor qilish: `pre_import` zaxirani tiklash → import qilingan obyektlar yo'q.
10. `DELETE /jobs/{id}` → to'plam fayli diskda yo'q. Audit: `migration.analyze`, `migration.apply` — sirlar `***`.
Real-check (`web/scripts/m5a-real-check.mjs`): sehrgar 5 bosqich jonli API bilan, uz/ru/en, light+dark, mobil 390px, konsol xatosiz.
