---
id: extensions
title: Ichki raqamlar
group: users
order: 10
path: /extensions
summary: Xodimlarning SIP ichki raqamlarini yaratish, sozlash, Follow Me, ovozli pochta va apparatlar bilan bogʻlash.
---

# Ichki raqamlar

Ichki raqam — har bir xodimga tegishli SIP hisobi: telefon apparati yoki brauzer softfoni shu raqam orqali ulanadi, qoʻngʻiroq qiladi va qabul qiladi. Bu boʻlimda raqamlarni yaratish, SIP sirini boshqarish, qoʻngʻiroq sozlamalarini (DND, yoʻnaltirish, yozib olish) va Follow Me/ovozli pochta/apparatlarni bir joydan sozlash mumkin.

## Qayerda

Menyu: **Foydalanuvchilar → Ichki raqamlar**. Kim koʻradi: `extensions:view` ruxsati. Qoʻshish/tahrirlash/oʻchirish/sirni almashtirish/import — `extensions:edit` ruxsati; boʻlmasa **"Sizda ichki raqamlarni boshqarish ruxsati yoʻq — faqat koʻrish mumkin"** eslatmasi chiqadi.

## Asosiy tushunchalar

- **SIP login/parol** — apparat yoki softfonni ulash uchun kerakli hisob maʼlumotlari; parol faqat yaratilgan/almashtirilgan paytda bir marta toʻliq koʻrsatiladi, keyin qayta koʻrib boʻlmaydi.
- **Brauzer softfoni (WebRTC)** — yoqilsa, bu raqamga fizik telefon emas, brauzerdagi softfon ulanadi; shu raqamga QR orqali apparat ulash imkoni yoʻqoladi.
- **Yozib olish siyosati** — kiruvchi va chiquvchi qoʻngʻiroq uchun **mustaqil** sozlanadi: **Har doim**, **Hech qachon**, **Talab boʻyicha** (telefondan `*1` bilan yoqiladi/oʻchiriladi).
- **Qoʻngʻiroq sozlamalari** — DND, har doim/band boʻlsa yoʻnaltirish, pickup guruhi, tashqi qoʻngʻiroqqa ruxsat, chiquvchi CallerID, kutish rejimi (Call Waiting) — bularning barchasi darhol kuchga kiradi, qayta ishga tushirish shart emas.
- **Follow Me** — javob boʻlmasa ketma-ket boshqa raqamlarga jiringlash qoidalari (batafsil pastda).
- **Telefonga ulash (QR)** — mobil Linphone ilovasini QR orqali parolsiz ulash; WebRTC yoqilgan raqamlar uchun bu tugma oʻchirilgan.
- **CSV import/eksport** — bir nechta ichki raqamni faylda ommaviy yaratish/yangilash; import "quruq urinish" (dry run) bilan oldindan koʻrsatiladi, yangi parollar faqat bir marta yuklab olinadigan CSV faylida beriladi.

## Maydonlar

**Roʻyxat** jadvali:

| Ustun | Nima koʻrsatadi |
|---|---|
| **Raqam** | Ichki raqam (WebRTC bilgisi bilan) |
| **Nom** | Xodim/boʻlim nomi |
| **Holat** | Onlayn/oflayn/oʻchirilgan (jonli yangilanadi) |
| **Yoqilgan** | Ha/Yoʻq |
| **Qoʻngʻiroqlar** | DND, yoʻnaltirish, toll-blok belgilari |
| **Yangilangan** | Oxirgi oʻzgartirilgan vaqt |

**Yangi ichki raqam** oynasi:

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| **Raqam** | Ixtiyoriy — boʻsh qoldirilsa boʻsh turgan birinchisi avtomatik tanlanadi | masalan `101` |
| **Nom** | Xodim/boʻlim nomi | — (majburiy, 60 belgigacha) |
| **SIP paroli** | Avtomatik taklif qilinadi, oʻzgartirish/qayta generatsiya mumkin | 8–64 belgi, harf+raqam, ichki raqamni oʻz ichiga olmasin |
| **Qoʻshimcha sozlamalar** (yoyiladigan) | WebRTC, yozib olish siyosati, qoʻngʻiroq sozlamalari | — |

**Tahrirlash** oynasida qoʻshimcha: **Yoqilgan**, **Follow Me**, **Ovozli pochta**, **Apparatlar** boʻlimlari va **SIP parolini almashtirish**.

## Qanday qilinadi

### Yangi ichki raqam yaratish
1. **Yangi ichki raqam** tugmasini bosing.
2. **Raqam**ni kiriting yoki boʻsh qoldiring (avtomatik tanlanadi), **Nom** kiriting.
3. SIP parolini koʻrib chiqing — kerak boʻlsa oʻzgartiring yoki **qayta generatsiya** qiling.
4. Kerak boʻlsa **Qoʻshimcha sozlamalar**ni ochib WebRTC/yozib olish/qoʻngʻiroq sozlamalarini belgilang.
5. **Yaratish** tugmasini bosing — chiqqan oynadan SIP login/parol/domen/portni nusxalab oling (bu maʼlumot keyin qayta koʻrsatilmaydi).

### SIP parolini almashtirish
1. Mavjud raqamni tahrirlang, **SIP parolini almashtirish** boʻlimida **Oʻz parolimni kiritaman** yoki **Yangi tasodifiy parol**ni tanlang.
2. Parolni kiriting (oʻz parol tanlansa), **Saqlash**ni bosing — yangi maʼlumot bir martalik oynada koʻrsatiladi.

