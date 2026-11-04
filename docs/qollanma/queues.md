---
id: queues
title: Navbatlar
group: routing
order: 30
path: /queues
summary: Qoʻngʻiroqlarni operatorlar orasida taqsimlash — strategiya, aʼzolar, kutish musiqasi, SLA, jonli holat.
---

# Navbatlar

**Navbat** — qoʻngʻiroqlarni bir nechta operator (ichki raqam) orasida taqsimlaydi. Masalan "Sotuv boʻyicha
navbat" — mijoz qoʻngʻiroq qilganda, qaysi operator boʻsh boʻlsa oʻshaniki jiringlaydi; hammasi band boʻlsa,
navbatda kutadi va kutish musiqasini eshitadi.

## Qayerda

Menyu: **Marshrutlash → Navbatlar**. Kim koʻradi: `routing` ruxsatiga ega foydalanuvchilar tahrirlaydi,
qolganlar faqat koʻradi. Operatorlar oʻz navbat holatini (kirish/chiqish/pauza) [Mening kabinetim](/docs/portal)
sahifasida boshqaradi.

## Asosiy tushunchalar

- **Strategiya** — qoʻngʻiroq operatorlarga qanday taqsimlanadi (jadvalga qarang).
- **Aʼzo** — navbatga bogʻlangan ichki raqam, **jazo ball** (penalty) bilan — ball kichik boʻlsa, avval
  oʻshaniki jiringlaydi (teng strategiyalarda ustuvorlik uchun ishlatiladi).
- **Dinamik aʼzo** — operator oʻzi kirgan/chiqgan agent (odatda [Mening kabinetim](/docs/portal) orqali
  navbatga qoʻshiladi/chiqadi); panel orqali admin qoʻshgan aʼzolar statik hisoblanadi.
- **Holat** — har bir aʼzo "Kirgan / Pauzada / Chiqgan" belgisi bilan koʻrsatiladi; pauza sababi bor boʻlsa
  belgini ustiga olib borganda koʻrinadi.
- **Kutish musiqasi (MOH)** — operator javob berguncha chaqiruvchiga eshittiriladigan musiqa; tanlanmasa
  standart (asosiy) musiqa ishlatiladi.
- **SLA chegarasi** — qoʻngʻiroq necha soniyada javob berilishi "yaxshi" hisoblanishi (hisobotlar uchun,
  kutishni uzaytirmaydi).
- **Jonli holat** — jadvaldagi "Jonli holat" ustuni hozir navbatda kutayotgan va onlayn aʼzolar sonini koʻrsatadi (real vaqtda yangilanadi).

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nom | Navbat nomi | Koʻpi bilan 60 belgi |
| Raqam | Ixtiyoriy — toʻgʻridan-toʻgʻri terish uchun | 2–10 ta `0-9*#` belgi |
| Strategiya | Taqsimlash usuli | Sukut — **Aylanma (xotirali)** |
| Aʼzolar | Navbatga bogʻlangan ichki raqamlar roʻyxati, har biri jazo ball bilan | Kamida 1 ta aʼzo shart |
| Kutish vaqti tugasa | Hech kim javob bermasa boradigan manzil | Majburiy |
| Kutish musiqasi | MOH klassi | Boʻsh — standart (asosiy) |
| Agentda jiringlash (s) | Har bir aʼzoda qancha jiringlaydi | 5–120, sukut 15 |
| Keyingi urinishgacha (s) | Jiringlamagandan keyin kutish | sukut 5, kamida 1 |
| Tugatish tanaffusi (s) | Qoʻngʻiroqdan keyin agent "band" boʻlib turadigan vaqt | sukut 0 |
| Maksimal kutish (s) | Navbatda eng koʻp qancha kutish mumkin, keyin "Kutish vaqti tugasa" manziliga oʻtadi | sukut 300 |
| SLA chegarasi (s) | Hisobot uchun "yaxshi javob" chegarasi | sukut 20 |
| Eʼlon chastotasi (s) | Navbatdagi oʻrin qancha tez-tez eʼlon qilinadi | sukut 60 (10–300) |
| Navbatdagi oʻrin chegarasi | Navbatda bir vaqtda necha kishi kutishi mumkin | Boʻsh — chegarasiz |
| Navbatdagi oʻrinni eʼlon qilish | «Siz navbatda 3-oʻringizdasiz» xabari | Sukut yoqilgan |
| Aʼzosiz ham navbatga qoʻshilsin | Oʻchirilsa — aʼzo yoʻqligida qoʻngʻiroq rad etiladi | Sukut oʻchirilgan |
| Suhbatni yozib olish | Navbat orqali oʻtgan suhbatlarni yozish | Sukut yoqilgan |

