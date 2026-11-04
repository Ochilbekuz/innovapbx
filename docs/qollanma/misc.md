---
id: misc
title: Maxsus manzillar
group: routing
order: 50
path: /misc
summary: Ichki raqamlar jadvalidan tashqari terish kodlari — boshqa manzil (masalan faks) va maxsus kod (*501).
---

# Maxsus manzillar

Bu boʻlim ikki narsani boshqaradi: **Boshqa manzillar** — ichki raqamlar roʻyxatiga kirmaydigan alohida terish
kodlari (masalan faks apparatiga toʻgʻridan-toʻgʻri ulanish), va **Maxsus kodlar** — telefon tugmalari bilan
terilganda (`*501` kabi) belgilangan manzilga darhol ulanadigan yorliqlar.

## Qayerda

Menyu: **Marshrutlash → Maxsus manzillar**. Kim koʻradi: `routing` ruxsatiga ega foydalanuvchilar tahrirlaydi,
qolganlar faqat koʻradi.

## Asosiy tushunchalar

- **Boshqa manzil** — oddiy "terish kodi" (dial string) — IVR/ish vaqti shartida va h.k. manzil roʻyxatida
  koʻrinadi, lekin ichki raqamlar jadvalida yoʻq (masalan analog faks porti).
- **Maxsus kod** — foydalanuvchi telefon tugmalarida tersa (masalan `*501`), belgilangan manzilga (ichki
  raqam, navbat, IVR va h.k.) toʻgʻridan-toʻgʻri ulanadi. Istalgan vaqtda yoqilgan/oʻchirilgan holatga olib
  qoʻyish mumkin.

## Maydonlar

### Boshqa manzil

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nom | Manzil nomi | — |
| Terish kodi | Asterisk tomonidan terib ulanadigan kod | Masalan `0022`; faqat `0-9*#+`, 1–32 belgi, ichki raqamlar bilan toʻqnashmasligi kerak |

### Maxsus kod

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nom | Kod nomi | — |
| Kod | Terish kodi | `*` bilan boshlanib 1–6 belgi (`*501`), yoki 1–10 raqamli oddiy kod |
| Manzil | Kod terilganda boradigan joy | Ichki raqam, navbat, IVR, qoʻngʻiroq guruhi, konferensiya, eʼlon, boshqa manzil va h.k. |
| Yoqilgan | Oʻchirilsa — kod ishlamay qoladi, lekin saqlanib qoladi | Sukut yoqilgan |

## Qanday qilinadi

### Boshqa manzil qoʻshish
1. **Manzillar** tabida **Manzil qoʻshish**ni bosing.
2. Nom va terish kodini kiriting (boshqa ichki raqam/kod bilan toʻqnashmasligiga eʼtibor bering).
3. **Qoʻshish**ni bosing.

### Maxsus kod qoʻshish
1. **Maxsus kodlar** tabida **Kod qoʻshish**ni bosing.
2. Nom, kod (`*501` kabi) va manzilni tanlang.
3. **Qoʻshish**ni bosing — kod darhol faol boʻladi.

### Maxsus kodni vaqtincha oʻchirish
1. Kodni tahrirlashga oching, **Yoqilgan** tugmachasini oʻchiring, **Saqlash**.
2. Kod oʻzi oʻchirilmaydi — faqat ishlamaydi, kerak boʻlganda qayta yoqish mumkin.

### Oʻchirish
1. Qator oxiridagi savat belgisini bosing.
2. Boshqa manzil boshqa joyda ishlatilayotgan boʻlsa, oʻchirish bloklanadi — avval shu bogʻlanishlarni olib tashlang.

> [!TIP]
> Maxsus kodlar — tezkor yorliqlar uchun qulay: masalan `*0` orqali to‘g‘ridan-to‘g‘ri qabulxonaga, `*99` orqali navbatchi tex. xizmatga ulash.

> [!WARNING]
> Maxsus kod boshqa [xususiyat kodlari](/docs/featurecodes) (masalan `*97`, `*98` kabi tizim kodlari) bilan toʻqnashmasligi (teng yoki prefiks boʻlmasligi — masalan `*7` va `*72`) kerak. Toʻqnashsa, panel kodni saqlamaydi: boshqa yoqilgan funksiya bilan toʻqnashsa — **"Bu kod boshqa funksiya bilan to'qnashadi"**, ichki raqam/manzil bilan toʻqnashsa — **"Bu kod ichki raqam/manzil bilan to'qnashadi"** xabari chiqadi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Terish kodi saqlanmayapti | Format notoʻgʻri (ruxsat etilmagan belgi) yoki boʻsh | Faqat `0-9*#+`, 1–32 belgi kiriting |
| Maxsus kod terilganda hech narsa boʻlmayapti | **Yoqilgan** oʻchirilgan | Kodni tahrirlab yoqing |
| Boshqa manzilni oʻchirib boʻlmayapti | Boshqa joyda (IVR, ish vaqti sharti va h.k.) ishlatilmoqda | Avval oʻsha bogʻlanishlarni olib tashlang |

## Bog'liq bo'limlar

- [IVR](/docs/ivr)
- [Xususiyat kodlari](/docs/featurecodes)
- [Kiruvchi marshrutlar](/docs/inbound)
