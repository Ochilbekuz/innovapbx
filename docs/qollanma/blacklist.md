---
id: blacklist
title: Qora roʻyxat
group: apps
order: 50
path: /blacklist
summary: Kiruvchi qoʻngʻiroqlarni raqam boʻyicha bloklash, jumladan yashirin (anonim) raqamlarni toʻliq rad etish.
---

# Qora roʻyxat

**Qora roʻyxat** — kiruvchi qoʻngʻiroqni chaqiruvchi raqamiga qarab avtomatik rad etish roʻyxati. Masalan:
doimiy bezovta qiladigan reklama raqamini roʻyxatga qoʻyib qoʻysangiz, u tizimga umuman kira olmaydi.

## Qayerda

Menyu: **Ilovalar → Qora roʻyxat**. Kim koʻradi: `apps` ruxsatiga ega foydalanuvchilar tahrirlaydi,
qolganlar faqat koʻradi.

## Asosiy tushunchalar

- **Raqam** — bloklanadigan chaqiruvchi raqami; saqlashdan oldin tizim uni kanonik shaklga keltiradi
  (faqat `0-9`, 3–15 ta raqam).
- **Sabab** — ixtiyoriy izoh, nega raqam bloklangani (masalan "spam").
- **Yashirin/anonim raqamlarni bloklash** — alohida kalit; yoqilsa, callerʼID koʻrsatilmagan (yashirin,
  "anonymous", "restricted" kabi) barcha qoʻngʻiroqlar rad etiladi. Texnik jihatdan bu ham roʻyxatning oddiy
  bir yozuvi — faqat raqam oʻrnida maxsus `anonymous` qiymati saqlanadi va jadvalda alohida koʻrsatiladi.
- Bloklash **realtime** ishlaydi — Asterisk kiruvchi qoʻngʻiroqni marshrutlashdan oldin roʻyxatni toʻgʻridan-toʻgʻri tekshiradi, alohida "qoʻllash" tugmasi kerak emas.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Raqam | Bloklanadigan chaqiruvchi raqami | `+998901234567`; saqlashda 3–15 raqamga normallashtiriladi |
| Sabab | Nega bloklangani haqida izoh | Ixtiyoriy, masalan `spam` |
| Yashirin/anonim raqamlarni bloklash | Callerʼid koʻrsatilmagan qoʻngʻiroqlarni rad etish | Sukut — oʻchirilgan |

## Qanday qilinadi

### Raqamni qora roʻyxatga qoʻshish
1. **Qoʻshish**ni bosing.
2. **Raqam** maydoniga chaqiruvchi raqamini kiriting (masalan `+998901234567`).
3. Kerak boʻlsa **Sabab** yozing.
4. **Qoʻshish**ni tasdiqlang — raqam shu zahoti bloklanadi.

### Yashirin/anonim raqamlarni bloklash
1. Jadval ustidagi **Yashirin/anonim raqamlarni bloklash** kalitini yoqing.
2. Callerʼid yubormaydigan (yashirin, anonim) barcha qoʻngʻiroqlar endi avtomatik rad etiladi.
3. Kalitni oʻchirsangiz — bunday qoʻngʻiroqlar yana odatdagicha oʻtadi.

### Raqamni roʻyxatdan olib tashlash
1. Qator oxiridagi savat belgisini bosing, tasdiqlang.
2. Raqam shu zahoti bloklanishdan chiqadi va qayta qoʻngʻiroq qila oladi.

> [!TIP]
> Qidiruv maydoni orqali roʻyxatdan raqam yoki sababga koʻra tezda topish mumkin.

> [!WARNING]
> Raqam allaqachon roʻyxatda boʻlsa, qayta qoʻshish xato beradi ("Bu raqam qora roʻyxatda allaqachon bor") — avval mavjud yozuvni tekshiring.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| "Raqam formati notoʻgʻri" xatosi | Kiritilgan qiymat normallashtirilganda 3–15 raqamga toʻgʻri kelmadi | Raqamni harf/belgisiz, toʻgʻri formatda kiriting |
| "Bu raqam qora roʻyxatda allaqachon bor" | Raqam avval qoʻshilgan | Mavjud yozuvni tahrirlash kerak boʻlsa, avval oʻchirib qayta qoʻshing |
| Kerakli raqam baribir oʻtib ketayapti | Raqam turli formatda (masalan koʻp operator prefiksi bilan) kelayapti | Qoʻshishda raqamni toʻliq, xalqaro formatda kiriting |
| Yashirin raqamlar hali ham oʻtayapti | Toggle oʻchirilgan yoki operator callerʼidni boshqacha uzatadi | Toggleni yoqilganini tekshiring; operator bilan bogʻlanib callerʼid uzatilishini soʻrang |

## Bog'liq bo'limlar

- [Kiruvchi marshrutlar](/docs/inbound)
- [CDR (qoʻngʻiroqlar tarixi)](/docs/cdr)
