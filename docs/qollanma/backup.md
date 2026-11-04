---
id: backup
title: Zaxira
group: system
order: 50
path: /settings/backup
summary: Qoʻlda/avtomatik zaxira yaratish, lokal/S3/SFTP saqlash, shifrlash paroli va fayldan tiklash.
---

# Zaxira

Tizimning toʻliq holatini (konfiguratsiya, qoʻngʻiroqlar tarixi, ovoz fayllari, ovozli xabarlar, yozib
olingan qoʻngʻiroqlar, sertifikatlar) zaxiraga olish va kerak boʻlganda qaytarish shu yerdan boshqariladi.
Zaxiralar avtomatik jadval boʻyicha yoki qoʻlda yaratilishi, lokal diskdan tashqari S3 yoki SFTP serveriga
ham nusxalanishi mumkin.

## Qayerda
Menyu: **Tizim → Zaxira**, uch tab: **Zaxiralar**, **Jadval va saqlash joylari**, **Fayldan tiklash**. Kim
koʻradi: har kim koʻra oladi, lekin faqat `*` (toʻliq administrator) ruxsati bor foydalanuvchi zaxira
yaratishi, oʻchirishi, tiklashi va sozlamalarni oʻzgartirishi mumkin.

## Asosiy tushunchalar

- **Qism (component)** — zaxiraga nimalar kiradi: Konfiguratsiya, Chaqiruvlar tarixi, Ovoz fayllari,
  Ovozli xabarlar, Yozib olingan qoʻngʻiroqlar (odatda eng katta hajmli), Sertifikatlar.
- **Zaxira turi**: Jadval boʻyicha (avtomatik), Qoʻlda, Tiklashdan oldin (har bir tiklashdan avval
  avtomatik olinadigan xavfsizlik nusxasi), Yuklangan (fayldan tiklash oqimida yuklangan `.ibk` fayl).
- **Nusxalar (copies)** — har bir zaxira bir nechta joyga (Lokal, S3, SFTP) nusxalanishi mumkin; har
  joydagi holat alohida: Kutilmoqda, Tayyor, Xatolik, Oʻchirilgan.
- **Zaxira paroli (passphrase)** — barcha zaxiralar shu parol bilan shifrlanadi. Parol oʻrnatilmaguncha
  yangi zaxira yaratib boʻlmaydi. **Parolni yoʻqotsangiz, mavjud zaxiralarni tiklab boʻlmaydi.**
- **`.ibk` fayl** — tiklash uchun yuklanadigan zaxira fayl formati.
- **Muvofiqlik tekshiruvi (inspect)** — yuklangan faylni tiklashdan oldin tizim versiyasi va mazmuni bilan
  solishtirib, moslik va ogohlantirishlarni koʻrsatadi.
- **Tiklashdan oldingi zaxira** — har qanday tiklashdan oldin joriy holat avtomatik saqlanadi — xato
  boʻlsa, shu nusxadan orqaga qaytarish mumkin.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| **Avtomatik jadval** → Yoqilgan | Rejalashtirilgan zaxirani yoqadi/oʻchiradi | — |
| Davriylik | Har kuni / Har hafta | — |
| Hafta kuni | Faqat "Har hafta" tanlansa | — |
| Vaqt | Zaxira boshlanadigan vaqt | — |
| Qaysi qismlar | Jadval boʻyicha zaxiraga kiradigan qismlar | — |
| **Lokal saqlash** → Nechta oxirgi nusxa saqlansin | Shu sondan koʻp eski lokal nusxa oʻchiriladi | — |
| **S3** → Endpoint/Region/Bucket/Prefiks/Access key/Secret key/Path-style | S3-mos xranilishga ulanish | — |
| **SFTP** → Server/Port/Foydalanuvchi/Parol/Shaxsiy kalit/Papka | SFTP serverga ulanish | — |
| Nechta oxirgi nusxa saqlansin (S3/SFTP) | Shu nishondagi eski nusxalarni tozalash | — |
| **Zaxira paroli** → Joriy parol / Yangi parol | Shifrlash parolini oʻrnatish/almashtirish | Kamida 12 belgi |

## Qanday qilinadi

### Hozir zaxira yaratish
1. **Zaxiralar** tabida **Hozir zaxiralash**ni bosing.
2. Kerakli qismlarni belgilang (kamida bittasi tanlangan boʻlishi kerak); **Yozib olingan qoʻngʻiroqlar**
   tanlansa, hajm va vaqt oshishi haqida ogohlantirish chiqadi.
3. **Boshlash**ni bosing — progress banneri koʻrinadi, tugagach muvaffaqiyat/qisman/xato haqida xabar
   chiqadi.

### Zaxirani yuklab olish / lokalga olib kelish / oʻchirish
1. Roʻyxatdagi qatorda lokal nusxa tayyor boʻlsa — **yuklab olish** belgisini bosib faylni kompyuterga
   saqlang.
2. Agar faqat tashqi (S3/SFTP) nusxa tayyor boʻlsa — **lokalga olib kelish** belgisini bosib avval lokalga
   koʻchiring, keyin yuklab oling.
3. Kerak boʻlmagan zaxirani **oʻchirish** (savat) belgisi bilan olib tashlang — tasdiqlash oynasida
   tasdiqlang; bu amal **qaytarilmaydi**.

### Roʻyxatdagi zaxiradan tiklash
1. Kerakli qatorda **tiklash** belgisini bosing.
2. Ochilgan oynada zaxira parolini kiriting (agar shifrlangan boʻlsa) va tasdiqlash maydoniga aynan
   **"TIKLASH"** deb yozing.
