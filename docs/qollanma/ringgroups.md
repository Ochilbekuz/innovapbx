---
id: ringgroups
title: Qoʻngʻiroq guruhlari
group: routing
order: 40
path: /ringgroups
summary: Bir nechta ichki raqam/tashqi raqamga bir vaqtda yoki tartib bilan jiringlatish (masalan "Buxgalteriya").
---

# Qoʻngʻiroq guruhlari

**Qoʻngʻiroq guruhi** — bir qoʻngʻiroqni bir nechta raqamga yoʻnaltiradi: masalan "Buxgalteriya" guruhiga
qoʻngʻiroq kelganda, boʻlimdagi barcha xodimlarning telefoni bir vaqtda jiringlaydi. Navbatdan farqi — bu yerda
kutish/navbat mantig‘i yoʻq, faqat "qaysi birisi birinchi koʻtaradi" tamoyili ishlaydi.

## Qayerda

Menyu: **Marshrutlash → Qoʻngʻiroq guruhlari**. Kim koʻradi: `routing` ruxsatiga ega foydalanuvchilar
tahrirlaydi, qolganlar faqat koʻradi.

## Asosiy tushunchalar

- **Strategiya** — qoʻngʻiroq aʼzolarga qanday yetib boradi (jadvalga qarang).
- **Aʼzo** — ichki raqam **yoki** tashqi raqam (mobil telefon kabi) boʻlishi mumkin, ikkisini bitta aʼzoda
  birga berib boʻlmaydi.
- **Koʻrsatiladigan raqam old qoʻshimchasi** — operator telefonida kiruvchi raqam oldiga qoʻshiladigan matn
  (masalan "SOTUV: "), shu orqali operator qaysi guruhdan qoʻngʻiroq kelayotganini biladi.
- **Javob boʻlmasa** manzili — hech kim koʻtarmasa (yoki belgilangan davomiylik tugasa) qoʻngʻiroq qayerga
  boradi.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nom | Guruh nomi | — |
| Raqam | Ixtiyoriy — toʻgʻridan-toʻgʻri terish uchun | 2–10 ta `0-9*#` belgi |
| Strategiya | Aʼzolarga jiringlash tartibi | Sukut — **Hammasi birdan** |
| Qoʻngʻiroq davomiyligi (soniya) | Javob kutish vaqti | 5–300, sukut 20 |
| Aʼzolar | Ichki raqamlar va/yoki tashqi raqamlar roʻyxati, tartib bilan | — |
| Koʻrsatiladigan raqam old qoʻshimchasi | Operator ekranida kiruvchi raqam oldiga qoʻshiladi | Ixtiyoriy, masalan `SOTUV: ` |
| Hech kim javob bermasa | Vaqt tugaganda boradigan manzil | Majburiy |

### Strategiyalar

| Strategiya | Qanday ishlaydi |
|---|---|
| Hammasi birdan (`ringall`) | Barcha aʼzolarga bir vaqtda jiringlaydi (sukut) |
| Navbat bilan (`hunt`) | Roʻyxat tartibida birin-ketin, har birida qoʻngʻiroq davomiyligi davomida |
| Yigʻilib boruvchi (`memoryhunt`) | Birinchi aʼzoga jiringlaydi, keyin 1+2ga, keyin 1+2+3ga... — oldingilar jiringlashda qoladi |

## Qanday qilinadi

### Yangi guruh yaratish
1. **Guruh qoʻshish**ni bosing, nom va strategiyani tanlang.
2. **+ Ichki raqam qoʻshish** orqali aʼzolarni qoʻshing; tashqi raqam qoʻshish uchun maxsus maydonga raqamni kiritib qoʻshing (`+998901234567` formatida, 3–15 belgi).
3. **Hech kim javob bermasa** manzilini tanlang (masalan ovozli pochta).
4. **Qoʻshish**ni bosing.

### Tashqi raqam qoʻshish
1. Aʼzolar roʻyxati pastidagi "tashqi" maydoniga raqamni kiriting va qoʻshing.
2. Notoʻgʻri formatdagi yoki allaqachon qoʻshilgan raqam xato koʻrsatadi.

### Aʼzo tartibini oʻzgartirish
1. `Navbat bilan` yoki `Yigʻilib boruvchi` strategiyasida tartib muhim — qatorni sudrab kerakli oʻringa qoʻying.

### Qoʻngʻiroq guruhini kiruvchi marshrutga ulash
1. [Kiruvchi marshrutlar](/docs/inbound) ekranida DID manzilini shu guruhga yoʻnaltiring.
2. Yoki IVR tugmasida/ish vaqti shartida manzil sifatida tanlang.

### Oʻchirish
1. Qator oxiridagi savat belgisini bosing.
2. Guruh boshqa joyda ishlatilayotgan boʻlsa, oʻchirish bloklanadi — avval shu bogʻlanishlarni olib tashlang.

> [!TIP]
> "Koʻrsatiladigan raqam old qoʻshimchasi"ni har bir guruhga alohida nom bilan belgilang — bir nechta guruhga kiradigan operator qaysi yoʻnalishdan qoʻngʻiroq kelayotganini ekranidan koʻra oladi.

> [!WARNING]
> Tashqi raqamga jiringlash davomiyligi umumiy operator tarifiga qoʻshimcha xarajat bo'lishi mumkin — "Qoʻngʻiroq davomiyligi"ni haddan tashqari uzun qilib qoʻymang.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Tashqi raqam qoʻshilmayapti | Format notoʻgʻri yoki allaqachon qoʻshilgan | Faqat raqamlar, 3–15 belgi, `+` ixtiyoriy bilan kiriting |
| `Yigʻilib boruvchi`da hamma birdan jiringlayapti | Qoʻngʻiroq davomiyligi juda qisqa, keyingi aʼzo tez qoʻshilib ketadi | Davomiylikni oshiring |
| Guruhni oʻchirib boʻlmayapti | Kiruvchi marshrut yoki boshqa manzilda ishlatilmoqda | Avval oʻsha bogʻlanishlarni olib tashlang |

## Bog'liq bo'limlar

- [Kiruvchi marshrutlar](/docs/inbound)
- [Ichki raqamlar](/docs/extensions)
- [Ish vaqti](/docs/timegroups)
