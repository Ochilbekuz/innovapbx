---
id: integrations
title: Integratsiyalar
group: system
order: 100
path: /settings/integrations
summary: REST API kalitlari, vebhuklar, Bitrix24/amoCRM, 1C namunalar, yozib olish va nutq sintezi sozlamalari.
---

# Integratsiyalar

Innova PBX’ni tashqi tizimlar (CRM, 1C, oʻz saytingiz, boshqa dasturlar) bilan bogʻlash shu yerdan amalga
oshiriladi: ochiq REST API uchun kalitlar, hodisalar haqida xabar beruvchi vebhuklar, Bitrix24/amoCRM
ulanishi, 1C uchun tayyor namunalar va qoʻshimcha sozlamalar (ochiq manzil, yozib olish, nutq sintezi).

## Qayerda
Menyu: **Tizim → Integratsiyalar**, yetti tab: **Umumiy**, **API kalitlari**, **Vebhuklar**, **Bitrix24**,
**amoCRM**, **1C**, **Sozlamalar**. Kim koʻradi: har kim koʻra oladi, lekin faqat `*` (toʻliq
administrator) ruxsati bor foydalanuvchi oʻzgartira oladi — boshqalarga «Faqat koʻrish» banneri chiqadi.

## Asosiy tushunchalar

- **REST API kalitlari** — `/api/public/v1/*` ochiq APIsiga kirish uchun kalit; har biri oʻz
  **ruxsatlariga (scope)** ega: qoʻngʻiroqlarni oʻqish, yozuvlarni oʻqish, chaqiruv boshlash, ichki
  raqamlarni oʻqish, hodisalar oqimi (WebSocket). Kalit yaratilganda toʻliq qiymati **faqat bir marta**
  koʻrsatiladi.
- **WebSocket hodisalar oqimi** — `events:read` ruxsatli kalit bilan qoʻngʻiroq hodisalarini jonli
  qabul qilish mumkin; sahifada tayyor ulanish namunasi bor.
- **Vebhuklar** — qoʻngʻiroq hodisasi (keldi/javob berildi/tugadi) haqida sizning serveringizga HTTP
  POSTsi yuboriladi; har bir yuborishga imzo (`X-Innova-Signature`) qoʻshiladi, buning siri bir marta
  koʻrsatiladi va istalgan vaqt **almashtirish** mumkin. Loopback/tizim manzillariga yuborish taqiqlangan.
- **Yetkazishlar jurnali** — har bir vebhuk yuborilishi (muvaffaqiyatli/xato/toʻxtatilgan) va HTTP kodi
  koʻrinadi; muvaffaqiyatsiz/toʻxtatilganlarni **qayta yuborish** mumkin.
- **Bitrix24 / amoCRM** — tugagan qoʻngʻiroqlarni CRM’ga yozish, nomaʼlum raqamlar uchun lid yaratish
  (Bitrix24) yoki «Saralanmagan»ga tushirish (amoCRM), popup/click-to-call. Maxfiy maydonlar (token,
  vebhuk manzili) saqlangandan keyin **maskalanadi**, faqat qayta kiritilganda almashtiriladi.
- **Foydalanuvchilar moslashuvi (user map)** — har bir ichki raqamga mos CRM foydalanuvchisi; **avtomatik**
  (tizim aniqlagan) yoki **qoʻlda** belgilangan. Mos kelmagan ichki raqamlar standart foydalanuvchiga
  yoʻnaltiriladi.
- **1C** — alohida server talab qilinmaydi; mavjud API kalit va vebhuk orqali ishlaydigan tayyor **BSL**
  namunalarni yuklab olish. Bu kod faqat sintaktik koʻrib chiqilgan, 1C platformasida ishga tushirilmagan.
