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

Tahrirlash formasi FreePBX uslubida boʻlimlarga ajratilgan: **Umumiy**, **Vaqt va agentlar**, **Sig'im**,
**E'lonlar**, **Kengaytirilgan**.

### Umumiy

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nom | Navbat nomi | Koʻpi bilan 60 belgi |
| Raqam | Ixtiyoriy — toʻgʻridan-toʻgʻri terish uchun | 2–10 ta `0-9*#` belgi |
| Strategiya | Taqsimlash usuli | Sukut — **Aylanma (xotirali)** |
| Aʼzolar | Navbatga bogʻlangan ichki raqamlar roʻyxati, har biri jazo ball bilan | Kamida 1 ta aʼzo shart |
| Kutish vaqti tugasa | Hech kim javob bermasa boradigan manzil | Majburiy |
| Kutish musiqasi | MOH klassi | Boʻsh — standart (asosiy) |
| Jiringlash rejimi | Kutayotganda chaqiruvchiga MOH eshittirilsinmi yoki oddiy jiringlash ohangi | Sukut — **MOH** |

### Vaqt va agentlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Agentda jiringlash (s) | Har bir aʼzoda qancha jiringlaydi | 5–120, sukut 15 |
| Keyingi urinishgacha (s) | Jiringlamagandan keyin kutish | sukut 5, kamida 1 |
| Tugatish tanaffusi (s) | Qoʻngʻiroqdan keyin agent "band" boʻlib turadigan vaqt | sukut 0 |
| Maksimal kutish (s) | Navbatda eng koʻp qancha kutish mumkin, keyin "Kutish vaqti tugasa" manziliga oʻtadi | sukut 300 |
| Og'irlik (weight) | Bir nechta navbat bir xil agentni ulashsa, ogʻirligi katta navbat ustunlik oladi | sukut 0 |
| Aʼzo kechikishi (s) | Qabul qilishdan oldin agent telefonida qoʻshimcha kutish (shoshilinch bosilgan tugmani bartaraf etadi) | sukut 0 |
| Avtomatik toʻldirish (Autofill) | Yoqilsa — bir nechta chaqiruvchi bir vaqtda boʻsh agentlarga parallel taqsimlanadi | Sukut oʻchirilgan |
| Band agentlarni oʻtkazib yuborish | Band/qabul qilmaydigan holatdagi agentlarga jiringlashga urinmaydi | Sukut yoqilgan |
| Boshqa joyda javob berilgan deb belgilash | Call-pickup/boshqa kanal orqali javob berilgan chaqiruvni "javob berilgan" deb CDR'ga yozadi | Sukut oʻchirilgan |
| Agent vaqti tugaganda qayta boshlash | Agent javob bermay qolganda uning navbatdagi "charchash" hisoblagichini qayta boshlaydi | Sukut oʻchirilgan |
| Maksimal kutish rejimi | `strict` — hisoblash chaqiruv boshidan; `loose` — faqat navbatga joylashgandan keyin boshlanadi | Sukut — **strict** |

### Sig'im

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Navbatdagi oʻrin chegarasi | Navbatda bir vaqtda necha kishi kutishi mumkin | Boʻsh — chegarasiz |
| Aʼzosiz ham navbatga qoʻshilsin | `ha/yoʻq/strict/loose` — qoʻngʻiroq navbatga qoʻshilishi shartlari | Sukut — **yoʻq** |
| Aʼzo yoʻqligida navbatni tark etish | `ha/yoʻq/strict/loose` — navbatda kutayotgan chaqiruvlar qachon chiqariladi | Sukut — **yoʻq** |
| Jazo ball aʼzolar chegarasi | Faqat shu ball va undan pastdagi aʼzolarga jiringlanadi (0 — chegarasiz) | sukut 0 |

### E'lonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Eʼlon chastotasi (s) | Navbatdagi oʻrin qancha tez-tez eʼlon qilinadi (0 — oʻchirilgan) | sukut 30 (0–300) |
| Eng kam eʼlon oraligʻi (s) | Eʼlonlar orasidagi eng kichik vaqt (juda tez-tez takrorlanishini oldini oladi) | sukut 15 |
| Navbatdagi oʻrinni eʼlon qilish | `ha/yoʻq/limit/more` — «Siz navbatda 3-oʻringizdasiz» xabari qachon oʻqiladi | Sukut — **ha** |
| Oʻrin eʼloni chegarasi | Shu raqamdan katta oʻrinlar uchun aniq raqam oʻrniga umumiy xabar oʻqiladi | sukut 10 |
| Kutish vaqtini eʼlon qilish | `ha/yoʻq/once` — taxminiy kutish vaqti qachon aytiladi | Sukut — **ha** |
| Kutish vaqtini hisobotga qoʻshish | Agent CDR'ida chaqiruvchining kutish vaqtini saqlaydi | Sukut oʻchirilgan |
| Davriy eʼlon audiosi | Davriy takrorlanadigan maxsus eʼlon (masalan reklama/maʼlumot) | Boʻsh — standart pozitsiya/kutish eʼloni |
| Davriy eʼlon chastotasi (s) | Davriy eʼlon necha soniyada bir marta eshittiriladi | sukut 0 — oʻchirilgan |
| Qoʻshilish eʼloni | Navbatga qoʻshilgan zahoti bir marta oʻqiladigan audio (masalan "Qoʻngʻirogʻingiz navbatga qoʻshildi") | Boʻsh — oʻchirilgan |
| Agentga eʼlon | Agent javob berishdan oldin faqat agentga eshittiriladigan qisqa audio (masalan navbat nomi) | Boʻsh — oʻchirilgan |

