---
id: campaigns
title: Kampaniyalar
group: apps
order: 60
path: /campaigns
summary: Roʻyxatdagi raqamlarga avtomatik qoʻngʻiroq (avtoinformator/avtoterish) — audio xabar yoki operatorga ulash.
---

# Kampaniyalar

**Kampaniya** — roʻyxatdagi koʻp raqamga tizim oʻzi, belgilangan kun/vaqt oynasida, avtomatik qoʻngʻiroq
qiladi. Masalan: "Qarzdorlik eslatmasi" kampaniyasi 500 ta mijozga ish kunlari 09:00–20:00 oralig'ida
qoʻngʻiroq qilib, audio xabar eshittiradi va "1" tugmasini bosganlarni operatorga ulaydi.

## Qayerda

Menyu: **Ilovalar → Kampaniyalar**. Kim koʻradi: `apps` ruxsatiga ega foydalanuvchilar tahrirlaydi,
qolganlar faqat koʻradi (**"Sizda kampaniyalarni boshqarish ruxsati yoʻq"** ogohlantirishi bilan).

## Asosiy tushunchalar

- **Turi (mode)** — ikki xil: **Audio xabar** (mijoz javob bersa audio eshittiriladi, ixtiyoriy ravishda
  "1" — operatorga ulash, "9" — boshqa qoʻngʻiroq qilmaslik) yoki **Operatorga ulash** (mijoz javob
  berishi bilan toʻgʻridan-toʻgʻri ichki raqam/navbat/guruhga ulanadi).
