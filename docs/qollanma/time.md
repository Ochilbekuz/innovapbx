---
id: time
title: Sana va vaqt
group: system
order: 130
path: /settings/time
summary: Server va PBX vaqt zonasini tanlash, vaqtni internetdagi NTP serverlar bilan sinxronlash.
---

# Sana va vaqt

Serverning vaqt zonasini tanlash va vaqtni internetdagi **NTP** serverlardan avtomatik toʻgʻrilab turish
shu yerda sozlanadi. Tanlangan zona bir vaqtda **server** va **PBX** zonasi boʻladi: ish vaqti qoidalari
(vaqt shartlari, bayramlar), kampaniya oynalari va zaxira jadvali shu zonada ishlaydi.

## Qayerda
Menyu: **Tizim → Sana va vaqt**. Kim koʻradi: faqat `*` (toʻliq administrator) ruxsati bor foydalanuvchi.

## Asosiy tushunchalar

- **Server vaqti** — yuqoridagi katta soat: serverning hozirgi vaqti **server zonasida** (har soniya yuradi),
  yonida sana, zona, UTC siljishi (masalan `UTC+05:00`) va UTC vaqti. Brauzer soatiga emas, serverga tayanadi.
- **Vaqt manbai** — vaqtni oxirgi marta bergan NTP server (masalan `0.asia.pool.ntp.org`) va sinxronlash
  xizmati nomi (`timesyncd`). «javob yoʻq» — server hali hech bir NTP serverdan javob olmagan.
- **Sinxronlangan/sinxronlanmagan** — serverning vaqti hozir NTP manbasi bilan mos kelayotgani.
- **Vaqt zonasi** — roʻyxatdan tanlanadi: shahar nomi yoki siljish (`+05:00`) boʻyicha qidiriladi, har zona
  yonida UTC siljishi, Oʻzbekiston va qoʻshni zonalar roʻyxat boshida.
- **NTP** — yoqilgan boʻlsa, server vaqti internetdagi NTP serverlardan avtomatik toʻgʻrilanadi.
- **NTP serverlar** — IP yoki host nomlari, vergul yoki qator bilan, koʻpi bilan 5 ta. **Boʻsh qoldirilsa**
  tanlangan zona mintaqasidagi `pool.ntp.org` serverlari ishlatiladi (Osiyo — `0–3.asia.pool.ntp.org`,
  Yevropa — `europe`, va h.k.); oʻz serverlaringiz koʻrsatilsa ham ular zaxira sifatida qoladi.
- **Hozir sinxronlash** — NTP xizmatini qayta ishga tushiradi va javob kelishini ~10 soniya kutadi.
- **Oʻzgarish darhol qoʻllanadi** — bu sahifada **Tarmoq**/**Firewall**dagi kabi tasdiqlash/avtomatik
  qaytarish oqimi **yoʻq** — **Saqlash**ni bosgandan keyin oʻzgarish darhol kuchga kiradi.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Vaqt zonasi | Server va PBX vaqt zonasi | `Asia/Tashkent` (UTC+05:00) |
| NTP yoqilgan | Internetdan avtomatik vaqt sinxronlashni yoqadi/oʻchiradi | Yoqilgan |
| NTP serverlar | Sinxronlash manbalari roʻyxati | Boʻsh — zonaning mintaqaviy pool serverlari |

## Qanday qilinadi

### Vaqt zonasini oʻzgartirish
1. **Vaqt zonasi** maydonini bosing — qidiruvli roʻyxat ochiladi.
2. Shahar nomini (masalan «Tashkent») yoki siljishni (`+05`) yozing va kerakli zonani tanlang
   (maydon ostida shu zonadagi hozirgi vaqt koʻrinadi).
3. **Saqlash**ni bosing. Zona oʻzgargan boʻlsa PBX ham yangi zonaga oʻtadi — «PBX vaqt zonasi yangilandi»
   xabari chiqadi.

### Vaqtni internet bilan sinxronlash
1. **NTP yoqilgan** yoqiq ekanini tekshiring (oʻchiq boʻlsa yoqib, **Saqlash**).
2. **NTP serverlar**ni boʻsh qoldiring (mintaqaviy pool) yoki oʻz serverlaringizni yozing.
3. **Hozir sinxronlash**ni bosing — «Vaqt internet bilan sinxronlandi» va manba server nomi chiqadi.

### NTP’ni yoqish/oʻchirish va serverlarni sozlash
1. **NTP yoqilgan** tugmachasini kerakli holatga oʻtkazing.
2. Yoqilgan boʻlsa, **NTP serverlar** maydoniga kerakli manbalarni (IP yoki host nomi) vergul yoki har
   birini alohida qatorga yozing.
3. **Saqlash**ni bosing.

## Maslahatlar va cheklovlar

> [!TIP]
> Vaqt zonasini toʻgʻri tanlash — kun/tun rejimi, hisobotlar va qoʻngʻiroq jurnali vaqtlarining toʻgʻri
> koʻrsatilishi uchun muhim; serverni oʻrnatishdan keyin birinchi navbatda shuni tekshiring.

> [!WARNING]
> Oʻzgarish bu sahifada **darhol** qoʻllanadi — Tarmoq/Firewall sahifalaridagi kabi avtomatik qaytarish
> yoʻq, shuning uchun vaqt zonasi va NTP serverlarini ehtiyotkorlik bilan kiriting.

- NTP oʻchirilgan boʻlsa, serverlar maydoni tahrirlanmaydi va **Hozir sinxronlash** tugmasi yopiq.
- Vaqt shartlari (ish vaqti) PBX zonasida tekshiriladi — Asterisk konteyneri UTCda ishlasa ham.
- Sahifa «faqat koʻrish» holatida boʻlsa (`readonly_reason`), sabab banner sifatida koʻrsatiladi va
  hech narsa oʻzgartirib boʻlmaydi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| «Vaqt zonasi IANA roʻyxatida topilmadi» | Notoʻgʻri/mavjud boʻlmagan nom kiritilgan | Roʻyxatdan aniq nomni tanlang |
| «Yaroqsiz NTP server» | IP/host nomi formatida xato | Toʻgʻri IP yoki host nomini kiriting |
| «Koʻpi bilan N ta NTP server boʻlishi mumkin» | Ruxsat etilgan sondan koʻp server kiritilgan | Ortiqcha serverlarni olib tashlang |
| Sahifa «faqat koʻrish» | `readonly_reason` bilan bloklangan | Koʻrsatilgan sababni bartaraf qiling |
| «Sinxronlanmagan» doim koʻrinadi | NTP serverlarga ulanish yoʻq yoki xizmat ishlamayapti | Server internet/tarmoq ulanishini va NTP serverlar roʻyxatini tekshiring |
| «NTP serverdan javob kelmadi» (Hozir sinxronlash) | Internet yoʻq yoki chiquvchi UDP 123 port yopiq | Firewall/routerda UDP 123 ni oching yoki ichki NTP serverni yozing |
| «NTP oʻchirilgan» | NTP yoqilmagan holda sinxronlash bosilgan | **NTP yoqilgan**ni yoqib saqlang |

## Bog'liq bo'limlar

- [Tarmoq](/docs/network)
- [Tizim holati](/docs/status)
