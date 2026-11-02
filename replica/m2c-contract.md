# M2c shartnomasi — SIP hujum himoyasi (S33), toll-fraud, Telegram ogohlantirishlar, trunk monitoringi

M0–M2b shartnomalari amalda qoladi: xato formati `{"error":{"code","message","field"?,"details"?}}`, `apply` bloki, `updated_at` → 409 `stale`,
vaqt UTC ISO, ro'yxat `{"items":[...]}`, yaratish/tahrir `{"item","apply"?}`, payload YASSI. Sirlar (token, parol) hech qachon javobda,
auditda, `alert_log`da, logda ochiq emas (audit `***`). Hammasi faqat `admin` (operator → 403).
M2c DAN TASHQARI: admin 2FA, disk_watch, host nftables, TTS, WebRTC (M3), rollar muharriri.

## 0. Tamoyillar
- **Bloklash SIP darajasida — PJSIP ACL** (CTO jonli sinagan, Asterisk 22): `/srv/dialplan/pjsip_acl_innova.conf` fayli
  (`[innova-ban]` `type=acl`, har IP uchun `deny=<ip>/32`; ban yo'q bo'lsa — faqat izoh qatori) statik `pjsip.conf`dan `#include` qilinadi.
  Qo'llash = atomik yozish (`app/services/atomic_write.py`) + AMI `Command: module reload res_pjsip.so`. Ban qilingan IP'ning har qanday
  SIP so'roviga Asterisk `403 Forbidden` qaytaradi; blokdan chiqarish ham faqat reload bilan (restart YO'Q). Mavjud qo'ng'iroqlar uzilmaydi.
- **Yagona manba — PostgreSQL** (`ip_bans`), ACL fayli undan generatsiya qilinadi (dialplan bilan BIR XIL qolip). API ishga tushganda fayl
  bazadan qayta yoziladi (fayl yo'q yoki eskirgan bo'lsa).
