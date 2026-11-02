# FreePBX manba stendi — haqiqiy fakt va sxema hujjati

> **Clean-room eslatma**: bu hujjat faqat FAKT va SXEMA tasnifi uchun. Innova PBX'ning
> o'z kodiga (dialplan generatori, GUI, importer) FreePBX'ning HECH QANDAY kodi,
> matni yoki logosi ko'chirilmaydi — faqat "qanday ishlaydi" bilimi qo'llaniladi.
>
> Noaniq/tekshirilmagan har bir band **"taxmin"** deb belgilangan. Qolgan hamma band
> `tests/freepbx-fixture/` stendida bevosita ishga tushirib, SQL/CLI orqali
> **tasdiqlangan** (2026-10-30).

## 0. Versiya

| Komponent | Qiymat | Qayerdan tasdiqlangan |
|---|---|---|
| FreePBX (framework moduli) | **17.0.33.2** | `fwconsole ma list` va `admin.version` jadvali bir xil qiymat berdi |
| `fwconsole -V` | FW Console - FreePBX Utility 17.0.33.2 | CLI |
| Asterisk | **22.8.2** | `asterisk -V` |
| PHP | 8.2.30 (CLI, NTS) | `php -v` |
| Docker image | `ekoyuliawan/freepbx:latest` (Docker Hub, rasmiy emas) | compose fayli |
| MariaDB | 10.6 (alohida konteyner, image ichida emas) | compose fayli |

Eslatma: oldingi ishchi hujjatlarda "framework 17.0.28" degan eski raqam yurgan edi —
bu stendda bevosita tekshirilgach, HAQIQIY versiya hamma joyda **17.0.33.2** ekani
aniqlandi (tuzatildi).

## 1. Stend tarkibi va ishga tushirish

Fayl: `tests/freepbx-fixture/docker-compose.yml`, loyiha nomi `innova-fpbx` (mavjud
`innova-m0` stekiga tegmaydi, alohida tarmoq `innova-fpbx-net`). Barcha portlar
**faqat `127.0.0.1`** ga bog'langan:

- Web GUI/API: `127.0.0.1:8720` -> konteyner ichida `:80`
- MySQL/MariaDB: `127.0.0.1:3320` -> konteyner ichida `:3306`

```bash
# Ishga tushirish:
cd /root/devteam/workspaces/6199793291/pbx-klon/tests/freepbx-fixture
docker compose -p innova-fpbx up -d

# To'xtatish (ma'lumot saqlanadi, named volume'lar o'chmaydi):
docker compose -p innova-fpbx stop

# Butunlay o'chirish (volume'lar bilan — EHTIYOT BO'LING):
docker compose -p innova-fpbx down -v
```

**Sinov hisob ma'lumotlari** (barchasi test qiymatlari, hech qanday real tizimda
ishlatilmagan):

| Narsa | Qiymat |
|---|---|
| MySQL root paroli | `sinov-root-PAROL1` |
| MySQL `freepbxuser` paroli | `notabeneNYA76` |
| Ext 101-103,106,107 SIP siri | `SinovSecret<ext>!` (masalan `SinovSecret101!`) |
| Ext 105 VM PIN | `1105` |
| Konferensiya 8000 user/admin PIN | `1234` / `4321` |
| Trunk1 SIP user/secret | `sinovuser1` / `SinovTrunkSecret1!` |
| Backup job nomi | `Sinov-Fixture-Backup` |

GUI'ga kirish: image ichida FreePBX o'rnatilgan holda keladi, lekin **GUI login
devori yo'q edi** — toki `findmefollow` modulini o'rnatish `userman` modulini
bog'liqlik sifatida tortib kelmaguncha (pastda 9-band, "taxmin" emas — ushbu
stendda bevosita kuzatilgan). `userman` o'rnatilgandan keyin GUI autentifikatsiya
talab qilishi mumkin — bu holatda admin foydalanuvchini `fwconsole user add`
(taxmin: aniq buyruq nomi tekshirilmadi) orqali yaratish kerak bo'ladi.

`seed.sh` (tests/freepbx-fixture/seed.sh) — idempotent wrapper: avval barcha
sinov jadvallarini tozalaydi (`DELETE FROM` + `AUTO_INCREMENT` reset), keyin
`seed_src/seed.php`'ni konteyner ichida ishga tushiradi, so'ngra `fwconsole reload`.

## 2. GUI-ekvivalenti PHP bootstrap naqshi

