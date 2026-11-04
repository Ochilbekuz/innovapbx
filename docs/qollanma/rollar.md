---
id: rollar
title: Rollar va ruxsatlar
group: start
order: 50
summary: Innova PBXda kimga nima koʻrinishi va nimani oʻzgartirish mumkinligini belgilaydigan rol/ruxsat tizimi.
---

# Rollar va ruxsatlar

Innova PBXda har bir foydalanuvchiga **rol** biriktiriladi — rol esa qaysi boʻlimlarni koʻrish va oʻzgartirish mumkinligini belgilaydi. Ikki tayyor (tizim) rol bor — **Admin** va **Operator** — va xohlasangiz oʻzingiz maxsus rollar yaratishingiz mumkin.

## Asosiy tushunchalar

- **Hudud** — panel boʻlimlari olti guruhga boʻlingan: **Monitoring** (boshqaruv paneli, jonli monitoring), **Ichki raqamlar** (ichki raqamlar, apparatlar, ovozli pochta), **Ulanish** (trunklar, kiruvchi/chiquvchi marshrutlar, PIN toʻplamlari, CID manbalari), **Yoʻnaltirish** (vaqt guruhlari, IVR, navbatlar, qoʻngʻiroq guruhlari va h.k.), **Ilovalar** (audio, konferensiya, parkovka, qora roʻyxat, kampaniyalar va h.k.), **Hisobotlar** (qoʻngʻiroqlar tarixi, hisobotlar, yozuvlar).
- **Ruxsat darajasi** — har hudud uchun alohida: **Yoʻq** (koʻrinmaydi), **Koʻrish** (faqat oʻqish), **Tahrirlash** (toʻliq boshqarish — Tahrirlash Koʻrishni oʻz ichiga oladi).
- **Admin** roli — barcha hududlarga **toʻliq** ruxsat, shu bilan birga foydalanuvchilar, rollar, tizim sozlamalari, zaxira nusxalash kabi faqat administratorga tegishli boʻlimlarga ham kirish huquqi. Oʻzgartirib yoki oʻchirib boʻlmaydi.
- **Operator** roli — faqat **oʻz qoʻngʻiroqlari tarixini** koʻradi va oʻz shaxsiy kabinetida ([Mening kabinetim](/docs/portal)) ishlaydi; boshqa hech qanday hududga kirish huquqi yoʻq. Oʻzgartirib yoki oʻchirib boʻlmaydi.
- **Maxsus rol** — har bir hudud uchun alohida daraja tanlab, oʻziga xos vakolat toʻplami yaratish imkonini beradi (masalan faqat "Ulanish"ni tahrirlay oladigan, "Hisobotlar"ni faqat koʻra oladigan texnik mutaxassis).
- Foydalanuvchilar, rollar va boshqa "Tizim" boʻlimlari (sozlamalar, xavfsizlik, zaxira nusxalash, audit va h.k.) — **faqat Admin** roliga ochiq, maxsus rolga berib boʻlmaydi.
- Rol oʻzgarishi **darhol** kuchga kiradi — foydalanuvchi qaytadan kirishi shart emas.

## Qanday qilinadi

### Yangi maxsus rol yaratish
1. **Foydalanuvchilar** boʻlimida **Rollar** tabini oching ( admin huquqi kerak).
2. **Yangi rol** tugmasini bosing, rol nomini kiriting.
3. Har bir hudud qatorida kerakli darajani (**Yoʻq** / **Koʻrish** / **Tahrirlash**) tanlang.
4. **Qoʻshish** tugmasini bosing.

### Foydalanuvchiga rol biriktirish
1. **Foydalanuvchilar** tabida kerakli foydalanuvchini tahrirlang (yoki yangisini yarating).
2. **Rol** maydonida kerakli rolni (tizim yoki maxsus) tanlang, **Saqlash**ni bosing.

### Mavjud maxsus rolni oʻzgartirish
1. **Rollar** tabida kerakli rol qatorini tahrirlang.
2. Hududlar darajasini kerakli tarzda oʻzgartiring, **Saqlash**ni bosing — oʻzgarish shu rolga ega barcha foydalanuvchilarga darhol taʼsir qiladi.

## Maslahatlar va cheklovlar

> [!WARNING]
> Bir hududga faqat **Koʻrish** darajasi berilsa, u foydalanuvchi shu boʻlimda hech narsani qoʻshish/oʻzgartirish/oʻchira olmaydi — tugmalar koʻrinmaydi yoki oʻchirilgan boʻladi.

> [!TIP]
> Tizim rollarini (Admin, Operator) oʻzgartirib boʻlmaydi — ularning oʻrniga oʻzingizning vakolat toʻplamingiz bilan maxsus rol yarating.

> [!WARNING]
> Foydalanuvchisi bor rolni oʻchirib boʻlmaydi — avval shu rolga tegishli foydalanuvchilarni boshqa rolga oʻtkazing.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Menyuda kerakli boʻlim koʻrinmayapti | Foydalanuvchi roliga shu hudud uchun **Koʻrish**/**Tahrirlash** berilmagan | [Foydalanuvchilar va rollar](/docs/users) boʻlimida roldagi hudud darajasini oshiring |
| Tugmalar (qoʻshish/tahrirlash/oʻchirish) koʻrinmaydi yoki bosilmaydi | Rolda shu hudud uchun faqat **Koʻrish** darajasi bor | Kerak boʻlsa rolga **Tahrirlash** darajasini bering |
| Rolni oʻchirib boʻlmayapti | Rolga hali foydalanuvchi(lar) bogʻlangan | Avval foydalanuvchilarni boshqa rolga oʻtkazing |
| "Tizim rolini oʻzgartirib boʻlmaydi" | Admin yoki Operator rolini tahrirlashga urinish | Buning oʻrniga maxsus rol yarating |

## Bog'liq bo'limlar

- [Foydalanuvchilar va rollar](/docs/users)
- [Mening kabinetim](/docs/portal)
- [Birinchi sozlash](/docs/birinchi-sozlash)