- **Sozlamalar** tabida: **ochiq (public) manzil** (CRM/vebhuk havolalari shu asosda yaratiladi), **yozuv
  havolasi muddati**, **qoʻngʻiroq yozib olish** saqlash muddati va faqat-tashqi cheklovi, **nutq sintezi
  (Yandex SpeechKit)** — provayder, API kalit, til boʻyicha ovozlar, sinash.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| **API kalit** → Nomi / Ruxsatlar / Amal qilish muddati | Kalitni yaratish | Muddat boʻsh — muddatsiz |
| **Vebhuk** → Nomi / Manzil (URL) / Hodisalar / Ichki qoʻngʻiroqlar ham | Yangi vebhuk | Faqat http/https |
| **Bitrix24** → Kiruvchi vebhuk manzili / Lid yaratish / Popup muddati (s) / Standart foydalanuvchi ID / Ilova tokeni | Ulanish | — |
| **amoCRM** → Portal manzili / Uzoq muddatli token / «Saralanmagan»ga tushsin / Standart foydalanuvchi ID | Ulanish | — |
| **Sozlamalar** → Ochiq manzil / Yozuv havolasi muddati (s) | Tashqi havolalar | — |
| Yozib olish → Saqlash muddati (kun) / Faqat tashqi qoʻngʻiroqlar | Qoʻngʻiroq yozuvlari siyosati | — |
| Nutq sintezi → Provayder / API kalit / Oʻzbek-Rus-Ingliz ovozlar | Yandex SpeechKit | Sukut: Oʻchirilgan |

## Qanday qilinadi

### API kaliti yaratish
1. **API kalitlari** tabida **Kalit yaratish**ni bosing.
2. Nomini kiriting, kerakli **ruxsatlar**ni belgilang (kamida bittasi shart), xohlasa amal qilish
   muddatini tanlang.
3. **Yaratish**ni bosing — toʻliq kalit qiymati **faqat hozir** koʻrsatiladi, nusxalab xavfsiz joyga
   saqlang.
4. Kerak boʻlmagan kalitni roʻyxatda **Bekor qilish** bilan oʻchirib qoʻyish mumkin — bu amal
   **qaytarilmaydi**, shu kalit bilan ishlayotgan integratsiyalar darhol toʻxtaydi.

### Vebhuk qoʻshish va sinov
1. **Vebhuklar** tabida **Vebhuk qoʻshish**ni bosing.
2. Nomi, manzil (URL) va qaysi hodisalar uchun yuborilishini belgilang; kerak boʻlsa ichki (ext↔ext)
   qoʻngʻiroqlarni ham qoʻshing.
3. **Yaratish**ni bosing — imzo siri bir marta koʻrsatiladi, saqlab qoʻying.
4. Roʻyxatda **Sinov yuborish** bilan test hodisasini yuboring, **Yetkazishlar jurnali**da natijani koʻring.
5. Muvaffaqiyatsiz yetkazishni jurnalda **Qayta yuborish** bilan qayta urining.
6. Kerak boʻlsa **Sirni almashtirish** bilan imzo sirini yangilang (eskisi endi ishlamaydi).

### Bitrix24 ulash
1. **Bitrix24** tabida integratsiyani yoqing.
2. Bitrix24’dan olingan **kiruvchi vebhuk manzili**ni kiriting, kerak boʻlsa **ilova tokeni**ni ham.
3. Nomaʼlum raqamlar uchun lid yaratish va popup muddatini sozlang.
4. **Saqlash**ni bosing, **Ulanishni tekshirish**ni bosib natijani koʻring.
5. Koʻrsatilgan **click-to-call manzili**ni Bitrix24’ning chiquvchi vebhuk sozlamalariga kiriting.

### amoCRM ulash
1. **amoCRM** tabida integratsiyani yoqing, portal manzili va uzoq muddatli tokenni kiriting.
2. Nomaʼlum raqamlar «Saralanmagan»ga tushishini xohlasangiz yoqing.
3. **Saqlash** va **Ulanishni tekshirish**ni bosing.

