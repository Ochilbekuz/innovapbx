# M1c shartnomasi — ovozli pochta, SIP TLS, ru/en tarjima, memoryhunt (backend ↔ frontend)

M0/M1a/M1b shartnomalari amalda qoladi (xato formati, `apply` bloki, `updated_at` → 409 `stale`, UTC, `Target`,
409 `in_use`). Bu fayl faqat QO'SHIMCHALAR. Ruxsat: yozish `system.manage`/`pbx.manage` (admin), o'qish `pbx.view`.
M1c DAN TASHQARI: TTS (o'zbekcha offline ovoz + tijoriy litsenziya — alohida qaror), operator portali (S30), WebRTC/WSS (S16).

## 1. memoryhunt (S21) — TAYYOR (2026-10-28)
`ringall` — hammasi birdan; `hunt` — bittadan; `memoryhunt` — yig'ilib boradi: `Dial(1)`, `Dial(1&2)`, `Dial(1&2&3)`.
Holat saqlanmaydi. Kod: `compiler._rg_dial_sets`.

## 2. Ovozli pochta (S23)
- Asterisk `app_voicemail`, fayl xotirasi `/var/spool/asterisk/voicemail` — YANGI umumiy hajm `voicemail` (asterisk + api).
  Konfiguratsiya: API `voicemail_innova.conf` ni `dialplan` hajmiga yozadi (`voicemail.conf` `#include`), keyin AMI `voicemail reload`.
  Kontekst = tenant `code`. Faylda PIN YO'Q (0644 fayl): har qutida tasodifiy yaroqsiz parol. PIN tekshiruvi — M1b PIN bilan bir xil
  ichki `CURL()` endpoint orqali, keyin `VoiceMailMain(box@ctx,s)`.
- `VoicemailBox = {"id","mailbox": "101","extension": {"id","number","name"}|null,"email": str|null,"email_notify","telegram_notify",
  "telegram_chat_id": str|null,"attach_audio","greeting": {"id","name"}|null,"has_pin": bool,"counts": {"new": int,"old": int},"updated_at"}`
  (`voicemail_boxes` jadvali bor; `email`/`telegram_chat_id` ustunlari migratsiya bilan qo'shiladi).
- CRUD `/voicemail-boxes` (kirish: `extension_id` yoki `mailbox` (umumiy quti), `pin` 4–8 raqam (yaratishda majburiy; PATCH da berilmasa
  o'zgarmaydi), qolgan maydonlar). Ichki raqam yaratilganda quti AVTOMATIK yaratilmaydi; ext kartasida «Ovozli pochta yoqish» bor.
  Quti yaratilganda `call_targets(kind='voicemail')` ham yaratiladi → u IVR/marshrut/ext `no_answer_target` sifatida tanlanadi.
- Dialplan: `<code>-dest-<vm_target_id>` → `VoiceMail(<box>@<code>,u)` (ext javob bermasa — `u`, band bo'lsa — `b`: ext `no_answer`
  maqsadi voicemail bo'lsa `DIALSTATUS=BUSY` → `b`). Xususiyat kodi `*97` — o'z qutisi (chaqiruvchi ext), `*98` — istalgan quti.
  ps_endpoints view'da `mailboxes` = qutisi bor ext uchun `<box>@<code>` (MWI). Proof SIPp UAS ssenariylari MWI NOTIFY ga
  bardoshli bo'lishi kerak (M0 da topilgan muammo — `mailboxes` faqat qutisi bor ext uchun to'ldiriladi).
- Xabarlar: `GET /voicemail-boxes/{id}/messages` → `[{"id": "INBOX/msg0000","folder": "inbox|old","callerid": str,"duration_s": int,
  "received_at","heard": bool}]` (spool fayllaridan, `msgNNNN.txt` metadata). `GET .../messages/{msg}/audio` (WAV, Blob),
  `POST .../messages/{msg}/heard` (INBOX → Old), `DELETE .../messages/{msg}`. Yo'l `..`/absolyut — 404 (path traversal yo'q).
- Bildirishnoma (API ichidagi fon vazifa, ~5 s so'rov): yangi xabar → e-mail (SMTP) va/yoki Telegram (`sendAudio`/`sendMessage`).
  Bir xabar bir marta yuboriladi (yuborilganlar jadvali; idempotent, API qayta ishga tushsa ham takror yo'q).
  `NotifySettings` = `GET/PATCH /settings/notify`: `{"smtp_host","smtp_port","smtp_tls": "none|starttls|tls","smtp_user","has_smtp_password",
  "from_email","has_telegram_token","telegram_api_base": "https://api.telegram.org"}` (parol/token shifrlanadi, qaytarilmaydi).
  `POST /settings/notify/test {"channel": "email|telegram","to": str}` → 200 yoki 502 `notify_failed` (sabab bilan).
- UI: `/voicemail` (qutilar ro'yxati, yangi/eski soni, drawer: sozlama + xabarlar ro'yxati + `<audio>` Blob orqali + o'chirish),
  ext kartasida yoqish, `/settings/notify` bo'limi (SIP sahifasi yonida «Bildirishnomalar»). Hamma holatlar: bo'sh, yuklanish, xato.

## 3. SIP TLS (S32 davomi)
- Sertifikat fayllari YANGI hajm `certs` (asterisk faqat o'qiydi): `innova.crt`, `innova.key` (0640, asterisk guruhi o'qiy oladi).
  Bazaga sertifikat yozilmaydi; metadata fayldan o'qiladi.
- `GET /settings/sip/tls` → `{"enabled": bool,"port": 5061|null,"certificate": {"subject","issuer","not_after","self_signed": bool,
  "fingerprint_sha256"}|null,"restart_required": bool}`.
- `POST /settings/sip/tls/certificate` (multipart `cert`, `key` PEM; `chain` ixtiyoriy) — kalit sertifikatga mosligi, muddati o'tmaganligi
  tekshiriladi → 422 `bad_certificate` (+ `details.reason`: `key_mismatch|expired|not_pem|encrypted_key`).
  `POST /settings/sip/tls/self-signed {"common_name": str}` — 2 yillik RSA-2048 yoki EC P-256 o'z-imzoli sertifikat.
- `sip_tls_port` bor VA sertifikat bor → `transport-tls` generatsiya qilinadi (`protocol = tls`, `cert_file`, `priv_key_file`,
  `method = tlsv1_2`, external_* va local_net UDP bilan bir xil). TLS maydonlari `transport_key` ga kiradi → o'zgarsa `restart_required`.
  Sertifikat almashtirilsa ham restart kerak. Restart tasdig'i `pjsip show transport transport-tls` ni ham tekshiradi.
- UI: SIP sahifasida «TLS» kartasi: holat, sertifikat ma'lumoti (muddati 30 kundan kam — ogohlantirish), yuklash, o'z-imzoli yaratish.

## 4. Interfeys tillari uz/ru/en (butun panel)
- Barcha ekran matnlari `react-i18next` orqali; har ekranning o'z namespace'i. uz/ru/en kalit to'plamlari AYNAN bir xil (vitest majburlaydi).
  JSX ichida qattiq yozilgan foydalanuvchiga ko'rinadigan matn qolmaydi (vitest skaneri). Sana/son formatlash `Intl` + joriy til.
  Backend xato `code` lari UI'da tarjima qilinadi (`errors` namespace; noma'lum kod → server `message`).
- Til tanlovi `User.language` ga saqlanadi (M0 da bor) va qayta kirishda tiklanadi.

## 5. Isbot (`scripts/m1c-proof.sh [--fresh]`) — m0, m1a, m1b isbotlari ham PASS qolishi shart
1. Qutili ext 201 ga SIPp qo'ng'iroq qiladi, 201 javob bermaydi → xabar qoldiriladi (RTP pcap 3+ s) → spool'da fayl → API ro'yxatida
   `new=1`, audio yuklab olinadi (WAV, >0 bayt), `heard` → `old=1`, o'chirish → 0.
2. Bildirishnoma: test SMTP (mailpit konteyneri, faqat proof) xatni oladi (WAV ilova bilan); soxta Telegram server `sendAudio` oladi;
   API restartidan keyin takror yuborilmaydi.
3. `*97` — PIN noto'g'ri → rad; to'g'ri → `VoiceMailMain` ga kiradi (CDR/`core show channels` bilan tasdiq).
4. TLS: o'z-imzoli sertifikat → `restart_required` → restart → `openssl s_client -connect asterisk:5061` sertifikat CN ni ko'rsatadi,
   `pjsip show transport transport-tls` bor; noto'g'ri kalit → 422 `key_mismatch`.
5. memoryhunt: 3 a'zoli guruh, SIPp UAS'lar — 1-a'zo INVITE'ni 1-qadamda, 1 va 2 ni 2-qadamda oladi.
