# M2a shartnomasi — qo'ng'iroq funksiyalari (backend ↔ frontend)

M0/M1a/M1b/M1c shartnomalari amalda qoladi: xato formati `{"error":{"code","message","field"?}}`, `apply` bloki,
`updated_at` → 409 `stale`, UTC, `Target`, 409 `in_use`, ro'yxat `{"items":[...]}`, yaratish/tahrir `{"item","apply"}`.
Ruxsat: yozish `pbx.manage` (admin), o'qish `pbx.view`. Sirlar (PIN) hech qachon API javobida/auditda ochiq emas (`has_pin`, audit `***`).
M2a DAN TASHQARI (M2b+): navbat agent login/pauza, jonli monitoring/ChanSpy (S29), operator portali (S30), analitika (S13),
xavfsizlik/toll fraud (S33), Follow Me, paging/intercom, TTS. WebRTC — M3.

## 0. Asosiy tamoyil — ish vaqtidagi holat API'siz ishlaydi
DND va yo'naltirish telefondan (*-kod) ham, paneldan ham o'zgaradi. Haqiqat manbai — PostgreSQL `extensions` qatori.
Asterisk uni realtime orqali o'qiydi/yozadi (`res_config_pgsql`, `extconfig.conf` xaritasi → yangi view, masalan
`asterisk_ext_state(endpoint, dnd, forward_always, forward_busy)` — oddiy, yangilanadigan view). Qo'ng'iroq yo'lida API'ga
(`CURL`) murojaat YO'Q (istisno: PIN tekshiruvi — M1b/M1c bilan bir xil ichki endpoint). Agar realtime yozish (view orqali) ishonchsiz
bo'lsa — muqobil va sababini build-log'ga yozing; AstDB'ni ikkinchi haqiqat manbai qilish TAQIQLANADI.
Qora ro'yxat ham realtime (o'zgarishi reload/apply talab qilmaydi). Xususiyat kodlari va konferensiyalar — dialplan (apply).

## 1. DND va qo'ng'iroqni yo'naltirish (ichki raqam)
- `ExtensionOut` ga qo'shiladi: `dnd: bool`, `forward_always: str|null`, `forward_busy: str|null`, `pickup_group: str|null`.
  `UpdateExtensionPayload` ga ham (aniq `null` = tozalash, berilmagan = o'zgarmaydi — `model_fields_set`). Raqam `^\+?[0-9]{2,15}$`
  (sxemada CHECK bor) → aks holda 422 `bad_number` (`field`). `pickup_group` `^[a-z0-9_-]{1,32}$` (migratsiya: yangi ustun).
  Bu maydonlar o'zgarishi apply/reload TALAB QILMAYDI (realtime) — `apply.status="applied"`.
- Semantika (to'g'ridan-to'g'ri ichki qo'ng'iroq VA `dest-<ext>` orqali kelgan qo'ng'iroq uchun bir xil):
  1) `dnd=true` → ext jiringlamaydi; `no_answer_target` ovozli pochta bo'lsa `VoiceMail(...,b)`, aks holda `Busy`.
  2) `forward_always` → ext jiringlamaydi, raqamga yo'naltiriladi. Ichki raqam bo'lsa — o'sha ext'ga (uning DND'si hisobga olinadi,
     zanjir chuqurligi ≤ 3, aylanma yo'naltirish to'xtaydi). Tashqi raqam — chiquvchi marshrutlar orqali, ruxsatlar YO'NALTIRUVCHI
     ext'niki (`outbound_allowed`, marshrut ext filtri, xalqaro blok) — tashqi chaqiruvchi bu orqali ruxsatsiz chiqa olmasin (toll fraud).
  3) `forward_busy` → `DIALSTATUS=BUSY` bo'lsa yo'naltiriladi (2-banddagi qoidalar), aks holda mavjud `no_answer` oqimi.
  4) Qo'ng'iroq guruhi a'zosi DND bo'lsa — o'tkazib yuboriladi (qolganlar jiringlaydi). Navbat — M2a'da DND'ni hisobga olmaydi (hujjatlang).
- UI: ext drawer'ida «Qo'ng'iroqlar» bo'limi — DND toggle, «Har doim yo'naltirish», «Band bo'lsa yo'naltirish», «Pickup guruhi».
  Ro'yxatda DND/yo'naltirish belgisi (badge). Telefondan o'zgarsa sahifa yangilanganda ko'rinadi.

