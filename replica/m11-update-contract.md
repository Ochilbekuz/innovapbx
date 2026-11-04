# M11 — Paneldan yangilash (1.0.13) — shartnoma

Maqsad: admin `/settings/update` sahifasida joriy/yangi versiyani, o'zgarishlar ro'yxatini ko'radi,
«Tekshirish» va «Yangilash» bosadi, jarayon logini jonli kuzatadi. Ish HOSTDA bajariladi
(mavjud `innova-update` = `iso/files/innova-update.sh`), API konteyneri qayta ishga tushsa ham uzilmaydi.

## 0. Tamoyillar
- API host'da HECH NARSA bajarmaydi va argument uzatmaydi — faqat `request` faylini yozadi (bitta so'z).
- `status`, `update.log`, `changelog.md`, `history` — FAQAT host agenti yozadi (bitta yozuvchi, `flock`).
- Agent `request` ichidagi so'zni allowlist bilan tekshiradi: `check` | `update`. Boshqasi — e'tiborsiz, o'chiriladi.
- Bir vaqtda bitta ish: `innova-update` barcha rejimlarda `flock -n /run/innova-update.lock` (CLI ham, timer ham, agent ham).

## 1. Host fayllari — `UPD=/var/lib/innova/update` (root, 0755; env `INNOVA_UPDATE_DIR` bilan almashtiriladi — testlar)
| fayl | yozuvchi | mazmun |
|---|---|---|
| `request` | API (`O_CREAT|O_EXCL`, 0600) | `check\n` yoki `update\n` |
| `status` | agent (tmp + `mv`, atomik) | `key=value` qatorlar, quyida |
| `update.log` | agent | oxirgi `update` yugurishining logi (har `update` boshida qayta yaratiladi), ANSI rangsiz |
| `changelog.md` | agent | `git show @{u}:CHANGELOG.md` (har muvaffaqiyatli tekshiruvdan keyin) |
| `history` | agent (qo'shib yozadi) | TSV: `finished_at<TAB>from<TAB>to<TAB>result(ok|failed:<code>)` |

`status` kalitlari (qiymatlar `[A-Za-z0-9._:+-]*`, bo'sh = yo'q):
```
state=idle|checking|updating|done|failed
phase=backup|code|install        # faqat state=updating paytida
current=1.0.12                   # host /opt/innova/VERSION
latest=1.0.13                    # @{u}:VERSION (oxirgi tekshiruv)
available=0|1
checked_at=2026-11-04T10:00:00Z  # UTC ISO
started_at=... finished_at=...   # oxirgi update yugurishi
error=no_source|fetch_failed|git_dirty|backup_failed|install_failed|interrupted|bad_request
backup=pre-update-1.0.12-20261104-100000.sql.gz   # faqat fayl nomi
```
`interrupted`: agent lock olganda `state=updating|checking` ko'rsa (oldingi yugurish o'lgan, masalan reboot) → `failed/interrupted`.

## 2. `innova-update` yangi rejimlari
- `--agent` — systemd path xizmati chaqiradi: `request` ni o'qiydi → o'chiradi → `check` yoki `update` (status yozib).
  `update` = mavjud oqim (zaxira → `git merge --ff-only` → `install.sh`), har bosqichda `phase`, oxirida `done`/`failed`.
  Yangi versiya bo'lmasa `update` → `failed` emas: `state=idle` (hech narsa qilinmaydi).
- `--check` status papkasi mavjud bo'lsa unga ham yozadi (timer shuni chaqiradi). Exit kodlari o'zgarmaydi (10 = bor).
- Mavjud CLI xatti-harakati va `tests/install/test_update.sh` buzilmasin.

## 3. systemd (install.sh o'rnatadi, `iso/files/`)
- `innova-update-agent.path`: `PathExists=/var/lib/innova/update/request`, `MakeDirectory=yes` → `innova-update-agent.service`.
- `innova-update-agent.service`: `Type=oneshot`, `ExecStart=/usr/local/sbin/innova-update --agent`, `TimeoutStartSec=3600`.
- `innova-update-check.timer` (`OnBootSec=10min`, `OnUnitActiveSec=12h`, `RandomizedDelaySec=30min`) → `innova-update-check.service`
  (`innova-update --check`, exit 10 = muvaffaqiyat: `SuccessExitStatus=10`).
