# M12 — qolgan kichik ishlar + xavfsizlik (reliz 1.0.14)

Sana: 2026-11-04. Asos: 1.0.13 (`e34dbbc`). Uslub: m9/m10 shartnomalari. Clean-room (FreePBX kodi/matni olinmaydi).

## A. Telefoniya (asterisk-engineer) — migratsiya `0035_m12a`

### A1. Kun/Tun rejimi (Call Flow Control)
- Jadval `day_night` (tenant_id, id, name, code 0–9 unikal tenant ichida, mode `day|night`, day_target_id → call_targets,
  night_target_id → call_targets, pin nullable — HMAC (mavjud PIN to'plami usuli), created/updated_at).
- `call_targets.kind` ga `day_night` qo'shiladi (CHECK kengaytiriladi) — marshrut/IVR/vaqt shartidan manzil bo'la oladi.
- Holat astdb'da EMAS — PG'da manba; dialplan `ODBC/func_realtime` yoki mavjud usul bilan o'qiydi (reload'siz almashsin).
  Kompilyator: `[t1-daynight-<code>]` → holatga qarab day/night manzilga.
- Funksiya kodi `*28` + raqam (`*280`…`*289`): PIN bo'lsa so'raydi, rejimni almashtiradi, «kun/tun rejimi yoqildi» ovozi;
  BLF: `DEVICE_STATE(Custom:DAYNIGHT<code>)` (tun = INUSE) — hint `*28<code>`.
- API `/api/v1/day-night` CRUD + `POST /{id}/toggle` (hudud `routing:edit`), audit. Web: Marshrutlash guruhida «Kun/Tun» sahifasi
  (ro'yxat, katta almashtirgich, manzil tanlagich — mavjud `TargetPicker`).

### A2. DISA
- Jadval `disa` (tenant_id, id, name, pin HMAC nullable, cid_override nullable, outbound kontekst = tenant chiquvchi marshrutlari,
  digit_timeout, response_timeout, max_attempts=3, enabled).
- `call_targets.kind` ga `disa`. Kompilyator: PIN → 3 xato urinishdan keyin Hangup; `DISA()` ilovasi o'rniga o'z dialplan
  (Read + chiquvchi marshrutga Goto) bo'lishi mumkin — muhimi: faqat chiquvchi marshrut ruxsatlari, ichki xizmat kodlariga yo'l YO'Q.
- Xavfsizlik: PIN bo'sh DISA yaratish faqat `allow_no_pin=true` + ogohlantirish bilan; toll-fraud — mavjud blacklist/rate cheklovlari ishlaydi.
- API `/api/v1/disa` CRUD (`routing:edit`), audit; Web sahifa «DISA» (Ilovalar guruhi).

### A3. Ring group `memoryhunt`
- BEKOR QILINDI (2026-11-04): aylanma xotira (`RG/<id>/last`) — bu `rrmemory`, FreePBX `memoryhunt` EMAS.
  `memoryhunt` m1c-contract.md:8 bo'yicha qoladi — yig'ilib boradi: `Dial(1)`, `Dial(1&2)`, `Dial(1&2&3)`
  (FreePBX importi `memoryhunt*`→`memoryhunt`, UI matni «1, 1+2, 1+2+3»; m1c-proof 5-band buni tekshiradi).

### A4. Callback CDR accountcode
- m10a callback qo'ng'iroqlari CDR'da `accountcode` bo'sh → `/cdr` da ko'rinmaydi. Originate kanaliga `Account=<tenant code>`
  (yoki `Set(CDR(accountcode)=...)` tenant kodi) — boshqa CDR maydonlarini soxtalashtirmasdan.

## B. Tizim (python-engineer) — migratsiya kerak bo'lsa `0036_m12b`

### B1. Sana/vaqt
- `GET /api/v1/system/time` → {now_utc, timezone, ntp_enabled, ntp_servers[], synced, backend: `timesyncd|chrony|none`, readonly_reason}.
- `PUT /api/v1/system/time` {timezone (IANA, allowlist `zoneinfo.available_timezones()`), ntp_servers (hostname/IP validatsiya, ≤5), ntp_enabled}
  → netd orqali (allowlist'ga `timedatectl` qo'shiladi; `/etc/systemd/timesyncd.conf.d/innova.conf` atomik yozuv).
  Asterisk/PG konteynerlariga TZ ta'siri: hujjatlashtiriladi (CDR UTC'da saqlanadi, UI Toshkent/tenant TZ'da).
- Web: Sozlamalar → «Sana va vaqt».

### B2. Qayta yuklash / o'chirish
- `POST /api/v1/system/power` {action: `reboot|poweroff`, confirm: <hostname>} — admin, audit, 10 s kechikish (javob qaytadi),
  netd allowlist'ga `systemctl` faqat `reboot`/`poweroff` argumentlari bilan (boshqa argument — rad).
- Faol qo'ng'iroqlar soni ko'rsatiladi va ogohlantiriladi. Web: «Tizim holati» sahifasida tugmalar + qo'lda yozib tasdiqlash modali.

### B3. Firewall GUI
- Manba: `nftables.conf` (`table inet innova`). Panel boshqaradi: xizmat bo'yicha ruxsat etilgan manbalar
  (SSH 22, Veb 80/443, SIP 5060/5061, RTP 10000–20000) — «hamma» yoki CIDR ro'yxati; doimiy bloklangan CIDR'lar.
  Konteyner/lo/established qoidalari va sip_guard (`innova-guard.nft`) TEGILMAYDI.
- Jadval `firewall_rules` (service, cidr, action allow|deny, comment) yoki bitta JSON sozlama — sodda variant.
- Qo'llash: netd `nft -c -f` (tekshiruv) → `nft -f` → commit-confirm (mavjud pending mexanizmi, sukut 120 s, tasdiqlanmasa eski
  ruleset tiklanadi). O'zini qulflashdan himoya: joriy admin IP'si (so'rov manbai) SSH/Veb uchun ruxsatda bo'lmasa — 422.
- `NETD_READONLY=1` (dev server!) → faqat ko'rish, yozish 409 `readonly`. DEV SERVER TARMOG'I/FIREWALL'IGA HECH QACHON YOZILMAYDI.
- Web: Sozlamalar → «Firewall».

### B4. Menyuda yangilanish nuqtasi
- `update_available` (GET /system/update) true bo'lsa, menyuda «Yangilash» bandida nuqta (admin uchun), 12 soatlik keshdan.

## C. Xavfsizlik (security-auditor) — chuqur audit
- Butun `api/app`, `web/src`, `asterisk/`, `deploy/`, `iso/files`, `install.sh` — OWASP Top 10, auth/RBAC (`require_access`),
  tenant izolyatsiyasi, dialplan injection, toll-fraud, SSRF, path traversal, fayl yuklash, sirlar, CSP/headers, docker/systemd sertifikatsiyasi.
- Avvalgi audit (1.0.12) da yopilganlar va «ataylab qoldirilgan» ro'yxat (HSTS, 80→443, non-root API, ...) qayta baholanadi.
- Natija: topilmalar ro'yxati (og'irlik, fayl:qator, ekspluatatsiya ssenariysi, tuzatish). Har CRITICAL/HIGH — koordinator qayta tekshiradi.

## Qabul mezoni
- pytest, vitest, tsc 0 xato; yangi proof `scripts/m12-proof.sh` (A: *28 almashtirish + kun/tun manzil, DISA PIN 3 urinish,
  memoryhunt aylanishi, callback CDR accountcode); butun --fresh regressiya 0 FAIL; CRAP<10 yangi kodda; mutator yangi servislarda.
