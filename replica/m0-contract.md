# M0 shartnomasi — backend ↔ frontend (yagona manba)

Ikkala tomon SHU faylga amal qiladi. O'zgartirish kerak bo'lsa — shu faylni yangilang va build-log'ga yozing.
Hammasi `/api/v1`, JSON, `Authorization: Bearer <access>`. Xato formati hamma joyda bir xil:
`{"error": {"code": "snake_case", "message": "o'zbekcha matn", "field": "ixtiyoriy", "details": {}}}`.
Vaqtlar — ISO 8601 UTC (`...Z`), UI tenant TZ'da (`Asia/Tashkent`) ko'rsatadi.
Yozuvchi so'rov javobida: `"apply": {"status": "applied"|"unchanged"|"rolled_back"|"realtime", "revision": int|null, "message": str|null}`.

## Setup / auth
- `GET /setup/state` → `{"needed": bool}` (adminlar yo'q bo'lsa true)
- `POST /setup` (faqat needed=true; aks holda 409 `setup_done`)
  `{"admin": {"login","password","full_name"}, "language": "uz|ru|en", "timezone": "Asia/Tashkent", "external_ip": str|null, "local_nets": ["10.0.0.0/8"]}`
  → `{"access": str, "refresh": str, "user": User}`
- `POST /auth/login` `{"login","password"}` → `{"access","refresh","user"}`; 401 `bad_credentials`, 423 `locked` (5 xato → 15 daq)
- `POST /auth/refresh` `{"refresh"}` → `{"access","refresh"}` (rotatsiya)
- `POST /auth/logout` `{"refresh"}` → 204
- `GET /auth/me` → `User`
- `User = {"id","login","full_name","role": "admin|operator","permissions": [str],"language"}`
- 2FA (TOTP) — M1. M0 da maydon yo'q.

## Ichki raqamlar (S04)
- `GET /extensions?q=&page=1&size=50` → `{"items": [Extension], "total": int}`
- `Extension = {"id","number": "101","name","enabled": bool,"status": "online|offline|unknown","contact": str|null,"user_agent": str|null,"updated_at"}`
  (`status` — AMI/`ps_contacts` dan jonli)
- `POST /extensions` `{"number"?: str, "name": str}` (number yo'q → birinchi bo'sh 100–999) → `{"item": Extension, "sip": {"username","password","domain","port"}, "apply"}`
  409 `number_taken`; parol FAQAT shu javobda va rotate'da ko'rinadi.
- `PATCH /extensions/{id}` `{"name"?, "enabled"?, "updated_at"}` → `{"item","apply"}`; 409 `stale` (optimistik qulf)
- `POST /extensions/{id}/rotate-secret` → `{"sip": {...}, "apply": {"status":"realtime"}}` — reload'SIZ kuchga kiradi
- `DELETE /extensions/{id}` → 204; 409 `in_use` + `details.usages: [{"kind":"inbound_route","id","label"}]`

## Trunklar (S06) — M0: faqat IP-trunk (registratsiyasiz, `match` bo'yicha)
- `GET /trunks` → `{"items": [Trunk]}`
- `Trunk = {"id","name","host": "ip yoki fqdn","port": 5060,"match": ["ip/cidr"],"codecs": ["alaw","ulaw"],"max_channels": int|null,"enabled","health": {"state": "ok|unreachable|unknown|disabled","rtt_ms": int|null,"checked_at": str|null},"updated_at"}`
- `POST /trunks`, `PATCH /trunks/{id}`, `DELETE /trunks/{id}` (409 `in_use`) → `{"item","apply"}`
- `POST /trunks/{id}/test` → `{"ok": bool, "rtt_ms": int|null, "detail": str}` (PJSIP qualify / OPTIONS)

## Kiruvchi marshrutlar (S07) — M0: manzil faqat ichki raqam
- `GET /inbound-routes` → `{"items": [InboundRoute]}`
- `InboundRoute = {"id","name","did": str|null (null = har qanday),"cid": str|null,"target": Target,"enabled","updated_at"}`
- `Target = {"id","kind": "extension","label": "101 · Dilnoza","number": "101","broken": bool}`
- `POST/PATCH/DELETE /inbound-routes[/{id}]` `{"name","did","cid","target_id","enabled"}` → `{"item","apply"}`; 409 `did_conflict`
- `GET /targets?kind=extension&q=` → `{"items": [Target]}`

## Tarix (S12)
- `GET /calls?from=&to=&q=&direction=in|out|internal&page=1&size=50` → `{"items": [Call], "total"}`
- `Call = {"uniqueid","started_at","src","dst","did": str|null,"direction","disposition": "answered|no_answer|busy|failed","duration": int,"billsec": int,"trunk": str|null}`

## Tizim
- `GET /system/health` → `{"asterisk": {"up": bool,"version": str|null,"uptime_s": int|null},"db": {"up": bool},"revision": int|null}`
- `GET /config/revisions?limit=20` → `{"items": [{"id","sha256","status","created_at","message"}]}`

## Ruxsatlar (M0)
admin — hammasi. operator — `GET /auth/me`, `GET /calls` (faqat o'z raqami). Qolgani 403 `forbidden`.
