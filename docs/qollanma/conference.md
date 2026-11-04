---
id: conference
title: Konferensiya xonalari
group: apps
order: 30
path: /conference
summary: Bir nechta kishi bir vaqtda qoʻshilib gaplashadigan xona — raqam, PIN, moderator PIN, aʼzolar chegarasi.
---

# Konferensiya xonalari

**Konferensiya** — bir nechta ichki/tashqi qoʻngʻiroq bir vaqtda qoʻshilib gaplashadigan "xona". Masalan
haftalik yigʻilish uchun xodimlar bir raqamni terib, PIN kiritib xonaga qoʻshiladi.

## Qayerda

Menyu: **Ilovalar → Konferensiya xonalari**. Kim koʻradi: `apps` ruxsatiga ega foydalanuvchilar
tahrirlaydi, qolganlar faqat koʻradi.

## Asosiy tushunchalar

- **Raqam** — xonaga qoʻshilish uchun teriladigan raqam; boʻsh qoldirilsa avtomatik beriladi.
- **PIN** — oddiy qatnashuvchilar uchun parol (ixtiyoriy).
- **Admin PIN** — moderator uchun alohida parol; moderator sifatida kirgan odam boshqa qatnashuvchilarni
  boshqarish huquqiga ega boʻladi.
- **Aʼzolar chegarasi** — xonada bir vaqtda necha kishi boʻlishi mumkin.
- **Hozir** ustuni — xonada hozir necha kishi borligini jonli koʻrsatadi.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nom | Xona nomi | Koʻpi bilan 128 belgi |
| Raqam | Xonaga qoʻshilish kodi | Boʻsh — avtomatik beriladi; 2–10 ta `0-9*#` belgi |
| PIN | Qatnashuvchilar uchun parol | Ixtiyoriy, 4–8 raqam |
| Admin PIN | Moderator uchun parol | Ixtiyoriy, 4–8 raqam |
| Suhbatni yozib olish | Konferensiya suhbatini yozish | — |
| Aʼzolar chegarasi | Maksimal qatnashuvchi soni | Ixtiyoriy, 2–100, boʻsh — chegarasiz |

## Qanday qilinadi

### Yangi konferensiya yaratish
1. **Konferensiya qoʻshish**ni bosing, nom kiriting.
2. Raqamni qoʻlda kiriting yoki boʻsh qoldirib avtomatik berilishiga ruxsat bering.
3. Kerak boʻlsa PIN va Admin PIN, aʼzolar chegarasini belgilang, suhbatni yozishni yoqing/oʻchiring.
4. **Qoʻshish**ni bosing.

### Konferensiyani kiruvchi marshrut/IVR'ga ulash
1. [Kiruvchi marshrutlar](/docs/inbound) ekranida DID manzilini shu konferensiyaga yoʻnaltiring, yoki IVR tugmasida manzil sifatida tanlang.
2. Ichki xodimlar toʻgʻridan-toʻgʻri xona raqamini terib ham qoʻshilishi mumkin.

### Moderator huquqini belgilash
1. Konferensiyaga **Admin PIN** qoʻying va shu PINni moderatorga bering — u PIN bilan kirganda alohida boshqaruv huquqiga ega boʻladi.

### Oʻchirish
1. Qator oxiridagi savat belgisini bosing.
2. Konferensiya boshqa joyda (marshrut, IVR) ishlatilayotgan boʻlsa, oʻchirish bloklanadi — avval shu bogʻlanishlarni olib tashlang.

> [!TIP]
> Oddiy qatnashuvchilar va moderator uchun turli PIN qoʻying — shunda moderator doim alohida tanilib, boshqaruv imkoniga ega boʻladi.

> [!WARNING]
> "Aʼzolar chegarasi" to'lgandan keyin qoʻshilmoqchi boʻlgan qoʻngʻiroqlar rad etiladi — muhim yigʻilishlar uchun yetarli chegara qoʻying yoki boʻsh (chegarasiz) qoldiring.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Raqam band deb xato beradi | Bu raqam boshqa manzilda allaqachon ishlatilgan | Boshqa raqam tanlang yoki boʻsh qoldirib avtomatikka ruxsat bering |
| Qatnashuvchi xonaga kira olmayapti | Aʼzolar chegarasiga yetilgan | Chegarani oshiring yoki boʻsh (chegarasiz) qiling |
| PIN notoʻgʻri deb rad etadi | PIN 4-8 raqamdan iborat emas | Toʻgʻri formatda PIN kiriting |
| Konferensiyani oʻchirib boʻlmayapti | Marshrut/IVR'da ishlatilmoqda | Avval oʻsha bogʻlanishlarni olib tashlang |

## Bog'liq bo'limlar

- [Kiruvchi marshrutlar](/docs/inbound)
- [IVR](/docs/ivr)