- **Hujum hodisalari manbai** — Asterisk `security` logger kanali → `/var/log/asterisk/innova/security.log` (yangi `astlog` volume:
  Asterisk rw, API ro). API `sip_guard` fon vazifasi har `SIP_GUARD_INTERVAL_S` (sukut 5) soniyada fayldagi YANGI qatorlarni o'qiydi
  (offset xotirada; API ishga tushganda — fayl oxiridan; fayl qisqarsa/inode o'zgarsa — boshidan).
- **Ishonchli tarmoqlar** (`trusted_nets`) hech qachon avtomatik bloklanmaydi; ularni qo'lda bloklash → 409 `trusted_ip`.
  Asterisk konteyneri, API konteyneri va `local_nets` avtomatik ishonchli EMAS (admin o'zi qo'shadi) — lekin 127.0.0.0/8 doim ishonchli.
- **Ogohlantirish = navbat**: hodisa joyida faqat `alert_log`ga `pending` qator yoziladi (chaqiruvchining tranzaksiyasida);
  `alert_dispatch` fon vazifasi (har 2 s) `FOR UPDATE SKIP LOCKED` bilan oladi va Telegram'ga yuboradi. API restartidan keyin ham `pending`
  yuboriladi, ikki marta yuborilmaydi (vm_notify bilan BIR XIL g'oya).
- Fon vazifalari `main.py` lifespan'da (vm_notify qolipi); har biri xatoda yiqilmaydi (log + keyingi aylanish).

## 1. Sozlamalar — `GET/PATCH /security/settings`
`system_settings.sip_guard` va `system_settings.toll_fraud` (JSONB, 0016 standart qiymat bilan to'ldiradi). Standart va chegaralar —
YAGONA joyda `app/services/security_config.py` (`SipGuardConfig`, `TollFraudConfig`, `parse_*`):
```
sip_guard:  { "enabled": true, "max_failures": 5 (3..100), "window_s": 60 (10..3600),
              "ban_s": 3600 (0 = muddatsiz | 10..2592000), "trusted_nets": [] (CIDR, ≤ 50) }
toll_fraud: { "enabled": true, "max_concurrent_outbound": 0 (0 = cheksiz | 1..500),
              "ext_max_per_hour": 60 (0 | 1..10000), "ext_international_per_day": 20 (0 | 1..10000) }
```
`GET` → `{sip_guard, toll_fraud, updated_at}`. `PATCH {sip_guard?: {...qisman}, toll_fraud?: {...qisman}, updated_at}` → 409 `stale`,
noto'g'ri qiymat 422 (`field` = `sip_guard.max_failures` kabi). `toll_fraud.max_concurrent_outbound` o'zgarsa — dialplan qayta
kompilyatsiya (javobda `apply` bloki). Audit `security.settings`.

## 2. SIP hujum himoyasi (S33)
- Sanaladigan hodisalar: `InvalidAccountID`, `ChallengeResponseFailed`, `InvalidPassword` (Asterisk 22 `security` kanali formati — jonli
  tekshirilsin, `RemoteAddress="IPV4/UDP/1.2.3.4/5060"`). `FailedACL` (bloklangan IP urinishi) — faqat statistikaga `blocked`.
- IP `window_s` ichida `max_failures` ta sanaladigan hodisaga yetsa (va ishonchli emas, `enabled`) → `ip_bans` qatori (`reason='auto'`,
  `failures`, `expires_at = now + ban_s` yoki null) → ACL qo'llash → `security_events(kind='ip_banned')` → ogohlantirish `ip_banned`
  (key = ip). N-chi muvaffaqiyatsiz urinishdan bloklashgacha ≤ 15 s.
- Statistika: `sip_attack_stats(tenant_id, hour, ip, failures, blocked)` — soat bo'yicha upsert (hujum ostida har urinish alohida qator
  YOZILMAYDI).
- Muddat: `expires_at <= now` → `lifted_at = now`, `lift_reason='expired'`, ACL qayta qo'llash, hodisa `ban_expired` (sip_guard aylanishida).
- API:
  - `GET /security/bans` → faqat faol (`lifted_at is null`): `{id, ip, reason: auto|manual, failures, note, created_at, expires_at, created_by}`.
  - `POST /security/bans {ip, note?, ban_s?}` → 201 `{item, apply}`; noto'g'ri IP 422 `bad_ip`; ishonchli → 409 `trusted_ip`;
    allaqachon faol → 409 `already_banned`. `ban_s` berilmasa — sozlamadagi.
  - `DELETE /security/bans/{id}` → 200 `{apply}`; `lifted_at`, `lift_reason='manual'`, hodisa `ip_unbanned`. Audit ikkalasida.
  - `GET /security/stats?hours=24` (1..168) → `{ "hours": [{hour, failures, blocked}] (to'liq qator, bo'sh soat = 0),
    "top_ips": [{ip, failures, last_at, banned}] (≤ 10), "totals": {failures, blocked, bans_active, bans_period} }`.
  - `GET /security/events?limit=100&kind=` → `{id, at, kind, ip, extension, details}`; kind ∈ `ip_banned, ip_unbanned, ban_expired,
    toll_blocked, toll_unblocked, concurrent_limit`.
- `apply` muvaffaqiyatsiz (AMI yo'q) → ban bazada qoladi, `apply.status='failed'`, keyingi `sip_guard` aylanishi qayta urinadi.

## 3. Toll-fraud
- **Bir vaqtdagi chiquvchi limit** (`max_concurrent_outbound > 0`) — dialplan, API'siz ishlaydi: chiquvchi marshrutda Dial'dan oldin
  `Set(GROUP(innova_out)=all)`; `GROUP_COUNT(all@innova_out) > N` → ichki `CURL` `/internal/toll/event?kind=concurrent_limit&ext=..`
  (javob e'tiborsiz) + `Congestion()`. `N = 0` → bu qatorlar umuman chiqmaydi.
- **Ichki raqam limitlari** — Dial'dan oldin `CURL(/internal/toll/check?token=..&ext=<raqam>&number=<terilgan>&intl=0|1)`
  (conntimeout 2, timeout 3). `intl=1` faqat raqam haqiqatan xalqaro bo'lganda (compiler `_route_international_lines` mantiqi).
  Javob `"1"` → davom; `"0"` → `Playback(ss-noservice)` + `Hangup(21)`; bo'sh (API ishlamayapti) → ichki/mahalliy raqamga RUXSAT,
  xalqaroga RAD (fail-closed faqat xalqaro uchun).
- `/internal/toll/check` mantiqi (token noto'g'ri → `"0"`; `enabled=false` → `"1"`):
  ext `toll_blocked_at` bo'lsa → `"0"`. Aks holda hisob oynasi boshlanishi = `max(now - 1h, toll_unblocked_at)` (xalqaro uchun
  `now - 24h`); shu oynadagi `allowed=true` urinishlar soni ≥ limit → ext bloklanadi (`toll_blocked_at=now`,
  `toll_block_reason='per_hour'|'international_per_day'`), hodisa `toll_blocked`, ogohlantirish `toll_blocked` (key = ext raqami),
  `"0"`. Har tekshiruv `outbound_attempts`ga yoziladi (`allowed` bilan). Toll bloki admin `outbound_allowed`dan ALOHIDA.
- API: `GET /security/toll-blocks` → `{items:[{extension_id, number, name, blocked_at, reason}]}`;
  `POST /security/toll-blocks/{extension_id}/unblock` → 200 `{item:{extension_id, number}}`, `toll_unblocked_at=now`, hodisa
  `toll_unblocked`, audit. Bloklanmagan → 409 `not_blocked`. `ExtensionOut`ga `toll_blocked_at`, `toll_block_reason`.

## 4. Ogohlantirishlar (Telegram) — `GET/PATCH /settings/alerts`, `POST /settings/alerts/test`, `GET /alerts`
`system_settings.telegram` JSONB (0016 standart):
```
{ "chat_ids": [] (≤ 10, ^-?\d{1,20}$), "dedup_s": 600 (0..86400),
  "events": { "ip_banned": true, "toll_blocked": true, "concurrent_limit": true, "trunk_down": true, "trunk_up": true } }
```
Bot token — mavjud `/settings/notify` (`telegram_token`, `telegram_api_base`) — qayta so'ralmaydi.
- `raise_alert(session, tenant_id, kind, key, text)` (`app/services/alerts.py`): hodisa turi o'chiq → `status='disabled'`; shu `(kind,key)`
  `dedup_s` ichida `sent`/`pending` bo'lsa → `suppressed`; aks holda `pending`. Dispatch: token yoki chat yo'q → `failed`
  (`error='no_token'|'no_chat'`); har chat'ga `sendMessage`; birortasi muvaffaqiyatsiz → `failed` + sabab (token'siz).
- Matn tenant tilida (uz/ru/en), qisqa: `🚫 SIP hujum: 1.2.3.4 bloklandi (6 urinish / 60 s)`, `☎️ Toll-fraud: 101 chiquvchi bloklandi
  (soatiga 60 limiti)`, `⚠️ Trunk «X» ishlamayapti: <sabab>`, `✅ Trunk «X» tiklandi`, `⛔ Bir vaqtdagi chiquvchi limit (N) to'ldi: 101`.
- `GET /settings/alerts` → `{chat_ids, dedup_s, events, has_telegram_token, updated_at}`; `PATCH` (updated_at, 409 `stale`, 422).
- `POST /settings/alerts/test` → sinxron, hamma chat'ga; 200 `{sent: n}`; token yo'q 422 `no_token`; chat yo'q 422 `no_chat`;
  Telegram xatosi 502 `notify_failed` (sabab, token'siz). `alert_log`ga `kind='test'` yoziladi.
- `GET /alerts?limit=50&kind=` → `{id, at, kind, key, text, status: pending|sent|failed|suppressed|disabled, error, sent_at}`.

## 5. Trunk monitoringi
- `trunk_monitor` fon vazifasi har `TRUNK_MONITOR_INTERVAL_S` (sukut 30): yoqilgan trunklar uchun mavjud `compute_trunk_health`
  (`app/services/trunk_health.py`) → `trunk_health` upsert (`state`, `reason`, `checked_at`). Holat «ishlaydi» ↔ «ishlamaydi» o'zgarsa
  (lug'at `trunk_health.py`dagi state'lardan, `unknown` — o'tish emas) → `trunk_down` / `trunk_up` (key = trunk id). Birinchi kuzatuv
  ogohlantirmaydi. `/trunks`, `/dashboard` mantig'i o'zgarmaydi.

## 6. Web (admin)
- `/settings/security` (S33): «Holat» (24 soat ustunli grafik — `dataviz` skili, jami, top IP + «bloklash»), «Bloklangan IP» (jadval,
  qo'lda bloklash dialogi, blokdan chiqarish, muddat), «Toll-fraud» (bloklangan ichki raqamlar + «blokdan chiqarish», limitlar),
  «Sozlamalar» (sip_guard + ishonchli tarmoqlar), «Hodisalar» (ro'yxat, filtr).
- `/settings/alerts`: chat ID'lar, hodisa turlari, dedup, «Sinov xabari», tarix jadvali (holat belgilari). Token yo'q → `/settings/notify`ga havola.
- Sidebar «Tizim» guruhiga ikkalasi; ichki raqamlar ro'yxatida «toll blok» belgisi. uz/ru/en, fake + real api, vitest, dizayn tizimi tokenlari.

## 7. Isbot — `scripts/m2c-proof.sh --fresh`
1. Sozlamalar: GET standartlar; PATCH qisman; 422 chegaralar; 409 stale; operator → 403.
2. SIP brute-force: X IP'dan 6 ta noto'g'ri parolli REGISTER → ≤ 15 s `GET /security/bans`da X (`auto`, failures ≥ 5); X'dan OPTIONS →
   403; soxta Telegram X'li xabar oldi; `ip_banned` hodisasi; `stats` X ≥ 5.
3. Ishonchli: Y `trusted_nets`da, 6 noto'g'ri → 15 s dan keyin ham ban yo'q, OPTIONS → 401.
4. Blokdan chiqarish: DELETE → X OPTIONS → 401, `ip_unbanned`. Qo'lda ban Z `ban_s=10` → 403 → ≤ 25 s ichida `ban_expired`, 401.
   Qo'lda ishonchli IP → 409 `trusted_ip`; takror → 409 `already_banned`.
5. Toll: `ext_max_per_hour=2` → 101 dan 2 chiquvchi OK, 3-si rad (trunk tomonga INVITE KELMAYDI), ext bloklangan, Telegram, hodisa;
   unblock → 4-si OK (oyna unblock'dan). Xalqaro `ext_international_per_day=1` → 2-xalqaro rad.
   API to'xtatilgan: mahalliy chiquvchi OK, xalqaro rad; API qaytadi.
6. Bir vaqtdagi limit `max_concurrent_outbound=1` → ikki parallel chiquvchi: ikkinchisi rad, `concurrent_limit` hodisasi + Telegram.
7. Trunk monitor: trunk peer konteyneri to'xtatiladi → `trunk_down` Telegram'da; qayta yoqiladi → `trunk_up`.
8. Ogohlantirishlar: dedup (`suppressed`), o'chiq tur (`disabled`), `/settings/alerts/test`, tarix; token javob/audit/alert_log'da yo'q.
Regressiya: m0, m1a, m1b, m1c, m2a, m2b — `--fresh` 0 FAIL.
