---
id: voicemail
title: Ovozli pochta
group: apps
order: 20
path: /voicemail
summary: Ichki raqam yoki umumiy quti uchun ovozli pochta — PIN, email/Telegram xabar, salomlashuv audiosi.
---

# Ovozli pochta

**Ovozli pochta** — qoʻngʻiroqqa javob berilmaganda chaqiruvchi xabar qoldirishi mumkin boʻlgan quti.
Masalan: "Ofis yopiq boʻlganda qoʻngʻiroq ovozli pochtaga tushsin" — [Ish vaqti](/docs/timegroups) shartining
"yopiq" manzili sifatida shu qutini tanlash kifoya.

## Qayerda

Menyu: **Ilovalar → Ovozli pochta**. Kim koʻradi: `extensions` ruxsatiga ega foydalanuvchilar tahrirlaydi,
qolganlar faqat koʻradi. Egasi oʻz xabarlarini [Mening kabinetim](/docs/portal) sahifasida tinglaydi.

## Asosiy tushunchalar

- **Egasi** — quti ikki xil boʻlishi mumkin: muayyan **ichki raqamga** bogʻlangan, yoki **umumiy quti**
  (hech bir ichki raqamga tegishli emas, faqat marshrutlashda manzil sifatida ishlatiladi).
- **Quti raqami** — ovozli pochta identifikatori (2–10 raqam); ichki raqamga bogʻlanganda avtomatik oʻsha
  raqam boʻladi, umumiy qutida qoʻlda beriladi.
- **PIN** — telefon orqali qutiga kirishda soʻraladigan parol.
- **Xabar berish (email/Telegram)** — yangi xabar kelganda bildirishnoma yuboradi; audio faylni biriktirish
  ham mumkin.
- **Salomlashuv audiosi** — chaqiruvchiga eshittiriladigan xabar; tanlanmasa standart salomlashuv ishlatiladi.
- Telefon orqali oʻz qutisini tinglash — `*97`; boshqa ichki raqam qutisini tinglash — `*98` (standart
  xususiyat kodlari, [Xususiyat kodlari](/docs/featurecodes) sahifasida oʻzgartirilishi mumkin).

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Egasi | Ichki raqam yoki umumiy quti | — |
| Ichki raqam | Egasi "ichki raqam" boʻlsa — qaysi raqam | Hali qutisi boʻlmagan raqamlar roʻyxatidan |
| Quti raqami | Egasi "umumiy" boʻlsa — quti identifikatori | 2–10 ta raqam |
| PIN | Qutiga kirish paroli | Yaratishda majburiy (4–8 raqam), tahrirda boʻsh qoldirilsa oʻzgarmaydi |
| Email | Bildirishnoma manzili | Ixtiyoriy |
| Email orqali xabar berish | Yangi xabarda emailga yuboriladi | Sukut oʻchirilgan |
| Telegram orqali xabar berish | Yangi xabarda Telegramga yuboriladi | Sukut oʻchirilgan |
| Telegram chat ID | Qaysi chatga yuboriladi | Masalan `123456789` yoki `@kanal_nomi` |
| Audio biriktirish | Xabar ovozi email/Telegram xabariga fayl sifatida qoʻshiladi | Sukut oʻchirilgan |
| Salomlashuv audiosi | Chaqiruvchiga eshittiriladigan xabar | Boʻsh — standart salomlashuv |

## Qanday qilinadi

### Ichki raqam uchun quti yaratish
1. **Quti yaratish**ni bosing, **Egasi** — "Ichki raqam"ni tanlang.
2. Hali qutisi yoʻq ichki raqamlardan birini tanlang.
3. PIN kiriting (4–8 raqam), kerak boʻlsa email/Telegram xabarlarini yoqing.
4. **Yaratish**ni bosing.

### Umumiy quti yaratish
1. **Egasi** — "Umumiy quti"ni tanlang, quti raqamini qoʻlda kiriting (masalan `200`).
2. PIN va bildirishnoma sozlamalarini kiritib, **Yaratish**ni bosing.
3. Umumiy qutini [Ish vaqti sharti](/docs/timegroups), [Kiruvchi marshrut](/docs/inbound), IVR va h.k. manzil sifatida tanlash mumkin.

### Email/Telegram xabarlarini yoqish
1. Qutini tahrirlashga oching, email manzilini kiriting va **Email orqali xabar berish**ni yoqing (yoki Telegram chat ID + **Telegram orqali xabar berish**).
2. Kerak boʻlsa **Audio biriktirish**ni yoqing — xabar ovozi fayl sifatida qoʻshiladi.

### Salomlashuv audiosini oʻrnatish
1. Avval [Audio kutubxona](/docs/audio)ga xabar yuklang.
2. Qutini tahrirlashda **Salomlashuv audiosi** maydonidan tanlang.

### Xabarlarni tinglash/oʻchirish (panel orqali)
1. Quti qatorini ochib, **Xabarlar** boʻlimida ro'yxatni koʻring.
2. **Eshitilgan deb belgilash** yoki savat belgisi bilan oʻchirishni bosing.

### Oʻchirish
1. Quti qatorida savat belgisini bosing.
2. Quti boshqa joyda (marshrut, IVR va h.k.) ishlatilayotgan boʻlsa, oʻchirish bloklanadi — avval shu bogʻlanishlarni olib tashlang.

> [!TIP]
> Ichki raqam egasi oʻz xabarlarini telefon orqali (`*97`) yoki [Mening kabinetim](/docs/portal) sahifasidan brauzerda ham tinglay oladi.

> [!WARNING]
> PIN tahrirlashda boʻsh qoldirilsa — eski PIN oʻzgarmaydi. Yangi PIN qoʻyish uchun maydonga toʻliq yangi qiymat kiritish shart.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Ichki raqam roʻyxatida koʻrinmayapti | Shu raqamda allaqachon quti bor | Avval eski qutini oʻchiring yoki boshqa raqam tanlang |
| Email/Telegram xabari kelmayapti | Bildirishnoma kanali oʻchirilgan yoki manzil/chat ID notoʻgʻri | Sozlamalarni tekshiring, [Integratsiyalar](/docs/integrations)da SMTP/Telegram ulanganini tasdiqlang |
| `*97`/`*98` ishlamayapti | Xususiyat kodi oʻchirilgan yoki oʻzgartirilgan | [Xususiyat kodlari](/docs/featurecodes)da joriy kodni tekshiring |
| Qutini oʻchirib boʻlmayapti | Marshrutda yoki IVR'da ishlatilmoqda | Avval oʻsha bogʻlanishlarni olib tashlang |

## Bog'liq bo'limlar

- [Audio kutubxona](/docs/audio)
- [Mening kabinetim](/docs/portal)
- [Xususiyat kodlari](/docs/featurecodes)
- [Ish vaqti](/docs/timegroups)
- [Integratsiyalar](/docs/integrations)
