---
id: migration
title: Ko'chirish
group: system
order: 60
path: /settings/migration
summary: FreePBX serveridan konfiguratsiyani 5 bosqichli sehrgar orqali Innova PBX’ga koʻchirish.
---

# Ko'chirish

FreePBX serverida ishlagan ichki raqamlar, trunklar, navbatlar, IVR, marshrutlar va shunga oʻxshash
sozlamalarni Innova PBX’ga qoʻlda qayta kiritmasdan koʻchirish uchun 5 bosqichli sehrgar: **Manba → Tahlil
→ Koʻrib chiqish → Qoʻllash → Natija**.

## Qayerda
Menyu: **Tizim → Koʻchirish**. Kim koʻradi: har kim koʻra oladi, lekin faqat `*` (toʻliq administrator)
ruxsati bor foydalanuvchi importni boshlashi va qoʻllashi mumkin.

## Asosiy tushunchalar

- **Eksport skripti** — FreePBX serverida **root** sifatida ishga tushiriladigan, faqat oʻqiydigan
  (hech narsani oʻzgartirmaydigan) skript (`innova-fpbx-export.sh`); natijada `fpbx-export-*.tar.gz`
  toʻplami hosil boʻladi.
- **Manba turi**: toʻplam faylini qoʻlda yuklash yoki SSH orqali avtomatik olib kelish — ikkisi ham bir xil
  tahlilga oʻtadi.
- **Tahlil** — yuklangan toʻplamni oʻqib, koʻchiriladigan obyektlar (ichki raqam, trunk, navbat, IVR,
  marshrut va h.k.) boʻyicha **reja** tuzadi; bu bosqichda Innova’da hech narsa oʻzgarmaydi.
- **Reja elementi va amal**: har bir obyekt uchun **Yaratiladi**, **Oʻtkazib yuboriladi**, **Toʻqnashuv**
  (Innova’da shu nomli/raqamli obyekt allaqachon bor) yoki **Qoʻllanmaydi** (Innova qoʻllab-quvvatlamaydi)
  deb belgilanadi.
- **Toʻqnashuvni hal qilish** — toʻqnashgan elementni **Oʻtkazib yuborish** yoki (agar obyekt qoʻlda
  yaratilmagan boʻlsa, "almashtirish mumkin") **Almashtirish**ga oʻzgartirish mumkin.
- **Zaif sirlar** — 12 belgidan kam SIP parolli ichki raqamlar; sukut boʻyicha oʻzgarmasdan koʻchadi
  (telefon qayta sozlanmasin deb), lekin xohlasa yangi tasodifiy parolga almashtirib qoʻyish mumkin.
- **Qoʻllash** — rejani haqiqatan Innova’ga yozish; oldidan joriy holatning avtomatik zaxirasi olinadi.
- **Natija** — yaratilgan/oʻtkazib yuborilgan/ogohlantirish sonlari, CSV hisobot va import muvaffaqiyatsiz
  boʻlsa yoki orqaga qaytarish kerak boʻlsa — import oldidagi zaxirani tiklash havolasi.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Toʻplam fayli | `fpbx-export-*.tar.gz`/`.tgz` formatida | — |
| **SSH** → Host/Port/Foydalanuvchi | Manba serverga ulanish | Port sukuti: 22 |
| Parol / Shaxsiy kalit | Ikkisidan kamida bittasi kerak | — |
| Zaif sirlarni almashtirish | Yoqilsa — zaif SIP parollar yangilanadi | Sukut: oʻchirilgan |
| Tasdiqlash soʻzi | Qoʻllashni boshlash uchun aynan yozilishi kerak | `KOCHIRISH` |

## Qanday qilinadi

### 1-bosqich — Manba
1. **Toʻplam yuklash** tabida avval **Skriptni yuklab olish**ni bosib, FreePBX serverida `root` sifatida
   `bash innova-fpbx-export.sh` buyrugʻini ishga tushiring — natijada toʻplam fayli hosil boʻladi.
2. Hosil boʻlgan `.tar.gz`/`.tgz` faylni tanlab **Yuklash va tahlilga oʻtish**ni bosing.
3. Yoki **SSH orqali olish** tabida host/port/foydalanuvchi va parol yoki shaxsiy kalitni kiritib,
   **Ulanishni tekshirish**, keyin **Olib kelish va tahlilga oʻtish**ni bosing. Birinchi ulanishda server
   barmoq izi koʻrsatiladi — toʻgʻri ekaniga ishonch hosil qilib tasdiqlang.

### 2-bosqich — Tahlil
1. **Tahlilni boshlash**ni bosing — progress koʻrsatiladi, bu paytda Innova’da hech narsa oʻzgarmaydi,
   faqat reja tuziladi.

