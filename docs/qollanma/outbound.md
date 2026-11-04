---
id: outbound
title: Chiquvchi marshrutlar
group: connect
order: 30
path: /outbound
summary: Tashqariga qoʻngʻiroq chiqarish qoidalari — naqshlar, trunk zanjiri, PIN, xalqaro qoʻngʻiroqlar, sinov.
---

# Chiquvchi marshrutlar

Chiquvchi marshrutlar — ichki raqamdan terilgan raqam qaysi trunk(lar) orqali va qanday oʻzgartirib (prefiks kesish/qoʻshish) tashqariga chiqarilishini belgilaydi. Marshrutlar ustunlikka (prioritet) koʻra tartiblangan roʻyxat sifatida ishlaydi — yuqoridagi birinchi mos keluvchi marshrut ishlatiladi.

## Qayerda

Menyu: **Ulanish → Chiquvchi marshrutlar**. Kim koʻradi: `connect:view` ruxsati. Qoʻshish/tahrirlash/oʻchirish/tartiblash — `connect:edit` ruxsati; boʻlmasa **"Sizda chiquvchi marshrutlarni boshqarish ruxsati yoʻq — faqat koʻrish va sinov mumkin"** eslatmasi chiqadi (sinov ruxsati koʻrish huquqi bilan ham ishlaydi).

## Asosiy tushunchalar

- **Ustunlik (prioritet)** — marshrutlar roʻyxatda tepadan pastga qarab tekshiriladi; terilgan raqamga birinchi mos keluvchi marshrut ishlatiladi. Roʻyxatni sudrab (drag) qayta tartiblash mumkin.
- **Naqsh qoidalari** — har bir marshrutda bir nechta qator boʻlishi mumkin: **Oldiga qoʻsh** (raqam boshiga qoʻshiladigan qiymat), **Prefiks** (kesib tashlanadigan qism), **Naqsh** (qaysi raqamlarga mos kelishi, masalan `998XXXXXXXXX`), va qatorga xos **CallerID**.
- **Trunk zanjiri** — qaysi trunk(lar) orqali chiqarilishi: birinchisi **Asosiy**, qolganlari **Zahira 1**, **Zahira 2** va h.k. — asosiysi ishlamasa navbatdagisi sinaladi. Har bir trunk sogʻlik holati bilan birga koʻrsatiladi.
- **PIN vs PIN toʻplami** — ikki alohida himoya usuli bir marshrutda birga ishlashi mumkin: oddiy **PIN** maydoni (shu marshrutga xos bitta kod) va alohida **PIN toʻplami** (bir nechta kod/foydalanuvchini boshqarish). Ikkisidan **istalgani yetadi** — biri toʻgʻri kiritilsa qoʻngʻiroq oʻtadi.
- **Xalqaro qoʻngʻiroqlar** — alohida yoqiladigan toggle; yoqilganda toll-fraud (notoʻgʻri foydalanishda katta xarajat) xavfi haqida ogohlantirish koʻrsatiladi.
- **Kimlar foydalana oladi** — marshrutni **Hammasi** (barcha ichki raqamlar) yoki **Tanlangan** ichki raqamlar roʻyxatiga cheklash mumkin.
- **Sinovchi (simulator)** — ichki raqam va raqam tanlab, marshrut haqiqatan qanday ishlayotganini (ruxsat/rad, qaysi trunk zanjiri, qadam-baqadam sabab) real vaqtda koʻrsatadigan ichki vosita.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| **Nom** | Marshrutni tanish uchun nom | — (majburiy) |
| **Yoqilgan** | Marshrutni vaqtincha oʻchirib qoʻyish | sukut: yoqilgan |
| **Naqsh qoidalari** | Oldiga qoʻsh / Prefiks / Naqsh / CallerID qatorlari | Naqsh: `998XXXXXXXXX` |
| **Trunk zanjiri** | Chiqish uchun ishlatiladigan trunklar tartibi | Birinchisi — Asosiy |
| **Chiquvchi Caller ID** | Trunkning sukut caller ID'sini bu marshrut uchun ustidan yozish | boʻsh — trunk sukutidan foydalaniladi |
| **Ustun** toggle | Bu marshrutning CallerID'si ichki raqamning oʻz caller ID'sidan ustun boʻlishi | sukut: oʻchirilgan |
| **PIN** + PIN qiymati | Shu marshrutga xos kod talab qilish | faqat raqamlar, 4–12 xona |
| **PIN toʻplami** | Alohida boshqariladigan kod toʻplamidan foydalanish | sukut: Tanlanmagan |
| **Xalqaro qoʻngʻiroqlar** | Xalqaro yoʻnalishlarga chiqishga ruxsat | sukut: oʻchirilgan |
| **Kimlar foydalana oladi** | **Hammasi** yoki **Tanlangan** ichki raqamlar | sukut: Hammasi |

## Qanday qilinadi

