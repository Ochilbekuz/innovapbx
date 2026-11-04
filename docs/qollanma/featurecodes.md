---
id: featurecodes
title: Xususiyat kodlari
group: system
order: 90
path: /settings/feature-codes
summary: Telefondan `*`-kodlar bilan ishlatiladigan xususiyatlarning kodini oʻzgartirish va yoqish/oʻchirish.
---

# Xususiyat kodlari

Ovozli pochta, DND, qoʻngʻiroqni yoʻnaltirish, pickup, park va shunga oʻxshash xususiyatlarni ichki
raqamdan `*`-kod terib ishlatish mumkin (masalan `*97` — ovozli pochta). Har bir xususiyatning kodi shu
yerda oʻzgartiriladi, kerak boʻlmasa butunlay oʻchirib qoʻyish mumkin.

## Qayerda
Menyu: **Tizim → Xususiyat kodlari**. Kim koʻradi: har kim koʻra oladi (jadval), lekin faqat `*` (toʻliq
administrator) ruxsati bor foydalanuvchi kod va yoqilgan/oʻchirilgan holatini oʻzgartira oladi.

## Asosiy tushunchalar

- **Xususiyat** — telefondan kod terib chaqiriladigan amal: Ovozli pochta (`*97`), Boshqa ichki raqam
  ovozli pochtasi (`*98`), DND almashtirish (`*76`), Doimiy yoʻnaltirishni yoqish/oʻchirish
  (`*72`/`*73`), Band boʻlsa yoʻnaltirishni yoqish/oʻchirish (`*90`/`*91`), Guruh pickup (`*8`),
  Toʻgʻridan-toʻgʻri pickup (`**`), Park (`*70`), Eho testi (`*43`), Gapiradigan soat (`*60`), Follow Me
  yoqish/oʻchirish (`*21`), Navbatga kirish/chiqish (`*45`), Navbatda pauza (`*46`), Interkom
  (avtojavob, `*80`), Qoʻngʻiroq kutishni yoqish/oʻchirish (`*56`/`*57`). Navbat va interkom
  xususiyatlarining oʻzi tegishli boʻlimlarda (Navbatlar, ichki raqam sozlamalari) boshqariladi — bu
  sahifada faqat kodini oʻzgartirish/standartga qaytarish mumkin.
- **Kod** — `*` bilan boshlanadigan, 1-6 belgidan iborat (raqam, `*`, `#`) ketma-ketlik, masalan `*97`.
- **Standart kod** — har bir xususiyatning oʻz standart kodi bor; oʻzgartirilgan kod standartdan farq
  qilsa, uni **standart holatga qaytarish** tugmasi paydo boʻladi.
- **Toʻqnashuv** — ikki kod **aynan bir xil** boʻlsagina emas, balki biri ikkinchisining **prefiksi**
  boʻlsa ham (masalan `*7` va `*72`) toʻqnashuv hisoblanadi — Asterisk ikkisini ishonchli ajrata
  olmaydi. Bunday holda tizim saqlashni rad etadi.
- **Yoqilgan/oʻchirilgan** — xususiyat butunlay oʻchirib qoʻyilsa, uning kodi endi hech narsaga ulanmaydi.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Xususiyat | Qaysi amal haqida gap ketayotgani (oʻzgartirib boʻlmaydi) | — |
| Kod | `*` + 1-6 belgi (raqam/`*`/`#`) | `*97` |
| Yoqilgan | Xususiyatni yoqadi/oʻchiradi | — |

## Qanday qilinadi

### Kodni oʻzgartirish
1. Kerakli xususiyat qatorida qalam belgisini bosing.
2. Yangi kodni kiriting (format: `*` bilan boshlanib, 1-6 belgi).
3. Belgi (✓) bosing — saqlanadi. Bekor qilish uchun ✕ bosing.

### Kodni standart holatga qaytarish
1. Agar kod standartdan farq qilsa, qatorda **qayta oʻrnatish** belgisi koʻrinadi — uni bosing.
2. Kod darhol standart qiymatga qaytadi.

### Xususiyatni yoqish/oʻchirish
1. Kerakli qatordagi **Yoqilgan** katakchasini bosib almashtiring.

## Maslahatlar va cheklovlar

> [!WARNING]
> Ikki xususiyatga bir xil **yoki bir-birining prefiksi boʻlgan** kod bera olmaysiz (masalan `*7` va
> `*72` bir vaqtda boʻlishi mumkin emas) — tizim «bu kod boshqa xususiyat bilan toʻqnashadi» deb xato
> qaytaradi.

> [!TIP]
> Kodni oʻzgartirgandan keyin ichki raqam foydalanuvchilariga yangi kodni xabar qilib qoʻying — eski kod
> endi ishlamaydi.

- Kod formati qattiq belgilangan: faqat `*`, raqamlar va `#`, uzunligi 1-6 belgi.
- Oʻqish huquqi hammada bor, lekin oʻzgartirish faqat toʻliq administratorga ruxsat etilgan — boshqalar
  uchun jadval faqat koʻrinadi, tahrirlash tugmalari chiqmaydi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| «Kod notoʻgʻri» | Format mos emas (uzun/notoʻgʻri belgi) | `*` bilan boshlab, faqat raqam/`*`/`#`, 1-6 belgi yozing |
| «Bu kod boshqa xususiyat bilan toʻqnashadi» | Shu kod allaqachon boshqa xususiyatga berilgan yoki uning prefiksi/davomi | Boshqa kod tanlang yoki avval eskisini oʻzgartiring |
| «Saqlab boʻlmadi» | Server xatosi | Qayta urinib koʻring |
| Tahrirlash tugmalari koʻrinmaydi | Toʻliq administrator ruxsati yoʻq | Administratordan `*` ruxsati soʻrang |

## Bog'liq bo'limlar

- [SIP va tarmoq](/docs/sip)
- [Xavfsizlik](/docs/security)
