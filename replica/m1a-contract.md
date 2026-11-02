# M1a shartnomasi — kiruvchi oqim ilovalari (backend ↔ frontend)

M0 shartnomasi (`m0-contract.md`) amalda qoladi: xato formati, `apply` bloki, optimistik qulf (`updated_at` → 409 `stale`),
UTC vaqtlar. Bu fayl faqat QO'SHIMCHALAR. Ruxsat: hammasi `routes.manage` (admin), o'qish `pbx.view`.

## Manzillar (polimorf) — `call_targets`
M1a da manzil turlari: `extension`, `ring_group`, `queue`, `ivr`, `time_condition`, `hangup`, `busy`.
(`announcement`, `voicemail`, `external`, `conference` — keyingi bosqichlar; UI ularni ko'rsatmaydi.)
- `hangup` va `busy` — tizim manzillari, har tenant uchun bittadan seed qilinadi (migratsiyada), o'chirib bo'lmaydi.
- `Target = {"id","kind","label","number": str|null,"broken": bool}` — M0 dagidek, endi barcha turlar.
- `GET /targets?kind=a,b&q=` → `{"items":[Target]}` (kind vergul bilan, bo'sh — hammasi)
- `GET /targets/{id}/usages` → `{"items":[{"kind": "inbound_route|ivr|ivr_option|time_condition|ring_group|queue","id","label","field": "target|timeout|invalid|open|closed|no_answer|digit:1"}]}`
- Har qanday obyektni o'chirish, agar uning target'i ishlatilsa → 409 `in_use` + `details.usages` (yuqoridagi format).
- Manzil tanlanadigan HAR maydon API'da `*_target_id` (uuid), javobda esa to'liq `Target` obyekt (`*_target`).

## Ish vaqti (S08)
- `TimeGroup = {"id","name","ranges":[{"weekdays":[1..7] (1=Dushanba),"start":"09:00","end":"18:00"}],"updated_at"}`
  CRUD `/time-groups` (`POST`/`PATCH` to'liq `ranges` ro'yxati bilan almashtiradi). 422 `range_order` (end <= start).
- `Holiday = {"id","name","day":"2026-03-21","recurring_yearly": bool}`; CRUD `/holidays`;
  `POST /holidays/import-uz {"year": 2026}` → `{"items":[Holiday], "created": int}` — O'zbekiston rasmiy bayramlari
  (1-yan, 8-mart, 21-mart, 9-may, 1-sent, 1-okt, 8-dek, 31-dek — recurring; Ramazon/Qurbon hayiti — o'sha yil sanasi
  ma'lum bo'lsa, yo'q bo'lsa qo'shilmaydi va javobda `"skipped": ["ramazon_hayit"]`). Takror import — idempotent.
- `TimeCondition = {"id","name","number": str|null,"time_group": {"id","name"},"honor_holidays","open_target": Target,
  "closed_target": Target,"override": "auto|force_open|force_closed","toggle_code": "*21"|null,"state_now": "open|closed","updated_at"}`
  CRUD `/time-conditions` (kirish: `time_group_id, open_target_id, closed_target_id, ...`).
  `POST /time-conditions/{id}/override {"override"}` → `{"item","apply"}` (tungi rejim tugmasi).
  `state_now` — server tenant TZ'da hisoblaydi (bayramlar hisobga olinadi).

## IVR (S09)
- `IVR = {"id","name","number": str|null,"greeting": Audio,"invalid_audio": Audio|null,"timeout_seconds","repeats","direct_dial": bool,
  "options":[{"digit":"1","target": Target}],"timeout_target": Target,"invalid_target": Target,"updated_at"}`
  CRUD `/ivrs` (kirish: `greeting_audio_id`, `options:[{"digit","target_id"}]`, ...). 422 `duplicate_digit`.
- Halqa: kompilyator IVR→…→IVR halqasini timeout/invalid yo'lida chiqishsiz topsa → 422 `loop` + `details.path: [label,...]`
  (yozuv saqlanmaydi). Tugma orqali halqa (qo'ng'iroq qiluvchi tanlaydi) — ruxsat.

## Qo'ng'iroq guruhlari (S21)
- `RingGroup = {"id","name","number","strategy":"ringall|hunt|memoryhunt","ring_seconds","members":[{"position","extension": {"id","number","name"}}],
  "no_answer_target": Target,"callerid_prefix": str|null,"updated_at"}`; CRUD `/ring-groups` (`members:[extension_id,...]` tartibda).
  M1a: a'zo faqat ichki raqam (tashqi raqam — M1b, chiquvchi bilan).

## Navbatlar (S10)
- `Queue = {"id","name","number","strategy":"ringall|leastrecent|fewestcalls|random|rrmemory|linear|wrandom","agent_ring_seconds","retry_seconds",
  "wrapup_seconds","max_wait_seconds","max_callers": int|null,"announce_position","announce_frequency_seconds","sla_seconds","join_empty","record",
  "members":[{"extension": {...},"penalty": 0..10}],"timeout_target": Target,"live": {"waiting": int,"members_online": int}|null,"updated_at"}`
  CRUD `/queues`. Navbat va a'zolar — Asterisk realtime (`queues`/`queue_members` view'lar), reload'siz.

## Raqamlar
`number` (ring_group, queue, ivr, time_condition) ixtiyoriy; berilsa — `dial_numbers` dagi umumiy nom maydoni:
ichki raqam bilan to'qnashsa 409 `number_taken`. `GET /numbers/free?from=100&to=999&limit=5` → `{"items":["103","104",...]}`.

## Audio (S11 — M1a minimal)
- `Audio = {"id","name","duration_ms","format":"wav","created_at"}`
- `GET /audio`, `POST /audio` (multipart `file` + `name`; wav/mp3/ogg ≤ 20 MB, server sox/ffmpeg bilan 8 kHz mono wav ga o'giradi;
  415 `bad_format`, 413 `too_large`), `GET /audio/{id}/stream` (Range qo'llab-quvvatlanadi), `DELETE /audio/{id}` (409 `in_use`).
- Tizim ovozlari tayyor yozuvlar sifatida seed qilinadi: kamida bitta «salomlashuv» namunasi (o'zimiz generatsiya qilgan ohang/sukut —
  Asterisk/FreePBX ovoz fayllarini nusxalamang), shunda IVR'ni audio yuklamasdan yaratish mumkin.

## Qo'ng'iroq oqimi grafigi
- `GET /flow/{inbound_route_id}` → `{"root": Node}`;
  `Node = {"target": Target,"edge": "target|open|closed|timeout|invalid|no_answer|digit:1"|null,"children":[Node],"loop": bool,"broken": bool}`
  Daraxt chuqurligi ≤ 12; takrorlangan tugun `loop: true` bilan to'xtaydi (bolasiz).

## Isbot (SIPp, `scripts/m1a-proof.sh`)
1. Ish vaqti `force_open` → DID → time_condition → IVR → «1» → navbat (101,102 a'zo) → 101 javob beradi → CDR answered.
2. `force_closed` → DID → hangup yo'li (CDR'da ko'rinadi, qo'ng'iroq rad etilgan).
3. IVR timeout → ring group (102) → 102 javob beradi.
4. IVR timeout → IVR o'ziga (chiqishsiz) → 422 `loop`.
5. Navbatga a'zo qo'shish → `queue show` da reload'siz ko'rinadi.
