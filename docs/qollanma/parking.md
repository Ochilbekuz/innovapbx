---
id: parking
title: Parkovka va chaqiruv
group: apps
order: 40
path: /parking
summary: Qoʻngʻiroqni "parklash" (vaqtincha kutishga qoʻyish) va boshqa telefondan qabul qilish uchun joylar.
---

# Parkovka va chaqiruv

**Parkovka** — qoʻngʻiroqni vaqtincha "joy"ga qoʻyib, boshqa xonadan yoki boshqa telefondan davom ettirish
imkonini beradi. Masalan: operator qoʻngʻiroqni parklab (`*70` yoki parkovka kodiga oʻtkazib), kerakli
xodimga "701-joyni koʻtar" deb aytadi — xodim oʻz telefonidan `701`ni terib qoʻngʻiroqni davom ettiradi.

## Qayerda

Menyu: **Ilovalar → Parkovka va chaqiruv**. Kim koʻradi: `apps` ruxsatiga ega foydalanuvchilar
tahrirlaydi, qolganlar faqat koʻradi. Sozlama — tenant uchun **yagona** (yangi "parkovka" yaratib
boʻlmaydi, faqat mavjud sozlamalar tahrirlanadi).

## Asosiy tushunchalar

- **Parkovka kodi** — qoʻngʻiroqni shu kodga oʻtkazib (transfer) parklash mumkin.
- **Boshlanish raqami va joylar soni** — parklangan qoʻngʻiroqlar olinadigan raqamlar oraligʻi (masalan
  701 dan boshlab 20 ta joy — `701`–`720`).
- **Vaqt tugaganda** — hech kim koʻtarmasa, qoʻngʻiroq **parklaganga qaytadi** yoki **boshqa manzilga**
  (masalan navbatga) yuboriladi.
- **Kutish ohangi** — parkda turgan paytda chaqiruvchiga eshittiriladigan musiqa.
- Telefon tugmalari bilan: guruh ichida boshqa jiringlayotgan telefonni koʻtarish — `*8` (pickup guruh),
  aniq bir telefonni koʻtarish — `**` (toʻgʻridan-toʻgʻri pickup), qoʻngʻiroqni parklash — `*70`
  (standart [xususiyat kodlari](/docs/featurecodes), oʻzgartirilishi mumkin).

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Parkovka kodi | Qoʻngʻiroqni parklash uchun oʻtkaziladigan kod | Sukut `700`, 1–10 ta `0-9*#` belgi |
| Boshlanish raqami | Birinchi parkovka joyi raqami | Sukut `701` |
| Joylar soni | Nechta parkovka joyi boʻladi | 1–100, sukut `20` |
| Kutish vaqti (soniya) | Hech kim koʻtarmasa qancha kutiladi | 10–3600, sukut `60` |
| Vaqt tugaganda | "Parklaganga qaytarish" yoki "Boshqa manzilga yuborish" | Sukut — parklaganga qaytarish |
| Vaqt tugaganda manzil | "Boshqa manzilga" tanlansa — qayerga | Ixtiyoriy |
| Kutish ohangi klassi | Parkda eshitiladigan musiqa | Boʻsh — standart ohang |

## Qanday qilinadi

### Parkovka sozlamalarini oʻzgartirish
1. **Sozlamalar** bloqida kerakli maydonlarni oʻzgartiring (kod, boshlanish raqami, joylar soni, vaqt).
2. **Vaqt tugaganda** — "Boshqa manzilga yuborish" tanlasangiz, manzilni belgilang.
3. **Saqlash**ni bosing.

### Qoʻngʻiroqni parklash (foydalanuvchi uchun)
1. Suhbat davomida qoʻngʻiroqni parkovka kodiga (sukut `700`) oʻtkazing (transfer).
2. Tizim boʻsh joy raqamini aytadi (masalan `701`).
3. Boshqa xodimga shu raqamni aytib bering.

### Parklangan qoʻngʻiroqni olish
1. Istalgan telefondan parkovka joy raqamini (`701` kabi) tering — qoʻngʻiroq davom etadi.

### Jiringlayotgan telefonni boshqa joydan koʻtarish (pickup)
1. Guruh ichidagi jiringlayotgan telefonni koʻtarish uchun `*8` (pickup guruh) kodini tering.
2. Aniq bitta telefonni koʻtarish uchun `**` (toʻgʻridan-toʻgʻri pickup) kodidan foydalaning.

### Jonli parklangan qoʻngʻiroqlarni kuzatish
1. **Parklangan qoʻngʻiroqlar** jadvali har 5 soniyada avtomatik yangilanadi — joy, chaqiruvchi, kim
   parklagani, oʻtgan vaqt va vaqt tugashigacha qolgan muddat koʻrinadi.

> [!TIP]
> "Joylar soni"ni jamoa hajmiga mos tanlang — koʻp xodim bir vaqtda parklasa, joylar yetmasligi mumkin.

> [!WARNING]
> "Vaqt tugaganda" → "Parklaganga qaytarish" boʻlsa, parklagan odam oʻz telefonini yopib qoʻyganda qoʻngʻiroq qayerga ketishini alohida tekshirib qoʻying — aks holda qoʻngʻiroq "osilib" qolishi mumkin.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Parklash ishlamayapti | Parkovka kodi notoʻgʻri terilgan yoki boshqa kod bilan toʻqnashgan | Sozlamalardagi aniq kodni tekshiring |
| Boʻsh joy topilmayapti | Barcha joylar band | Joylar sonini oshiring yoki parklangan qoʻngʻiroqlarni tezroq olib ketishni taʼminlang |
| Vaqt tugaganda qoʻngʻiroq kutilmagan joyga ketdi | "Vaqt tugaganda" manzili notoʻgʻri belgilangan | Sozlamalarni tekshirib toʻgʻrilang |

## Bog'liq bo'limlar

- [Xususiyat kodlari](/docs/featurecodes)
- [Audio kutubxona](/docs/audio)
