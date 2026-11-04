---
id: users
title: Foydalanuvchilar
group: system
order: 110
path: /settings/users
summary: Panel foydalanuvchilari (login/parol), rollar va har bir hudud boʻyicha ruxsatlar (koʻrish/tahrirlash).
---

# Foydalanuvchilar

Boshqaruv panelidan foydalanadigan hisoblar (administrator, operator va boshqa maxsus rollar) va ularning
qaysi hudud (boʻlim)ga koʻrish yoki tahrirlash huquqi borligi shu yerda boshqariladi. Bu **ichki raqamlar
(telefon)** emas — panelga **kirish hisoblari**.

## Qayerda
Menyu: **Tizim → Foydalanuvchilar**, ikki tab: **Foydalanuvchilar**, **Rollar**. Kim koʻradi: har kim
koʻra oladi, lekin faqat `*` (toʻliq administrator) ruxsati bor foydalanuvchi qoʻshishi, tahrirlashi va
oʻchirishi mumkin.

## Asosiy tushunchalar

- **Foydalanuvchi** — login, toʻliq ism, email (ixtiyoriy), **rol**, ixtiyoriy bogʻlangan **ichki raqam**,
  til (uz/ru/en), faol/faolsizlantirilgan holati, 2FA (ikki bosqichli tasdiqlash) yoqilgan-yoʻqligi.
- **Tizim rollari** — **Admin** (barcha hududlarga toʻliq huquq) va **Operator** (faqat oʻz
  qoʻngʻiroqlari tarixini koʻradi); bular **oʻzgartirilmaydi va oʻchirilmaydi**, faqat koʻrish uchun
  ochiladi.
- **Maxsus rol** — tizim rollaridan tashqari yaratiladigan rol; har bir **hudud** (Monitoring, Ichki
  raqamlar, Ulanish, Yoʻnaltirish, Ilovalar, Hisobotlar) boʻyicha alohida darajada: **Yoʻq / Koʻrish /
  Tahrirlash**.
- **Hudud** — `system` guruhidagi sahifalar (Tizim boʻlimi) bu roʻyxatda yoʻq — ularga faqat `*`
  (toʻliq administrator) kirishi mumkin, boshqa hech qanday rol bilan emas.
- **Ichki raqamga bogʻlash** — bir ichki raqam faqat **bitta** panel foydalanuvchisiga bogʻlanishi
  mumkin; allaqachon bogʻlangan raqamlar tanlovda chiqmaydi.
- **2FA tiklash** — foydalanuvchi qurilmasini yoʻqotib qoʻysa, administrator uning 2FA’sini **kod
  soʻramasdan** tiklab, keyingi kirishda qaytadan ulashini taʼminlashi mumkin.
- **Oʻzini oʻzi cheklashdan himoya** — joriy foydalanuvchi oʻz hisobini oʻchira olmaydi, oʻz rolini va
  faol holatini oʻzgartira olmaydi (tasodifan tizimdan chiqib qolmaslik uchun).

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Login | Kirish uchun foydalanuvchi nomi | — |
| Toʻliq ism | Koʻrsatiladigan ism | — |
| Email | Ixtiyoriy | — |
| Rol | Admin / Operator / maxsus rol | Sukut: Operator |
| Ichki raqam | Ixtiyoriy bogʻlanish | Bogʻlanmagan |
| Til | uz/ru/en | — |
| Parol | Kamida 10 belgi | — |
| Faol | Oʻchirilsa — kira olmaydi | — |
| **Rol** → Nomi | 1-40 belgi | — |
| **Rol** → Hudud darajasi | Yoʻq / Koʻrish / Tahrirlash (har hudud uchun) | Sukut: Yoʻq |

## Qanday qilinadi

### Yangi foydalanuvchi qoʻshish
1. **Foydalanuvchilar** tabida **Yangi foydalanuvchi**ni bosing.
2. Login, toʻliq ism, email (ixtiyoriy), rol, ixtiyoriy ichki raqam, til va parolni (kamida 10 belgi)
   kiriting.
3. **Qoʻshish**ni bosing.

### Foydalanuvchini tahrirlash
1. Roʻyxatda kerakli qatorni bosing yoki qalam belgisini bosing.
2. Ism, email, rol, ichki raqam, faol holatini oʻzgartiring; parolni oʻzgartirmoqchi boʻlmasangiz bo'sh
   qoldiring.
3. **Saqlash**ni bosing.

### 2FA’ni tiklash
1. 2FA yoqilgan foydalanuvchi qatorida qalqon belgisini bosing.
2. Tasdiqlang — foydalanuvchi endi kod soʻramasdan kira oladi va keyingi kirishda qaytadan 2FA ulashi
   kerak boʻladi.

### Foydalanuvchini oʻchirish
1. Savat belgisini bosib, ochilgan oynada tasdiqlang — hisob **butunlay oʻchiriladi**.
2. Oʻz hisobingizni oʻchira olmaysiz — bu tugma oʻzingiz uchun oʻchirilgan boʻladi.

### Maxsus rol yaratish
1. **Rollar** tabida **Yangi rol**ni bosing.
2. Rol nomini kiriting (1-40 belgi).
3. Har bir hudud qatorida **Yoʻq / Koʻrish / Tahrirlash** darajasini belgilang.
4. **Qoʻshish**ni bosing.

### Rolni tahrirlash/oʻchirish
1. Maxsus rol qatorida qalam belgisini bosib nomi/ruxsatlarini oʻzgartiring, **Saqlash**ni bosing.
2. Oʻchirish uchun savat belgisini bosing — agar rolga foydalanuvchilar bogʻlangan boʻlsa, avval ularni
   boshqa rolga oʻtkazish kerak boʻladi.
3. Tizim rollari (**Admin**, **Operator**) oʻchirilmaydi/tahrirlanmaydi — ularni ochganda faqat
   tasvir koʻrinadi.

## Maslahatlar va cheklovlar

> [!WARNING]
> `system` guruhidagi (Tizim boʻlimi) sahifalarga maxsus rol orqali huquq berib boʻlmaydi — ularga
> faqat **Admin** (toʻliq `*`) kirishi mumkin.

> [!TIP]
> Operatorlarga koʻp holatda faqat **Koʻrish** darajasi yetarli — **Tahrirlash**ni faqat haqiqatan
> oʻzgartirish huquqi kerak boʻlgan hududlarga bering.

- Bir ichki raqamni ikki foydalanuvchiga bogʻlab boʻlmaydi.
- Oʻzingizning rolingiz va faol holatingizni oʻzingiz oʻzgartira olmaysiz.
- Rolga bogʻlangan foydalanuvchilar bor ekan, u rol oʻchirilmaydi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| «Bu rolga N ta foydalanuvchi bogʻlangan» | Oʻchirishdan oldin foydalanuvchilar hali shu rolda | Avval foydalanuvchilarni boshqa rolga oʻtkazing |
| Yangi foydalanuvchi qoʻshilmadi (login xatosi) | Login allaqachon band | Boshqa login tanlang |
| Ichki raqam tanlovda yoʻq | Raqam boshqa foydalanuvchiga bogʻlangan | Avval eski bogʻlanishni olib tashlang |
| «Oʻchirib boʻlmadi» | Server xatosi yoki ruxsat yoʻq | Qayta urinib koʻring, ruxsatni tekshiring |
| Tahrirlash/oʻchirish tugmalari oʻchirilgan | Toʻliq administrator ruxsati yoʻq | Administratordan `*` ruxsati soʻrang |

## Bog'liq bo'limlar

- [Audit jurnali](/docs/audit)
- [Xavfsizlik](/docs/security)