FreePBX GUI'siz, to'g'ridan-to'g'ri PHP CLI'dan GUI'ning "add" funksiyalarini
chaqirish uchun ishlatilgan asosiy naqsh (haqiqiy, ishlagan):

```php
define('FREEPBX_IS_AUTH_ADMIN', true);
require_once('/etc/freepbx.conf');
require_once('/var/www/html/admin/modules/core/functions.inc.php');
// AMI qo'lda ulanadi — ko'p "add" funksiyalari ichkarida $astman'ga tayanadi:
$astman = new agi_asteriskmanager();
$astman->connect('127.0.0.1:5038', FreePBX::Config()->get('AMPMGRUSER'), FreePBX::Config()->get('AMPMGRPASS'));
```

PHP 8.x'da FreePBX 17'ning o'z deprecation/warning'larini xatolikka aylantirish
xulq-atvorini bosish uchun maxsus `set_error_handler()` kerak bo'ldi (aks holda
har qanday `empty()`/`ctype_digit()` ogohlantirishi butun skriptni to'xtatadi).

`FreePBX::<Komponent>()` — "Component" naqshi: `Core::__get($var)` komponentlarni
"lazy" yaratadi. **MUHIM fakt**: Outbound Routing komponenti property nomi
`routing` (GUI menyusidagi nomdan farqli — `Outboundrouting` EMAS):
`FreePBX::Core()->routing->add(...)`.

## 3. Jadval/ustun sxemasi (DESCRIBE orqali tasdiqlangan)

### 3.1 Extensionlar: `users` + `devices` + `sip`/`pjsip` (keyword-jadval)

```
users:    extension, password, name, voicemail, ringtimer, noanswer, recording,
          outboundcid, sipname, noanswer_cid, busy_cid, chanunavail_cid,
          noanswer_dest, busy_dest, chanunavail_dest, mohclass
devices:  id, tech, dial, devicetype, user, description, emergency_cid, hint_override
sip:      id, keyword, data, flags   -- "EAV" (entity-attribute-value) jadval
pjsip:    id, keyword, data, flags   -- xuddi shu shakl, LEKIN FAQAT TRUNKLAR uchun
```

**Empirik, versiyaga bog'liq fakt**: PJSIP extension/device sozlamalari
`sip` keyword-jadvalida saqlanadi, `pjsip` jadvalida EMAS — sababi: PHP klassi
`PJSip extends Sip` va `addDevice()` metodini qayta aniqlamaydi, shuning uchun
yozish yo'li meros bo'yicha eski `Sip` klassiga tushadi. Bu — **saqlash qatlami**
haqidagi fakt; lekin `fwconsole reload` keyin generatsiya qilingan `pjsip.conf`
tomon **to'g'ri chan_pjsip endpoint'lar** chiqadi (`pjsip show endpoints` orqali
tasdiqlangan: `101/101`, `102/102` va h.k. ko'rinadi). Demak: DB saqlash ustuni
bilan runtime Asterisk config generatori boshqa-boshqa qatlam — importer buni
"sip" keyword jadvalidan o'qib PJSIP semantikasida talqin qilishi SHART.