### Foydalanuvchilar moslashuvini sozlash (Bitrix24/amoCRM)
1. Mos tab ichida **Foydalanuvchilar moslashuvi** jadvalida har bir ichki raqam qatorida CRM
   foydalanuvchi ID’sini kiritib **Moslashuvni saqlash**ni bosing.
2. Mos kelmagan ichki raqamlar haqida banner koʻrinadi — ular standart foydalanuvchiga yoʻnaltiriladi.

### 1C namunalarini olish
1. **1C** tabida koʻrsatmani oʻqing: avval `calls:originate` ruxsatli API kalit yaratish, keyin vebhuk
   qoʻshish kerak.
2. Kerakli namunani **Yuklab olish**ni bosib oling va 1C konfiguratsiyangizga HTTP-xizmat sifatida ulang.

### Umumiy sozlamalar va nutq sintezi
1. **Sozlamalar** tabida **Ochiq (public) manzil**ni kiriting (CRM/vebhuk havolalari shu asosda
   yaratiladi) va yozuv havolasi muddatini belgilang.
2. **Qoʻngʻiroq yozib olish** boʻlimida saqlash muddati (kun) va faqat-tashqi cheklovini sozlang.
3. **Nutq sintezi** boʻlimida provayderni (Yandex SpeechKit) tanlang, API kalitni kiriting, har til uchun
   ovoz kodini belgilang, **Saqlash**, keyin **Sinash**ni bosing (saqlanmagan oʻzgarish bilan sinab
   boʻlmaydi — avval saqlash kerak).

## Maslahatlar va cheklovlar

> [!WARNING]
> API kalit va vebhuk siri **faqat yaratilgan paytda bir marta** koʻrsatiladi — keyin qayta koʻrib
> boʻlmaydi, faqat yangisini yaratish/almashtirish mumkin.

> [!TIP]
> Avval **Umumiy** tabidagi kartalardan qaysi integratsiya ulanganini (holat belgisi) bir qarashda
> koʻrish mumkin — tafsilotga tegishli tabga **Sozlash** tugmasi orqali oʻting.

- Vebhuk manzili **loopback yoki tizim manzillariga** yoʻnaltirilmaydi — xavfsizlik uchun bloklangan.
- Bitrix24/amoCRM maxfiy maydonlari (token, vebhuk manzili) saqlangandan keyin maskalanadi — boʻsh
  qoldirib saqlasangiz, eski qiymat **oʻzgarmaydi**.
- Nutq sintezini sinashdan oldin oʻzgarishlarni albatta saqlang — aks holda sinov saqlangan (eski)
  sozlama bilan ishlaydi va chalgituvchi natija berishi mumkin.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| «Kamida bitta ruxsat tanlang» | API kalit yaratishda ruxsat belgilanmagan | Kerakli ruxsat(lar)ni belgilang |
| «Bu manzilga vebhuk yuborish taqiqlangan» | URL loopback/tizim manzili | Haqiqiy tashqi manzil koʻrsating |
| Vebhuk «Avtomatik oʻchirilgan» | Ketma-ket muvaffaqiyatsiz yetkazishlar | Sababini oʻqing, manzilni/serverni tekshirib qayta yoqing |
| CRM «Ulanish muvaffaqiyatsiz» | Token/manzil notoʻgʻri | Maʼlumotlarni qayta tekshirib saqlang |
| «Mos kelmagan ichki raqamlar» banneri | Foydalanuvchi moslashuvi toʻliq emas | **Foydalanuvchilar moslashuvi** jadvalida moslashtiring yoki standart foydalanuvchini belgilang |
| Nutq sintezi «Sinash» bosilmaydi | Saqlanmagan oʻzgarish bor | Avval **Saqlash**ni bosing |
| «Sozlamalar boshqa joyda oʻzgartirilgan edi» | Boshqa administrator shu paytda saqlagan | Sahifa qiymatlarni yangilaydi — qayta tekshirib saqlang |

## Bog'liq bo'limlar

- [SIP va tarmoq](/docs/sip)
- [Xavfsizlik](/docs/security)
- [Audit jurnali](/docs/audit)