- `deploy/docker-compose.appliance.yml` → `api`: `- /var/lib/innova/update:/var/lib/innova/update` va env `INNOVA_VERSION: ${INNOVA_VERSION:-}`.
  Asosiy `docker-compose.yml` (dev) ga TEGILMAYDI — dev'da papka yo'q → `agent=false`.

## 4. API (`/api/v1`, faqat admin — `require_access`, marshrut xaritasida YO'Q = fail-closed `*`)
`settings.update_dir` (sukut `/var/lib/innova/update`), `settings.innova_version` (env `INNOVA_VERSION`, bo'sh → null).

`GET /system/update` → `SystemUpdateOut`:
```json
{ "agent": true, "current": "1.0.12", "latest": "1.0.13", "available": true,
  "state": "idle", "phase": null, "pending": null,
  "checked_at": "...", "started_at": null, "finished_at": null,
  "error": null, "backup": null,
  "changelog": [{"version": "1.0.13", "date": "2026-11-04", "body": "markdown"}] }
```
- `agent` = papka mavjud va yozish mumkin. `false` bo'lsa qolgan maydonlar null/[] (front: «paneldan yangilash o'rnatilmagan» + CLI yo'riqnomasi).
- `current`: `status.current` → yo'q bo'lsa `settings.innova_version`.
- `pending` = `request` fayli bor bo'lsa uning so'zi (`check`/`update`), aks holda null.
- `changelog` = `changelog.md` dan `current` dan KATTA versiyali `## X.Y.Z — sana` bo'limlari, yangisi birinchi (sof funksiya, semver solishtirish).
- Noma'lum/buzuq `status` qiymatlari — e'tiborsiz (null), 500 emas.

`POST /system/update/check` → 202 + `SystemUpdateOut` (`pending="check"`).
`POST /system/update/start` `{ "version": "1.0.13" }` → 202 + `SystemUpdateOut` (`pending="update"`); audit `system.update.start` (from/to).
Xatolar (`ApiError`): 503 `update_agent_missing`; 409 `update_busy` (request bor yoki state checking/updating);
409 `update_not_available` (available≠1); 409 `update_version_mismatch` (version≠latest — eskirgan sahifa); 422 versiya formati `^[0-9A-Za-z._-]{1,32}$`.

`GET /system/update/log?offset=0` → `{ "offset": <keyingi>, "size": <jami>, "text": "..." }`, bir martada ≤ 64 KiB, ANSI kodlar tozalanadi,
offset > size → 0 dan (log qayta yaratilgan). Fayl yo'q → `{offset:0,size:0,text:""}`.

## 5. Front (`/settings/update`, guruh `system`, ikonka lucide `RefreshCw`/`ArrowUpCircle`, faqat `*`)
- Versiya kartasi: joriy versiya, oxirgi tekshiruv vaqti (Toshkent), «Tekshirish» tugmasi.
- Yangi versiya bo'lsa: `latest` + o'zgarishlar (changelog markdown, xavfsiz render — HTML yo'q) + «Yangilash» → tasdiq modali
  (zaxira olinadi, 5–15 daqiqa, qo'ng'iroqlar ~1 daqiqa uziladi, versiya raqamini yozib tasdiqlash).
- Jarayon: bosqichlar (zaxira → kod → o'rnatish → qayta ishga tushish) + jonli log (2 s polling `log?offset`).
  API 502/503/tarmoq xatosi update paytida = «tizim qayta ishga tushmoqda», polling davom etadi (xato emas).
  `state=done` va `current` yangi → muvaffaqiyat + «Sahifani yangilash» (yangi front assetlari).
- `failed` → xato kodi bo'yicha o'zbekcha tushuntirish + zaxira fayl nomi + logni ko'rish.
- `agent=false` → izohli bo'sh holat (`sudo innova-update` CLI).
- Sidebar/topbar: `available=true` bo'lsa «Yangilanish» yonida kichik nuqta (ixtiyoriy, oddiy).