`104/chan_sip` — **IMKONSIZ** bu stendda: Asterisk 22'da `chan_sip` to'liq olib
tashlangan (`module show like sip` faqat `chan_pjsip*`ni ko'rsatadi). Buyurtma
shartiga ko'ra bu majburiy emas ("agar modul mavjud bo'lsa").

### 3.2 Trunklar: `trunks` + `pjsip` (keyword)

```
trunks: trunkid, tech, channelid, name, outcid, keepcid, maxchans, failscript,
        dialoutprefix, usercontext, provider, disabled, continue, routedisplay
```

PJSIP trunk uchun to'liq standart kalitlar ro'yxati (ishlatilgan, chunki
`fwconsole reload` ulardan BIRINING yo'qligida `Undefined array key` bilan
qulaydi): `channelid, dialoutprefix, maxchans, outcid, peerdetails, usercontext,
userconfig, register, keepcid, failtrunk, disabletrunk, provider, continue,
dialopts, tech, extdisplay, sv_trunk_name, sv_usercontext, sv_channelid, npanxx,
trunk_name, hcid, dialoutopts_cb, failtrunk_enable, prepend_digit, username,
auth_username, secret, authentication, registration, language, sip_server,
sip_server_port, context, transport, dtmfmode, auth_rejection_permanent,
allow_unauthenticated_options, forbidden_retry_interval, fatal_retry_interval,
retry_interval, expiration, max_retries, qualify_frequency, outbound_proxy,
user_eq_phone, contact_user, from_domain, from_user, client_uri, server_uri,
media_address, aors, aor_contact, match, support_path, t38_udptl, t38_udptl_ec,
t38_udptl_nat, t38_udptl_maxdatagram, fax_detect, trust_rpid, sendrpid,
trust_id_outbound, identify_by, inband_progress, direct_media, rewrite_contact,
rtp_symmetric, media_encryption, force_rport, message_context`.

**Haqiqiy kod tuzog'i** — `Core::checkPJSIPsettings($settings, $posts)`:
birinchi argument ($settings) ichkarida BUTUNLAY tashlanadi (`$settings = [];`),
ikkinchi argument ICHIDAGI `$posts['imports']` kaliti ishlatiladi (`$posts`
to'g'ridan-to'g'ri EMAS!). To'g'ri chaqiruv:
```php
$settings = FreePBX::Core()->checkPJSIPsettings([], ['imports' => $customSettings]);
FreePBX::Core()->addTrunk($trunkName, 'pjsip', $settings);
```
Bu formatni noto'g'ri qilib (`['imports'=>...]`siz) chaqirish `fwconsole reload`
vaqtida XATOLIK BERMAYDI (sukut qiymatlar bilan to'ladi), lekin natijada
`sip_server`/`registration`/`trunk_name` kabi muhim maydonlar JIMGINA bo'sh/
standart qiymatda qoladi — bu eng xavfli turdagi xato, chunki hech qanday
exception chiqmaydi, faqat generatsiya qilingan `pjsip.conf` yoki
`pjsip.registration.conf` kutilmagan natija beradi (yoki registratsiya
umuman ishlamay qoladi).

Registratsiyali trunk uchun qo'shimcha qoida (`PJSip.class.php` genConfig,
~550-qator): `registration='send'` bo'lsa, `sip_server` **bo'sh bo'lmasligi
SHART** — aks holda `throw new Exception('Asterisk will crash if sip_server
is blank!')` bilan `fwconsole reload` to'liq to'xtaydi.

### 3.3 Inbound route (DID): `incoming`

```
incoming: cidnum, extension, destination, privacyman, alertinfo, ringing,
          fanswer, mohclass, description, grppre, delay_answer, pricid,
          pmmaxretries, pmminlength, reversal, rvolume, indication_zone
```

`extension` bo'sh bo'lsa — "har qanday DID" (catch-all) qoidasi. `destination`
ustuni — pastda tasvirlangan xom destination-string grammatikasi.

### 3.4 Outbound route: `outbound_routes` + `outbound_route_patterns` + `outbound_route_trunks`

```
outbound_routes:        route_id, name, outcid, outcid_mode, password,
                         emergency_route, intracompany_route, mohclass,
                         time_group_id, dest, time_mode, calendar_id,
                         calendar_group_id, timezone, notification_on
outbound_route_patterns: route_id, match_pattern_prefix, match_pattern_pass,
                         match_cid, prepend_digits   (hammasi PRIMARY KEY qismi!)
outbound_route_trunks:  route_id, trunk_id, seq      (seq = trunk ketma-ketlik tartibi)
outbound_route_email:   route_id (PRIMARY, bitta ustunli), emailfrom, emailto,
                        emailsubject, emailbody
```

**Yana bir haqiqiy kod tuzog'i** (`Outboundrouting::add()` / `setOutboundRouteEmail()`,
tasdiqlangan idempotentlik testi orqali): `add()` metodi HAR DOIM, email
sozlamalari bo'sh bo'lsa ham, `setOutboundRouteEmail($route_id,...)`ni
chaqiradi, va bu metod ICHIDA **plain `INSERT`** ishlatiladi (`REPLACE`/
`INSERT ... ON DUPLICATE KEY` EMAS). Agar `outbound_route_email` jadvalida
shu `route_id` bilan ESKI qator (masalan oldingi seed ishidan qolgan) mavjud
bo'lsa — `outbound_routes`/`outbound_route_patterns`/`outbound_route_trunks`
jadvallariga yozish MUVAFFAQIYATLI o'tadi (chunki `outbound_routes.route_id`
ustuni haqiqatda bo'sh/to'g'ri edi), lekin shundan KEYIN `setOutboundRouteEmail()`
ICHIDAGI INSERT "Duplicate entry '<route_id>' for key 'PRIMARY'" bilan
chiqadi — bu xato tashqi `try/catch`ga chiqib, GO'YO butun marshrut
yaratilmagan bo'lib ko'rinadi, HOLBUKI asosiy marshrut qatori allaqachon
TO'G'RI yozilgan bo'ladi (faqat email-bildirishnoma qatori yozilmay qoladi).
Har qanday idempotent reset/importer skripti `outbound_route_email`ni ham
MAJBURIY tozalashi kerak — bu jadval boshqa hech qaysi "standart" ro'yxatda
(masalan GUI "Outbound Routes" sahifasida) ko'rinmaydi, shuning uchun uni
unutib qolish OSON.