### Kengaytirilgan

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| SLA chegarasi (s) | Hisobot uchun "yaxshi javob" chegarasi | sukut 20 |
| Suhbatni yozib olish | Navbat orqali oʻtgan suhbatlarni yozish | Sukut yoqilgan |
| CID ism prefiksi | Chaqiruvchining koʻrinadigan ismi oldiga qoʻshiladi (masalan `Sotuv: Ism Familiya`) | Boʻsh — qoʻshilmaydi |
| Alert-Info sarlavhasi | SIP `Alert-Info` sarlavhasi — maxsus/ajratilgan jiringlash ohangi uchun (telefon qoʻllab-quvvatlashi kerak) | Boʻsh — yuborilmaydi |
| Avtomatik pauza | `yoʻq/ha/all` — agent javob bermaganda avtomatik pauzaga oʻtkazilsinmi (faqat shu navbatda / barcha navbatlarda) | Sukut — **yoʻq** |
| Avtomatik pauza kechikishi (s) | Avtomatik pauzadan oldin necha marta/soniya kutiladi | sukut 0 |
| ...band boʻlganda | Agent "band" signal bersa ham avtomatik pauzaga oʻtkazish | Sukut oʻchirilgan |
| ...javob bermasa | Agent "qabul qilmadi" signal bersa ham avtomatik pauzaga oʻtkazish | Sukut oʻchirilgan |
| IVR'dan chiqish manzili (breakout) | Chaqiruvchi navbatda kutayotganda tugma bosib chiqib ketishi mumkin boʻlgan manzil | Boʻsh — chiqish imkoni yoʻq |

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

### Kengaytirilgan sozlamalarni topish
1. Tahrirlash formasida pastga tushib **Vaqt va agentlar**, **Sig'im**, **E'lonlar**, **Kengaytirilgan**
   boʻlimlarini qarang — agent jiringlash vaqti, urinishlar orasi, SLA, eʼlon chastotasi, navbat chegarasi,
   avtomatik pauza va IVR'dan chiqish manzili shu yerda joylashgan.

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

## Ataylab qoʻshilmagan sozlamalar

Quyidagi `queues.conf`/FreePBX sozlamalari **ataylab** kiritilmadi — sababi:

| Sozlama | Sabab |
|---|---|
| Qayta aloqa paroli / qregex / statik-dinamik matn maydonlari | Mavjud "Aʼzolar" roʻyxati UI'si orqali toʻliq va xavfsizroq boshqariladi — alohida matn/parol maydoniga ehtiyoj yoʻq |
| `monitor-type`/`monitor-format`/eshitilgan-aytilgan fayllar | Yozib olish allaqachon "Suhbatni yozib olish" tugmasi orqali tizim darajasida ishlaydi; ikkinchi, parallel yozib olish mexanizmi chalkashlik keltiradi |
| `eventwhencalled`/`eventmemberstatus` (AMI hodisalari) | Faqat AMI integratsiyasi uchun past darajali sozlama, operator panelida foydasi yoʻq |
| `callconfirm`/`confirmholdtime` | Call-confirm funksiyasi tizimda hali boshqa joyda (Ring Groups) qoʻllab-quvvatlanmaydi — mustaqil qoʻshish nomuvofiqlik yaratardi |
| `rvolume` (eʼlon ovoz balandligi) | Juda nozik sozlama, amaliy foyda past, xavfsiz sukut bilan ishlaydi |
| "Dinamik aʼzolarni cheklash" (Restrict Dynamic Agents) | Dinamik aʼzo qoʻshish/olib tashlash allaqachon faqat operator oʻzi (Mening kabinetim) orqali ishlaydi — qoʻshimcha cheklov hozircha ortiqcha |

## Bog'liq bo'limlar

- [Mening kabinetim](/docs/portal)
- [Kiruvchi marshrutlar](/docs/inbound)
- [Audio kutubxona](/docs/audio)
- [Sifat baholash](/docs/quality)
- [Jonli holat](/docs/live)
