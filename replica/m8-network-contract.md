# M8 — Tarmoq sozlamalari (Issabel «Network» andozasi) + yig'iladigan menyu — 1.0.8

Manba: foydalanuvchi so'rovi (2026-11-03): «issabeldan ham andoza olish kerak. statik route va interfacelarni
sozlash imkonini ham qoshish kerak. Asosiy menyularni yigiladigan qilish kerak».
Issabel'da: System → Network → Network Parameters (hostname, shlyuz, DNS) + Network Interfaces (DHCP/Static).
Bizdagi ustunlik: **statik marshrutlar** + **tasdiqlanmasa avtomatik qaytarish** (commit-confirm) — veb-paneldan IP
o'zgartirib serverni yo'qotib qo'yish imkonsiz.

## 1. Arxitektura
API konteyneri host tarmog'iga tegolmaydi. Yangi compose servisi **`netd`** (api obrazi, buyruq `python -m app.netd`):
- `privileged: true`, `pid: host`, `network_mode: host`, `restart: unless-stopped`.
- Host fayllari — `/proc/1/root/<yo'l>` orqali o'qiladi/yoziladi (atomik: shu papkada tmp + `os.replace`).
- Host buyruqlari — FAQAT `nsenter -t 1 -m -u -n -i -p -- <argv>` (shell YO'Q, argv ro'yxati, qat'iy allowlist:
  `ip`, `ifup`, `ifdown`, `hostname`). Har biriga timeout.
- API bilan aloqa: unix socket `/run/innova-netd/netd.sock` (named volume `netd-sock`, ikkala servisda bir xil
  yo'lda; socket 0600, ikkalasi root). Protokol: bitta qator JSON so'rov → bitta qator JSON javob.
  `{"op":"state"}` | `{"op":"validate","config":{..}}` | `{"op":"apply","config":{..},"timeout_s":N,"meta":{..}}`
  | `{"op":"confirm","id":".."}` | `{"op":"rollback","id":".."}`. Xato: `{"ok":false,"error":"..","fields":[..]}`.
- `NETD_READONLY=1` — har qanday yozuvni rad etadi (dev serverda SHU rejim; dev server Ubuntu/netplan —
  uning tarmog'iga HECH QACHON tegilmaydi).
- Backend aniqlash: `/etc/network/interfaces` mavjud va netplan/NetworkManager boshqarmayotgan → `ifupdown`
  (ISO = Debian 13 netinst — asosiy nishon, TO'LIQ tahrir). `netplan` / `networkmanager` / `unknown` → faqat
  ko'rish (`readonly_reason` tushunarli o'zbekcha matn).
- DNS faqat `/etc/resolv.conf` oddiy fayl bo'lsa tahrirlanadi (symlink → `dns.editable=false`).
- Hostname: `/etc/hostname`, `/etc/hosts` dagi `127.0.1.1` qatori, `hostname <nom>` (nsenter).

## 2. Commit-confirm (eng muhim)
1. `apply`: joriy holat snapshot → `/proc/1/root/var/lib/innova/netd/pending.json` (eski fayllar matni, deadline,
   id, xulosa). Fayllar yoziladi; o'zgargan interfeyslar `ifdown --force X; ifup X`; faqat marshrut o'zgargan
   bo'lsa — jonli `ip route replace/del` (ifdown'siz).
2. Taymer (sukut 180 s, 60..600) ichida `confirm` kelmasa — eski fayllar qaytariladi va qayta qo'llanadi.
3. `netd` qayta ishga tushganda `pending.json` bo'lsa — DARHOL qaytarish (xavfsiz tomonga).
4. Bir vaqtda faqat bitta pending (ikkinchisi → 409).
5. Qaytarish/tasdiqlash natijasi `last_result` sifatida state'da (UI ko'rsatadi: «Sozlama qaytarildi — tasdiqlanmadi»).

## 3. ifupdown fayli
- Parser `/etc/network/interfaces` ni bloklarga ajratadi; tushunilmagan qatorlar/stanzalar (inet6, bridge_*, dns-*,
  source, izohlar) SO'ZMA-SO'Z saqlanadi (round-trip testi: parse→render = asl matn, o'zgarish bo'lmasa).
