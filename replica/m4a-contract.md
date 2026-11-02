# M4a shartnomasi — telefon apparatlarini avtoprovizioning (S35 «Qurilmalar», FreePBX EPM o'rniga)

M0–M3b shartnomalari amalda qoladi: xato formati `{"error":{"code","message","field"?,"details"?}}`, `updated_at` → 409 `stale`, ro'yxat `{"items":[...]}`,
yaratish/tahrir `{"item"}`, vaqt UTC ISO, payload YASSI, admin bo'limlari faqat `admin` (operator → 403), audit (sirlar `***`), uz/ru/en.
M4a DAN TASHQARI: ishlab chiqaruvchi bulut yo'naltirish xizmatlari (Yealink RPS, Grandstream GDMS, Fanvil FDPS), firmware yangilash, DECT bazalari,
kengaytma modullari (EXP), mobil softfon QR (keyingi bosqich), bir apparatda bir nechta akkaunt (faqat 1-akkaunt).

## 0. Tamoyillar (CTO qarorlari)
- **Apparat config'ni HTTP orqali o'zi oladi** (DHCP option 66 yoki qo'lda kiritilgan URL). Provizioning URL'i:
  `http(s)://<pbx>/prov/<prov_token>/` — `prov_token` (32 belgi, tenant uchun bitta, `system_settings.provisioning`) maxfiy yo'l segmenti.
  Apparat HTTP Basic qila olmasligi mumkin — shuning uchun himoya qatlamlari: (1) token, (2) faqat RO'YXATDAGI MAC'ga sirli config,
  (3) `allowed_networks` (CIDR ro'yxati, bo'sh = hammasi; sukut — RFC1918), (4) IP bo'yicha xato limiti: 10 daqiqada 20 ta 404/403 → shu IP 30 daqiqa 403
  (+ `raise_alert` kind `prov_bruteforce`), (5) har so'rov `provision_requests` jurnaliga (ip, ua, fayl, natija) — sir HECH QACHON logda emas.
- `web` nginx servisi `/prov/` ni API'ga proksi qiladi (`X-Forwarded-For` = `$remote_addr`, M3a saboq). Javob `Cache-Control: no-store`.
- **Konfiguratsiya generatori — sof funksiya** (`render(vendor, model, ctx) -> (filename, bytes)`), qiymatlar escape qilinadi
  (Yealink/Fanvil: qator ichida `\r`/`\n` taqiqlangan → 422 saqlashda; Grandstream: XML escape). Yaratilgan config deterministik (snapshot testlar).
- **Kim bo'lishidan qat'i nazar SIP paroli faqat** to'g'ri token + ro'yxatdagi MAC + ruxsat etilgan tarmoqdan keladi. Noma'lum MAC → 404 (lekin
  `discovered_devices` ga yoziladi — «Topilgan qurilmalar»). Umumiy (model-wide) fayllarda sir YO'Q.
- Apparat — `devices` jadvali (0001 da bor: kind `ip_phone`, vendor, model, mac, extension_id, provisioned_at). Ichki raqam `webrtc=true` bo'lsa
  ip_phone biriktirib bo'lmaydi (422 `extension_webrtc`). Bitta raqamga apparatlar soni ≤ `max_contacts`.
- Sir almashtirilganda (ichki raqam `rotate-secret` yoki parol o'zgarishi) — shu raqamdagi apparatlarga avtomatik **check-sync NOTIFY**
  (Asterisk `pjsip send notify innova-check-sync endpoint <id>`; `pjsip_notify.conf` da `Event: check-sync` — Yealink/Fanvil/Grandstream
  qayta config yuklaydi). Qo'lda «Qayta sozlash» tugmasi ham shu.

## 1. Ma'lumotlar (migratsiya `0020_m4a_provisioning`)
- `devices`: qo'shiladi `label text`, `last_seen_at`, `last_ip inet`, `user_agent text`, `firmware text`, `config_hash text` (oxirgi berilgan),
  `enabled bool default true`, `notes`. MAC normallashtiriladi (12 hex, kichik harf; `AA:BB-..` kiritilsa ham).
- `device_keys(device_id, idx 1..60, type: blf|speed_dial|line|park|dnd|none, value, label)` UNIQUE(device_id, idx). `blf` qiymati — mavjud
  ichki raqam (422 aks holda), `park` — park sloti.
- `discovered_devices(mac PK per tenant, vendor, model, ip, user_agent, firmware, first_seen_at, last_seen_at, requests int)` — biriktirilganda o'chadi.
- `provision_requests(at, ip, mac|null, vendor|null, path, status_code, reason)` — 30 kun saqlanadi (tozalovchi).
- `system_settings.provisioning = {prov_token, allowed_networks: ["10.0.0.0/8","172.16.0.0/12","192.168.0.0/16"], admin_password_enc,
  language: "uz|ru|en", timezone: "Asia/Tashkent", ntp_server: "pool.ntp.org", sip_transport: "udp|tcp|tls", sip_server_host: null (bo'sh →
  `integrations.public_base_url` hosti → so'rov Host sarlavhasi), extra: {yealink: "", grandstream: "", fanvil: ""}}` — `extra` — vendor uchun
  qo'shimcha xom qatorlar (admin o'z xavfi bilan; qator formati tekshiriladi: Yealink/Fanvil `key = value`, Grandstream `Pnnn=value`).

## 2. Vendorlar va fayllar (qo'llab-quvvatlanadigan modellar ro'yxati `GET /devices/models`)
- **Yealink** (T3x/T4x/T5x, masalan T31P, T33G, T43U, T46U, T54W): `GET /prov/<t>/y000000000000.cfg` (umumiy, sirsiz — tz, til, NTP,
  `static.auto_provision.*`) va `GET /prov/<t>/<mac>.cfg` (`#!version:1.0.0.1`, `account.1.*` — enable, label, display_name, auth_name,
  user_name, password, sip_server.1.address/port/transport_type (0 UDP/1 TCP/2 TLS), `voice_mail.number.1 = *97`, `linekey.N.*` (BLF type 16,
  speed dial 13), `static.security.user_password = admin:<parol>`). Modelga xos umumiy fayl nomlari (`y0000000000xx.cfg`) — hammasiga bitta umumiy kontent.
- **Grandstream** (GXP16xx/17xx/21xx, GRP26xx): `GET /prov/<t>/cfg<mac>.xml` — `<gs_provision version="1"><mac>..</mac><config version="1">` P-kodlar
  (P271 akkaunt yoqilgan, P47 server, P35 user, P36 auth id, P34 parol, P3 ism, P270 akkaunt nomi, P2 admin parol, P33 ovozli pochta *97, P64/P246 vaqt
  zonasi, P30 NTP, P1362 til, BLF/MPK P-kodlari modelga qarab). `cfg<mac>` (xml'siz) so'rovi → 404 (eski firmware; jurnalda `reason=legacy_binary`).
- **Fanvil** (X1/X3/X4/X5/X6/X7 seriyalari): `GET /prov/<t>/<mac>.cfg` — `<<VOIP CONFIG FILE>>Version:2.0000000000` bo'limlari (`<SIP CONFIG MODULE>`
  `SIP1 Phone Number`, `SIP1 Display Name`, `SIP1 Register Addr/Port/User/Pswd`, `SIP1 Enable Reg :1`; `<DSS CONFIG MODULE>` BLF; `<WEB CONFIG MODULE>` parol;
  vaqt/NTP). Fanvil va Yealink bir xil `<mac>.cfg` nomini ishlatadi → vendor `devices.vendor` dan, ro'yxatda yo'q bo'lsa User-Agent'dan aniqlanadi.
- Vendor/model User-Agent'dan aniqlanadi (`Yealink SIP-T46U 108.86.0.20 805ec0aabbcc`, `Grandstream Model HW GXP2170 SW 1.0.11.x DevId c074ad...`,
  `Fanvil X4U 2.12.x 0c383e...`). MAC so'rov yo'lidan, bo'lmasa UA'dan.