Fixture namunasi (haqiqiy saqlangan qatorlar):
```
route_id=1 name=Sinov-Mobil outcid=+998901110000 outcid_mode=ALLOW password=SinovRoutePass1
  pattern: prefix=0 pass=XXXXXXXXX prepend=+998
  trunks (seq tartibida): trunk_id=1 seq=0, trunk_id=2 seq=1   <- failover: 1 band bo'lmasa 2'ga
route_id=2 name=Sinov-Xizmat
  pattern: prefix=1 pass=XX prepend=(bo'sh)
  trunks: trunk_id=2 seq=0
```

API: `FreePBX::Core()->routing->add($name,$outcid,$outcid_mode,$password,
$emergency_route,$intracompany_route,$mohclass,$time_group_id,$patterns,$trunks,...)`
— `$patterns` massiv ichidagi assoc-massivlar, `$trunks` — ID'lar massivi
(tartib = seq).

### 3.5 Ring group: `ringgroups`

```
ringgroups: grpnum, strategy, grptime, grppre, grplist, annmsg_id, postdest,
            description, alertinfo, remotealert_id, needsconf, toolate_id,
            ringing, cwignore, cfignore, cpickup, recording, progress,
            elsewhere, rvolume
```

`grplist` — tire bilan ajratilgan a'zolar ro'yxati; tashqi raqam oxiriga `#`
qo'shiladi (masalan `"101-102-103-0991234567#"`).

### 3.6 Navbat (Queue): `queues_config` + `queues_details`

```
queues_config:  extension (PRI), descr, grppre, alertinfo, ringing, maxwait,
                password, ivr_id, dest, cwignore, queuewait, use_queue_context,
                togglehint, qnoanswer, callconfirm, callconfirm_id, qregex,
                agentannounce_id, joinannounce_id, monitor_type, monitor_heard,
                monitor_spoken, callback_id
queues_details: id, keyword, data, flags   -- EAV jadval (strategy, timeout,
                wrapuptime, maxlen, joinempty, leavewhenempty, music va h.k.
                shu yerda keyword/data juftligi sifatida saqlanadi)
```

**Haqiqiy persistence funksiyasi** GUI kontroller klassida EMAS, balki
protsedura ko'rinishida: `queues_add()` fayl
`admin/modules/queues/functions.inc/geters_seters.php` ichida. Ko'p
sozlamalarni (`maxlen,joinempty,leavewhenempty,strategy,timeout,retry,
wrapuptime,announce-frequency,...`) PARAMETR orqali EMAS, balki global
`$_REQUEST`'dan o'qiydi — CLI'dan chaqirishda `$_REQUEST` qo'lda to'ldirilishi
SHART.

Statik a'zo format (REST API kodidan tasdiqlangan): bir harfli prefiks
konvensiyasi — `P`=PJSIP, `S`=SIP, `X`=IAX2, `Z`/`D`=DAHDI/ZAP, `A`=Agent,
standart (prefikssiz)=`Local`. Fixture'da ishlatilgan haqiqiy format:
`Local/<ext>@from-queue/n,<penalty>` (masalan `Local/101@from-queue/n,0`).

