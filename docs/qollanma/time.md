---
id: time
title: Sana va vaqt
group: system
order: 130
path: /settings/time
summary: Server vaqt zonasi va NTP (vaqt sinxronlash) serverlarini sozlash.
---

# Sana va vaqt

Serverning vaqt zonasini tanlash va vaqtni avtomatik toʻgʻrilab turadigan **NTP** xizmatini sozlash shu
yerda amalga oshiriladi. Toʻgʻri vaqt zonasi va sinxronlangan vaqt — chaqiruv jurnali, hisobotlar va
jadval asosidagi yoʻnaltirishlar (kun/tun rejimi) toʻgʻri ishlashi uchun muhim.

## Qayerda
Menyu: **Tizim → Sana va vaqt**. Kim koʻradi: faqat `*` (toʻliq administrator) ruxsati bor foydalanuvchi.

## Asosiy tushunchalar

- **Hozirgi vaqt (UTC)** — serverning hozirgi vaqti, har doim **UTC**da koʻrsatiladi (brauzer/tenant
  vaqt zonasiga aylantirilmaydi) — chalkashlik boʻlmasligi uchun.
- **Sinxronlash xizmati** — vaqtni toʻgʻrilab turuvchi tizim xizmatining nomi.
- **Sinxronlangan/sinxronlanmagan** — serverning vaqti hozir NTP manbasi bilan mos kelayotgani.
- **Vaqt zonasi** — IANA roʻyxatidan (masalan `Asia/Tashkent`) qidirib tanlanadi; roʻyxatda yoʻq nom
  kiritilsa xato chiqadi.
- **NTP** — yoqilgan boʻlsa, server vaqti belgilangan serverlar asosida avtomatik toʻgʻrilanadi.
- **NTP serverlar** — IP yoki host nomlari, vergul yoki qator bilan ajratilgan, koʻpi bilan bir nechta
  (chegara sahifada koʻrsatiladi) ta.
- **Oʻzgarish darhol qoʻllanadi** — bu sahifada **Tarmoq**/**Firewall**dagi kabi tasdiqlash/avtomatik
  qaytarish oqimi **yoʻq** — **Saqlash**ni bosgandan keyin oʻzgarish darhol kuchga kiradi.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Vaqt zonasi | IANA vaqt zonasi nomi | `Asia/Tashkent` |
| NTP yoqilgan | Avtomatik vaqt sinxronlashni yoqadi/oʻchiradi | — |
| NTP serverlar | Sinxronlash manbalari roʻyxati | NTP oʻchiq boʻlsa tahrirlanmaydi |

## Qanday qilinadi

### Vaqt zonasini oʻzgartirish
1. **Vaqt zonasi** maydoniga shahar/mintaqa nomini yozib qidiring (masalan «Tashkent»).
2. Roʻyxatdan kerakli vaqt zonasini tanlang.
3. **Saqlash**ni bosing.

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

- NTP oʻchirilgan boʻlsa, serverlar maydoni tahrirlanmaydi.
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

## Bog'liq bo'limlar

- [Tarmoq](/docs/network)
- [Tizim holati](/docs/status)