## 2. Xususiyat kodlari (S24)
- `feature_codes` jadvali bor (tenant, feature, code, enabled). Migratsiya: CHECK ga `cf_busy_on`, `cf_busy_off` qo'shiladi; har tenantga
  standart kodlar seed qilinadi (yangi tenant yaratilganda ham). Standartlar (FreePBX odati):
  `voicemail *97`, `voicemail_other *98`, `dnd_toggle *76`, `cf_always_on *72`, `cf_always_off *73`, `cf_busy_on *90`, `cf_busy_off *91`,
  `pickup_group *8`, `pickup_direct **`, `park *70`, `echo_test *43`, `speaking_clock *60`.
  (`queue_*`, `call_flow_toggle`, `record_now` — M2a'da ishlatilmaydi: ro'yxatda qaytarilmaydi.)
- Ishlashi: `*76` — DND almashtiradi, «yoqildi/o'chirildi» ovozi; `*72<raqam>` (masalan `*72203`) yoki `*72` keyin raqam tergandan so'ng `#`
  — yo'naltirishni yoqadi; `*73` o'chiradi; `*90<raqam>`/`*91` — band bo'lsa. `*8` — o'z `pickup_group`idagi jiringlayotgan qo'ng'iroqni oladi;
  `**<ext>` — aniq ext'dagi jiringlayotgan qo'ng'iroqni oladi. `*43` echo, `*60` vaqt. M1c dagi `*97`/`*98` endi shu jadvaldan olinadi.
