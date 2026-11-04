---
id: timegroups
title: Ish vaqti
group: routing
order: 10
path: /timegroups
summary: Ish kunlari/dam olish jadvali, bayramlar va "ochiq/yopiq" shartlar — qoʻngʻiroqni vaqtga qarab ikki manzilga ajratish.
---

# Ish vaqti

Ofis ishlamayotganda qoʻngʻiroqlar boshqa joyga (masalan ovozli pochta yoki tungi navbatchiga) tushishi kerak.
**Ish vaqti** boʻlimi aynan shu uchun: haftalik jadval (qachon "ochiq"), bayramlar roʻyxati va DID'ni ikkiga
ajratadigan "shart" — hammasi shu yerda yigʻilgan.

## Qayerda

Menyu: **Marshrutlash → Ish vaqti**. Kim koʻradi: `routing` ruxsatiga ega foydalanuvchilar tahrirlaydi,
qolganlar faqat koʻradi.

## Asosiy tushunchalar

- **Guruh** — haftalik jadval: har kun uchun bir nechta vaqt oralig'i ("dushanba 09:00–13:00, 14:00–18:00" kabi).
  Katakchalarni bosib yoki sudrab belgilanadi.
- **Bayram** — maxsus kun, sana (`YYYY-MM-DD`) va "har yili takrorlanadi" belgisi bilan. `honor_holidays`
  yoqilgan shartlar uchun bayram kuni jadvaldan qatʼiy nazar "yopiq" hisoblanadi.
- **Shart** — guruhga bogʻlanadi va ikkita manzil belgilaydi: **ochiq boʻlganda** va **yopiq boʻlganda**.
  Shu shartni **Kiruvchi marshrut**da tanlasangiz, qoʻngʻiroq vaqtga qarab avtomatik ikkiga ajraladi.
- **Rejim (override)** — har bir shartni qoʻlda ham boshqarish mumkin: `Avtomatik` (jadval boʻyicha),
  yoki `Tungi rejim` (majburan yopiq qilib qoʻyish). Panel sahifasidagi oy/quyosh tugmasi shuni almashtiradi.
- **Oʻtkazish kodi** — ixtiyoriy `*271` kabi kod: telefon tugmalari bilan shartni tungi rejimga/avtomatikka
  oʻtkazish uchun (har bir shart uchun alohida belgilanadi).

## Maydonlar

### Guruh

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nom | Guruh nomi | Koʻpi bilan 60 belgi |
| Ish vaqti jadvali | Haftalik katakchalar setkasi | Sukut — boʻsh (hech qachon "ochiq" emas) |

### Bayram

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nom | Bayram nomi | Koʻpi bilan 60 belgi |
| Sana | `YYYY-MM-DD` formatida | — |
| Har yili takrorlanadi | Yoqilsa — yil-sayin shu kun/oyda hisoblanadi | Yangi qoʻshilganda sukut yoqilgan |

### Shart

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nom | Shart nomi | Koʻpi bilan 60 belgi |
| Raqam | Ixtiyoriy — toʻgʻridan-toʻgʻri terish uchun | 2–10 ta `0-9*#` belgi |
| Ish vaqti guruhi | Qaysi haftalik jadvalga qarab hisoblanadi | — |
| Bayramlarni hisobga olish | Yoqilsa — bayram kuni har doim "yopiq" | Sukut yoqilgan |
| Ochiq boʻlganda | Jadval boʻyicha "ochiq" paytdagi manzil | Ichki raqam, navbat, IVR, qoʻngʻiroq guruhi, konferensiya, eʼlon, maxsus manzil, band/toʻxtatish |
| Yopiq boʻlganda | "Yopiq" paytdagi manzil | xuddi shu roʻyxatdan |
| Oʻtkazish kodi | Ixtiyoriy, `*` + 2–4 raqam | Masalan `*271` |

## Qanday qilinadi

### Ish vaqti guruhi yaratish
1. **Guruhlar** tabida **Guruh qoʻshish**ni bosing.
2. Nom kiriting, haftalik setkada ish soatlarini belgilang (bosish yoki sudrab tanlash).
3. **Qoʻshish**ni bosing. Shu guruhga bogʻlangan shartlar darhol yangi jadval boʻyicha ishlay boshlaydi.