### 3-bosqich — Koʻrib chiqish
1. **Turlar boʻyicha** kartalarda har bir obyekt turi uchun jami son va toʻqnashuvlar sonini koʻring.
2. Reja jadvalida turi/amal boʻyicha filtrlab, kerakli elementlarni topib, toʻqnashgan qatorlarda amalni
   **Oʻtkazib yuborish**/**Almashtirish**/**Yaratish**ga oʻzgartiring (qoʻlda yaratilgan obyektni
   almashtirib boʻlmaydi — faqat oʻtkazib yuborish mumkin).
3. **Zaif sirlar** boʻlimida kerak boʻlsa **Zaif sirlarni yangi tasodifiy parolga almashtirish**ni yoqing.
4. **Qoʻllashga oʻtish**ni bosing.

### 4-bosqich — Qoʻllash
1. Zaxira paroli oʻrnatilmagan boʻlsa, sahifa ogohlantiradi — avval [Zaxira](/docs/backup) sozlamalariga
   oʻtib parolni oʻrnating.
2. Tasdiqlash maydoniga aynan **"KOCHIRISH"** deb yozing.
3. **Qoʻllash**ni bosing — jarayon progress bilan koʻrsatiladi.
4. Agar reja eskirgan boʻlsa (Innova’da shu orada oʻzgarish boʻlgan), tizim **Qayta tahlil qilish**ni
   taklif qiladi — rejani yangilab, koʻrib chiqishni qaytadan tasdiqlang.

### 5-bosqich — Natija
1. Yaratilgan/oʻtkazib yuborilgan/ogohlantirish sonlarini koʻring.
2. **Hisobotni yuklab olish (CSV)** bilan toʻliq tafsilotni saqlang.
3. Natija muvaffaqiyatsiz boʻlsa yoki import nazarda tutilmagan oʻzgarish kiritgan boʻlsa — **Bekor
   qilish — import oldidagi zaxirani tiklash** havolasi orqali orqaga qaytarish mumkin.
4. **Yangi import boshlash** bilan sehrgarni boshidan boshlang.

### Oldingi importlar tarixini koʻrish/oʻchirish
1. Sahifa pastidagi **Koʻchirish tarixi** jadvalida avvalgi importlarni koʻring.
2. Kerak boʻlmagan toʻplam faylini savat belgisi bilan oʻchiring — bu faqat **faylni** diskdan oʻchiradi,
   import natijasi (reja, hisobot) saqlanib qoladi.

## Maslahatlar va cheklovlar

> [!WARNING]
> Toʻplamda **SIP parollari** ham bor — import tugagach fayl serverdan oʻchiriladi, lekin yuklash paytida
> uni ishonchli kanal orqali uzatish kerak.

> [!TIP]
> Avval **Tahlil** va **Koʻrib chiqish** bosqichida hech narsa Innova’da oʻzgarmaydi — reja bilan
> xohlagancha tanishib, toʻqnashuvlarni sinchiklab hal qilib, keyin **Qoʻllash**ga oʻting.

- Bir vaqtda faqat bitta zaxira/koʻchirish ishi bajarilishi mumkin — boshqasi ketayotganda **Qoʻllash**
  bloklanadi, tugashini kutish kerak.
- Zaxira paroli oʻrnatilmaguncha **Qoʻllash** bosqichiga oʻtib boʻlmaydi (import oldidan avtomatik zaxira
  kerak).
- Qoʻlda (Innova’ning oʻzida) yaratilgan obyektlar bilan toʻqnashuv — faqat **oʻtkazib yuborish** mumkin,
  **almashtirish** mumkin emas.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| «.tar.gz yoki .tgz fayl tanlang» | Boshqa formatdagi fayl yuklangan | FreePBX eksport skripti chiqargan toʻplamni tanlang |
| SSH «Ulanmadi» | Host/port/foydalanuvchi/parol notoʻgʻri | Maʼlumotlarni tekshirib qayta urinib koʻring |
| «Ish boshlanishidan oldin Innova'da holat oʻzgargan» | Tahlildan keyin boshqa oʻzgarish kiritilgan | **Qayta tahlil qilish**ni bosing |
| «Hozir boshqa zaxira/koʻchirish ishi ketmoqda» | Parallel ish bajarilmoqda | Oldingi ish tugashini kutib qayta urinib koʻring |
| Amal bajarilmadi (reja elementida) | Server xatosi yoki obyekt holati oʻzgargan | Qayta tahlil qilib rejani yangilang |
| Natija «Muvaffaqiyatsiz» | Import jarayonida xato chiqqan | Xato matnini oʻqing; **Bekor qilish** havolasi bilan import oldidagi holatga qaytaring |

## Bog'liq bo'limlar

- [Zaxira](/docs/backup)
- [Konfiguratsiya reviziyalari](/docs/revisions)
- [Audit jurnali](/docs/audit)
- [Muammolar](/docs/muammolar)