3. **Tiklash**ni bosing. Agar hozir faol qoʻngʻiroqlar bor boʻlsa, tizim ogohlantiradi — **Baribir
   tiklash**ni tanlasangiz, ular uziladi.
4. Tiklash tugagach, barcha foydalanuvchi tizimdan chiqariladi va login sahifasiga qaytariladi.

### Fayldan tiklash
1. **Fayldan tiklash** tabida `.ibk` faylni tanlang va **Yuklash**ni bosing.
2. Kerak boʻlsa zaxira parolini kiritib **Tekshirish**ni bosing — tizim fayl mazmunini (yaratilgan sana,
   versiya, server, qismlar) va **joriy tizim bilan mos/mos emas**ligini koʻrsatadi.
3. Mos kelmasa, tiklashni davom ettirib boʻlmaydi. Mos kelsa, **Tiklashga oʻtish**ni bosing va roʻyxatdagi
   zaxiradan tiklash bilan bir xil tasdiqlash oqimidan oʻting ("TIKLASH" deb yozish).

### Avtomatik jadval va saqlash joylarini sozlash
1. **Jadval va saqlash joylari** tabida **Avtomatik zaxira jadvali**ni yoqib, davriylik/kun/vaqt va
   qismlarni belgilang.
2. **Lokal saqlash**da nechta oxirgi nusxa saqlanishini kiriting.
3. Kerak boʻlsa **S3** va/yoki **SFTP** bloklarini yoqib, ulanish maʼlumotlarini kiriting.
4. Har birida **Ulanishni tekshirish**ni bosib, toʻgʻri sozlanganini tasdiqlang.
5. SFTP’ga birinchi marta ulanishda server barmoq izi (fingerprint) koʻrsatiladi — toʻgʻri server ekaniga
   ishonch hosil qilgandan keyingina **Ha, ishonaman**ni bosing.
6. **Saqlash**ni bosing.

### Zaxira parolini oʻrnatish/almashtirish
1. **Zaxira paroli** boʻlimida (parol oʻrnatilmagan boʻlsa — **Oʻrnatilmagan** belgisi koʻrinadi) yangi
   parolni kiriting (kamida 12 belgi).
2. Parol allaqachon oʻrnatilgan boʻlsa, avval **Joriy parol**ni kiritib tasdiqlang.
3. **Parolni saqlash**ni bosing.

## Maslahatlar va cheklovlar

> [!WARNING]
> Zaxira parolini yoʻqotsangiz, mavjud zaxiralarni **hech qanday usul bilan** tiklab boʻlmaydi — parolni
> ishonchli joyda (masalan parol boshqaruvchisida) saqlang.

> [!WARNING]
> Tiklash amali joriy maʼlumotlarni **toʻliq almashtiradi** va barcha foydalanuvchini tizimdan chiqaradi.
> Tiklashdan oldin avtomatik xavfsizlik nusxasi olinadi, lekin ishni band boʻlmagan vaqtda bajarish tavsiya
> etiladi.

> [!TIP]
> **Yozib olingan qoʻngʻiroqlar** qismi odatda eng katta hajmga ega — agar faqat konfiguratsiya va
> sozlamalarni tez-tez zaxiralashni istasangiz, avtomatik jadvalda shu qismni oʻchirib qoʻyish mumkin.

- Zaxira yaratish uchun avval **Zaxira paroli** oʻrnatilgan boʻlishi shart — aks holda sahifada
  ogohlantirish chiqadi.
- Tiklashdan keyin muvaffaqiyatli yakunlangan har bir urinish uchun "Tiklashdan oldingi zaxira"ga havola
  **Tiklash tarixi**da saqlanadi — kerak boʻlsa shu nusxadan yana orqaga qaytarish mumkin.
- S3/SFTP uchun maxfiy kalit/parol maydonlari boʻsh qoldirilsa, avval saqlangan qiymat oʻzgarmaydi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| «Zaxira yaratib boʻlmadi» | Zaxira paroli oʻrnatilmagan | **Jadval va saqlash joylari** tabida parolni oʻrnating |
| S3/SFTP «Ulanmadi» | Notoʻgʻri maʼlumotlar yoki tarmoq bloklaydi | Endpoint/kalitlar yoki server/port/foydalanuvchini tekshiring |
| «Server barmoq izi oldingisidan farq qiladi» | SFTP server oʻzgargan yoki MITM xavfi | Faqat server haqiqatan oʻzgarganiga ishonchingiz komil boʻlsa tasdiqlang |
| «Joriy tizim bilan mos emas» | Zaxira boshqa versiyadagi tizimdan olingan | Shu faylni tiklash tavsiya etilmaydi; versiyani solishtiring |
| Tiklash «Faol qoʻngʻiroqlar bor» deydi | Hozir qoʻngʻiroqlar davom etayotgan | Band boʻlmagan vaqtni kuting yoki **Baribir tiklash**ni tanlang |
| Tiklab boʻlmadi, xato | Server xatosi yoki fayl buzilgan | Xabar matnini oʻqing; **Tiklashdan oldingi zaxira**dan qayta urinib koʻring |

## Bog'liq bo'limlar

- [Konfiguratsiya reviziyalari](/docs/revisions)
- [Koʻchirish](/docs/migration)
- [Audit jurnali](/docs/audit)
- [Muammolar](/docs/muammolar)