Dinamik a'zolar DB'da EMAS, balki **astdb**'da: `QPENALTY/<queueExt>/agents`
(key=a'zo, value=penalty) va `QPENALTY/<queueExt>` (key=dynmemberonly flag).

### 3.7 IVR: `ivr_details` + `ivr_entries`

```
ivr_details: id, name, description, announcement, directdial, invalid_loops,
             invalid_retry_recording, invalid_destination, timeout_enabled,
             invalid_recording, retvm, timeout_time, timeout_recording,
             timeout_retry_recording, timeout_destination, timeout_loops,
             timeout_append_announce, invalid_append_announce,
             timeout_ivr_ret, invalid_ivr_ret, alertinfo, rvolume,
             strict_dial_timeout, accept_pound_key
ivr_entries: ivr_id, selection, dest, ivr_ret
```

`Ivr::saveDetails($vals)` — `$vals` massivida `'id'=>null` (yoki haqiqiy ID)
kaliti ALBATTA bo'lishi kerak, aks holda "Undefined array key" bilan
INSERT/REPLACE yo'lini noto'g'ri tanlaydi. `saveEntries($id,$entries)` —
`$entries` shakli: `['ext'=>[digit,...],'goto'=>[dest-string,...],
'ivr_ret'=>[0/1,...]]` (parallel massivlar, index bo'yicha mos keladi).
Maxsus digit'lar `i` (invalid) va `t` (timeout) alohida ustunlar orqali
(`invalid_destination`/`timeout_destination`) ishlaydi, `ivr_entries`ga
YOZILMAYDI.

### 3.8 Vaqt guruhi/sharti: `timegroups_groups` + `timegroups_details` + `timeconditions`

```
timegroups_groups:  id, description
timegroups_details: id, timegroupid, time   -- 'time' ustuni Asterisk pipe-format
timeconditions:      timeconditions_id, displayname, time (=timegroup id),
                     truegoto, falsegoto, deptname, generate_hint, invert_hint,
                     fcc_password, priority, timezone, mode, calendar_id,
                     calendar_group_id
```

**Vaqt format** (`buildTime()` orqali tasdiqlangan, haqiqiy fixture namunasi):
```
09:00-18:00|mon-fri|*|*          <- HH:MM-HH:MM|dow-dow|dom-dom|mon-mon
*|*|1|jan                        <- faqat 1-yanvar (bayram), vaqt/kun joker (*)
```
`'-'` kiritilganda GUI/API darajasida "joker" (`extract($val)` orqali
`buildTime()`ga uzatiladi, chiqishda `*` bo'ladi). Qiymatlar: hour/minute/mday
— raqamli; wday/month — 3-harfli qisqartma (`mon`,`fri`,`jan`).

**MUHIM va NOANIQ FreePBX KOD TUZOG'I** (`Timeconditions::addTimeCondition()`,
tasdiqlangan amaliy test orqali): kirish massivida `$post['goto1']`/`$post[<X>.'1']`
qiymati haqiqatda **`falsegoto`** ustuniga, `$post['goto0']`/`$post[<X>.'0']`
qiymati esa **`truegoto`** ustuniga yoziladi — ya'ni raqam indekslari (1/0)
nom va natija bo'yicha TESKARI. Birinchi urinishda bu teskari qo'llanilgan va
natijada ish-vaqti (true) shartiga e'lon, ish-vaqtidan tashqari (false)
shartiga IVR bog'lanib qolgan edi. To'g'ri chaqiruv namunasi (fixture'da
qo'llanilgan, qayta tekshirilgan):
```php
$post = [
    'goto0' => 'truekey',  'truekey0'  => "ivr-1,s,1",            // TRUE -> IVR
    'goto1' => 'falsekey', 'falsekey1' => "app-announcement-1,s,1" // FALSE -> e'lon
];
```
Har qanday FreePBX importerida bu nuqta **sinovdan o'tkazilishi SHART** —
sxema darajasida (`truegoto`/`falsegoto` ustunlari) hech qanday chalkashlik
yo'q, faqat GUI/API **kirish** formatida bor.

### 3.9 Follow Me: `findmefollow`

```
findmefollow: grpnum, strategy, grptime, grppre, grplist, annmsg_id, postdest,
              dring, rvolume, remotealert_id, needsconf, toolate_id, pre_ring,
              ringing, calendar_enable, calendar_id, calendar_group_id,
              calendar_match
```

`grplist` — tire bilan ajratilgan, tashqi raqamlar oxirida `#` (fixture:
`"107-0991234567#"`).

### 3.10 Boshqa obyektlar (sxema)

```
recordings:   id, displayname, filename (longblob — amalda nisbiy yo'l satri,
              masalan 'custom/sinov-tizim-yozuvi'), description, fcode,
              fcode_pass, fcode_lang
music:        id, category (UNIQUE), type, random, application, format
announcement: announcement_id, description, recording_id, allow_skip (INT!
              0/1 — 'yes'/'no' EMAS), post_dest, return_ivr, noanswer (INT!),
              repeat_msg
meetme:       exten, options, userpin, adminpin, description, joinmsg_id,
              music, users, language, timeout
miscdests:    id, description, destdial   -- destdial = xom dialable satr
              (masalan '101'), dialplan generatorida to'g'ridan-to'g'ri
              Goto(from-internal,<destdial>,1) sifatida ishlatiladi
featurecodes: modulename, featurename, defaultcode, customcode, enabled,
              providedest, depend, description, helptext
```

`*97` -> `*970` o'zgartirish (haqiqiy, sinovdan o'tgan):
```sql
UPDATE featurecodes SET customcode='*970'
WHERE modulename='voicemail' AND featurename='myvoicemail';
```
Keyin `fwconsole reload` — generatsiya qilingan `extensions_additional.conf`da
`exten => *970,1,...` ko'rinadi (eski `*97` qolmaydi, to'liq almashtiradi).