- Biz boshqaradigan: `iface X inet dhcp|static`, `address A/P` (yoki `address`+`netmask` o'qiladi, CIDR yoziladi),
  `gateway`, `mtu`; statik marshrutlar shu interfeys stanzasida
  `up ip route replace <dst> via <gw> dev X metric M  # innova-route` va mos `down ip route del ... # innova-route`.
  Marshrut interfeysi berilmasa — shlyuz qaysi interfeys subnetiga tushsa, o'sha.
- `allow-hotplug`/`auto` mavjudi saqlanadi; yangi statik interfeysga `auto X`.

## 4. API (FastAPI, `/api/v1/network/*`, faqat admin `*`, `require_access` — system.py dagi kabi)
```
GET  /network/state → NetworkStateOut
POST /network/validate  NetworkConfigIn → {ok, errors:[{field,message}], warnings:[str], diff:[str]}
POST /network/apply     NetworkConfigIn → NetworkStateOut   (409 pending bor; 422 xato; 503 netd yo'q/readonly) + audit
POST /network/confirm   {pending_id}    → NetworkStateOut   + audit
POST /network/rollback  {pending_id}    → NetworkStateOut   + audit
```
NetworkStateOut:
```
{ helper:{available:bool, version:str|null, error:str|null},
  backend:'ifupdown'|'netplan'|'networkmanager'|'unknown', editable:bool, readonly_reason:str|null,
  hostname:str,
  dns:{servers:[str], search:[str], editable:bool},
  default_gateway:{address:str|null, interface:str|null},           // jonli (ip route)
  interfaces:[{name, mac:str|null, kind:'ethernet'|'vlan'|'bond'|'bridge'|'wireless'|'other',
               oper_state:'up'|'down'|'unknown', carrier:bool, speed_mbps:int|null, mtu:int,
               live_ipv4:[cidr], live_ipv6:[cidr], editable:bool,
               config:{mode:'dhcp'|'static'|'manual'|'unconfigured', address:cidr|null, gateway:str|null, mtu:int|null}}],
  routes:{static:[{destination:cidr, gateway:str|null, interface:str|null, metric:int|null}],
          live:[{destination, gateway:str|null, interface:str|null, metric:int|null, protocol:str|null}]},
  pending:null|{id, applied_at, expires_at, summary:[str]},
  last_result:null|{kind:'confirmed'|'rolled_back'|'apply_failed', at, message:str|null} }
```
Interfeyslar ro'yxati: `lo`, `docker0`, `br-*`, `veth*` va boshqa virtual (konteyner) qurilmalar KO'RSATILMAYDI.
`editable` = backend ifupdown && fizik/bond/vlan.

NetworkConfigIn (to'liq kerakli holat — qisman patch emas):
```
{ hostname:str, dns:{servers:[ipv4|ipv6] ≤3, search:[domain] ≤6},
  interfaces:[{name, mode:'dhcp'|'static', address:cidr|null, gateway:ipv4|null, mtu:int|null (576..9000)}],
  routes:[{destination:cidr, gateway:ipv4|null, interface:str|null, metric:int|null (0..9999)}],
  timeout_s:int=180 (60..600) }
```
Tekshiruv (422 `fields`): hostname RFC1123; static → address majburiy, gateway shu subnetda; butun konfiguratsiyada
≤1 gateway; interfeys nomi mavjud va editable; marshrut: `0.0.0.0/0` taqiqlangan (gateway maydoni bor), gateway yoki
interface majburiy, gateway biror interfeys subnetiga tushishi kerak (aks holda xato), dublikat (dst+metric) yo'q;
hech bo'lmasa bitta interfeys manzilli qoladi.
Ogohlantirish (warnings): so'rov kelgan host IP (Host sarlavhasi) o'zgaradigan interfeysda bo'lsa —
«Siz ulangan manzil o'zgaradi. Yangi manzil: http://<yangi-ip>/ — 180 s ichida o'sha yerdan kirib tasdiqlang».
Audit: `action="network.apply|network.confirm|network.rollback"`, `entity="network"`, diff = qisqa xulosa.

## 5. Frontend
- Ekran `network`: `/settings/network`, guruh `system`, ikon lucide `EthernetPort`; i18n uz/ru/en (`network` ns).
- Sahifa: sarlavha + 3 tab — **Umumiy** (hostname, DNS 1–3, qidiruv domenlari; joriy asosiy shlyuz faqat ko'rish),
  **Interfeyslar** (jadval: nom, MAC, ulanish/tezlik, joriy IP, rejim; tahrir modal: DHCP/Statik, IP/prefiks,
  shlyuz, MTU), **Statik marshrutlar** (jadval + qo'shish/tahrir/o'chirish; yig'iladigan «Joriy marshrut jadvali»).
- Tahrirlar lokal qoralama; pastda yopishqoq panel «N ta o'zgarish · Bekor qilish · Qo'llash». Qo'llash →
  `validate` → tasdiq oynasi (diff + ogohlantirishlar + taymer tanlash) → `apply`.
- Pending banner (sahifa tepasida): teskari sanoq, «Tasdiqlash» (asosiy) va «Hozir qaytarish». `last_result` banneri.
- `editable=false` → tahrir tugmalari yo'q, sabab banneri. `helper.available=false` → «Tarmoq xizmati ishlamayapti».
- Fake klient (`api/fake.ts`): ifupdown, 2 interfeys (ens18 statik, ens19 dhcp), 1 marshrut; apply→pending.

## 6. Yig'iladigan menyu
Sidebar'dagi har bir guruh sarlavhasi — tugma (chevron, `aria-expanded`, `aria-controls`). Holat
`localStorage['innova.nav.collapsed']` (guruh id ro'yxati). Faol sahifa joylashgan guruh doim ochiq
(yopiq bo'lsa ham avtomatik ochiladi). Silliq balandlik animatsiyasi (`prefers-reduced-motion` hurmat).
Yig'ilgan guruhda ichida «jonli» (live) nuqtali ekran bo'lsa — nuqta guruh sarlavhasida ko'rinadi.