- **Holat** — kampaniya besh holatdan birida boʻladi: **Qoralama** → **Ishlayapti** → **Pauzada**/
  **Tugadi**/**Toʻxtatilgan**. Faqat **Qoralama** va **Pauzada** holatlarida tahrirlash/oʻchirish mumkin —
  ishlayotganida (`running`) oʻzgartirib boʻlmaydi.
- **Qoʻngʻiroq vaqti oynasi** — hafta kunlari + boshlanish/tugash vaqti (Toshkent vaqti). Agar tugash vaqti
  boshlanishdan oldin boʻlsa (masalan `22:00`–`02:00`), oyna tun oshib davom etadi.
- **Tezlik va urinishlar** — bir vaqtda nechta qoʻngʻiroq parallel ketishi, band/javobsiz boʻlsa necha marta
  va qancha oraliqdan keyin qayta urinilishi.
- **Kontaktlar** — CSV orqali yuklanadigan raqamlar roʻyxati; har birining holati (navbatda, terilmoqda,
  qayta uriniladi, bajarildi, yetib boʻlmadi, oʻtkazib yuborildi) va qoʻngʻiroq natijasi alohida kuzatiladi.
- **Rad etganlar (opt-out)** — "9" tugmasini bosgan raqamlar butunlay rad etganlar roʻyxatiga tushadi va
  **boshqa kampaniyalarda ham** qayta terilmaydi; kampaniya oʻchirilsa ham bu roʻyxat saqlanib qoladi.

## Maydonlar

### Mijoz nima eshitadi

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nomi | Kampaniya nomi | Koʻpi bilan 80 belgi |
| Turi | **Audio xabar** yoki **Operatorga ulash** | — |
| Audio xabar | "Audio xabar" turida eshittiriladigan fayl | [Audio kutubxona](/docs/audio)dan tanlanadi, majburiy |
| Kimga ulanadi | Ichki raqam, navbat yoki guruh raqami | "Operatorga ulash" turida majburiy; "Audio xabar"da faqat "1" yoqilgan boʻlsa kerak |
| «1» — operatorga ulash | Xabardan keyin "1" bosilsa yuqoridagi raqamga ulanadi | Faqat "Audio xabar" turida koʻrinadi |
| «9» — boshqa qoʻngʻiroq qilmaslik | "9" bosgan raqam rad etganlar roʻyxatiga tushadi | Sukut — yoqilgan |
| Mijozga koʻrinadigan raqam | CallerID sifatida koʻrsatiladigan raqam | Boʻsh — trunk sozlamasidagi raqam, 3–15 raqam |

### Qachon qoʻngʻiroq qilinadi

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Boshlanishi / Tugashi | Qoʻngʻiroq oynasi (Toshkent vaqti) | Sukut `09:00`–`20:00` |
| Hafta kunlari | Qaysi kunlari qoʻngʻiroq qilinadi | Sukut — dushanbadan shanbagacha |

### Tezlik va urinishlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Bir vaqtda | Parallel qoʻngʻiroqlar soni | 1–30, sukut `2` |
| Urinishlar | Band/javobsiz boʻlganda necha marta qayta terilishi | 1–5, sukut `3` |
| Oraliq, daqiqa | Qayta urinishdan oldingi kutish | 1–1440, sukut `600` daqiqa (10 soat) |
| Jiringlash, soniya | Har bir urinishda necha soniya jiringlashi | 10–30, sukut `25` |

## Qanday qilinadi

### Yangi kampaniya yaratish
1. **Yangi kampaniya**ni bosing.
2. **Nomi** va **Turi**ni tanlang.
3. "Audio xabar" boʻlsa — audio tanlang, kerak boʻlsa "1"/"9" tugmalarini yoqing/oʻchiring.
   "Operatorga ulash" boʻlsa — **Kimga ulanadi** maydonini toʻldiring.
4. Qoʻngʻiroq vaqti oynasi va kunlarini belgilang, tezlik/urinish sozlamalarini kerak bo'lsa oʻzgartiring.
5. **Yaratish**ni bosing — kampaniya **Qoralama** holatida yaraladi, endi raqamlarni yuklash kerak.

### Raqamlarni CSV orqali yuklash
1. Kampaniyani ochib, **Raqamlarni yuklash** boʻlimiga oʻting.
2. CSV faylni tanlang yoki matnni qoʻlda joylashtiring. Har qatorda: raqam, ism (ixtiyoriy); ajratgich —
   vergul yoki nuqtali vergul; birinchi qator sarlavha boʻlishi mumkin.
3. Takrorlangan va yaroqsiz qatorlar avtomatik aniqlanadi va soni koʻrsatiladi.
4. **Eski roʻyxat oʻrniga** belgini yoqsangiz — avvalgi barcha kontaktlar va ularning natijalari oʻchib,
   yangi roʻyxat bilan almashtiriladi.
5. **Yuklash**ni bosing.

> [!WARNING]
> Tugagan yoki toʻxtatilgan kampaniyaga yangi raqam qoʻshib boʻlmaydi — bunday holatda yangi kampaniya yarating.

### Kampaniyani boshlash/pauza/toʻxtatish
1. **Qoralama** yoki **Pauzada** holatidagi kampaniyada **Boshlash**ni bosing — holat **Ishlayapti**ga oʻtadi.
2. Ishlayotgan kampaniyani vaqtincha toʻxtatish uchun **Pauza**ni bosing — keyin **Davom ettirish** bilan
   qayta boshlash mumkin, qolgan kontaktlar saqlanib qoladi.
3. **Toʻxtatish**ni bosish — **qaytarib boʻlmaydigan** amal: kampaniya **Toʻxtatilgan** holatiga oʻtadi va
   qayta boshlab boʻlmaydi (vaqtincha toʻxtatish uchun Pauzadan foydalaning).

### Tahrirlash
1. **Qoralama** yoki **Pauzada** holatdagi kampaniyani oching, kerakli maydonlarni oʻzgartiring, **Saqlash**.
2. **Ishlayapti** holatidagi kampaniyani tahrirlab boʻlmaydi — avval **Pauza**ga qoʻying.

### Kontaktlar jarayonini kuzatish
1. Kampaniya ichida **Kontaktlar** jadvalida har bir raqamning holati, urinishlar soni, oxirgi/keyingi
   urinish vaqti va natijasi (javob berdi, band, javob bermadi, qora roʻyxatda va h.k.) koʻrinadi.
2. Holat boʻyicha filtrlash va raqam/ism boʻyicha qidirish mumkin.
3. **CSV yuklab olish** orqali joriy kontaktlar roʻyxatini natijalari bilan birga tashqariga olish mumkin.

### Oʻchirish
1. **Qoralama** yoki **Pauzada** holatdagi kampaniyani oʻchirish mumkin — qator oxiridagi savat belgisini bosing.
2. Kampaniya, barcha kontaktlar va natijalari butunlay oʻchadi; faqat **rad etganlar (opt-out) roʻyxati**
   saqlanib qoladi.
3. **Ishlayapti** holatidagi kampaniyani oʻchirib boʻlmaydi — avval toʻxtating yoki pauzaga qoʻying.

> [!TIP]
> Qoʻngʻiroq oynasini mijozlar uchun qulay vaqtga (masalan ish kunlari 09:00–20:00) moslang — tungi yoki
> erta tongdagi avtomatik qoʻngʻiroqlar shikoyatlarga sabab boʻlishi mumkin.

> [!WARNING]
> "9" tugmasi bilan rad etgan raqamlar **barcha** keyingi kampaniyalarda ham avtomatik oʻtkazib yuboriladi — bu roʻyxatni panel orqali qayta tiklab boʻlmaydi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Kampaniyani tahrirlab/oʻchirib boʻlmayapti | Holati **Ishlayapti** | Avval **Pauza**ga qoʻying, keyin tahrirlang/oʻchiring |
| CSV yuklanganda koʻp raqam "yaroqsiz" deb chiqdi | Raqamlar notoʻgʻri formatda yoki 3–15 raqamdan tashqarida | Raqamlarni faqat raqamlardan iborat, toʻgʻri uzunlikda yozing |
| Kampaniya ishga tushmayapti | Joriy vaqt belgilangan qoʻngʻiroq oynasi/kunidan tashqarida | Oyna va hafta kunlarini tekshiring, kerak boʻlsa kengaytiring |
| Mijoz doim "qora roʻyxatda" natijasi olayapti | Raqam [Qora roʻyxat](/docs/blacklist)da yoki avval "9" bosib rad etgan | Qora roʻyxatni yoki oldingi opt-out holatini tekshiring |
| "1" bosilganda operatorga ulanmayapti | **Kimga ulanadi** maydoni boʻsh yoki notoʻgʻri | Maydonni toʻldiring — ichki raqam, navbat yoki guruh raqami boʻlishi kerak |

## Bog'liq bo'limlar

- [Audio kutubxona](/docs/audio)
- [Qora roʻyxat](/docs/blacklist)
- [Navbatlar](/docs/queues)
- [Qoʻngʻiroq guruhlari](/docs/ringgroups)
