# M4b shartnomasi — zaxira nusxa va tiklash (S34 «Zaxira», FreePBX Backup & Restore o'rniga)

M0–M4a shartnomalari amalda qoladi: xato formati `{"error":{"code","message","field"?,"details"?}}`, `updated_at` → 409 `stale`, ro'yxat `{"items":[...]}`,
yaratish/tahrir `{"item"}`, vaqt UTC ISO, payload YASSI, faqat `admin` (operator → 403), audit (sirlar `***`), uz/ru/en, light+dark.
M4b DAN TASHQARI: FreePBX zaxirasini import qilish (keyingi bosqich), Google Drive/FTP/Dropbox, inkremental/differensial zaxira, bir nechta ijarachi
(butun tizim bitta zaxira), PITR/WAL arxiv, zaxirani boshqa versiyaga (yangiroq → eskiroq) tiklash.

## 0. Tamoyillar (CTO qarorlari)
- **Zaxira = bitta shifrlangan fayl** `innova-<host>-<YYYYmmdd-HHMMSS>-<id8>.ibk`. Ichida tar: `manifest.json` + qismlar. Format `INNOVABK1`:
  sarlavha (magic, versiya, scrypt salt/parametrlar n=2^15 r=8 p=1, base nonce) + 1 MiB bo'laklar, har biri AES-256-GCM (nonce = base‖counter,
  AAD = counter + `last` bayroq) → o'zgartirish, kesish, bo'lak almashtirish ANIQLANADI (422 `backup_corrupt`). Kalit = scrypt(**zaxira paroli**).
  Lokal nusxa ham shifrlangan (bitta format, bitta kod yo'li). Oqimli (streaming) — butun arxiv xotiraga yuklanmaydi, GB'lik yozuvlar ishlaydi.
- **Zaxira paroli** (`system_settings.backup.passphrase_enc`, `encrypt_secret` bilan) — o'rnatilmaguncha zaxira 409 `passphrase_required`.
  Parol HECH QACHON javob/log/audit/manifestda yo'q. UI: «Parolni yo'qotsangiz, zaxirani tiklab bo'lmaydi» ogohlantirishi. Min 12 belgi.
  Parol almashtirilsa eski zaxiralar ESKI parol bilan qoladi (qayta shifrlanmaydi) — tiklashda parol so'raladi, sukut = joriy parol.
- **Qismlar (components)**: `config` (DOIM; DB — tarix jadvallari MA'LUMOTISIZ), `history` (cdr, cel, queue_log, agent_events, alert_log,
  audit_log, provision_requests, integration_deliveries/events va h.k. — ro'yxat `backup_parts.HISTORY_TABLES`, test: har yangi jadval yoki
  config'da yoki history'da — jim tushib qolmaydi), `sounds` (`/var/lib/innova/sounds`), `voicemail`, `recordings`, `certs`.
  Sukut: hammasi, `recordings` ixtiyoriy (katta). Dialplan/generatsiya qilingan conf fayllar ZAXIRALANMAYDI — tiklashdan keyin qayta yaratiladi.
- **DB**: `pg_dump -Fc` (klient 16 — `postgresql-client-16` PGDG'dan; bookworm'dagi 15 server 16 bilan ishlamaydi). `backups`, `backup_copies`,
  `restore_jobs` jadvallari ma'lumoti dump'ga KIRMAYDI va tiklashda saqlanib qoladi (tarix yo'qolmaydi).
- **Manifest**: `format, product_version, alembic_revision, created_at, source_host, components[], parts[{name, size, sha256}], db_key_fp`
  (`db_key_fp` = INNOVA_DB_KEY ning sha256 dan 16 belgi — kalitning o'zi EMAS). Arxiv ichida `db_key.enc` — INNOVA_DB_KEY zaxira paroli bilan
  shifrlangan (arxiv o'zi shifrlangani uchun — faqat shu qism). Kerakligi: boshqa serverga tiklashda sirlarni qayta shifrlash (re-key).
- **Saqlash joylari**: `local` (volume `backups` → `/var/lib/innova/backups`, DOIM), `s3` (S3-mos: AWS/MinIO/Wasabi/Yandex; endpoint, region,
  bucket, prefix, access key, secret `encrypt_secret`, path-style; multipart), `sftp` (host, port, user, parol YOKI kalit (encrypt_secret),
  papka; **host kaliti pin**: «Ulanishni tekshirish» barmoq izini ko'rsatadi → admin tasdiqlaydi → `host_key_fp` saqlanadi; mos kelmasa
  `host_key_mismatch`, jim qabul YO'Q). Har saqlash joyida `keep_last` (1–365; local sukut 7). Retention faqat MUVAFFAQIYATLI yangi nusxadan keyin
  ishlaydi va faqat o'zimizning `innova-*.ibk` fayllarga tegadi. Bitta zaxira barcha yoqilgan joylarga yuklanadi → `backup_copies`.
  Holat: hammasi ok → `ok`; lokal ok, masofaviy xato → `partial` (+ alert); lokal xato → `failed`.
- **Jadval**: `system_settings.backup.schedule` — `enabled, frequency (daily|weekly), weekday, time "HH:MM"` (tenant TZ), `components`.
  Fon vazifasi (minutiga 1 tekshiradi, `BACKUP_SCHEDULER_ENABLED`). Server o'chiq bo'lib o'tkazib yuborilsa — ishga tushgach BIR marta (catch-up).
  Bir vaqtda bitta ish (zaxira yoki tiklash): pg advisory lock → 409 `job_running`. Xato → `raise_alert` kind `backup_failed`;
  2× davr davomida muvaffaqiyatli zaxira yo'q → `backup_stale` (kuniga 1 marta).
- **Tiklash — ikki bosqich**: (1) `inspect` — faylni shifrdan ochib, BARCHA sha256 tekshiradi, manifestni qaytaradi (hech narsa o'zgarmaydi);
  (2) `restore` — `confirm: "TIKLASH"` + parol. Ketma-ketlik: faol qo'ng'iroq bor → 409 `active_calls` (`force=true` bilan davom) →
  **avtomatik `pre_restore` zaxira** (lokal, bekor qilish uchun) → texnik xizmat rejimi (boshqa API so'rovlari 503 `maintenance`, `/healthz` va
  `/backups/jobs/{id}` ochiq, fon vazifalari pauza) → `pg_restore --clean --if-exists --single-transaction --no-owner` (xato → tranzaksiya
  qaytadi, eski holat buzilmaydi) → `alembic upgrade head` → `db_key_fp` farq qilsa re-key (`crypto_registry.ENCRYPTED_COLUMNS` — har shifrlangan
  ustun; test: `encrypt_secret` yoziladigan har ustun ro'yxatda) → fayl qismlari (vaqtinchalik papkaga ochib, keyin almashtirish) →
  barcha generatsiya qilinadigan fayllar qayta yaratiladi (`regen_all.py`: dialplan kompilyatsiya + reload, MOH, ACL, transport/RTP, voicemail,
  pjsip_notify, TLS) → Asterisk reload (transport o'zgarsa `restart_required` S32 kabi) → audit. Manifest `alembic_revision` joriydan YANGIROQ →
  422 `backup_newer`. Tiklashdan keyin sessiyalar bekor (foydalanuvchilar jadvali almashgan) — UI login sahifasiga «Tizim tiklandi» xabari bilan.
- **Boshqa serverga ko'chirish (disaster recovery)** asosiy ssenariy: yangi o'rnatilgan Innova'da fayl yuklash → inspect → restore.
  Yuklash oqimli, `web` nginx `/api/v1/backups/upload` uchun `client_max_body_size 50g; proxy_request_buffering off;`.

## 1. Ma'lumotlar (migratsiya `0021_m4b_backup`)
- `backups` (0001 da bor) ga: `kind (scheduled|manual|pre_restore|uploaded)`, `components text[]`, `status` ga `partial`, `step text`,
  `progress smallint`, `file_name`, `sha256`, `manifest jsonb`, `created_by`. `target`, `path` ustunlari — `backup_copies` ga ko'chadi.
- `backup_copies(id, backup_id → backups ON DELETE CASCADE, target local|s3|sftp, status pending|ok|failed|deleted, remote_path, size_bytes,
  error, uploaded_at)`, unique `(backup_id, target)`.
- `restore_jobs(id, tenant_id, backup_id null, source local|upload, status running|ok|failed, step, progress, error, force, pre_restore_backup_id,
  started_by, started_at, finished_at, result jsonb)`.
- `system_settings.backup`: `passphrase_enc, schedule{...}, targets{local{keep_last}, s3{enabled,...}, sftp{enabled,...}}`.

## 2. API — `/api/v1/backups` (admin)
- `GET /backups` (yangi birinchi; copies bilan), `POST /backups {components[]}` → 202 `{job:{kind:"backup", id}}`, `GET /backups/{id}`,
  `DELETE /backups/{id}` (barcha nusxalar; `pre_restore` oxirgisi o'chirilsa ham ruxsat, audit), `GET /backups/{id}/download` (lokal nusxa, oqim;
  yo'q bo'lsa 409 `no_local_copy`), `POST /backups/{id}/fetch` (masofaviydan lokalga qaytarib olish — lokal retention o'chirgan bo'lsa).
- `POST /backups/upload` (multipart, oqimli) → `{item}` (kind `uploaded`, manifest hali yo'q). `POST /backups/{id}/inspect {passphrase?}` →
  `{manifest, checks:{sha256:"ok"}, compatible: bool, warnings[]}`; xatolar 422 `bad_passphrase` | `backup_corrupt` | `backup_newer`.
- `POST /backups/{id}/restore {passphrase?, confirm:"TIKLASH", force?}` → 202 `{job:{kind:"restore", id}}`; 409 `active_calls`(`details.count`),
  `job_running`; 422 `confirm_required`.
- `GET /backups/jobs/{id}` → `{kind, status, step, progress, error}` (maintenance paytida ham ochiq; tiklashdan keyin eski token ishlamasa ham
  job_id ni biluvchi uchun 200 — job id 128-bit tasodifiy, faqat holat, sirsiz). `GET /backups/restores` (tarix).
- `GET/PUT /settings/backup` (sirlar `***` / `has_*: true`), `PUT /settings/backup/passphrase {passphrase, current?}` (almashtirishda joriy shart),
  `POST /settings/backup/targets/{s3|sftp}/test` → `{ok, error?, host_key_fp?}` (yozib-o'qib-o'chirib sinaydi), `POST .../sftp/trust {host_key_fp}`.

## 3. UI — `/settings/backup` (S34), uz/ru/en, light+dark
- Yuqorida holat kartasi: oxirgi muvaffaqiyatli zaxira (qachon, hajm, joylar), keyingi rejalashtirilgan vaqt, parol o'rnatilmagan bo'lsa ogohlantirish.
- «Hozir zaxiralash» (qismlar tanlovi, recordings hajmi ko'rsatiladi) → progress (step + %); tugagach toast.
- Zaxiralar jadvali: sana, turi (Jadval/Qo'lda/Tiklashdan oldin/Yuklangan), qismlar, hajm, nusxalar chiplari (Lokal/S3/SFTP: ok/xato tooltip bilan),
  amallar: yuklab olish, tiklash, o'chirish (tasdiq). Bo'sh holat — «Hali zaxira yo'q» + «Birinchi zaxirani yarating».
- «Jadval va saqlash joylari»: jadval, keep_last, S3 va SFTP formalari («Ulanishni tekshirish»; SFTP barmoq izi tasdiq dialogi).
  «Zaxira paroli» bo'limi (o'rnatish/almashtirish, kuch ko'rsatkichi, yo'qotish ogohlantirishi).
- «Fayldan tiklash»: yuklash (progress) → parol → inspect natijasi (sana, manba server, versiya, qismlar, hajmlar, ogohlantirishlar) →
  tiklash dialogi: nima almashtirilishini aniq aytadi, faol qo'ng'iroqlar soni, `TIKLASH` yozib tasdiqlash → to'liq ekran progress →
  tugagach login sahifasi «Tizim tiklandi». Tiklash tarixi (kim, qachon, natija, `pre_restore` zaxirasiga havola = «bekor qilish»).

## 4. Isbot (`scripts/m4b-proof.sh --fresh`)
Proof tarmog'ida MinIO (S3) va SFTP (`atmoz/sftp`) konteynerlari, SIPp.
1. Parolsiz zaxira 409 `passphrase_required`; parol o'rnatildi; to'liq zaxira (recordings bilan) → `ok`, lokal fayl bor, faylda ochiq matn YO'Q
   (raqam/trunk nomi/`PGDMP` grep 0), inspect → barcha sha256 ok. Parol/sirlar javob, audit, `docker logs api` da YO'Q.
2. Buzilish: 1 bayt o'zgartirilgan, oxiri kesilgan, noto'g'ri parol → mos ravishda `backup_corrupt`, `backup_corrupt`, `bad_passphrase`.
3. S3 + SFTP: test (to'g'ri → ok; noto'g'ri kalit/parol → aniq xato), SFTP barmoq izi tasdiqlanmasa zaxira `partial`, kalit almashsa
   `host_key_mismatch`. 3 ta zaxira, `keep_last=2` → MinIO va SFTP da to'g'ridan-to'g'ri sanalganda 2 ta, begona fayl tegilmagan.
   SFTP o'chirilgan → `partial` + `alert_log` da `backup_failed`.
4. Shu serverga tiklash: zaxiradan keyin o'zgarishlar (ext 150 qo'shish, 102 o'chirish, IVR o'zgartirish, MOH fayl o'chirish) → restore →
   holat zaxiradagiga TENG (`/extensions`, `/ivr`, `/trunks`, `/settings/*` kanonik JSON solishtirish), 101 eski parol bilan REGISTER 200,
   101→102 qo'ng'iroq javob topadi, MOH fayl va yozuv audio API orqali 200, CDR tarix bor. `pre_restore` zaxira yaratilgan; uni tiklash → ext 150 qaytadi.
   Tiklash paytida boshqa so'rov 503 `maintenance`. Faol qo'ng'iroqda 409 `active_calls`; parallel ikkinchi ish 409 `job_running`.
5. Disaster recovery: zaxira faylini yuklab olish → `docker compose down -v` → BOSHQA `INNOVA_DB_KEY` bilan fresh up (asl `.env` keyin qaytariladi)
   → upload → inspect → restore → trunk siri to'g'ri (re-key; realtime view'da eski parol), ext eski parol bilan REGISTER 200, zaxiradagi admin login.
6. Jadval: 1 daqiqadan keyingi vaqtga qo'yiladi → ≤ 120 s ichida `scheduled` zaxira paydo bo'ladi (bitta).
7. Operator → `/backups` 403. `backup_newer` va jadval/retention chegaralari — pytest.
8. UI real API bilan (`web/scripts/m4b-real-check.mjs`): parol o'rnatish, hozir zaxiralash + progress, jadval saqlash, fayl yuklab olish,
   inspect, tiklash (shu stekda, `TIKLASH`) → login sahifasi; skrinshotlar `replica/clone-screens/m4b-*.png` light+dark; 5xx/console xato = FAIL.
Barcha oldingi isbotlar (m0 … m4a) `--fresh` 0 FAIL; pytest, vitest, tsc toza; ub-mode (crapper < 10, dryer, mutator) yangi kodda.
