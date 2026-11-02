# M3a shartnomasi — WebRTC softfon (S16), veb konteyner (nginx), click-to-call

M0–M2c shartnomalari amalda qoladi: xato formati `{"error":{"code","message","field"?,"details"?}}`, `apply` bloki, `updated_at` → 409 `stale`,
vaqt UTC ISO, ro'yxat `{"items":[...]}`, yaratish/tahrir `{"item","apply"?}`, payload YASSI. Sirlar logda/auditda ochiq emas (`***`).
M3a DAN TASHQARI: bitta raqamda bir vaqtda stol telefoni + brauzer («ikki qurilma» — keyin), STUN/TURN sozlamalari UI, video, mobil push,
CRM/webhook/provizioning/zaxira/import/kampaniyalar (M3b+).

## 0. Tamoyillar (CTO qarorlari)
- **Raqam rejimi:** `extensions.webrtc` (ustun 0001'dan bor, API'da ko'rinmagan) — `true` bo'lsa raqamning YAGONA qurilmasi brauzer.
  Endpoint `webrtc=yes` (Asterisk 22: DTLS-SRTP, AVPF, ICE, rtcp_mux, `dtls_auto_generate_cert`) — oddiy SIP telefon u bilan ishlamaydi.
  Afzallik: dial satri o'zgarmaydi (`PJSIP/{code}-{number}`) → navbat, RG, transfer, pickup, ChanSpy, DND, /live, CDR — hammasi avtomatik.
- **Bitta kelib chiqish (origin):** yangi `web` servisi (nginx) — SPA + `/api/` → `api:8000` + `/sip-ws` → `asterisk:8088/ws`.
  Brauzer SIP'ni faqat shu orqali ko'radi; Asterisk HTTP (8088) hostga PUBLISH QILINMAYDI. Produksiyada TLS shu nginx'da (keyin).
- **WS darvozasi:** `/sip-ws?t=<ticket>` — nginx `auth_request` → API. Ticket = HMAC-SHA256 (`SECRET_KEY`) imzoli
  `{uid, ext_id, exp}`, TTL `SOFTPHONE_TICKET_TTL_S` (sukut 600). Ticketsiz/eskirgan/imzosi noto'g'ri/foydalanuvchi faolsiz/raqam
  endi webrtc emas → 401 (WS ochilmaydi). `/sip-ws` uchun nginx `access_log off` (ticket query'da).
- **SIP guard:** WS orqali kelgan hodisalarda Asterisk nginx IP'sini ko'radi → `sip_guard` `RemoteAddress` transporti `WS`/`WSS`
  bo'lgan hodisalarni AVTO-BAN UCHUN SANAMAYDI (aks holda bitta foydalanuvchi butun softfonlarni bloklaydi). Hodisa `security_events`ga
  `transport='ws'` bilan yoziladi. Darvoza = panel login + ticket.
- **Bitta tab registratsiya qiladi:** `navigator.locks` (`innova-softphone`) — ikkinchi tab «Boshqa oynada faol» ko'rsatadi.

## 1. Asterisk
- `http.conf`: `enabled=yes`, `bindaddr=0.0.0.0`, `bindport=8088`, `enablestatic=no`. Faqat ichki tarmoq.
- `sip_transport.py` generatoriga DOIM `[transport-wss] type=transport protocol=wss bind=0.0.0.0` qo'shiladi (ws va wss ikkisini oladi;
  `external_*` S32 dan). ps_endpoints view allaqachon webrtc'da `transport-wss` beradi.
- `rtp.conf` / `rtp_innova`: `icesupport=yes`. Modullar: `res_http_websocket`, `res_pjsip_transport_websocket`, `res_srtp`, `codec_opus` yuklanadi
  (tekshirilsin), `res_phoneprov.so`, `res_prometheus.so` → noload (keraksiz HTTP yuzalar).
- Jonli tasdiq: `pjsip show transports` → transport-wss; `http show status` → `Server Enabled and Bound to 0.0.0.0:8088`.

## 2. API
- Migratsiya `0017_m3a_webrtc.sql`: kerak bo'lsa (masalan `security_events.transport`). `extensions.webrtc` bor.
- `ExtensionOut.webrtc: bool`; `CreateExtensionPayload.webrtc=False`, `UpdateExtensionPayload.webrtc?`.
  webrtc=true va `codecs` berilmagan → `["opus","ulaw","alaw"]`. webrtc=true bo'lsa kodeklar ⊂ {opus, g722, ulaw, alaw} va kamida bitta,
  aks holda 422 `webrtc_codec` (`field="codecs"`). Rejim o'zgarishi reload'siz (realtime). Audit `extension.update` (`webrtc` maydoni).
- `GET /api/v1/me/softphone` (har qanday kirgan foydalanuvchi, faqat O'Z raqami) — `Cache-Control: no-store`:
  - `users.extension_id` yo'q → 404 `no_extension`; raqam webrtc emas → 409 `webrtc_disabled`; raqam `enabled=false` → 409 `extension_disabled`.
  - 200: `{"number":"101","display_name":"...","ws_path":"/sip-ws","ticket":"...","ticket_expires_at":"...",
     "sip":{"uri":"sip:t1-101@innova","auth_user":"t1-101","password":"...","realm":"asterisk"},"ice_servers":[]}`.
  - Parol FAQAT egasiga (FreePBX UCP kabi). Audit `softphone.credentials` (parolsiz). Rate limit: 30/daq foydalanuvchiga → 429.
- `GET /internal/softphone/ws-auth` (nginx `auth_request`; ticket `X-Original-URI` sarlavhasidagi `t` dan) → 204 yoki 401. Tana yo'q.
  Ticket logda yozilmaydi.
- `sip_guard`: §0 qoidasi + unit test (WS hodisasi sanalmaydi, UDP hodisasi sanaladi).

## 3. Web konteyner (`web/Dockerfile`, `deploy/web-nginx.conf`, compose `web` servisi)
- Multi-stage: `node:20` (`npm ci && npm run build`) → `nginx:1.27-alpine`. Publish `127.0.0.1:${WEB_HOST_PORT:-8711}:80`.
- `/` — SPA (`try_files $uri /index.html`), `/assets/` uzoq kesh; `/api/` → api:8000; `= /sip-ws` → `auth_request /_ws_auth` →
  `proxy_pass http://asterisk:8088/ws` (Upgrade/Connection, `proxy_read_timeout 3600s`); `/_ws_auth` internal → api `/internal/softphone/ws-auth`.
  `/internal/` tashqaridan → 404. Sarlavhalar: CSP (`connect-src 'self' ws: wss:`; `media-src 'self' blob:`), `Permissions-Policy: microphone=(self)`,
  `X-Content-Type-Options`, `Referrer-Policy`.
- Vite dev'da ham `/sip-ws` proksi bo'lsin (8711 ga).

## 4. Softfon (S16) — `web/src/softphone/` (SIP.js 0.21)
- `softphoneStore` (zustand) + `SoftphoneEngine` (SIP.js UserAgent/Registerer/Inviter/Invitation o'rami; UI'dan ajratilgan, testda mock).
  Holatlar: `unavailable` (raqam yo'q/webrtc emas — chip ko'rinmaydi), `other_tab`, `connecting`, `registered`, `error`(sabab),
  qo'ng'iroq: `idle | incoming | outgoing(ringing) | talking | hold`, `ended`(sabab).
- Ticket eskirishi / WS uzilishi → yangi `/me/softphone` + qayta ulanish (eksponensial 1→30 s); logout → unregister + yopish.
- Mikrofon: ruxsat rad etilsa — aniq xabar (uz/ru/en) va qo'ng'iroq tugmasi o'chiq. `<audio autoplay>` masofaviy oqim uchun.
- AppShell headerida `SoftphoneChip` (holat nuqtasi + raqam) → popover `SoftphonePanel` (mavjud `pbx/Softphone.tsx` dizayni):
  tergich (klaviaturadan ham), Qo'ng'iroq, kiruvchi oyna (raqam + ism, Javob/Rad, jiringlash ovozi WebAudio), gaplashmoqda (taymer, mute,
  hold, DTMF — RFC 4733 `sendDtmf`, blind transfer `refer`), Yakunlash. Kiruvchi qo'ng'iroq popover yopiq bo'lsa ham o'zi ochiladi.
- Click-to-call: `/calls` va `/me` tarixidagi raqam yonida «Qo'ng'iroq» (faqat softfon `registered` bo'lsa) → softfonda tergan holda qo'ng'iroq.
- Admin: ichki raqam formasida «Brauzer softfoni (WebRTC)» toggle + izoh («stol telefoni bu raqamda ishlamaydi»), ro'yxatda belgi.
- `data-testid`: `softphone-chip`, `softphone-state`, `softphone-dial-input`, `softphone-call`, `softphone-answer`, `softphone-reject`,
  `softphone-hangup`, `softphone-mute`, `softphone-hold`, `softphone-timer`, `softphone-incoming-from`, `softphone-transfer`.
- Diagnostika (isbot uchun): `window.__innovaSoftphone.stats()` → `{packetsSent, packetsReceived, codec}` (RTCPeerConnection getStats)
  — faqat `import.meta.env.DEV` yoki `?diag=1` da.

## 5. Isbot (`scripts/m3a-proof.sh --fresh`) — real Chromium (Playwright, `--use-fake-device-for-media-stream --use-fake-ui-for-media-stream`)
1. `web` konteyneri: `/` 200 HTML, `/api/v1/system/health` proksi (401 JSON), `/internal/x` → 404; `/sip-ws` ticketsiz → 401, buzilgan ticket → 401,
   to'g'ri ticket bilan WS `Sec-WebSocket-Protocol: sip` → 101.
2. 101, 103 — webrtc; 102 — oddiy SIP (python UAS). Operator A (101), B (103) brauzerda kiradi → chip `registered`;
   `pjsip show contacts` da ikkala `ws` kontakt. Operator C (102 — webrtc emas) → chip yo'q, `/me/softphone` 409.
3. Brauzer↔brauzer: A 103 ga tergich bilan qo'ng'iroq → B'da kiruvchi oyna (`101`) → Javob → ikkala tomonda ≥ 3 s keyin
   `packetsReceived > 50` va `packetsSent > 50` (DTLS-SRTP haqiqiy media), A yakunlaydi → CDR ANSWERED 101→103, billsec ≥ 2.
4. Brauzer → SIP: A 102 ga → UAS javob beradi → CDR ANSWERED 101→102. SIP → brauzer: UAS-uac 102 dan 101 ga → A javob → CDR ANSWERED.
5. Mute (`packetsSent` o'smaydi yoki audio track disabled), hold (Asterisk'da MOH / kanal hold holati), DTMF: A IVR raqamiga qo'ng'iroq,
   `1` bosadi → IVR 1-tanlov manziliga yetadi (CDR/kanal). Blind transfer: A↔B gaplashmoqda, B → 102 ga transfer → 102 jiringlaydi.
6. Navbat: 103 navbat a'zosi → trunkdan kiruvchi → B'da kiruvchi oyna, javob → `GET /live` da agent band.
7. Darvoza va guard: ticket muddati o'tgach (TTL=5 s bilan alohida) ulanish 401; noto'g'ri parol bilan WS REGISTER × 10 → nginx IP
   `ip_bans`da YO'Q, softfon A hamon `registered`.
8. Admin 101 ni webrtc=false qiladi → keyingi ticket 409/401, chip `error`/yo'qoladi (≤ 60 s).
Barcha oldingi isbotlar (m0, m1a, m1b, m1c, m2a, m2b, m2c) `--fresh` 0 FAIL qolishi shart. pytest, vitest, tsc toza.
`web/scripts/m3a-real-check.mjs` — skrinshotlar `replica/clone-screens/m3a-*.png` (chip, panel idle, kiruvchi, gaplashmoqda; light+dark).
