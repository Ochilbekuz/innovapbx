---
id: dashboard
title: Boshqaruv paneli
group: overview
order: 10
path: /dashboard
summary: Tizim sogʻligʻi, jonli qoʻngʻiroqlar, bugungi hajm, navbatlar va ogohlantirishlarni bir ekranda koʻrish.
---

# Boshqaruv paneli

Boshqaruv paneli — tizimga kirganda birinchi koʻrinadigan ekran: Asterisk va baza ishlab turganini, bugun nechta qoʻngʻiroq boʻlganini, hozir kim gaplashayotganini va qaysi joyda muammo borligini bir qarashda koʻrsatadi. Maʼlumotlar har 10 soniyada avtomatik yangilanadi.

## Qayerda

Menyu: **Umumiy → Boshqaruv paneli**. Kim koʻradi: `monitor:view` ruxsati bor har qanday rol (odatda **admin**; maxsus rollarda — Monitoring hududiga koʻrish huquqi berilgan boʻlsa). Pastdagi **Kutish xonasi (park)** kartasi uchun qoʻshimcha `apps:view` ruxsati kerak — bu ruxsat boʻlmasa karta umuman koʻrinmaydi (masalan operator rolida).

## Asosiy tushunchalar

- **Tizim sogʻligʻi** — Asterisk, maʼlumotlar bazasi, disk boʻsh joyi va har bir trunkning holati. Har biri yashil (`ok`) yoki qizil (`crit`) rangda koʻrsatiladi; muammo boʻlsa qisqa sabab yoziladi (masalan "Asterisk prosessi javob bermayapti").
- **Ogohlantirishlar** — sahifa tepasida, faqat muammo boʻlgandaginameydona koʻrinadi; bosilsa tegishli boʻlimga olib boradi.
- **Soatlik hajm** — bugungi kiruvchi/chiquvchi/oʻtkazib yuborilgan qoʻngʻiroqlar soni, soat boʻyicha ustunli diagramma.

## Maydonlar

Bu ekranda forma yoʻq — faqat koʻrish uchun kartalar:

| Karta | Nima koʻrsatadi |
|---|---|
| KPI qatori | **Faol qoʻngʻiroqlar**, **Bugungi jami**, **Javob berildi**, **Oʻtkazib yuborilgan**, **Oʻrtacha kutish** |
| **Soatlik hajm** | Bugungi kiruvchi/chiquvchi/oʻtkazib yuborilgan qoʻngʻiroqlar — soat boʻyicha diagramma |
| Tizim sogʻligʻi | Asterisk, Maʼlumotlar bazasi, Disk, har bir trunk holati (**Batafsil** havolasi — Tizim holati sahifasiga) |
| **Jonli qoʻngʻiroqlar** | Hozir davom etayotgan qoʻngʻiroqlar — kimdan, kimga, yoʻnalish, davomiyligi |
| **Navbatlar** | Har bir navbat: onlayn aʼzolar soni, kutayotganlar soni, eng uzoq kutish vaqti |
| **Oʻtkazib yuborilgan qoʻngʻiroqlar** | Vaqt, kimdan, qaysi DIDga, qaytarilgan/qaytarilmagan belgisi, qaytarib chaqirish havolasi |
| **Kutish xonasi (park)** | Hozir kutish xonasida turgan qoʻngʻiroqlar — slot raqami, kim qoʻygani, qachondan beri |

## Qanday qilinadi

### Muammoni topish va tegishli boʻlimga oʻtish
1. Sahifa tepasidagi ogohlantirishlar roʻyxatiga qarang — har bir qator qaysi muammoga tegishli ekanini yozadi.
2. **Koʻrish** tugmasini bosib muammoli boʻlimga oʻting (masalan trunk aloqasi uzilgan boʻlsa — Trunklar sahifasi ochiladi).
3. Tizim sogʻligʻi kartasida qizil belgi koʻrinsa, **Batafsil** havolasi orqali Tizim holati sahifasiga oʻtib toʻliq diagnostikani koʻring.

### Oʻtkazib yuborilgan qoʻngʻiroqni qaytarib chaqirish
1. **Oʻtkazib yuborilgan qoʻngʻiroqlar** kartasida kerakli qatorni toping.
2. Agar qator **Qaytarilmagan** belgisida boʻlsa — **Qaytarib chaqirish** havolasini bosing (brauzer/tizim telefon ilovasi orqali raqam teriladi).

## Maslahatlar va cheklovlar

> [!TIP]
> Barcha kartalar avtomatik yangilanadi — sahifani qayta yuklash shart emas.

> [!WARNING]
> **Kutish xonasi (park)** kartasi faqat `apps:view` ruxsati bor foydalanuvchilarga koʻrinadi. Operator roli bu ruxsatga ega emas, shuning uchun operator panelida bu karta umuman chiqmaydi — bu xato emas.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| "Yuklab boʻlmadi." xabari | Panel bilan server orasida tarmoq/API muammosi | **Qayta urinish** tugmasini bosing; davom etsa tarmoq ulanishini tekshiring |
| Trunk qatorida qizil belgi | Trunk ro'yxatdan o'tmagan yoki aloqa yo'q | [Trunklar](/docs/trunks) boʻlimida trunk holatini tekshiring |
| "Asterisk prosessi javob bermayapti" | Asterisk xizmati ishlamayapti yoki ortiqcha yuklangan | Server administratoriga/[Tizim holati](/docs/status) sahifasiga murojaat qiling |
| Disk qatorida qizil/sariq belgi | Disk boʻsh joyi kamayib ketgan | Eski yozuvlar/zaxiralarni tozalang yoki diskni kengaytiring |

## Bog'liq bo'limlar

- [Jonli monitoring](/docs/live)
- [Trunklar](/docs/trunks)
