# M5b kontrakt — Follow Me + SIP sozlamasi QR orqali (2026-10-31)

Manba: features.csv «Follow Me / javob bo'lmasa mobilga yo'naltirish» (should, B2), «SIP ma'lumotini QR bilan ko'rsatish» (should, B2).
Hozirgi holat: `extensions.follow_me` JSONB ustuni bor (models.py:166), lekin hech qayerda ishlatilmaydi. QR umuman yo'q.

## 1. Follow Me

### Ma'lumot (extensions.follow_me, JSONB — migratsiya 0024 normallashtiradi)
```json
{"enabled": false, "numbers": [], "strategy": "ring_all", "include_extension": true,
 "ring_seconds": 20, "confirm": true}
```
- `numbers`: 1..6 ta; har biri ichki raqam (mavjud, o'zi emas) yoki tashqi raqam (`normalize_number`). Takror yo'q.
- `strategy`: `ring_all` (hammasi birga) | `sequential` (ro'yxat tartibida, har biriga `ring_seconds`).
- `include_extension`: FAQAT ring_all'da ma'noli — ichki raqam ham ro'yxat bilan birga jiringlaydi (sequential'da e'tiborsiz).
- `ring_seconds`: 5..120 (amalga oshirishda 5 — isbotda tez sinov uchun; sukut 20).
- `confirm`: tashqi raqam javob bersa «qabul qilish uchun 1 ni bosing» (mobil ovozli pochtasi qo'ng'iroqni «yeb» qo'ymasin). Faqat tashqi raqamlarga.
- Tashqi raqam bo'lsa va ext `outbound_allowed=false` yoki toll-blok → 422 `follow_me_outbound_forbidden` (saqlashda); qo'ng'iroq paytida ham toll/ruxsat tekshiruvi ishlaydi (yo'naltirish kabi — chiqish ruxsatlari ext'niki, `INNOVA_FWD_FROM`).

### Qo'ng'iroq oqimi (`{code}-ext-call`)
DND → forward_always → ext `ring_seconds` jiringlaydi → BUSY va forward_busy bo'lsa → fwd →
**javobsiz/CHANUNAVAIL va follow_me.enabled → Follow Me bosqichi** → `no_answer` manzili (yo'q bo'lsa Hangup).
- BUSY bo'lsa ham (forward_busy yo'q) Follow Me ishlaydi.
- Halqa himoyasi mavjud `INNOVA_FWD_SEEN` mexanizmi bilan; Follow Me ro'yxatidagi ichki raqamlarning o'z Follow Me'si ishga TUSHMAYDI (bir pog'ona).
- Asl CallerID saqlanadi; CDR'da qo'ng'iroq bitta `linkedid` ostida.
- O'zgarish dialplan reload'SIZ kuchga kiradi (M2a kabi realtime: `asterisk_ext_state` view'ga kerakli ustunlar).
- Tasdiq prompti: Asterisk sound pack'dagi mavjud fayllar (masalan `followme/options`), mavjudligini tekshiring; yo'q bo'lsa — o'zimiz yozgan qisqa audio (repo ichida).

### API
- `GET/PUT /api/v1/extensions/{id}/follow-me` (admin) — to'liq obyekt, validatsiya, audit (`extension.follow_me`).
- `GET/PUT /api/v1/me/follow-me` (operator — faqat o'z raqami).
- Xususiyat kodi `followme_toggle` standart `*21` (S24 jadvaliga; prefiks to'qnashuvi 409 mavjud mexanizm bilan). Ro'yxat bo'sh bo'lsa yoqmaydi (prompt).
- FreePBX importi (`services/fpbx/mappers/extension.py`) yangi shaklga mos yozsin (grplist → numbers, strategy ringallv2→ring_all, hunt→sequential, pre_ring → include_extension).
  Amalda: o'z raqami grplist'da → include_extension; `enabled` = astdb `AMPUSER/<N>/followme/ddial == DIRECT`
  (FreePBX: kalit yo'q yoki `EXTENSION` = o'chiq, `Findmefollow.class.php`); pre_ring yo'q → `partial_mapping` ogohlantirishi.

### UI
- Ichki raqam tahriri (S04) → «Follow Me» bo'limi: yoqish, raqamlar ro'yxati (qo'shish/o'chirish/tartib), strategiya, vaqt, tasdiq.
  Tushunarli izoh: «Ichki raqam N soniya javob bermasa, quyidagilarga jiringlaydi».
- Operator portali `/me` → xuddi shu blok (soddalashtirilgan).
- uz/ru/en tarjimalar.

## 2. SIP sozlamasi QR orqali

- Maqsad: mobil softfonni (Linphone) QR skanerlab sozlash. Parol QR ichida EMAS — QR'da bir martalik havola.
- `POST /api/v1/extensions/{id}/qr-provisioning` (admin) va `POST /api/v1/me/qr-provisioning` (operator, o'z raqami) →
  `{"url": "https://<public_host>/prov/qr/<token>/linphone.xml", "expires_at": "...", "transport": "tls|udp|tcp"}`.
  QR havolasi `allowed_networks` (M4a) cheklovini e'tiborsiz qoldiradi — telefon mobil tarmoqdan oladi; himoya = token+TTL+rate-limit.
  Token: 32+ bayt tasodifiy, bazada faqat xeshi, TTL 15 daqiqa, birinchi muvaffaqiyatli olishdan keyin 60 s ichida yaroqsiz; yangi token eskisini bekor qiladi.
- `GET /prov/qr/<token>/linphone.xml` (autentifikatsiyasiz, M4a `/prov` rate-limit mexanizmi): Linphone remote-provisioning XML
  (proxy, auth_info, transport; TLS yoqilgan bo'lsa TLS), `Cache-Control: no-store`. Yaroqsiz/eskirgan → 404 (farqi bilinmasin).
  `public_host` — M4a provizioning sozlamasidagi manzil; sozlanmagan bo'lsa POST → 409 `public_host_not_configured`.
- Audit: token yaratildi / ishlatildi (sirsiz). Log'da token ko'rinmasin.
- WebRTC-only ext (`webrtc=true`) → 409 `extension_webrtc_only`.
- UI: ext sahifasi va `/me` → «Telefonga ulash» tugmasi → modal: QR (frontend'da generatsiya), qolgan vaqt hisoblagichi,
  «Linphone → Sozlamalar → Assistent → QR skanerlash» ko'rsatmasi, «Yangilash».

## Isbot
`scripts/m5b-proof.sh --fresh` (oldingilar kabi; qoldiq bo'lsa exit 2): Follow Me ring_all/sequential (SIPp: ext javob bermaydi → ro'yxatdagi
ichki raqam javob beradi; tashqi raqam trunk orqali chiqadi, confirm'da DTMF 1), reload'siz o'zgarish, *21, 422 holatlari, operator boshqa ext'ga 403;
QR: token oqimi (olish → XML'da to'g'ri foydalanuvchi, takror olish 60 s dan keyin 404, eskirgan 404, xesh bazada), rate-limit.
Oldingi isbotlar (m0..m5a) 0 FAIL qolsin. `web/scripts/m5b-real-check.mjs` (real API).
