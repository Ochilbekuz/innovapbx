# M7 — Rollar muharriri (S31 to'liq) — 1.0.5

M2b/M2c da «rollar muharriri» ataylab qoldirilgan edi (faqat `admin`/`operator`). Endi: maxsus rollar,
bo'limlar bo'yicha `Yo'q / Ko'rish / Tahrirlash` ruxsatlari (FreePBX «User Management → Groups / Admin access» analogi).

## 1. Ruxsat modeli
- Ruxsat kaliti: `<hudud>:view` yoki `<hudud>:edit` (`edit` ⇒ `view`). Mavjudlar saqlanadi: `*` (admin), `calls:read:own`, `me:*`.
- Hududlar (faqat shular maxsus rolga beriladi; boshqa kalit → 422 `validation_error`, field `permissions`):

| hudud | ekranlar (screens.ts id) | API (asosiy prefikslar) |
|---|---|---|
| `monitor` | dashboard, live | /dashboard, /alerts, /live (edit = jonli qo'ng'iroq amallari) |
| `extensions` | extensions, devices, voicemail | /extensions, /devices, /voicemail-boxes, follow_me, /settings/provisioning |
| `connect` | trunks, inbound, outbound | /trunks, /inbound-routes, /outbound-routes |
| `routing` | timegroups, ivr, queues, ringgroups, misc | /time-groups, /holidays, /time-conditions, /ivrs, /queues, /ring-groups |
| `apps` | audio, conference, parking, blacklist, campaigns | /audio, /moh-classes, /conferences, /parking, /blacklist, /campaigns |
| `reports` | cdr (hammasi), analytics, quality | /calls (hammasi), /reports, /recordings |

- **Tizim** guruhi (sip, audit, security, alerts, backup, migration, status, featurecodes, integrations, license, users/rollar)
  va unga tegishli API (/settings*, /security, /backups, /migration*, /audit, /users, /roles, /system, /feature-codes,
  /integrations*, /numbers? — pastga qarang) — FAQAT `*` (admin). Sabab: zaxira tiklash / foydalanuvchi boshqaruvi orqali
  imtiyozni oshirib bo'lmasin.
- Tekshiruv MARKAZIY (`app/api/deps.py`): marshrut shabloni (`request.scope["route"].path`) bo'yicha eng uzun prefiks →
  hudud; GET/HEAD → `view`, qolgani → `edit`. Xaritada yo'q marshrut → faqat `*` (fail-closed). Mavjud 201 ta
  `Depends(require_admin)` shu dependency'ga o'tadi. Istisnolar (masalan o'qish uchun POST) — aniq ro'yxat bilan.
- Umumiy tanlagichlar (destination picker va h.k.: `/targets`, `/flow`, `/numbers`, ro'yxat GET'lari) — kamida bitta
  hududda `edit` bo'lgan rolga GET ruxsat (sahifa ishlashi uchun). Aniq ro'yxat kodda + test.
- `calls`: `*` yoki `reports:view` → hammasi; `calls:read:own` → faqat o'zi; aks holda 403.
- Ruxsatlar har so'rovda bazadan (rol joined) o'qiladi → rol o'zgarishi DARHOL ta'sir qiladi (token bekor qilish shart emas).
- `/me/*` va `/softphone` — har qanday kirgan foydalanuvchiga (o'zgarmaydi).

## 2. Rollar API (faqat `*`)
- `GET /roles` → `{items: RoleOut[]}`; `RoleOut = {id, name, permissions: string[], is_system, user_count, updated_at}`
  (tartib: tizim rollari avval — admin, operator — keyin nom bo'yicha).
- `POST /roles` `{name, permissions}` → 201 `{item: RoleOut}`. `name` trim, 1–40 belgi; band → 409 `role_name_taken` (field name);
  `admin`/`operator` nomlari band.
- `PATCH /roles/{id}` `{name?, permissions?, updated_at}` → `{item}`; eskirgan → 409 `stale` (mavjud `check_not_stale`);
  tizim roli → 409 `system_role`.
- `DELETE /roles/{id}` → 204; tizim roli → 409 `system_role`; foydalanuvchisi bor → 409 `role_in_use` (`details.user_count`).
- Ruxsatlar normallashtiriladi: takrorlar olib tashlanadi, `X:edit` bo'lsa `X:view` ham saqlanmaydi (faqat eng yuqori daraja).
- Audit: `role.create/update/delete`.

## 3. Foydalanuvchilar (o'zgarish)
- `role` — endi istalgan mavjud rol NOMI (string). Noma'lum → 422 `validation_error` field `role`. Qolgan qoidalar
  (`self_lockout`, `last_admin`, token bekor qilish rol o'zgarsa) o'zgarmaydi.
- `/auth/me` va login javobida `role` + `permissions` (allaqachon bor) — web shundan foydalanadi.

## 4. Web
- `/settings/users` sahifasida ikki tab: **Foydalanuvchilar** | **Rollar** (FreePBX uslubi).
- Rollar tabi: jadval (nom, foydalanuvchilar soni, qisqa ruxsatlar xulosasi, tizim belgisi). «Yangi rol» → modal: nom +
  hududlar matritsasi (har qatorda segment: Yo'q / Ko'rish / Tahrirlash), tizim rollari faqat ko'rish (tavsif bilan).
  O'chirish — tasdiq dialogi; `role_in_use` → tushunarli xabar.
- Foydalanuvchi formasida rol tanlovi `/roles` dan (tizim rollari tarjimada, maxsus — nomi bilan).
- Navigatsiya/marshrut himoyasi `permissions` bo'yicha: ekran ko'rinadi ⇔ `*` yoki hududida `view`; tizim guruhi — faqat `*`;
  portal (`/me`) — hammaga; cdr — `reports:view` yoki `calls:read:own`. Bosh sahifa: admin/monitor:view → `/dashboard`,
  aks holda birinchi ko'rinadigan ekran, bo'lmasa `/me`.
- Ko'rish darajasida: «Yangi …», tahrir/o'chirish tugmalari yashirin (umumiy hook `useCanEdit(hudud)`); baribir 403 kelsa —
  «Ruxsat yo'q» toast.
- `web/src/api/fake.ts` — rollar endpointlari va ruxsat tekshiruvi backend bilan BIR XIL mantiqda.
- i18n: uz/ru/en.

## 5. Isbot (scripts/m7-proof.sh --fresh)
Admin `routing:edit`+`reports:view` rol yaratadi → foydalanuvchi kiradi: GET /ivrs 200, POST /ivrs 201, GET /trunks 403,
POST /trunks 403, GET /users 403, GET /calls 200 (hammasi). Rolni `routing:view` ga tushirish → POST /ivrs 403 darhol.
Rol o'chirish (foydalanuvchi bor) 409 `role_in_use`; tizim rolini tahrirlash 409 `system_role`; `foo:edit` → 422.
Operator xatti-harakati o'zgarmagan (m2b isboti 0 FAIL).
