# M1b shartnomasi — chiquvchi qo'ng'iroqlar, tizim sozlamalari, bosh panel, audit va rollback (backend ↔ frontend)

M0 (`m0-contract.md`) va M1a (`m1a-contract.md`) amalda qoladi: xato formati, `apply` bloki, optimistik qulf
(`updated_at` → 409 `stale`), UTC vaqtlar, `Target`, 409 `in_use` + `details.usages`. Bu fayl faqat QO'SHIMCHALAR.
Ruxsat: yozish `routes.manage`/`system.manage` (admin), o'qish `pbx.view`, audit `users.manage`.
M1b DAN TASHQARI (M1c): butun panelning ru/en tarjimasi, TTS, ring group `memoryhunt` holati, ovozli pochta.

## 1. Trunklar — chiquvchi uchun kengaytma (S06)
- `Trunk` ga qo'shiladi: `"auth_mode": "ip|register"`, `"username": str|null`, `"from_domain": str|null`,
  `"outbound_callerid": str|null`, `"has_password": bool` (parol HECH QACHON qaytarilmaydi),
  `"health"` ga `"registration": "registered|rejected|unregistered|null"` va `"reason": str|null`.
- Kirish: `auth_mode`, `username`, `password` (faqat yozish; PATCH da berilmasa — o'zgarmaydi), `from_domain`, `outbound_callerid`.
  `register` rejimi → realtime `ps_registrations` + `ps_auths` (outbound auth), reload'siz bo'lmasa — `pjsip reload` apply ichida.
  422 `password_required` (register + parol yo'q), 422 `bad_host`.
- Trunk o'chirish chiquvchi marshrutda ishlatilsa → 409 `in_use` (`usages[].kind = "outbound_route"`).

## 2. Chiquvchi marshrutlar (S22)
- `OutboundRoute = {"id","name","priority": int (1 = birinchi tekshiriladi),"enabled",
  "patterns":[{"strip_prefix": str|null,"pattern": "998XXXXXXXXX","add_prefix": str|null,"callerid_match": str|null}],
  "trunks":[{"position","trunk": {"id","name","health_state"}}] (failover tartibi),
  "callerid": str|null,"override_extension_callerid": bool,"has_pin": bool,"international": bool,
  "extensions": "all" | [{"id","number","name"}] (qaysi ichki raqamlar foydalana oladi),"updated_at"}`
- CRUD `/outbound-routes` (kirish: `patterns`, `trunk_ids` tartibda, `pin` (4–8 raqam, null = olib tashlash, berilmasa o'zgarmaydi),
  `extension_ids` yoki `"all"`). `PUT /outbound-routes/order {"ids":[...]}` → priority qayta raqamlanadi.
- Naqsh sintaksisi — Asterisk: `X Z N . ! [1-5]` va raqamlar; `pattern` `_` siz yoziladi. Server tekshiradi → 422 `bad_pattern`
  + `details: {"index": i, "reason"}`. `trunk_ids` bo'sh → 422 `no_trunk`.
- `international: false` bo'lsa, terilgan raqam `00` yoki `+` bilan boshlansa VA `998` bilan boshlanmasa, shu marshrut UNI QABUL QILMAYDI
  (toll-fraud himoyasi). Standart: `false`. Yangi o'rnatishda seed: «Mahalliy va mobil (UZ)» — `998XXXXXXXXX`, `XXXXXXXXX` (+998 qo'shib),
  trunk yo'q bo'lsa marshrut `enabled=false`.
- Dialplan: `<code>-from-internal` dagi ichki raqamlarga mos kelmagan raqam → marshrutlar priority tartibida (ichki raqam ruxsati,
  naqsh, xalqaro qoida) → PIN bo'lsa `Authenticate` → CallerID (route.callerid override bo'lsa — u, aks holda ext.outbound_callerid,
  aks holda route.callerid, aks holda trunk.outbound_callerid) → trunklar tartibda `Dial(PJSIP/${num}@<trunk-endpoint>)`;
  `DIALSTATUS` CHANUNAVAIL/CONGESTION bo'lsa keyingi trunk (BUSY/NOANSWER bo'lsa — failover YO'Q, chaqiruvchiga busy).
  Hech bir marshrut mos kelmasa → `Congestion` + `NoOp(Innova: chiquvchi marshrut yo'q)`. `extensions.outbound_allowed=false` → rad.
- CDR: chiquvchi qo'ng'iroqda `Call.trunk` = haqiqatda ishlatilgan trunk NOMI (kiruvchida ham to'ldirilsin — M0 ochiq masala);
  `direction: "out"`. Buning uchun CDR'ga `userfield` yoki alohida ustun — backend tanlaydi, `/calls` javobi o'zgarmaydi.
- `POST /outbound-routes/simulate {"extension": "101","number": "0901234567"}` →
  `{"allowed": bool,"route": {"id","name"}|null,"dialed": "998901234567"|null,"callerid": str|null,"trunks":[{"id","name","health_state"}],
   "steps":[{"route": str,"result": "match|no_pattern|ext_not_allowed|international_blocked|disabled","detail": str}],"reason": str|null}`
  — dialplan bilan BIR XIL qoidalar (bitta Python funksiya kompilyator va simulyatorda umumiy bo'lsin).

## 3. Qo'ng'iroq guruhi — tashqi a'zo (S21)
- `members:[{"position","extension": {...}|null,"external_number": str|null}]`; kirish `members:[{"extension_id"}|{"external_number"}]`.
  Tashqi raqam chiquvchi marshrutlar orqali teriladi (`Local/<raqam>@<code>-outbound-rg`, guruh nomidan, ichki raqam ruxsatisiz,
  lekin xalqaro qoida amal qiladi). Mos marshrut yo'q → 422 `no_outbound_route` + `details.number`.

## 4. SIP va tarmoq sozlamalari (S32)
- `GET /settings/sip` → `{"external_ip": str|null,"external_host": str|null,"local_nets":["192.168.0.0/16"],"sip_udp_port": 5060,
  "sip_tls_port": 5061|null,"rtp_start": 10000,"rtp_end": 20000,"codecs":["alaw","ulaw","g722","opus"],"detected": {"public_ip": str|null,
  "local_ips":[str]},"restart_required": bool,"updated_at"}`
- `PATCH /settings/sip` → `{"item","apply"}`; 422 `bad_cidr`, `bad_port`, `rtp_range` (end-start < 100 yoki port to'qnashuvi).
  Asterisk'ga yetkazish: transport/rtp fayllari generatsiya qilinadi; qaysi o'zgarish restart talab qilishini backend aniq aniqlaydi
  (`restart_required` + `apply.status = "restart_required"`). `POST /settings/sip/restart` → Asterisk xavfsiz qayta ishga tushirish
  (`core restart gracefully` emas — faol qo'ng'iroq bo'lsa 409 `active_calls` + `details.count`; `?force=true` bilan baribir).
  `codecs` — global standart (yangi ichki raqam/trunk uchun).

## 5. Bosh panel (S03)
- `GET /dashboard` → `{"health": {"asterisk": {...M0},"db": {...},"disk": {"used_pct": int,"free_gb": float},"trunks":[{"id","name","state","registration","reason"}]},
  "live": {"active_calls": int,"calls":[{"channel","from","to","state","duration_s","direction"}]},
  "queues":[{"id","name","waiting": int,"members_online": int,"longest_wait_s": int}],
  "today": {"total": int,"answered": int,"missed": int,"out": int,"avg_wait_s": int|null,"by_hour":[{"hour": 0..23,"in": int,"out": int,"missed": int}]},
  "missed":[{"uniqueid","started_at","src","did": str|null,"called_back": bool}] (oxirgi 10, bugun, qayta qo'ng'iroq qilinmaganlar avval),
  "alerts":[{"level": "warn|danger","code": "trunk_down|disk_low|asterisk_down|no_outbound_route|revision_rolled_back","text","link": "/trunks"}]}`
  «Bugun» — tenant TZ (Asia/Tashkent). `called_back` — o'sha raqamga keyinroq chiquvchi answered qo'ng'iroq bo'lganmi.
  Javob ≤ 300 ms (keshsiz, 10k CDR qatorida) — indeks kerak bo'lsa migratsiya bilan.

## 6. Audit jurnali
- Har yozuvchi endpoint (POST/PATCH/PUT/DELETE, login muvaffaqiyatli/xato ham) `audit_log` ga yozadi: `action` (`create|update|delete|login|login_failed|restore|restart|override`),
  `entity` (`extension|trunk|outbound_route|...`), `entity_id`, `diff` — `{"field": [eski, yangi]}`; parol/PIN/sir maydonlari `"***"`.
- `GET /audit?entity=&user_id=&action=&from=&to=&q=&page=1&size=50` → `{"items":[{"id","at","user": {"id","login"}|null,"action","entity","entity_id",
  "label": str|null,"diff": {...},"ip": str|null}],"total"}`

## 7. Konfiguratsiya reviziyalari va qaytarish
- `GET /config/revisions` elementiga qo'shiladi: `"user": {"id","login"}|null`, `"summary": str|null` (qaysi audit yozuvi sabab bo'lgan).
- `GET /config/revisions/{id}` → element + `"dialplan": str`; `GET /config/revisions/{id}/diff?against=prev|current` → `{"unified": str}`.
- `POST /config/revisions/{id}/restore` → shu reviziyaning dialplan MATNINI qayta qo'llaydi (`apply` bloki, yangi reviziya `restored_from: id`),
  409 `not_applied` (faqat `applied` holatdagisini tiklash mumkin). Ogohlantirish: bu faqat dialplanni qaytaradi, bazadagi obyektlarni emas —
  javobda `"drift": true` va keyingi har qanday saqlash dialplanni bazadan qayta quradi. UI buni aniq aytadi.

## 8. Audio va kutish musiqasi (S11 to'liq, TTS siz)
- `POST /audio` qo'shimcha formatlar: `webm`/`ogg` (opus) — brauzerda yozilgan ovoz (MediaRecorder). Max 5 daqiqa.
- `MohClass = {"id","name","shuffle": bool,"files":[Audio],"updated_at"}`; CRUD `/moh-classes`; `default` sinf seed qilinadi (o'chirib bo'lmaydi).
  Asterisk'ga: realtime yoki `musiconhold` fayl generatsiyasi + `moh reload`. Navbat (`Queue.moh_class_id`, javobda `moh_class: {id,name}|null`)
  va trunk'dan kelgan qo'ng'iroq kutishida ishlatiladi.

## 9. Isbot (SIPp, `scripts/m1b-proof.sh [--fresh]`) — m0 va m1a isbotlari ham PASS qolishi shart
1. 101 → `0901234567` → marshrut «UZ» → trunk A (UAS 503 qaytaradi) → trunk B (UAS javob beradi). UAS B qabul qilgan INVITE'da
   Request-URI = `998901234567`, From/PAI'da route CallerID. CDR: `direction=out`, trunk = B nomi, ANSWERED (dstchannel trunk B).
2. Xalqaro: 101 → `0044201234567`, `international=false` → rad (trunkka INVITE BORMAYDI — UAS'da 0 INVITE), CDR failed/congestion.
3. `outbound_allowed=false` ichki raqam → rad. PIN'li marshrut → noto'g'ri PIN bilan o'tmaydi (DTMF), to'g'ri bilan o'tadi.
4. Simulate javobi 1–3 natijalari bilan bir xil (route, dialed, trunks).
5. Ring group'da tashqi a'zo → kiruvchi DID → guruh → tashqi raqam trunk orqali terildi (UAS INVITE oldi, javob berdi).
6. Revision restore: A holat → B holat saqlandi → A reviziyasi tiklandi → `dialplan show` A matnini ko'rsatadi; audit'da `restore` bor.
7. Register-trunk: test registrar (SIPp UAS REGISTER→401→200) — `health.registration = registered`.
8. Audit: trunk paroli o'zgartirildi → `audit_log.diff` da `"***"`, ochiq parol bazada/jurnalda yo'q (grep).