### 3.11 Voicemail — DIQQAT: alohida DB jadval YO'Q

`asterisk` bazasida `voicemail` nomli jadval **MAVJUD EMAS**
(`ERROR 1146: Table 'asterisk.voicemail' doesn't exist`). Ovozli xat
sozlamalari (PIN, email, mailbox) to'g'ridan-to'g'ri **`/etc/asterisk/voicemail.conf`**
faylida generatsiya qilinadi (`[default]` kontekst, format:
`<mailbox>=<PIN>,<Ism>,<email>,<pager>,<options>`). `users.voicemail` ustuni
faqat `novm` yoki `<vmcontext>` (masalan `default`) qiymatini oladi — bu
mailbox mavjudligini bildiruvchi bayroq, sozlamalarning o'zi EMAS.

**Haqiqiy kod tuzog'i** (`Core::addUser()`, ~3233-qator): `users.voicemail`
ustuni kiritilgan `$settings['voicemail']`'dan MUSTAQIL — ichkarida
`FreePBX::Voicemail()->getMailbox($extension)` chaqirilib, agar mailbox
topilmasa **majburan** `"novm"` yoziladi. Demak to'g'ri tartib:
1) avval `FreePBX::Voicemail()->addMailbox($ext, ['vm'=>'enabled','vmpwd'=>...,
   'email'=>...,'vmcontext'=>'default', ...])` bilan mailbox yaratiladi,
2) FAQAT SHUNDAN KEYIN `Core::addUser($ext,$settings)` chaqiriladi — shundagina
   `users.voicemail` to'g'ri `default` qiymatini oladi.
Teskari tartibda chaqirilsa — HECH QANDAY XATO CHIQMAYDI, lekin `voicemail.conf`da
mailbox paydo bo'lmaydi (jim xato, faqat natijani tekshirib aniqlanadi).

`Voicemail::saveVMSettingsByExtension()` — nomidan farqli, bu funksiya
mailbox'ni YARATMAYDI, faqat MAVJUDINI tahrirlaydi (`getVoicemailBoxByExtension()`
bilan boshlanadi).

### 3.12 Call forward / DND: astdb oilalari (DB jadval emas)

`Core.class.php` kodidan tasdiqlangan oilalar, barchasi `/<FAMILY>/<extension>`
kaliti bilan:
```
CF   — call forward unconditional (doim)
CFB  — call forward busy
CFU  — call forward no-answer/unavailable
DND  — Do Not Disturb (qiymat: 'YES'/boshqa)
CW   — Call Waiting
```
Fixture'da haqiqiy qatorlar (`astdb show` orqali tasdiqlangan):
```
/CF/102   : 106
/CFB/102  : 106
/CFU/102  : 105
/DND/106  : YES
```
`blacklist` oilasi (key=raqam, value=tavsif) — `Blacklist::numberAdd()` orqali.

## 4. Destination-string grammatikasi (haqiqiy fixture namunalari)

FreePBX ichki dialplan "destination" satri formati — har doim
`<context>,<extension/holat>,<priority>` uch qismli, vergul bilan ajratilgan:

| Destination turi | Format namunasi | Qayerda ishlatiladi |
|---|---|---|
| IVR | `ivr-1,s,1` | `incoming.destination`, `timeconditions.truegoto` |
| Ring group | `ext-group,600,1` | `incoming.destination`, `ivr_entries.dest` |
| Navbat (Queue) | `ext-queues,700,1` | `ivr_entries.dest` |
| Vaqt sharti | `timeconditions,1,1` | `incoming.destination` |
| E'lon (Announcement) | `app-announcement-1,s,1` | `timeconditions.falsegoto` |
| Qora ro'yxat/hangup | `app-blackhole,hangup,1` | IVR invalid/timeout destination |
| Ichki extension | `ext-local,101,1` | `ivr_entries.dest`, ring group `postdest` |
| Konferensiya | (taxmin: `ext-meetme,<room>,1` — bu fixture'da sinab ko'rilmadi) | — |

