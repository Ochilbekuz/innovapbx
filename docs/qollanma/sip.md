---
id: sip
title: SIP va tarmoq
group: system
order: 10
path: /settings/sip
summary: Tashqi IP/domen, lokal tarmoqlar, SIP/RTP portlar, kodeklar, TLS sertifikati va bildirishnoma kanallari.
---

# SIP va tarmoq

IP-ATSning tashqi dunyo va telefonlar bilan qanday "gaplashishi"ni belgilaydigan asosiy tarmoq sozlamalari:
qaysi tashqi IP/domen koʻrsatiladi, qaysi portlar ovoz (RTP) uchun ishlatiladi, qanday kodeklar yoqilgan,
SIP TLS (shifrlangan ulanish) sertifikati va ovozli pochta/ogohlantirish xabarlarini yuborish uchun
email/Telegram kanallari.

## Qayerda
Menyu: **Tizim → SIP va tarmoq**. Kim koʻradi: faqat `*` (toʻliq administrator) ruxsati bor foydalanuvchi
oʻzgartira oladi; boshqalarga "Sizda tizim sozlamalarini boshqarish ruxsati yoʻq — faqat koʻrish mumkin"
deb koʻrsatiladi (maydonlar oʻchirilgan holda koʻrinadi).

## Asosiy tushunchalar

- **Tashqi IP/domen** — telefonlar NAT ortidan ulanganda ATS qaysi manzilni ovoz (RTP) oqimi uchun eʼlon
  qiladi. Agar serveringiz NAT orqasida boʻlsa, bu yerga oʻzining **ommaviy** IP manzilini koʻrsatish kerak.
- **Lokal tarmoqlar (CIDR)** — shu tarmoqlardagi qurilmalar "NATsiz" (lokal) deb hisoblanadi, ularga maxsus
  NAT ishlov berish qoʻllanmaydi.
- **RTP diapazoni** — ovoz paketlari uchun port oraligʻi; har bir faol qoʻngʻiroq shu oraliqdan bir juft
  port oladi.
- **TLS sertifikati** — SIP signalizatsiyasini shifrlash uchun (`sips://`); oʻz sertifikatingizni yuklash
  yoki serverda oʻz-oʻzidan imzolangan sertifikat yaratish mumkin.
- **Bildirishnomalar** — ovozli pochta va boshqa tizim xabarlarini email (SMTP) va/yoki Telegram orqali
  yuborish sozlamalari (masalan, [Ogohlantirishlar](/docs/alerts) shu kanallar orqali yetib boradi).

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Tashqi IP | NAT ortidagi ommaviy IP (ixtiyoriy) | `203.0.113.10` |
| Tashqi domen | Tashqi domen nomi (ixtiyoriy) | `pbx.kompaniya.uz` |
| Lokal tarmoqlar (CIDR) | Har qatorda bitta tarmoq | `192.168.1.0/24` |
| SIP UDP port | SIP signalizatsiya porti | — |
| SIP TLS port | Shifrlangan SIP porti (ixtiyoriy, UDP portdan farqli boʻlishi shart) | oʻchirilgan bo'lishi mumkin |
| RTP boshlanishi / tugashi | Ovoz porti oraligʻi — kamida 100 port farqi boʻlishi shart | — |
| Kodeklar | `ulaw`, `alaw`, `g722`, `opus` — kamida bittasi tanlangan boʻlishi kerak | — |
| **TLS** → Sertifikat/Kalit/Zanjir | Yuklanadigan fayllar (PEM format) | — |
| Common name | Oʻz-oʻzidan imzolangan sertifikat uchun domen nomi | `pbx.kompaniya.uz` |
| **Bildirishnomalar** → SMTP host/port/shifrlash/foydalanuvchi/parol | Email yuborish uchun SMTP server maʼlumotlari | — |
| Yuboruvchi email | "Kimdan" maydoni | — |
| Telegram bot tokeni | Bot API tokeni | — |
| Telegram API manzili | Odatda standart, oʻzgartirish kerak boʻlmaydi | — |

## Qanday qilinadi

### Aniqlangan tarmoqni qoʻllash
1. Sahifa yuqorisidagi **Aniqlangan tarmoq** blokida server avtomatik aniqlagan tashqi IP va lokal
   tarmoqlar koʻrsatiladi.
2. **Qoʻllash** — aniqlangan tashqi IPni **Tashqi IP** maydoniga koʻchiradi.
3. **Hammasini qoʻllash** — aniqlangan lokal tarmoqlarni **Lokal tarmoqlar** maydoniga koʻchiradi.

