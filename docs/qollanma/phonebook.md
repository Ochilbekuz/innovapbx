---
id: phonebook
title: Telefon kitobi
group: apps
order: 80
path: /phonebook
summary: Kontaktlar roʻyxati — kiruvchi qoʻngʻiroqda chaqiruvchi raqam oʻrniga ism/tashkilot koʻrsatish uchun.
---

# Telefon kitobi

**Telefon kitobi** — tashqi kontaktlar (mijozlar, hamkorlar) roʻyxati. Bu yerda saqlangan raqamlardan birortasi
qoʻngʻiroq qilsa, panelda va qoʻllab-quvvatlaydigan SIP telefonlarda raqam oʻrniga kontakt nomi koʻrinadi.

## Qayerda

Menyu: **Qoʻshimcha → Telefon kitobi**. Kim koʻradi: `routing` ruxsatiga ega foydalanuvchilar tahrirlaydi,
qolganlar faqat koʻradi.

## Asosiy tushunchalar

- **Kontakt** — nom (majburiy), tashkilot va izoh (ixtiyoriy) hamda bir nechta raqamdan iborat.
- **Raqamlar** — har bir kontaktda bir nechta raqam boʻlishi mumkin, har biriga ixtiyoriy belgi (label)
  qoʻyiladi (masalan "Mobil", "Ish").
- **CSV import/eksport** — butun telefon kitobini faylga olish yoki fayldan koʻp kontaktni bir yoʻla
  qoʻshish/yangilash mumkin.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nom | Kontakt nomi | Majburiy, koʻpi bilan 128 belgi |
| Tashkilot | Qaysi tashkilotga tegishli | Ixtiyoriy, koʻpi bilan 128 belgi |
| Izoh | Qoʻshimcha eslatma | Ixtiyoriy, koʻpi bilan 512 belgi |
| Raqamlar | Kontaktga tegishli bir yoki bir nechta raqam | Har biriga ixtiyoriy belgi (masalan "Mobil") qoʻyiladi |

## Qanday qilinadi

### Yangi kontakt qoʻshish
1. **Yangi kontakt**ni bosing.
2. Nom, kerak boʻlsa tashkilot va izoh kiriting.
3. **Raqam qoʻshish**ni bosib kerakli raqam(lar)ni va ixtiyoriy belgini kiriting.
4. **Qoʻshish**ni bosing.

### Kontaktni tahrirlash
1. Qator ustida tahrirlash tugmasini bosing, maydonlarni oʻzgartiring, **Saqlash**.

### Qidirish
1. Qidiruv maydoniga nom, tashkilot yoki raqamning bir qismini kiriting.

### CSV orqali eksport qilish
1. **CSV eksport**ni bosing — butun telefon kitobi fayl koʻrinishida yuklab olinadi.

### CSV orqali import qilish
1. **CSV import**ni bosing, faylni tanlang.
2. Tizim avval oʻzgarishlarni **oldindan koʻrsatadi** (hech narsa saqlanmaydi) — nechta yangi, nechta
   yangilanadigan, nechta oʻtkazib yuboriladigan qator va xatolar soni koʻrinadi.
3. Natija toʻgʻri boʻlsa **Qoʻllash**ni bosing — oʻzgarishlar saqlanadi.
4. Faylda `name`, `company`, `note`, `numbers` ustunlari boʻlishi kerak; `numbers` ustunida bir nechta
   raqam `;` bilan, raqam va belgi `:` bilan ajratiladi (masalan `998901112233:Mobil;998712223344:Ish`).

> [!TIP]
> Import paytida mavjud raqamga toʻgʻri keladigan qator — yangi kontakt yaratish oʻrniga **mavjud kontaktni
> yangilaydi** (raqam boʻyicha moslashtiriladi).

> [!WARNING]
> Import bitta yaxlit amal: agar faylda jiddiy xato topilsa, **hech bir qator saqlanmaydi** — avval oldindan
> koʻrish natijasidagi xatolar roʻyxatini tekshirib toʻgʻrilang.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Qoʻngʻiroqda ism koʻrinmayapti | Chaqiruvchi raqam telefon kitobida yoʻq yoki formati mos emas | Raqamni kontaktga toʻgʻri formatda qoʻshing |
| Import qatori "xato" deb chiqdi | `name` ustuni boʻsh | Har qatorda nom maydonini toʻldiring |
| Import kerakli kontaktni yangilamadi, yangisini yaratdi | Raqam avvalgisidan formatda farq qiladi (normalizatsiyadan oʻtmaydi) | Raqamni toʻgʻri, xalqaro formatda kiriting |
| Kontaktni oʻchirib boʻlmayapti | — (telefon kitobi boshqa joyda ishlatilmaydi, cheklovsiz oʻchiriladi) | — |

## Bog'liq bo'limlar

- [Qora roʻyxat](/docs/blacklist)
- [CID manbalari](/docs/cidsources)
- [CDR (qoʻngʻiroqlar tarixi)](/docs/cdr)