- API: `GET /feature-codes` → `{"items":[{"feature","code","default_code","enabled"}]}` (tartib — yuqoridagi ro'yxat).
  `PATCH /feature-codes/{feature}` `{"code"?, "enabled"?}` → `{"item","apply"}`; xatolar: 422 `bad_code` (`^\*[0-9*#]{1,6}$`),
  409 `code_taken` (boshqa feature kodi, yoki biror kod boshqasining PREFIKSI bo'lsa — masalan `*7` va `*72`), 404 `not_found`.
  `POST /feature-codes/{feature}/reset` → standartga qaytaradi. O'zgarish dialplan'ga yoziladi (apply + `dialplan reload`).
- UI: `/feature-codes` (Sozlamalar → «Xususiyat kodlari»): jadval (nomi, tavsif, kod — inline tahrir, yoqish toggle, «standart» tugmasi).

## 3. Transfer va park (S26)
- Ichki/kiruvchi qo'ng'iroqlarda `Dial` opsiyalari `tT` — ikkala tomon transfer qila oladi. `features.conf`: blind `##`, attended `*2`
  (DTMF `info` rejimida ishlashini tasdiqlang). Transfer konteksti = tenant `from-internal`.
- Park: `res_parking`, tenant bo'yicha lot: kirish raqami `700` (transfer `##700` → park qiladi va joy raqamini aytadi), joylar `701–720`,
  vaqt 60 s → qaytib park qilgan ext'ga jiringlaydi. `701` tergan ext qo'ng'iroqni oladi. `*70` (`park` kodi) — `700` bilan bir xil.
  700–720 raqamlari `dial_numbers`/ext raqamlari bilan to'qnashmasin: ext/raqam yaratishda 409 `number_taken` (`reserved`).
- API: `GET /parking` → `{"lot":"700","slots":"701-720","timeout_s":60,"parked":[{"slot","callerid","parked_by","since"}]}` (AMI `ParkedCalls`).
  Sozlash M2a'da yo'q (faqat ko'rish). UI: `/parking` emas — Bosh paneldagi (dashboard) kichik «Park qilingan» kartasi.

## 4. Konferensiya (S25)
- `conferences` jadvali bor (`pin_hash`, `admin_pin_hash`, `record`, `max_members`). `call_targets(kind='conference')` + `dial_numbers` raqami.
  Asterisk `app_confbridge`; profil/menyu — API `confbridge_innova.conf` ni `dialplan` hajmiga yozadi (`#include`), keyin `module reload app_confbridge.so`.
- `Conference = {"id","name","number","has_pin","has_admin_pin","record","max_members": int|null,"target_id","updated_at",
  "live": {"members": int}}` (`live` — AMI `ConfbridgeList`/`ConfbridgeListRooms`; Asterisk yo'q bo'lsa `members: 0` va xato emas).
- CRUD `/conferences` (`name`, `number` (ixtiyoriy — bo'sh raqam beriladi), `pin`/`admin_pin` 4–8 raqam yoki `null` (PATCH'da berilmasa
  o'zgarmaydi), `record`, `max_members` 2–100|null). O'chirish — boshqa joyda ishlatilsa 409 `in_use` (mavjud `usages` mexanizmi).
- Dialplan `dest-<conf_target>`: PIN bo'lsa so'raydi (3 urinish) — tekshiruv ichki `CURL()` endpoint (PIN bazada xesh, faylda yo'q);
  admin PIN to'g'ri bo'lsa admin profili (marked/mute boshqaruvi). `max_members` to'lsa — «xona to'la» va uziladi.
- UI: `/conferences` sahifa (ro'yxat: nomi, raqami, PIN bor/yo'q, hozir N kishi; drawer — tahrir). Manzil tanlagichda «Konferensiya» turi.

## 5. Qora ro'yxat (S27)
- `blacklist` jadvali bor (tenant, number, reason). `number` normalizatsiya: bo'shliq/`-`/`()` olib tashlanadi, boshidagi `+` saqlanmaydi
  (`^[0-9]{3,15}$`) yoki maxsus `anonymous` (yashirin/`anonymous`/`restricted`/bo'sh CallerID). Taqqoslash ham shu normalizatsiyada
  (kiruvchi `+998901234567` va `998901234567` bir xil).
- Kiruvchi (`from-trunk`) qo'ng'iroq marshrutlashdan OLDIN realtime tekshiriladi → mos kelsa `Hangup(21)` (rad etildi), CDR `userfield`
  `blacklisted`. Ichki qo'ng'iroqlarga ta'sir qilmaydi. Reload/apply yo'q.
- API: `GET /blacklist?q=` → `{"items":[{"number","reason","created_at"}]}`; `POST /blacklist {"number","reason"?}` → 201 `{"item"}`,
  takror → 409 `exists`, noto'g'ri → 422 `bad_number`; `DELETE /blacklist/{number}` → 204 (yo'q → 404). Audit yoziladi.
- UI: `/blacklist` sahifa (qidiruv, qo'shish formasi, «Yashirin raqamlarni bloklash» toggle = `anonymous` yozuvi, o'chirish tasdiq bilan).
  Qo'ng'iroqlar tarixida (CDR) kiruvchi qatorda «Bloklash» amali (raqamni oldindan to'ldirib forma ochadi).

## 6. Isbot — `scripts/m2a-proof.sh --fresh` (SIPp/Python yordamchilar `tests/sipp/`, M2a qoldiqlari bo'lsa exit 2)
1. DND API orqali → 201 ga qo'ng'iroq `486 Busy`; `*76` 201 telefonidan → `GET /extensions` da `dnd=false`; yana qo'ng'iroq → jiringlaydi.
2. `*72203` 201 dan → 201 ga qo'ng'iroq 203 da jiringlaydi; `*73` → yana 201. Tashqi raqamga yo'naltirish → SIPp trunk UAS INVITE oladi;
   `outbound_allowed=false` ext'ning tashqi yo'naltirishi trunkka CHIQMAYDI.
3. `forward_busy`: 201 band → 203 ga o'tadi.
4. Qora ro'yxat: raqam qo'shilgach trunkdan kiruvchi INVITE rad etiladi (marshrut maqsadi jiringlamaydi), olib tashlangach o'tadi; `anonymous`.
5. Pickup: 202 → 201 jiringlayapti, 203 (bir guruh) `*8` → 203 javob beradi va 202 bilan ulanadi; `**201` ham.
6. Blind transfer: 202↔201 gaplashmoqda, 201 `##203` → 203 jiringlaydi va 202 bilan ulanadi.
7. Park: `##700` → `GET /parking` da 1 ta; 203 `701` → ulanadi; `parked` bo'shaydi.
8. Konferensiya: PIN'li xonaga 2 ta chaqiruvchi kiradi → `live.members=2`; noto'g'ri PIN → uziladi.
9. Xususiyat kodi `dnd_toggle` → `*77` (apply) → `*77` ishlaydi, `*76` ishlamaydi; prefiks to'qnashuvi 409.
Hamma eski isbotlar (`m0`/`m1a`/`m1b`/`m1c --fresh`) o'tishda davom etadi.
