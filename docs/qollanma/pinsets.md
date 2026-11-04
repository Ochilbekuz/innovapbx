---
id: pinsets
title: PIN toʻplamlari
group: connect
order: 40
path: /pinsets
summary: Chiquvchi qoʻngʻiroqdan oldin kod soʻraydigan PIN toʻplamlarini yaratish va boshqarish.
---

# PIN toʻplamlari

PIN toʻplami — [chiquvchi marshrut](/docs/outbound)ga biriktirilib, qoʻngʻiroq ulanishidan oldin foydalanuvchidan kod soʻraydigan PINlar roʻyxati. Bir toʻplamda bir nechta PIN boʻlishi mumkin — har biriga alohida yorliq (masalan xodim ismi) biriktiriladi, shunga koʻra kim qaysi kod bilan qoʻngʻiroq qilgani kuzatilishi mumkin.

## Qayerda

Menyu: **Ulanish → PIN toʻplamlari**. Kim koʻradi: `connect:view` ruxsati. Qoʻshish/tahrirlash/oʻchirish/PIN boshqarish — `connect:edit` ruxsati; boʻlmasa **"Sizda PIN toʻplamlarini boshqarish ruxsati yoʻq — faqat koʻrish mumkin"** eslatmasi chiqadi.

## Asosiy tushunchalar

- **PIN toʻplami** — nom va sozlamalar (CDRda yozish) bilan belgilangan konteyner; oʻzi hech narsaga taʼsir qilmaydi, [chiquvchi marshrut](/docs/outbound)ning **PIN toʻplami** maydoniga biriktirilgandan keyin ishlay boshlaydi.
- **CDRda yozilsin** — yoqilsa, qaysi PIN (yorligi bilan) ishlatilgani qoʻngʻiroqlar tarixida saqlanadi — kim qaysi kod bilan qoʻngʻiroq qilganini keyin tekshirish mumkin.
- **Har bir PIN** — 4–12 xonali raqamli kod + yorliq (masalan xodim ismi yoki boʻlim nomi). Yorliq majburiy — faqat raqam kiritib boʻlmaydi.
- Bitta PIN bir nechta toʻplamda ishlatilib boʻlmaydi — band boʻlgan PIN kiritilsa xato chiqadi.

## Maydonlar

**Toʻplamlar** jadvali:

| Ustun | Nima koʻrsatadi |
|---|---|
| **Nom** | Toʻplam nomi |
| **CDRda yozilsin** | Yoqilgan (✓) yoki oʻchirilgan (—) |
| **PIN soni** | Toʻplamdagi PINlar soni |
| **Qayerda ishlatiladi** | Shu toʻplamni ishlatayotgan chiquvchi marshrutlar nomi |

**Toʻplam qoʻshish/tahrirlash** formasi:

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| **Nom** | Toʻplamni tanish uchun nom | — (majburiy) |
| **CDRda yozilsin** | Ishlatilgan PINni qoʻngʻiroqlar tarixida saqlash | sukut: oʻchirilgan |

**PINlarni boshqarish** oynasi:

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| **Yangi PINlar qoʻshish** | Har qatorga bitta PIN: `pin;yorliq` formatida | `1234;Direktor` |

## Qanday qilinadi

### Yangi PIN toʻplami yaratish
1. **Yangi toʻplam** tugmasini bosing.
2. **Nom** kiriting, kerak boʻlsa **CDRda yozilsin**ni yoqing.
3. **Qoʻshish** tugmasini bosing.

### Toʻplamga PIN qoʻshish
1. Jadvalda kerakli toʻplam qatorida PIN (kalit) ikonkasini bosing.
2. Ochilgan oynada **Yangi PINlar qoʻshish** maydoniga har qatorga bitta kod yozing, format: `pin;yorliq` (masalan `1234;Direktor`).
3. **Qoʻshish** tugmasini bosing — xato boʻlsa qaysi qatorda ekani koʻrsatiladi.

### PINni oʻchirish
1. Toʻplamni ochib PINlar roʻyxatida kerakli yorliq qatoridagi X tugmasini bosing.

### Toʻplamni chiquvchi marshrutga biriktirish
1. [Chiquvchi marshrutlar](/docs/outbound) boʻlimida kerakli marshrutni tahrirlang.
2. **PIN toʻplami** maydonida yaratilgan toʻplamni tanlang, **Saqlash**ni bosing.

### Toʻplamni oʻchirish
1. Qatorda **Oʻchirish** ikonkasini bosing.
2. Agar toʻplam hali bir chiquvchi marshrutda ishlatilayotgan boʻlsa, tizim qaysi marshrutlar ekanini koʻrsatadi va oʻchirishga ruxsat bermaydi — avval marshrutdan olib tashlang.

## Maslahatlar va cheklovlar

> [!TIP]
> Har bir xodim/boʻlim uchun alohida PIN va yorliq yaratish tavsiya etiladi — shunda **CDRda yozilsin** yoqilganda kim qaysi marshrutdan foydalanganini aniq koʻrish mumkin.

> [!WARNING]
> PIN toʻplami oʻzi yagona holda hech narsaga taʼsir qilmaydi — faqat chiquvchi marshrutning **PIN toʻplami** maydoniga biriktirilgandan keyin ishlay boshlaydi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| "{{row}}-qator notoʻgʻri — format «PIN;yorliq»..." | Qator noto'gʻri formatda (`;` yoʻq, PIN 4-12 raqam emas, yoki yorliq boʻsh) | Har qatorni `1234;Yorliq` koʻrinishida yozing |
| "Bu PIN allaqachon band" | Kiritilgan kod boshqa joyda allaqachon ishlatilgan | Boshqa kod tanlang |
| Toʻplamni oʻchirib boʻlmayapti | Toʻplam hali bir chiquvchi marshrutda ishlatilmoqda | Koʻrsatilgan marshrut(lar)dan avval olib tashlang |
| Qoʻngʻiroqda PIN soʻralmayapti | Toʻplam hech qaysi chiquvchi marshrutga biriktirilmagan | [Chiquvchi marshrutlar](/docs/outbound)da marshrutni tahrirlab **PIN toʻplami**ni tanlang |

## Bog'liq bo'limlar

- [Chiquvchi marshrutlar](/docs/outbound)
- [Trunklar](/docs/trunks)