### Strategiyalar

| Strategiya | Qanday ishlaydi |
|---|---|
| Hammasi birdan (`ringall`) | Barcha boʻsh aʼzolarga bir vaqtda jiringlaydi |
| Eng koʻp dam olgan (`leastrecent`) | Eng uzoq vaqt qabul qilmagan aʼzoga birinchi navbatda |
| Eng kam qabul qilgan (`fewestcalls`) | Eng kam qoʻngʻiroq qabul qilgan aʼzoga birinchi navbatda |
| Tasodifiy (`random`) | Tasodifiy tanlab jiringlaydi |
| Aylanma (xotirali) (`rrmemory`) | Aylanma tartibda, oxirgi toʻxtagan joydan davom etadi (sukut) |
| Tartib boʻyicha (`linear`) | Doim roʻyxatdagi tartib boʻyicha, birinchidan boshlab |
| Vaznli tasodifiy (`wrandom`) | Jazo balliga qarab vaznlangan tasodifiy tanlov |

## Qanday qilinadi

### Yangi navbat yaratish
1. **Navbat qoʻshish**ni bosing, nom va strategiyani tanlang.
2. **Aʼzolar** roʻyxatidan ichki raqamlarni qoʻshing (kamida bitta shart), kerak boʻlsa jazo ballni oʻzgartiring.
3. **Kutish vaqti tugasa** manzilini tanlang (majburiy) — masalan ovozli pochta yoki tungi navbatchi.
4. **Qoʻshish**ni bosing.

### Aʼzo tartibini oʻzgartirish
1. Navbatni tahrirlashga oching, aʼzolar roʻyxatida qatorni sudrab yangi oʻringa qoʻying (`linear`/`rrmemory` strategiyalarida tartib muhim).

### Aʼzoni olib tashlash
1. Aʼzo qatoridagi **Olib tashlash** tugmasini bosing, soʻng **Saqlash**.

### Qoʻshimcha sozlamalarni ochish
1. Forma pastidagi **Qoʻshimcha sozlamalar**ni bosing — agent jiringlash vaqti, urinishlar orasi, SLA, eʼlon chastotasi va navbat chegarasi shu yerda.

### Kutish musiqasini oʻzgartirish
1. **Kutish musiqasi** maydonida tayyor MOH klassini tanlang (avval [Audio kutubxona](/docs/audio)da yaratilgan boʻlishi kerak) yoki standart (asosiy) qoldiring.

### Navbatni kiruvchi marshrutga ulash
1. [Kiruvchi marshrutlar](/docs/inbound) ekranida DID manzilini shu navbatga yoʻnaltiring.

### Oʻchirish
1. Qator oxiridagi savat belgisini bosing.
2. Navbat boshqa joyda (kiruvchi marshrut, IVR tugmasi va h.k.) ishlatilayotgan boʻlsa, oʻchirish bloklanadi — avval shu bogʻlanishlarni olib tashlang.

> [!TIP]
> Jonli holat ustuni va forma sarlavhasidagi "Hozir: N kutmoqda, M onlayn" yozuvi real vaqtda yangilanadi — navbat yukini shu yerdan kuzatish mumkin.

> [!WARNING]
> "Aʼzosiz ham navbatga qoʻshilsin" oʻchirilgan boʻlsa va navbatda hech bir aʼzo boʻsh/kirgan boʻlmasa — qoʻngʻiroq rad etiladi, "Kutish vaqti tugasa" manziliga ham tushmaydi. Doim zaxira manzil (masalan ovozli pochta) borligiga ishonch hosil qiling.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Qoʻngʻiroq operatorga yetib bormayapti | Agent navbatga "kirmagan" yoki pauzada | Operator [Mening kabinetim](/docs/portal) orqali kirishi/pauzani olib tashlashi kerak |
| Navbat doim "band" deb rad etadi | "Navbatdagi oʻrin chegarasi" toʻlgan | Chegarani oshiring yoki boʻsh qoldiring |
| Qoʻngʻiroq darhol rad etiladi | Aʼzo yoʻq va "Aʼzosiz ham navbatga qoʻshilsin" oʻchirilgan | Aʼzo qoʻshing yoki shu sozlamani yoqing |
| Navbatni oʻchirib boʻlmayapti | Kiruvchi marshrut yoki boshqa manzilda ishlatilmoqda | Avval oʻsha bogʻlanishlarni olib tashlang |

## Bog'liq bo'limlar

- [Mening kabinetim](/docs/portal)
- [Kiruvchi marshrutlar](/docs/inbound)
- [Audio kutubxona](/docs/audio)
- [Sifat baholash](/docs/quality)
- [Jonli holat](/docs/live)
