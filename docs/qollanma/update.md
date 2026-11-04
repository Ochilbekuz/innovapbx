---
id: update
title: Yangilanish
group: system
order: 120
path: /settings/update
summary: Paneldan versiya tekshirish va bir tugma bilan yangilash — jonli jarayon, jurnal va avtomatik zaxira bilan.
---

# Yangilanish

Innova PBX’ning yangi versiyasi chiqganda uni paneldan toʻgʻridan-toʻgʻri, terminalga kirmasdan oʻrnatish
mumkin. Yangilashdan oldin **avtomatik zaxira** olinadi, jarayon bosqichlab (zaxira → kod → oʻrnatish →
qayta ishga tushirish) koʻrsatiladi, xato chiqsa sabab va jurnal bilan birga bildiriladi.

## Qayerda
Menyu: **Tizim → Yangilanish**. Kim koʻradi: faqat `*` (toʻliq administrator) ruxsati bor foydalanuvchi.

## Asosiy tushunchalar

- **Yangilash agenti** — serverda ishlab turadigan, haqiqiy yangilashni bajaradigan xizmat. Agent
  topilmasa (koʻp holatda ishlab chiqish muhitida), panel buni koʻrsatadi va terminaldan
  `sudo innova-update` buyrugʻini taklif qiladi.
- **Joriy versiya** — serverda hozir oʻrnatilgan versiya raqami va oxirgi marta qachon tekshirilgani.
- **Yangi versiya va oʻzgarishlar roʻyxati (changelog)** — tekshirish natijasida yangi versiya topilsa,
  uning raqami va oʻzgarishlar matni (sarlavha, roʻyxat, qalin/kod belgilash qoʻllab-quvvatlanadi)
  koʻrsatiladi.
- **Tasdiqlash oynasi** — yangilashni boshlashdan oldin versiya raqamini **qoʻlda yozib** tasdiqlash
  kerak — bu tasodifan tugmani bosib yuborishdan himoya.
- **Bosqichlar** — Zaxira olinmoqda → Kod yuklanmoqda → Oʻrnatilmoqda → Qayta ishga tushirilmoqda; har
  bosqich jarayon chizigʻida (stepper) belgilanadi.
- **Qayta ishga tushirish paytida uzilish** — bu bosqichda panel bir muddat serverdan javob olmaydi;
  bu **normal holat** deb alohida koʻrsatiladi, xato emas.
- **Jurnal** — yangilash davomida chiqadigan texnik matnlar jonli (har 2 soniyada) yangilanib boradi;
  qoʻlda yuqoriga aylantirilsa avto-aylanish toʻxtaydi, **Oxiriga oʻtish** bilan qaytarish mumkin.
- **Yakun** — muvaffaqiyatli tugasa «Yangilandi» koʻrinadi va sahifani yangilash tugmasi chiqadi;
  muvaffaqiyatsiz tugasa xato sababi, zaxira fayl nomi (bor boʻlsa) va jurnalni koʻrish tugmasi chiqadi.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Joriy versiya | Hozir oʻrnatilgan versiya | — |
| Oxirgi tekshiruv | Qachon oxirgi marta tekshirilgani | Hali tekshirilmagan |
| Yangi versiya | Topilgan yangi versiya raqami | — |
| Versiya raqamini yozing (tasdiqlash) | Yangilashni boshlash uchun aniq mos kelishi kerak | — |

## Qanday qilinadi

### Yangilanishni tekshirish
1. **Tekshirish** tugmasini bosing.
2. Yangi versiya topilsa, uning raqami va oʻzgarishlar roʻyxati koʻrinadi; topilmasa «Siz eng soʻnggi
   versiyadasiz» deb chiqadi.

### Yangilashni boshlash
1. Yangi versiya koʻrinib turganda **Yangilash** tugmasini bosing.
2. Ochilgan oynada ogohlantirishlarni oʻqing: avtomatik zaxira olinadi, jarayon 5-15 daqiqa davom etadi,
   qoʻngʻiroqlar ~1 daqiqaga uzilishi mumkin.