### Yangi chiquvchi marshrut qoʻshish
1. **Yangi marshrut** tugmasini bosing.
2. **Nom** kiriting.
3. Kamida bir **Naqsh** qoidasi kiriting (masalan `998XXXXXXXXX`), kerak boʻlsa **Oldiga qoʻsh**/**Prefiks** toʻldiring.
4. **Trunk zanjiri**da kamida bir trunk tanlang.
5. **Qoʻshish** tugmasini bosing.

### Naqsh va trunk zanjirini sozlash
1. Marshrutni tahrirlang.
2. **Qoida qoʻshish** orqali qoʻshimcha naqsh qatorlarini kiriting; har qatorda xato boʻlsa qator ostida qizil chiziq bilan koʻrsatiladi.
3. **Trunk zanjiri**da trunklarni qoʻshing/olib tashlang, tartibini sudrab oʻzgartiring — birinchisi **Asosiy** boʻladi.
4. **Saqlash**ni bosing.

### PIN yoki PIN toʻplami bilan himoyalash
1. Marshrutni tahrirlang.
2. **PIN**ni yoqib kodni kiriting, va/yoki **PIN toʻplami**dan mavjud toʻplamni tanlang.
3. **Saqlash**ni bosing — endi shu marshrut orqali terishda kod soʻraladi.

### Xalqaro qoʻngʻiroqlarni yoqish
1. Marshrutni tahrirlang.
2. **Xalqaro qoʻngʻiroqlar** toggle'ni yoqing — ogohlantirish bannerini oʻqing.
3. **Saqlash**ni bosing.

### Marshrutdan foydalanishni ichki raqamlar bilan cheklash
1. Marshrutni tahrirlang.
2. **Kimlar foydalana oladi**da **Tanlangan**ni tanlang.
3. Kerakli ichki raqamlarni roʻyxatga qoʻshing (kerak boʻlmaganini belgidan olib tashlang).
4. **Saqlash**ni bosing.

### Sinovchidan foydalanish
1. Sahifa yon panelidagi **Sinovchi** boʻlimida ichki raqamni va sinaladigan raqamni kiriting.
2. **Sinash** tugmasini bosing.
3. Natija: **Ruxsat etilgan**/**Rad etilgan**, qaysi trunk zanjiri ishlatilgani va qadam-baqadam sabablar roʻyxati koʻrinadi.

### Marshrutlarni ustunlik boʻyicha qayta tartiblash
1. Roʻyxatda kerakli marshrut qatorini uning sudrash dastagidan ushlab tortib boshqa oʻringa qoʻyib yuboring.
2. Yangi tartib avtomatik saqlanadi.

### Marshrutni oʻchirish
1. Qatorda **Oʻchirish** ikonkasini bosing.
2. Agar marshrut hali ishlatilayotgan boʻlsa (masalan bir ichki raqam roʻyxatida), tizim ishlatilayotgan joylarni koʻrsatadi va oʻchirishga ruxsat bermaydi — avval ulardan olib tashlang.

## Maslahatlar va cheklovlar

> [!WARNING]
> **Xalqaro qoʻngʻiroqlar**ni yoqishdan oldin ehtiyot boʻling — notoʻgʻri foydalanish (masalan buzilgan ichki raqam) katta xalqaro xarajatlarga (toll-fraud) olib kelishi mumkin. Faqat haqiqatan kerakli ichki raqamlarga ruxsat bering.

> [!TIP]
> PIN va PIN toʻplami bir marshrutda birga ishlatilsa, ikkisidan **istalgani** kodni toʻgʻri kiritish yetarli — ikkalasini ham bilish shart emas.

> [!TIP]
> **Chiquvchi Caller ID** boʻsh qoldirilsa, trunkdagi sukut caller ID ishlatiladi; faqat shu marshrutga xos raqam koʻrsatish kerak boʻlsa toʻldiring.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Naqsh qatorida qizil chiziq | Naqsh notoʻgʻri formatda yozilgan | Koʻrsatilgan belgi oldidagi qismni tekshirib tuzating |
| "Kamida bitta trunk kerak" | Trunk zanjiri boʻsh qoldirilgan | **Trunk zanjiri**ga kamida bitta trunk qoʻshing |
| Marshrutni oʻchirib boʻlmayapti | Marshrut hali boshqa joyda (masalan ichki raqamda) ishlatilmoqda | Koʻrsatilgan ishlatilish roʻyxatidan avval olib tashlang |
| Qoʻngʻiroq "Rad etilgan" (sinovchida) | Naqshga mos kelmadi, trunk ishlamayapti yoki PIN notoʻgʻri | Sinovchidagi qadam-baqadam sabablarni koʻrib tegishli maydonni tuzating |
| Xalqaro raqamga chiqmayapti | **Xalqaro qoʻngʻiroqlar** oʻchirilgan | Marshrutda yoqing (ogohlantirishni oʻqib) |

## Bog'liq bo'limlar

- [Trunklar](/docs/trunks)
- [PIN toʻplamlari](/docs/pinsets)
- [Kiruvchi marshrutlar](/docs/inbound)
