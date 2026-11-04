---
id: ivr
title: IVR
group: routing
order: 20
path: /ivr
summary: Ovozli menyu — qoʻngʻiroq qiluvchi tugma bosib boʻlim tanlaydi ("Sotuv uchun 1, buxgalteriya uchun 2").
---

# IVR

**IVR** (ovozli menyu) — qoʻngʻiroq qiluvchiga audio orqali boʻlim tanlashni taklif qiladi: "Sotuv boʻlimi
uchun 1ni, buxgalteriya uchun 2ni bosing". Har bir tugma oʻz manzilga (ichki raqam, navbat, boshqa IVR va h.k.)
olib boradi.

## Qayerda

Menyu: **Marshrutlash → IVR**. Kim koʻradi: `routing` ruxsatiga ega foydalanuvchilar tahrirlaydi, qolganlar
faqat koʻradi.

## Asosiy tushunchalar

- **Salomlashuv audiosi** — IVR ochilganda eshittiriladigan xabar (avval [Audio kutubxona](/docs/audio)da yuklanган boʻlishi kerak).
- **Tugma xaritasi** — har bir tugma (`0-9`, `*`, `#`) uchun alohida manzil. Boʻsh tugma — belgilanmagan.
- **Toʻgʻridan-toʻgʻri terish** — yoqilsa, qoʻngʻiroq qiluvchi menyuni tinglab turmay boshqa ichki raqamni
  toʻliq terib oʻtib ketishi mumkin.
- **Vaqt tugashi / notoʻgʻri tugma** — belgilangan vaqt ichida hech narsa bosilmasa yoki boʻlinmagan tugma
  bosilsa, mos audio (ixtiyoriy) eshittiriladi va alohida manzilga oʻtiladi.
- **Halqa (loop) tekshiruvi** — IVR oʻzini yoki boshqa IVR orqali oʻziga qaytib ulansa, tizim xato beradi va
  qaysi yoʻl orqali halqa hosil boʻlganini koʻrsatadi.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nom | IVR menyu nomi | Koʻpi bilan 128 belgi |
| Raqam | Ixtiyoriy — toʻgʻridan-toʻgʻri terish uchun | 2–10 ta `0-9*#` belgi |
| Salomlashuv audiosi | Menyu ochilganda eshittiriladigan xabar | Majburiy |
| Notoʻgʻri tugma bosilganda audio | Ixtiyoriy xabar | Boʻsh — notoʻgʻri tugmada darhol xato manzilga oʻtadi |
| Kutish vaqti (soniya) | Tugma bosilmasa qancha kutish | 1–60, sukut 7 |
| Takrorlash soni | Vaqt tugaganda salomlashuv necha marta qaytariladi | 0–5, sukut 2 |
| Toʻgʻridan-toʻgʻri terish | Boshqa ichki raqamni toʻliq terib oʻtish imkoni | Sukut oʻchirilgan |
| Tugma xaritasi | Har bir tugma uchun manzil | Kamida 1 ta tugma belgilangan boʻlishi shart |
| Vaqt tugaganda | Hech narsa bosilmasa boradigan manzil | Majburiy |
| Notoʻgʻri tugma boʻlganda | Boʻlinmagan tugma bosilsa boradigan manzil | Majburiy |

Manzil sifatida tanlanadi: ichki raqam, qoʻngʻiroq guruhi, navbat, boshqa IVR, ish vaqti sharti, konferensiya,
toʻxtatish/band ohangi, eʼlon, maxsus manzil.

## Qanday qilinadi

### Yangi IVR qoʻshish
1. Avval [Audio kutubxona](/docs/audio)da salomlashuv audiosini yuklang.
2. **IVR qoʻshish**ni bosing, nom va salomlashuv audiosini tanlang.
3. Kerakli tugmalarga manzillarni belgilang (kamida bittasi shart) — har bir katakchani bosib `DestinationPicker` orqali tanlanadi.
4. **Vaqt tugaganda** va **Notoʻgʻri tugma boʻlganda** manzillarini belgilang (ikkisi ham majburiy).
5. **Qoʻshish**ni bosing.

### Tugma manzilini oʻzgartirish yoki tozalash
1. IVRni tahrirlashga oching, kerakli tugma katakchasini bosing, yangi manzilni tanlang.
2. Tugmani boʻshatish uchun katakcha yonidagi X belgisini bosing.

### Toʻgʻridan-toʻgʻri terishni yoqish
1. IVR tahririda **Toʻgʻridan-toʻgʻri terish** tugmachasini yoqing — endi qoʻngʻiroq qiluvchi menyu tugashini kutmay boshqa ichki raqamni toʻliq terib oʻtib ketishi mumkin.

### IVR'ni kiruvchi marshrutga ulash
1. [Kiruvchi marshrutlar](/docs/inbound) ekranida DID manzilini shu IVR'ga yoʻnaltiring.
2. Yoki boshqa IVR'ning biror tugmasida shu IVR'ni manzil qilib tanlang (ichma-ich menyu uchun).

### Oʻchirish
1. Qator oxiridagi savat belgisini bosing.
2. IVR boshqa joyda ishlatilayotgan boʻlsa, oʻchirish bloklanadi — avval shu bogʻlanishlarni olib tashlang.

> [!WARNING]
> Bir IVR ikkinchisining tugmasida (yoki vaqt tugashi/xato manzilida) tanlansa va u orqali oʻziga qaytib ulansa — saqlashda "halqa" xatosi chiqadi va yoʻl koʻrsatiladi. Shu holatda zanjirni qayta koʻrib chiqing.

> [!TIP]
> "Notoʻgʻri tugma bosilganda audio" boʻsh qoldirilsa, notoʻgʻri tugma bosilgach xabar eshittirilmay darhol belgilangan manzilga oʻtadi — bu kutish vaqtini qisqartiradi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| "Qoʻshish" tugmasi bosilmaydi | Hech bir tugma belgilanmagan yoki vaqt/xato manzili tanlanmagan | Kamida bitta tugma va ikkala majburiy manzilni toʻldiring |
| Saqlashda "halqa" xatosi | IVR oʻzini bevosita yoki boshqa IVR orqali oʻziga ulagan | Koʻrsatilgan yoʻlni tekshirib, zanjirni uzing |
| IVR'ni oʻchirib boʻlmayapti | Kiruvchi marshrut yoki boshqa tugmada ishlatilmoqda | Avval oʻsha bogʻlanishlarni olib tashlang |
| Audio tanlov roʻyxati boʻsh | Hali audio yuklanmagan | [Audio kutubxona](/docs/audio)ga fayl yuklang |

## Bog'liq bo'limlar

- [Audio kutubxona](/docs/audio)
- [Kiruvchi marshrutlar](/docs/inbound)
- [Navbatlar](/docs/queues)
- [Ish vaqti](/docs/timegroups)