3. Koʻrsatilgan versiya raqamini maydonga **aynan** yozing.
4. **Boshlash**ni bosing — jarayon darhol boshlanadi, bosqichlar va jurnal jonli koʻrinadi.

### Jarayonni kuzatish
1. Yuqorida qaysi bosqichda turganini (Zaxira/Kod/Oʻrnatish/Qayta ishga tushirish) koʻring.
2. Qayta ishga tushirish bosqichida panel bir muddat javob bermasa — kuting, bu kutilgan holat.
3. Jurnalni kerak boʻlsa pastga/yuqoriga aylantiring; oxiriga qaytish uchun **Oxiriga oʻtish**ni bosing.

### Yakunni koʻrish
1. Muvaffaqiyatli tugasa **Sahifani yangilash** tugmasini bosing — panel yangi versiyada qayta yuklanadi.
2. Muvaffaqiyatsiz tugasa xato sababini oʻqing, kerak boʻlsa **Jurnalni koʻrish**ni bosib toʻliq matnni
   chiqarib koʻring.

## Maslahatlar va cheklovlar

> [!WARNING]
> Yangilash davomida serverni **qoʻlda oʻchirmang** va qayta yuklamang — bu jarayonni toʻxtatib, tizimni
> yarim yangilangan holatda qoldirishi mumkin («Jarayon uzildi» xatosi).

> [!TIP]
> Yangilashni ish vaqti tirband boʻlmagan paytga rejalashtiring — jarayon davomida qoʻngʻiroqlar
> taxminan 1 daqiqaga uzilishi mumkin.

- Yangilash agenti oʻrnatilmagan serverda bu sahifa orqali yangilab boʻlmaydi — terminaldan
  `sudo innova-update` ishlatiladi.
- Versiya tasdiqlash maydoni aniq mos kelishi shart — boshqacha yozilsa tugma bosilmaydi.
- Zaxira muvaffaqiyatsiz boʻlsa, kod hali oʻzgarmagan boʻladi — tizim avvalgidek ishlashda davom etadi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| «Paneldan yangilash oʻrnatilmagan» | Serverda yangilash agenti yoʻq | Terminaldan `sudo innova-update` ishlatiladi |
| «Manba sozlanmagan» | Git repozitoriysi yoki upstream topilmagan | Terminalda `innova-update --check` bilan sababni koʻring |
| «Yuklab boʻlmadi» (fetch_failed) | Tarmoq yoki ruxsat xatosi | Internet aloqasini tekshirib qayta urining |
| «Kodda saqlanmagan oʻzgarish bor» | Hostda qoʻlda kiritilgan oʻzgarishlar bor | Administratorga murojaat qiling |
| «Zaxira olinmadi» | Disk joyi yetarli emas yoki boshqa sabab | Disk joyini tekshirib qayta urining — kod hali oʻzgarmagan |
| «Oʻrnatishda xatolik» | Zaxiradan keyingi bosqich muvaffaqiyatsiz | Administratorga murojaat qiling — zaxiradan qoʻlda tiklash kerak boʻlishi mumkin |
| «Jarayon uzildi» | Oldingi yangilanish tugamay server qayta ishga tushgan | Holatni tekshirib qaytadan urining |
| «Versiya raqami mos kelmadi» | Tasdiqlash maydoniga notoʻgʻri raqam yozilgan | Koʻrsatilgan versiya raqamini aynan yozing |
| «Sahifa eskirgan edi» | Boshqa joyda holat oʻzgargan (409) | Holat avtomatik yangilandi — qaytadan tekshirib koʻring |

## Bog'liq bo'limlar

- [Zaxira](/docs/backup)
- [Tizim holati](/docs/status)
- [Audit jurnali](/docs/audit)
