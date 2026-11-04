---
id: alerts
title: Ogohlantirishlar
group: system
order: 40
path: /settings/alerts
summary: Xavfsizlik va trunk hodisalari yuz berganda Telegramga avtomatik xabar yuborish sozlamalari.
---

# Ogohlantirishlar

IP bloklanganda, toll-fraud bloklanganda, parallel chaqiruv chegarasiga yetilganda yoki trunk ishdan
chiqib/tiklanganda — tizim shu hodisalar haqida tanlangan Telegram chatlarga avtomatik xabar yuboradi.
Qaysi hodisalar uchun xabar yuborilishi, qaysi chatlarga va qanchalik tez-tez — shu yerda sozlanadi.

## Qayerda
Menyu: **Tizim → Ogohlantirishlar**. Kim koʻradi: har kim koʻra oladi, lekin faqat `*` (toʻliq administrator)
ruxsati bor foydalanuvchi sozlamalarni oʻzgartirishi va sinov xabari yuborishi mumkin.

## Asosiy tushunchalar

- **Telegram bot tokeni** — avval [SIP va tarmoq](/docs/sip) sahifasidagi Bildirishnomalar boʻlimida
  sozlanishi kerak; token yoʻq boʻlsa, sahifa yuqorisida ogohlantirish chiqadi va shu sahifaga havola
  beriladi.
- **Chat ID'lar** — xabarlar yuboriladigan Telegram chatlar roʻyxati (raqamli ID, masalan
  `-1001234567890`); istalgancha chat qoʻshish mumkin.
- **Hodisa turlari** — har biri alohida yoqilishi/oʻchirilishi mumkin: IP bloklandi, toll-fraud bloklash,
  parallel chaqiruv chegarasi, trunk ishdan chiqdi, trunk tiklandi.
- **Takrorlanishni bostirish (dedup)** — bir xil hodisa belgilangan soniya ichida qayta yuborilmaydi (spam
  boʻlib ketmasligi uchun); `0` — har safar yuboriladi.
- **Tarix** — yuborilgan har bir xabarning holati: kutilmoqda, yuborildi, xato, bostirilgan (dedup
  tufayli), oʻchirilgan (hodisa turi oʻchiq boʻlgani uchun yuborilmagan).

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Chat ID | Xabar yuboriladigan Telegram chat (raqamli) | `-1001234567890` |
| IP bloklandi (SIP hujum) | Shu hodisada xabar yuborish | — |
| Toll-fraud bloklash | Shu hodisada xabar yuborish | — |
| Parallel chaqiruv chegarasi | Shu hodisada xabar yuborish | — |
| Trunk ishdan chiqdi | Shu hodisada xabar yuborish | — |
| Trunk tiklandi | Shu hodisada xabar yuborish | — |
| Takrorlanishni bostirish (soniya) | `0` — har doim yuboriladi | — |

## Qanday qilinadi

### Chat ID qoʻshish/oʻchirish
1. **Chat ID'lar** boʻlimida maydonga Telegram chat ID’sini kiriting (`Enter` tugmasi ham ishlaydi).
2. **Qoʻshish**ni bosing.
3. Oʻchirish uchun kerakli chat belgisidagi **×** tugmasini bosing.

### Qaysi hodisalar uchun xabar yuborilishini belgilash
1. **Qaysi hodisalar uchun yuborilsin** boʻlimida kerakli hodisalarni yoqing/oʻchiring.
2. **Takrorlanishni bostirish** maydoniga soniya kiritib, bir xil xabarning qancha tez-tez yuborilishini
   cheklang.
3. **Saqlash**ni bosing.

### Sinov xabari yuborish
1. **Sinov xabari** boʻlimida **Sinov xabari yuborish**ni bosing.
2. Tizim joriy sozlamalar bilan barcha qoʻshilgan chatlarga haqiqiy xabar yuboradi va natijani (nechta
   chatga yetib borgani) koʻrsatadi.
3. Yuborilgan xabar **Tarix** jadvalida ham koʻrinadi.

### Xabarlar tarixini koʻrish
1. Sahifa pastidagi **Yuborilgan ogohlantirishlar tarixi** jadvalida vaqt, xabar matni va holatini koʻring.

## Maslahatlar va cheklovlar

> [!WARNING]
> Telegram bot tokeni sozlanmagan boʻlsa, hech qanday xabar yuborilmaydi — avval
> [SIP va tarmoq](/docs/sip) sahifasida tokenni kiriting.

> [!TIP]
> Sozlamani oʻzgartirgandan keyin darhol **Sinov xabari yuborish**ni bosib, chat ID toʻgʻri kiritilganini
> tekshiring.

- Bir xil chat ID ikki marta qoʻshilmaydi.
- Dedup oynasi ichida kelgan takroriy hodisa **bostirilgan** sifatida tarixda qayd etiladi, xabar
  yuborilmaydi — bu xato emas.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| «Telegram bot tokeni sozlanmagan» banneri | SIP sahifasida token kiritilmagan | [SIP va tarmoq](/docs/sip) sahifasida tokenni sozlang |
| Sinov xabari «Yuborib boʻlmadi» | Token notoʻgʻri yoki chat ID botni bloklagan/bot chatga qoʻshilmagan | Tokenni va chat ID’ni tekshiring; botni kerakli guruhga/chatga qoʻshing |
| Hodisa yuz berdi, lekin xabar kelmadi | Shu hodisa turi oʻchirilgan yoki dedup oynasi ichida bostirilgan | **Qaysi hodisalar uchun yuborilsin**ni tekshiring; **Tarix**da holatini koʻring |
| «Sozlamalar boshqa joyda oʻzgartirilgan edi» | Boshqa administrator shu paytda saqlagan | Sahifa qiymatlarni yangilaydi — qayta tekshirib saqlang |

## Bog'liq bo'limlar

- [SIP va tarmoq](/docs/sip)
- [Xavfsizlik](/docs/security)
- [Audit jurnali](/docs/audit)