### Qoʻngʻiroq sozlamalarini (DND, yoʻnaltirish) oʻzgartirish
1. Raqamni tahrirlang, **Qoʻngʻiroqlar** boʻlimida kerakli toggle/maydonlarni oʻzgartiring (DND, har doim/band yoʻnaltirish, pickup guruhi, tashqi qoʻngʻiroq, CallerID, kutish rejimi).
2. **Saqlash**ni bosing — oʻzgarish darhol kuchga kiradi.

### Follow Me sozlash
1. Raqamni tahrirlang, **Follow Me** boʻlimida toggle'ni yoqing.
2. **Raqamlar** roʻyxatiga ichki/tashqi raqamlarni qoʻshing (tartibini oq-pastga koʻchirish bilan oʻzgartirish mumkin), **Qanday jiringlasin**ni tanlang (**Hammasi birga** yoki **Navbat bilan**).
3. **Navbat bilan** tanlansa **Jiringlash vaqti**ni kiriting; **Hammasi birga**da xohlasangiz **Ichki raqam ham jiringlasin**ni yoqing.
4. **Follow Meʼni saqlash** tugmasini bosing.

### Ovozli pochtani yoqish
1. Raqamni tahrirlang, **Ovozli pochta** boʻlimida **Yoqish**ni bosing.
2. 4–8 xonali **PIN** kiriting, tasdiqlang.

### Telefonga QR orqali ulash
1. Jadvalda kerakli raqam qatorida QR ikonkasini bosing (WebRTC yoqilgan raqamlarda bu tugma oʻchirilgan).
2. Ochilgan QR kodni 15 daqiqa ichida mobil Linphone bilan skanerlang — havola telefon uni olgandan keyin 60 soniyada yaroqsiz boʻladi.
3. Muddati tugasa **Yangi QR** tugmasini bosing.

### CSV orqali ommaviy import/eksport
1. **CSV eksport** tugmasi bilan joriy roʻyxatni faylga yuklab olish mumkin.
2. **CSV import** tugmasini bosing, faylni tanlang — tizim avval oʻzgarishlarni (yangi/yangilanadigan/xatolar sonini) **saqlamasdan** koʻrsatadi.
3. Xatolar boʻlmasa **Qoʻllash** tugmasini bosing; yangi raqamlar uchun parollar faqat shu paytda yuklab olinadigan CSV faylida beriladi — keyin qayta olib boʻlmaydi.

### Ichki raqamni oʻchirish
1. Qatorda **Oʻchirish** ikonkasini bosing, ogohlantirishni oʻqib tasdiqlang.
2. Agar raqam biror [kiruvchi marshrut](/docs/inbound) yoki boshqa joyda ishlatilayotgan boʻlsa, oʻchirish rad etiladi va qaysi joylarda ishlatilgani koʻrsatiladi.

## Maslahatlar va cheklovlar

> [!WARNING]
> Yangi yaratilgan yoki almashtirilgan SIP parol faqat shu oynada **bir marta** toʻliq koʻrsatiladi — yopilgandan keyin qayta koʻrish imkoni yoʻq, faqat qayta generatsiya qilish mumkin.

> [!WARNING]
> **Brauzer softfoni (WebRTC)** yoqilgan raqamga fizik apparat ulab boʻlmaydi — ikkisi birga ishlamaydi, shu sababli bunday raqamlarda QR ulash tugmasi oʻchirilgan.

> [!TIP]
> CSV import orqali ommaviy qoʻshishda avval **dry run** (saqlamasdan) natijasini koʻrib, xatolarni tuzatgandan keyin **Qoʻllash**ni bosing — xato boʻlgan qatorlar boʻlsa tugma oʻchirilgan boʻladi.

> [!TIP]
> Qoʻngʻiroq sozlamalari (DND, yoʻnaltirish) telefon apparatidan `*`-kodlar bilan ham oʻzgartirilishi mumkin — bunday holatda sahifani yangilaganda yangi holat koʻrinadi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| "Parol kamida 8 belgidan iborat boʻlsin" / "Parol ichki raqamni oʻz ichiga olmasin" va shunga oʻxshash xabarlar | SIP parol talablariga mos emas | Koʻrsatilgan qoidaga mos parol kiriting yoki tasodifiy generatsiya qiling |
| Oʻchirish rad etildi | Raqam kiruvchi marshrut yoki boshqa joyda ishlatilmoqda | Koʻrsatilgan joylardan avval olib tashlang |
| "Bu sozlama boshqa joyda oʻzgargan" | Follow Me/raqam maʼlumoti boshqa oynadan oʻzgartirilgan | **Qayta yuklash** tugmasini bosib qaytadan saqlang |
| QR kodining muddati tugadi | 15 daqiqadan koʻp vaqt oʻtdi yoki telefon 60 soniya ichida ishlatmadi | **Yangi QR** tugmasini bosib qayta skanerlang |
| Import xatolari | CSV qatorida formatga mos boʻlmagan maʼlumot | Koʻrsatilgan qator raqami va xabarga qarab faylni tuzating, qayta yuklang |

## Bog'liq bo'limlar

- [Telefon apparatlari](/docs/devices)
- [Mening kabinetim](/docs/portal)
- [Kiruvchi marshrutlar](/docs/inbound)
