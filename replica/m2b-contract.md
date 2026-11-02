# M2b shartnomasi — navbat agentlari, jonli monitoring, foydalanuvchilar, operator portali, analitika

M0–M2a shartnomalari amalda qoladi: xato formati `{"error":{"code","message","field"?,"details"?}}`, `apply` bloki, `updated_at` → 409 `stale`,
vaqt UTC ISO, ro'yxat `{"items":[...]}`, yaratish/tahrir `{"item","apply"?}`, payload YASSI (`{"name":..}`, `item` ichida emas).
Sirlar (parol, PIN) hech qachon javobda/auditda ochiq emas (audit `***`).
M2b DAN TASHQARI: xavfsizlik/fail2ban/toll-fraud limitlari (S33), Telegram ogohlantirish, rollar muharriri (faqat `admin`/`operator`),
Follow Me, WebSocket (M2b — polling), WebRTC softfon (M3), CSV eksport, TTS.

## 0. Tamoyillar
- Agent holati (navbatga kirgan/pauza) — YAGONA manba PostgreSQL (M2a §0 bilan bir xil): Asterisk realtime `asterisk_queue_members`
  view'idan o'qiydi; telefondan (*-kod) yozish `Set(REALTIME(...))` → view + INSTEAD OF trigger. AstDB / AMI `QueueAdd` — ikkinchi manba
  sifatida TAQIQLANADI. Panel yoki telefon o'zgartirgan holat ≤ 3 s ichida kuchga kirishi kerak (kutayotgan qo'ng'iroq uchun ham) —
  kerak bo'lsa API yozgandan keyin AMI orqali «yangilash» turtkisi (masalan `QueuePause`/`QueueReload`) beriladi, lekin holat PG'da.
- Har holat o'zgarishi `agent_events` jadvaliga yoziladi (trigger, manbadan qat'i nazar) — analitika login/pauza vaqtini shundan hisoblaydi.
- Asterisk `queue_log` realtime orqali PG `queue_log` jadvaliga yoziladi (jadval bor, 0001). Analitika: navbat — `queue_log`;
  navbatsiz qo'ng'iroqlar — `cdr` (linkedid darajasida dedup); login/pauza — `agent_events`.

## 1. Navbat agentlari — dinamik login/logout va pauza
- `queue_members` ga ustunlar: `dynamic bool default false`, `logged_in bool default false`, `paused bool default false`,
  `pause_reason text null` (≤ 64), `state_at timestamptz`. Statik a'zo (`dynamic=false`) har doim navbatda; dinamik — faqat `logged_in=true`.
  Pauza — statik va dinamik ikkalasiga (`asterisk_queue_members.paused` shu ustundan).
- `agent_events(id bigserial, tenant_id, extension_id, queue_id null, event in ('login','logout','pause','unpause'), reason, source in
  ('phone','portal','admin'), at timestamptz)`.