### SIP/RTP sozlamalarini oʻzgartirish
1. Kerakli maydonlarni toʻldiring (tashqi IP/domen, lokal tarmoqlar, portlar, RTP oraligʻi, kodeklar).
2. **Saqlash**ni bosing.
3. Agar tarmoq sozlamalari oʻzgargan boʻlsa, sahifa yuqorisida ogohlantirish chiqadi — **Qayta ishga
   tushirish** tugmasi bilan Asterisk xizmatini qayta yuklang, aks holda yangi sozlamalar amal qilmaydi.
4. Agar hozir faol qoʻngʻiroqlar bosib yuborilayotgan boʻlsa, tizim ogohlantiradi — **Baribir qayta ishga
   tushirish**ni tanlasangiz, barcha faol qoʻngʻiroqlar uziladi.

### TLS sertifikatini yuklash
1. **TLS sertifikati** blokida **Sertifikat yuklash**ni bosing.
2. Sertifikat (`cert`) va maxfiy kalit (`key`) fayllarini tanlang (PEM format); zanjir (`chain`) ixtiyoriy.
3. **Sertifikat yuklash**ni tasdiqlang.
4. Agar sertifikat/kalit mos kelmasa, muddati tugagan boʻlsa yoki PEM formatida boʻlmasa — tizim aniq
   sababini koʻrsatadi.

### Oʻz-oʻzidan imzolangan sertifikat yaratish
1. **Oʻz-oʻzidan imzolangan yaratish**ni bosing.
2. **Common name** (domen nomi) kiritib tasdiqlang.

### Bildirishnoma kanallarini sozlash
1. **Bildirishnomalar** blokida SMTP (host, port, shifrlash turi, foydalanuvchi, parol, yuboruvchi email)
   va/yoki Telegram bot tokeni va API manzilini kiriting.
2. Parol/token maydonini boʻsh qoldirsangiz — avval saqlangan qiymat oʻzgarmaydi.
3. **Saqlash**ni bosing.
4. **Sinov xabari** blokida kanalni (Email/Telegram) tanlab, manzilni (email yoki Telegram chat ID/@kanal)
   kiritib, **Sinov yuborish**ni bosing — kanal toʻgʻri sozlanganini tekshirish uchun.

## Maslahatlar va cheklovlar

> [!WARNING]
> Asterisk xizmatini qayta ishga tushirish barcha **faol qoʻngʻiroqlarni uzadi**. Imkon qadar band
> boʻlmagan vaqtda bajaring.

> [!TIP]
> Agar server bulut provayderida NAT ortida boʻlsa, **Tashqi IP**ni toʻgʻri koʻrsatmasangiz, qoʻngʻiroqda
> ovoz bir tomonlama yoki umuman eshitilmasligi mumkin — batafsil: [Muammolar](/docs/muammolar).

- RTP oraligʻi kamida **100 port** boʻlishi shart.
- SIP UDP va TLS portlari bir xil boʻlishi mumkin emas.
- Kamida bitta kodek tanlangan boʻlishi kerak.
- Sertifikat muddati tugashiga yaqin boʻlsa (necha kun qolgani koʻrsatiladi) yoki allaqachon tugagan boʻlsa
  — sahifada aniq ogohlantirish chiqadi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| «RTP oraligʻi kamida 100 port boʻlishi kerak» | Boshlanishi/tugashi orasida farq yetarli emas | Oraliqni kengaytiring |
| «UDP va TLS portlari bir xil boʻlmasligi kerak» | Ikki portga bir xil qiymat kiritilgan | TLS portini boshqa qiymatga oʻzgartiring |
| Sertifikat yuklanmaydi, «Kalit sertifikatga mos kelmaydi» | Boshqa juftlikdagi fayllar yuklangan | Toʻgʻri cert/key juftligini yuklang |
| Sertifikat yuklanmaydi, «Fayl PEM formatida emas» | `.der`/boshqa format yuklangan | Faylni PEM (`.pem`/`.crt`) formatiga aylantirib yuklang |
| Sinov xabari yuborilmaydi, «SMTP serverga ulanib boʻlmadi» | Host/port notoʻgʻri yoki tarmoq bloklaydi | SMTP maʼlumotlarini tekshiring |
| Sinov xabari yuborilmaydi, «Telegram bot tokeni notoʻgʻri» | Token xato kiritilgan | Botdan yangi tokenni tekshirib qayta kiriting |
| Qayta ishga tushirishdan keyin ovoz yoʻq/bir tomonlama | Tashqi IP yoki RTP oraligʻi firewallda ochilmagan | [Firewall](/docs/firewall) va [Muammolar](/docs/muammolar)ni tekshiring |

## Bog'liq bo'limlar

- [Ogohlantirishlar](/docs/alerts)
- [Firewall](/docs/firewall)
- [Tarmoq](/docs/network)
- [Muammolar](/docs/muammolar)