Umumiy qoida: `<prefiks>-<obyekt turi>[,-<id>],<kirish nuqtasi>,<ustuvorlik>` —
prefiks har bir modul uchun statik (`ivr-`, `ext-group`, `ext-queues`,
`app-announcement-`, `timeconditions`, `ext-local`, `app-blackhole`), ID faqat
ba'zi prefikslarda raqamga ulangan holda (`ivr-<ID>`, `app-announcement-<ID>`),
boshqalarida alohida pozitsiyada (`ext-group,<ID>,1`).

## 5. Boshqa eksport fayllari — tarkib va format

`tests/freepbx-fixture/export/` quyidagilarni o'z ichiga oladi:

- `asterisk.sql` — to'liq `mysqldump --single-transaction` (barcha jadvallar,
  DDL+DML).
- `tables/<jadval>.tsv` — har bir muhim jadval uchun `mysql -B -e 'SELECT * FROM ...'`
  natijasi (tab-separated, NULL so'z sifatida `NULL` chiqadi, maxsus belgilar
  `mysql -B` tomonidan avtomatik backslash-escape qilinadi — masalan
  tab/yangi qator ichki qiymatlarda `\t`/`\n` ko'rinishida chiqadi).
- `astdb.txt` — `asterisk -rx "database show"` to'liq natijasi (barcha
  AMPUSER/CF/CFB/CFU/DND/QPENALTY/blacklist kalitlari).
- `files/voicemail.conf`, `files/extensions_custom.conf`, `files/sounds/custom/*`,
  `files/moh/sinov-moh/*` — haqiqiy generatsiya qilingan/yuklangan fayllar.
- `backup/innova-fixture-backup.tar.gz` — **native FreePBX Backup & Restore**
  moduli orqali yaratilgan haqiqiy backup (quyida tarkibi).

### 5.1 Native Backup & Restore `.tar.gz` tarkibi (haqiqiy, ochib tekshirilgan)

```
modulejson/<ModulNomi>.json   -- har bir modul uchun alohida JSON (masalan
                                  Core.json, Ivr.json, Queues.json, ...);
                                  modul manifesti + eksport qilingan sozlamalar
files/<asl absolyut yo'l>     -- masalan files/etc/asterisk/voicemail.conf,
                                  files/var/lib/asterisk/moh/..., files/etc/asterisk/keys/...
tmp/cdr_dump/cdr.sql.gz        -- CDR/CEL alohida gzip SQL dump sifatida
tmp/cel_dump/cel.sql.gz
tmp/Devices_dump/Devices.sql   -- "Core" moduli devices/users/sip/pjsip jadvalini
                                  shu yerga dump qiladi (modulejson/Core.json ICHIDA
                                  emas, alohida SQL fayl sifatida)
```

Backup job **DB'da emas, `kvstore_FreePBX_modules_Backup`/`kvstore`da JSON**
ko'rinishida saqlanadi (`backupList`, `migratedbackups` kabi "turlar" bilan).
Yaratish uchun GUI-ekvivalenti chaqiruv: `FreePBX::Backup()->updateGQLBackup($input)`
(`$input` — `backup_name`,`backup_items` (`[['modulename'=>'Core','selected'=>true],...]`),
`backup_storage` (Filestore drayver ID massivi) kabi kalitlar), so'ngra
`fwconsole backup --backup=<id>` haqiqiy faylni yaratadi.