- Sifat: har vendor uchun snapshot test + format validatsiyasi (Grandstream — XML parse; Yealink/Fanvil — har qator `key = value`/bo'lim formati).
  Aniq bo'lmagan P-kod/kalitlar shartnomada «tekshirilmagan» deb belgilanadi va UI'da emas, faqat `docs` da aytiladi.

## 3. API — `/api/v1/devices` (admin)
- `GET /devices?extension_id=&vendor=&q=` → items `{id, mac, vendor, model, label, extension:{id,number,name}, enabled, status, provisioned_at,
  last_seen_at, last_ip, firmware, registered: bool, keys_count}`. `status`: `never` (hech so'ramagan) | `provisioned` (config oldi) |
  `registered` (PJSIP contact'i shu IP'dan) | `stale_config` (config_hash joriy render'dan farq qiladi — masalan parol o'zgargan, apparat hali olmagan).
- `POST /devices {mac, vendor, model, extension_id, label?, keys?:[...]}` → 201; MAC dublikat → 409 `mac_taken`; vendor/model ro'yxatda yo'q → 422.
- `PATCH /devices/{id}` (+`updated_at`), `DELETE /devices/{id}`, `PUT /devices/{id}/keys {keys:[...]}`.
- `POST /devices/{id}/resync` → check-sync NOTIFY; apparat ro'yxatdan o'tmagan bo'lsa 409 `not_registered`. Audit `device.resync`.
- `GET /devices/{id}/config` — admin uchun ko'rish (parollar `***` bilan maskalangan; `?reveal=1` YO'Q — sir faqat apparatga).
- `GET /devices/discovered` → items; `POST /devices/discovered/{mac}/assign {extension_id, model?, label?}` → device yaratadi (vendor/model UA'dan),
  `DELETE /devices/discovered/{mac}` (e'tiborsiz qoldirish).
- `GET /devices/models` → `[{vendor, model, keys: <dastur tugmalari soni>, family}]`.
- `GET /devices/requests?mac=&ip=&limit=` → provizioning jurnali (oxirgi 200).
- `GET/PATCH /settings/provisioning` → `{url: "<to'liq provizioning URL>", has_admin_password, allowed_networks, language, timezone, ntp_server,
  sip_transport, sip_server_host, extra, updated_at}`; `POST /settings/provisioning/rotate-token` (eski URL darhol 404; tasdiq kerak — UI ogohlantiradi
  «barcha apparatlarda URL'ni o'zgartirish kerak»). `admin_password` faqat yoziladi.
- Ichki raqam sahifasi (S05) da «Apparatlar» bloki: biriktirilgan apparatlar + «Apparat qo'shish».

## 4. UI — `/devices` (S35), uz/ru/en, light+dark
- Yuqorida «Provizioning manzili» kartasi: URL (nusxa tugmasi), DHCP option 66 qiymati, qo'llanma (Yealink/Grandstream/Fanvil — apparat web
  panelida qayerga yozish, 3 qadam). Token almashtirish (xavfli amal, tasdiq dialogi).
- «Topilgan qurilmalar» banneri/jadvali (N ta yangi apparat): MAC, vendor/model (UA'dan), IP, oxirgi so'rov → «Raqamga biriktirish» (raqam qidiruvi).
- Apparatlar jadvali: holat belgisi (Hech so'ramagan / Sozlandi / Ro'yxatda / Yangilanishi kerak), MAC (mono), model, raqam, IP, firmware,
  oxirgi ko'rinish; amallar: Tahrirlash, Tugmalar (BLF tahrirlovchi — tugma raqami, turi, qiymat, yorliq; model tugmalar soni bilan cheklangan),
  Qayta sozlash, Config'ni ko'rish (maskalangan, mono), O'chirish.
- Sozlamalar tabi: til, vaqt zonasi, NTP, transport, server hosti, ruxsat etilgan tarmoqlar, apparat admin paroli (bir martalik kiritish), vendor extra.
- Jurnal tabi: provizioning so'rovlari (status, sabab — `unknown_mac|bad_token|network_denied|rate_limited|ok|legacy_binary`).

## 5. Isbot (`scripts/m4a-proof.sh --fresh`)
Proof tarmog'ida «apparat» = curl/python konteyneri (haqiqiy UA satrlari bilan) + SIPp (provizion qilingan fayldan o'qilgan login/parol bilan).
1. Token/xavfsizlik: noto'g'ri token → 404 (jurnalda `bad_token`); to'g'ri token + noma'lum MAC → 404 + `discovered_devices` da paydo bo'ladi
   (vendor/model UA'dan to'g'ri); `allowed_networks` dan tashqari IP → 403; 21-xato so'rovdan keyin shu IP → 403 `rate_limited` + alert; boshqa IP ishlaydi.
   Umumiy `y000000000000.cfg` da parol YO'Q. Jurnal/audit/`/devices/{id}/config` da parol YO'Q (`***`).
2. Yealink: topilgan apparatni 101 ga biriktirish → `<mac>.cfg` 200, `account.1.*` to'g'ri; config'dan olingan user/parol bilan SIPp REGISTER → 200,
   `/devices` da status `registered`; BLF 102 tugmasi `linekey.1.type = 16`, `value = 102`.
3. Grandstream: `cfg<mac>.xml` — XML valid, P35/P34/P47 to'g'ri, SIPp shu ma'lumot bilan ro'yxatdan o'tadi. Fanvil — `SIP1 Register User/Pswd` to'g'ri.
4. Yangilanish: 101 `rotate-secret` → status `stale_config` → apparat (SIPp UAS) `NOTIFY Event: check-sync` oladi → qayta yuklash → `provisioned`,
   yangi parol bilan REGISTER 200, eski parol 401. `POST /resync` ro'yxatda bo'lmagan apparatga → 409.
5. Validatsiya: MAC dublikat 409, webrtc raqamga 422, `max_contacts` dan ortiq 422, BLF noma'lum raqam 422, label'da `\n` 422, `extra` noto'g'ri qator 422.
6. Token almashtirish → eski URL 404, yangi 200. Operator → `/devices` 403.
7. UI real API bilan (`web/scripts/m4a-real-check.mjs`): topilganni biriktirish, BLF tahrirlash, config ko'rish (maskalangan), qayta sozlash;
   skrinshotlar `replica/clone-screens/m4a-*.png` light+dark; 5xx/console xato = FAIL.
Barcha oldingi isbotlar (m0 … m3b) `--fresh` 0 FAIL; pytest, vitest, tsc toza; ub-mode (crapper < 10, dryer, mutator) yangi kodda.