### Oʻzbekiston bayramlarini qoʻshish
1. **Bayramlar** tabida **Oʻzbekiston bayramlarini qoʻshish**ni bosing — joriy yil uchun rasmiy bayramlar avtomatik qoʻshiladi.
2. Sana yil boʻyicha aniq boʻlmagan bayramlar (masalan diniy bayramlar) oʻtkazib yuboriladi — bildirishnomada koʻrsatilgan kunlarni qoʻlda qoʻshing.

### Bayramni qoʻlda qoʻshish
1. **Yangi bayram**ni bosing, nom va sanani kiriting.
2. "Har yili takrorlanadi"ni kerak boʻlmasa oʻchiring (bir martalik kun uchun).

### Ish vaqti sharti yaratish va kiruvchi marshrutga ulash
1. Avval **Guruhlar**da kamida bitta guruh boʻlishi kerak.
2. **Shartlar** tabida **Shart qoʻshish**, nom bering, ish vaqti guruhini tanlang.
3. **Ochiq boʻlganda** va **Yopiq boʻlganda** manzillarini tanlang (masalan ochiqda — navbat, yopiqda — ovozli pochta).
4. Kerak boʻlsa bayramlarni hisobga olishni va oʻtkazish kodini sozlang, **Qoʻshish**.
5. [Kiruvchi marshrutlar](/docs/inbound) ekranida DID manzilini shu shartga yoʻnaltiring — endi qoʻngʻiroq vaqtga qarab avtomatik ajraladi.

### Shartni qoʻlda tungi rejimga oʻtkazish
1. Jadvalda shart qatoridagi oy/quyosh belgisini bosing — `Avtomatik` ↔ `Tungi rejim` almashadi.
2. Shu amalni telefon orqali ham qilish mumkin — shart tahririda belgilangan **Oʻtkazish kodi**ni terib.

### Oʻchirish
1. Qator oxiridagi savat belgisini bosing.
2. Agar guruh/shart boshqa joyda ishlatilayotgan boʻlsa (masalan kiruvchi marshrutda), oʻchirish bloklanadi va qaysi joylarda ishlatilgani koʻrsatiladi — avval oʻsha bogʻlanishlarni olib tashlang.

> [!TIP]
> Ish vaqti sharti faqat **kiruvchi marshrut**larda emas, IVR/navbat/qoʻngʻiroq guruhining "manzil" maydonlarida ham tanlanishi mumkin — ya'ni istalgan nuqtada "ochiq/yopiq"ga qarab yoʻl ayirish mumkin.

> [!WARNING]
> "Tungi rejim"ga qoʻlda oʻtkazilgan shart avtomatik qaytmaydi — jadval "ochiq" boʻlib qolsa ham, qaytib "Avtomatik"ga oʻtkazmaguningizcha qoʻngʻiroqlar "yopiq" manzilga tushadi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Shart doim "yopiq" koʻrsatadi | Guruh jadvali boʻsh yoki bugungi kun belgilanmagan | Guruhni tahrirlab, kerakli kun/soatlarni belgilang |
| Bayram kuni ham "ochiq" boʻlib qoldi | Shartda "Bayramlarni hisobga olish" oʻchirilgan | Shart tahririda yoqing |
| Guruh/shartni oʻchirib boʻlmayapti | Boshqa joyda (kiruvchi marshrut va h.k.) ishlatilmoqda | Koʻrsatilgan roʻyxatdan avval olib tashlang |
| Oʻtkazish kodi ishlamayapti | Kod formatiga mos emas yoki boʻsh | `*` + 2–4 raqam formatida kiriting |

## Bog'liq bo'limlar

- [Kiruvchi marshrutlar](/docs/inbound)
- [IVR](/docs/ivr)
- [Navbatlar](/docs/queues)
- [Kun/Tun rejimi](/docs/day_night)
- [Xususiyat kodlari](/docs/featurecodes)