- Xususiyat kodlari (M2a jadvali, endi faol, ro'yxatda qaytariladi): `queue_login *45` (almashtiradi: kirgan bo'lsa chiqaradi), `queue_pause *46`
  (almashtiradi). Ta'sir — ext'ning BARCHA navbatlaridagi dinamik a'zoliklari (login) / barcha a'zoliklari (pauza). Ovozli javob
  («agent kirdi/chiqdi», «pauza yoqildi/o'chirildi» — Asterisk standart tovushlari). `queue_logout` — M2b'da ishlatilmaydi (ro'yxatda yo'q).
- API (admin): `QueueOut.members[]` ga `dynamic, logged_in, paused, pause_reason, state_at`; `POST /queues/{id}/members` va yangi
  `PATCH /queues/{id}/members/{extension_id}` — `{penalty?, dynamic?}`.
  Holat: `POST /queues/{id}/members/{extension_id}/{login|logout|pause|unpause}` `{reason?}` → `{item: QueueMemberOut}`
  (`dynamic=false` a'zoga login/logout → 409 `not_dynamic`). Manba `admin`.
- Navbat DND: DND yoqilgan ext navbatdan qo'ng'iroq OLMAYDI (M2a'dagi ochiq band yopiladi) — tavsiya: view `paused` = `paused OR dnd`.

## 2. Jonli monitoring (S29) — `GET /live` (admin), web 2 s polling
```
{ "at": ISO,
  "calls": [{ "id": "<linkedid>", "direction": "inbound|outbound|internal", "from": "998901234567", "to": "101",
              "state": "ringing|up|queued|held|parked", "started_at": ISO, "answered_at": ISO|null,
              "queue_id": uuid|null, "extension": "101"|null, "channels": ["PJSIP/t1-101-0000002a", ...] }],
  "queues": [{ "id", "name", "number", "waiting": [{ "from", "since": ISO, "position": 1 }],
               "agents": [{ "extension": "101", "name", "dynamic", "logged_in", "paused", "pause_reason",
                            "state": "idle|ringing|busy|paused|offline|unavailable", "answered_today": 3 }] }],
  "extensions": [{ "number": "101", "name", "state": "idle|ringing|busy|unavailable|dnd", "dnd": bool }] }
```
- Manba: AMI (`CoreShowChannels`, `QueueStatus`, `DeviceStateList`/`ExtensionStateList`) + PG; Asterisk yo'q bo'lsa 200, ro'yxatlar bo'sh,
  `"asterisk": "down"`. Javob ≤ 300 ms (10 kanal) — AMI chaqiruvlari parallel.
- `POST /live/spy` `{"call_id": "<linkedid>" | "channel": "...", "mode": "listen|whisper|barge"}` → so'rovchining O'Z ichki raqamiga
  (`users.extension_id`) qo'ng'iroq qilinadi (Originate), javob bersa `ChanSpy(<kanal>,q[w|B])`. Kuzatiladigan kanal — ext tomoni
  (agent). So'rovchida ext yo'q → 409 `no_extension`; kanal topilmadi → 404. Audit `live.spy` (call_id, mode). Javob `{"status":"calling"}`.
- Agent boshqaruvi jonli sahifadan — §1 endpointlari.

## 3. Foydalanuvchilar (S31, minimal)
- `GET /users`, `POST /users`, `PATCH /users/{id}`, `DELETE /users/{id}` (admin).
  `UserOut`: `id, username, full_name, email, role ("admin"|"operator"), extension: {id, number, name}|null, is_active, language,
  must_change_password, last_login_at, updated_at` (parol/TOTP yo'q).
  Yaratish: `{username, full_name, email?, role, extension_id?, password (≥ 10), language?}` → `must_change_password=true`.
  Tahrir: yuqoridagilar + `is_active`, `password?` (admin yangi parol qo'yadi → `must_change_password=true`) + `updated_at`.
- Qoidalar: `username` takror → 409 `username_taken`; ext boshqa foydalanuvchida → 409 `extension_taken` (`details.username`);
  o'zini o'chirish/o'chirib qo'yish/rolini tushirish → 409 `self_lockout`; oxirgi faol admin → 409 `last_admin`.
  Faolsizlantirish, rol yoki parol o'zgarishi → shu foydalanuvchining refresh tokenlari bekor (keyingi refresh 401).
  `must_change_password=true` bo'lsa login ishlaydi, javobda `must_change_password: true` — web parol almashtirishga majbur qiladi
  (`POST /auth/change-password {current, new}` — agar hali bo'lmasa qo'shiladi).
- Audit: `user.create/update/delete`, parol `***`. Ext o'chirilsa — `users.extension_id` NULL (FK `on delete set null`).

## 4. Operator portali (S30) — `/me` (har qanday tizimga kirgan foydalanuvchi, o'z ma'lumoti)
- `GET /me/overview` → `{ user: UserOut, extension: {id, number, name, dnd, forward_always, forward_busy, outbound_allowed,
  voicemail_box_id|null, updated_at} | null, queues: [{id, name, number, dynamic, logged_in, paused, pause_reason}],
  today: {answered, missed, talk_seconds} }`.
- `PATCH /me/extension` `{dnd?, forward_always?, forward_busy?, updated_at}` — admin PATCH bilan BIR XIL tekshiruv va normalizatsiya
  (bitta funksiya; `+` olib tashlanadi, o'z raqami 422 `bad_number`), realtime (apply yo'q). Boshqa maydonlar — 422.
- `POST /me/queues/{queue_id}/{login|logout|pause|unpause}` `{reason?}` — manba `portal`; a'zo emas → 404.
- `GET /me/calls` — `/calls` bilan bir xil format, faqat o'z ext'i (mavjud `calls:read:own`).
- `GET /me/voicemail` (o'z qutisi xabarlari), `GET /me/voicemail/{msg}/audio`, `POST .../heard`, `DELETE ...` — mavjud
  voicemail_boxes logikasi qayta ishlatiladi, faqat o'z qutisi.
- Ext biriktirilmagan foydalanuvchi: `GET /me/overview` → `extension: null, queues: []`; qolganlari 409 `no_extension`.
- Operator ruxsatlari: `calls:read:own`, `me:*`. Admin ham `/me` dan foydalana oladi (o'z ext'i bo'lsa).
- Web: operator login → `/me` (Mening kabinetim): DND/yo'naltirish kartasi, navbatlarim (login/pauza tugmalari + sabab), bugungi
  statistika, so'nggi qo'ng'iroqlarim, ovozli pochtam (tinglash/o'qildi/o'chirish). Operator uchun menyu faqat `/me` va `/calls`.

## 5. Analitika (S13) — `GET /reports/*?from=YYYY-MM-DD&to=YYYY-MM-DD[&queue_id=]` (admin)
- Sana — tenant vaqt zonasida (`tenants.timezone`, sukut Asia/Tashkent), `from..to` ikkala kun kiradi; oraliq ≤ 92 kun, aks holda 422
  `bad_range` (`field: "to"`). Javobda `{"from","to","timezone", ...}`.
- Ta'riflar (bitta joyda, sof funksiyalar + test; hujjatda ham):
  * qo'ng'iroq = bitta `linkedid` (transfer/forward/ring group oyoqlari bitta qo'ng'iroq).
  * yo'nalish: trunkdan kelgan → `inbound`; ext → trunk → `outbound`; ext → ext → `internal`.
  * `answered` = kamida bitta ext oyog'i ANSWERED (`dstchannel` ext, `billsec>0`); IVR `Answer()` hisoblanmaydi (M1a saboq).
  * `missed` = inbound, javob berilmagan (qora ro'yxat `userfield=blacklisted` — alohida `blocked`, missed EMAS).
  * navbat: `entered` (ENTERQUEUE), `answered` (CONNECT), `abandoned` (ABANDON), `timeout` (EXITWITHTIMEOUT/EXITEMPTY),
    `wait` = CONNECT/ABANDON holdtime, `sla_percent` = CONNECT holdtime ≤ `queues.sla_seconds` / (answered + abandoned) × 100
    (entered=0 → `null`).
- `GET /reports/summary` → `{total, inbound, outbound, internal, answered, missed, blocked, avg_wait_seconds, avg_talk_seconds,
  sla_percent, busiest_hour}`.
- `GET /reports/queues` → `{items: [{queue_id, name, entered, answered, abandoned, timeout, avg_wait_seconds, max_wait_seconds, sla_percent}]}`.
- `GET /reports/agents` → `{items: [{extension, name, answered, missed_ring (RINGNOANSWER), talk_seconds, avg_talk_seconds,
  login_seconds, pause_seconds}]}` — login/pauza `agent_events` dan, oraliq chegarasida kesiladi; hali ochiq sessiya `now()` gacha.
- `GET /reports/hourly` → `{items: [{hour: 0..23, inbound, answered, missed}]}` (24 ta qator har doim; yig'indi = summary).
- `GET /reports/daily` → `{items: [{date, total, answered, missed}]}` (oraliqdagi har kun, bo'sh kun 0).
- Tezlik: 92 kun × 50k qo'ng'iroq ≤ 2 s (indekslar: `cdr(linkedid)`, `queue_log(queuename,time)` bor). Natijalar faqat yangi
  ta'rifga mos ekanini testda aniq raqamlar bilan isbotlang (fixture: aniq qo'ng'iroqlar → kutilgan son).
- Web (S13): sana oralig'i (bugun/kecha/7 kun/30 kun/maxsus), navbat filtri; KPI kartalar, kunlik va soatlik grafik, navbat va agent
  jadvallari. `dataviz` qoidalari; brend palitrasi; dark rejim.

## 6. Isbot (`scripts/m2b-proof.sh --fresh`)
1. Admin operator yaratadi (ext 101) → operator kiradi, parolni almashtiradi → `GET /me/overview` 101 ni ko'rsatadi; operator
   `/extensions` → 403; boshqa ext bilan ikkinchi foydalanuvchi → 409 `extension_taken`; oxirgi admin o'chirilmaydi → 409.
2. Operator `PATCH /me/extension {dnd:true}` → 101 ga qo'ng'iroq jiringlamaydi; o'chiradi → jiringlaydi.
3. Navbat Q: 101 statik, 102 dinamik (kirmagan). Kiruvchi → faqat 101 jiringlaydi. 102 `*45` → `GET /live` da `logged_in` va keyingi
   qo'ng'iroq 102 ga ham boradi; 102 `*46` → pauza, jiringlamaydi; `POST /me/queues/.../unpause` → yana jiringlaydi (≤ 3 s).
4. 101 DND → navbatdan qo'ng'iroq olmaydi.
5. Faol qo'ng'iroq paytida `GET /live`: `calls` da from/to/state=up, navbatda kutayotgan bo'lsa `waiting` 1.
6. Admin (ext 103 biriktirilgan) `POST /live/spy listen` → 103 jiringlaydi, javob beradi → Asterisk'da ChanSpy kanali; audit `live.spy`.
7. Isbot oxirida `GET /reports/summary|queues|agents|hourly` bugun uchun — isbot o'zi yaratgan qo'ng'iroqlar soniga AYNAN teng
   (inbound/answered/missed/navbat answered/abandoned; agent login_seconds > 0, pause_seconds > 0; hourly yig'indi = summary).
8. Faolsizlantirilgan foydalanuvchi kira olmaydi va refresh 401.
Barcha oldingi isbotlar (m0, m1a, m1b, m1c, m2a) `--fresh` 0 FAIL qolishi shart.
