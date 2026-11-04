---
id: announcements
title: Eʼlonlar
group: routing
order: 60
path: /announcements
summary: Qoʻngʻiroq qiluvchiga xabar eshittirib, keyin boshqa manzilga yoʻnaltirish (masalan "Suhbat yoziladi").
---

# Eʼlonlar

**Eʼlon** — qoʻngʻiroq qiluvchiga bir audio xabarni eshittiradi, soʻngra belgilangan keyingi manzilga
oʻtkazadi. Masalan: "Diqqat, suhbat sifat nazorati uchun yozib olinadi" degan xabardan keyin qoʻngʻiroqni
navbatga ulash.

## Qayerda

Menyu: **Marshrutlash → Eʼlonlar**. Kim koʻradi: `routing` ruxsatiga ega foydalanuvchilar tahrirlaydi,
qolganlar faqat koʻradi.

## Asosiy tushunchalar

- **Audio fayl** — xabar matni ovoz sifatida oldindan [Audio kutubxona](/docs/audio)ga yuklangan boʻlishi kerak.
- **Keyingi manzil** — xabar tugagach (yoki oʻtkazib yuborilgach) qoʻngʻiroq qayerga boradi.
- **Oʻtkazib yuborishga ruxsat** — yoqilsa, chaqiruvchi `#` tugmasini bosib xabarni oxirigacha tinglamay
  oʻtkazib yuborishi mumkin.
- **Takrorlash tugmasi** — belgilangan tugma bosilsa, xabar boshidan qayta eshittiriladi.
- **Qoʻngʻiroqni javob berib boshlash** — yoqilsa, xabar boshlanishidan oldin qoʻngʻiroq "javob berilgan"
  hisoblanadi (billing/CDR uchun muhim — aks holda xabar paytida qoʻngʻiroq hali "javobsiz" holatda sanaladi).

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nom | Eʼlon nomi | Koʻpi bilan 128 belgi |
| Audio fayl | Chaqiruvchiga eshittiriladigan xabar | Majburiy |
| Keyingi manzil | Xabardan keyin boradigan joy | Majburiy — ichki raqam, navbat, IVR, qoʻngʻiroq guruhi, ish vaqti sharti, konferensiya, boshqa eʼlon va h.k. |
| Oʻtkazib yuborishga ruxsat | `#` bilan xabarni oʻtkazib yuborish | Sukut oʻchirilgan |
| Takrorlash tugmasi | Bosilsa xabar qaytadan boshlanadi | Bir ta `0-9*#` belgi, ixtiyoriy — tanlanmasa takrorlanmaydi |
| Qoʻngʻiroqni javob berib boshlash | Xabardan oldin qoʻngʻiroqni javob berilgan deb belgilash | Sukut yoqilgan |

## Qanday qilinadi

### Yangi eʼlon qoʻshish
1. Avval [Audio kutubxona](/docs/audio)ga xabar audiosini yuklang (yuklanmagan boʻlsa, sahifada eslatma chiqadi).
2. **Eʼlon qoʻshish**ni bosing, nom va audio faylni tanlang.
3. **Keyingi manzil**ni belgilang (majburiy).
4. Kerak boʻlsa oʻtkazib yuborish, takrorlash tugmasi va "javob berib boshlash"ni sozlang.
5. **Qoʻshish**ni bosing.

### Eʼlonni kiruvchi marshrutga yoki IVR'ga ulash
1. [Kiruvchi marshrutlar](/docs/inbound) ekranida DID manzilini shu eʼlonga yoʻnaltiring.
2. Yoki IVR tugmasida/ish vaqti shartida manzil sifatida tanlang.

### Oʻchirish
1. Qator oxiridagi savat belgisini bosing.
2. Eʼlon boshqa joyda ishlatilayotgan boʻlsa, oʻchirish bloklanadi va shu bogʻlanishlar koʻrsatiladi — avval ulardan olib tashlang.
3. Oʻchirilgan eʼlonga yoʻnaltirilgan qoʻngʻiroqlar endi javobsiz ohang eshittiradi — oʻchirishdan oldin bogʻlanishlarni tozalang.

> [!TIP]
> "Qoʻngʻiroqni javob berib boshlash"ni yoqib qoʻying — aks holda operator tarmoq operatori xabar davomida qoʻngʻiroqni "javobsiz" deb hisoblashi mumkin (ayniqsa billing uchun muhim).

> [!WARNING]
> Eʼlonning "Keyingi manzili" sifatida yana shu eʼlonni tanlamang — xabar cheksiz takrorlanib qolishi mumkin.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Eʼlon qoʻshish bloklangan | Hali hech qanday audio yuklanmagan | [Audio kutubxona](/docs/audio)ga fayl yuklang |
| `#` bosilganda xabar oʻtkazib yuborilmayapti | "Oʻtkazib yuborishga ruxsat" oʻchirilgan | Eʼlonni tahrirlab yoqing |
| Eʼlonni oʻchirib boʻlmayapti | Kiruvchi marshrut, IVR yoki boshqa manzilda ishlatilmoqda | Avval oʻsha bogʻlanishlarni olib tashlang |

## Bog'liq bo'limlar

- [Audio kutubxona](/docs/audio)
- [Kiruvchi marshrutlar](/docs/inbound)
- [IVR](/docs/ivr)