**Local filestore drayveri** — o'rnatilganda avtomatik yaratiladigan standart
yozuv: `kvstore_FreePBX_modules_Filestore` jadvalida `driver='Local'`,
`path='__ASTSPOOLDIR__/backup/'` (ya'ni `/var/spool/asterisk/backup/`), ID
— tasodifiy UUID (bu stendda `1928bb11-a81d-4e19-9779-a625cda6a1de`, albatta
har bir o'rnatishda BOSHQACHA bo'ladi — importer buni ID bo'yicha emas,
`driver='Local'` maydoni bo'yicha aniqlashi kerak).

## 6. Versiya farqlari 13-17 (taxmin — bu stendda faqat 17 tekshirildi)

- **13-14**: hali `chan_sip` mavjud edi (standart tech), PJSIP ixtiyoriy edi —
  demak `sip` keyword-jadvali o'sha paytda haqiqatda chan_sip uchun ishlatilgan,
  keyinroq PJSIP uchun QAYTA ISHLATILGAN (meros sinf arxitekturasi tufayli) —
  **taxmin**: shuning uchun "pjsip extensionlar `sip` jadvalida" degan fakt aslida
  tarixiy meros, versiyalar davomida o'zgarmagan.
- **15-16**: PJSIP standart tech bo'ldi, `chan_sip` hali modul sifatida mavjud
  edi (ixtiyoriy o'rnatiladigan) — **taxmin**.
- **17 / Asterisk 21-22**: `chan_sip` Asterisk manba kodidan TO'LIQ olib
  tashlangan (bu stendda **tasdiqlangan fakt**, taxmin emas) — demak 104/chan_sip
  kabi extension endi FreePBX GUI darajasida ham tanlanishi mumkin emas.
- Backup & Restore formati (`modulejson/*.json` + `files/`) — **taxmin**: bu
  format taxminan FreePBX 14-15'dan beri shu tarzda barqaror, ammo eski
  (13 va undan oldingi) versiyalarda ".tar.gz" ichida boshqacha (flat SQL dump +
  INI-format sozlamalar) tuzilma bo'lgan — bu da'vo TEKSHIRILMAGAN.

## 7. Boshqa "taxmin" deb belgilangan bandlar

- `userman`'ning `findmefollow`ga bog'liqlik sifatida avtomatik o'rnatilishi va
  shu orqali GUI login devorining paydo bo'lishi — **bu stendda bevosita
  kuzatilgan FAKT**, lekin "har doim shunday bo'ladimi" (masalan boshqa versiya/
  image'da userman allaqachon o'rnatilgan bo'lishi mumkin) — qisman taxmin.
- Konferensiya uchun destination-string formati (`ext-meetme,...`) — ushbu
  fixture'da hech bir boshqa obyekt konferensiyaga yo'naltirilmagani uchun
  TEKSHIRILMAGAN, faqat FreePBX manba kodi konvensiyasidan kelib chiqilgan
  taxmin.
- `fwconsole user add` admin yaratish buyrug'i aniq nomi — tekshirilmagan,
  taxmin (stendda GUI autentifikatsiyasiga kirish talab qilinmagani uchun
  sinab ko'rilmadi).
- Custom `extensions_custom.conf` konteksti — bu FreePBX tomonidan HECH QANDAY
  DB izsiz, faqat fayl darajasida boshqariladi (tasdiqlangan fakt); Innova PBX
  import vositasi UCHUN bu — **birinchi versiyada qo'llab-quvvatlanmaydigan,
  lekin ogohlantirish berilishi kerak bo'lgan edge case** sifatida belgilanadi.

## 8. Fixture obyektlari ro'yxati (yakuniy holat)

| Obyekt | Qiymat/ID | Izoh |
|---|---|---|
| Extension 101,102,103,105,106,107 | PJSIP | 104/chan_sip imkonsiz |
| Ext 102 | CF->106, CFB->106, CFU->105 | astdb orqali |
| Ext 105 | VM PIN 1105, email sinov105@example.test | addMailbox+addUser tartibi |
| Ext 106 | outboundcid +998901110106, DND=YES | |
| Ext 107 | Follow Me -> 107-0991234567# | findmefollow moduli |
| Trunk 1 | Sinov-Registered-Trunk (PJSIP, registration=send) | |
| Trunk 2 | Sinov-IPAuth-Trunk (PJSIP, identify_by=ip, match=203.0.113.10/32) | registratsiyasiz |
| Inbound 1 | 998712345601 -> ivr-1,s,1 | |
| Inbound 2 | 998712345602 -> timeconditions,1,1 | |
| Inbound 3 | (har qanday DID) -> ext-group,600,1 | |
| Outbound 1 | Sinov-Mobil, prefix 0->+998, trunk1 keyin trunk2 (failover) | |
| Outbound 2 | Sinov-Xizmat, prefix 1XX, trunk2 | |
| Ring group 600 | 101-102-103-tashqi raqam | |
| Queue 700 | statik 101,102 + dinamik 103 | |
| IVR 1 | 1->101, 2->ext-group 600, 3->ext-queues 700 | |
| Vaqt guruhi 1 | Dush-Juma 09-18 + 1-yanvar | |
| Vaqt sharti 1 | TRUE->ivr-1,s,1, FALSE->app-announcement-1,s,1 | |
| E'lon 1 | recording_id=1 asosida | |
| Tovush yozuvi 1 | custom/sinov-tizim-yozuvi (demo-congrats asosida) | |
| MOH kategoriya | sinov-moh | |
| Konferensiya 8000 | PIN 1234/4321 | |
| Qora ro'yxat | 0998887766 | |
| Boshqa manzil (Misc dest) | ->101 | |
| Feature code | *97 -> *970 | |
| Custom context | extensions_custom.conf: [sinov-custom-context] exten 999 | DB'siz, fayl darajasida |
