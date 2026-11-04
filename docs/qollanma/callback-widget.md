---
id: callback-widget
title: Qayta qoʻngʻiroq vidjeti
group: apps
order: 110
path: /settings/integrations/widget
summary: Saytga joylashtiriladigan "Qayta qoʻngʻiroq" tugmasi — mijoz raqamini qoldirsa, tizim avtomatik operatorga ulanib, mijozga qoʻngʻiroq qiladi.
---

# Qayta qoʻngʻiroq vidjeti

**Vidjet** — veb-saytga joylashtiriladigan kichik skript, u yerda mijoz telefon raqamini qoldirishi mumkin
boʻlgan tugma/forma koʻrsatadi. Mijoz raqam qoldirgach, tizim avval **operatorga** (ichki raqam/navbat/
guruh/IVR), keyin mijozga qoʻngʻiroq qilib, ikkisini ulaydi. Masalan: saytdagi "Bizga qayta qoʻngʻiroq
qiling" tugmasi orqali mijoz raqamini qoldiradi — tizim darhol sotuv boʻlimiga, soʻng mijozga qoʻngʻiroq qiladi.

## Qayerda

Menyu: **Sozlamalar → Integratsiyalar → Veb-sayt vidjeti** (`/settings/integrations/widget`). Kim koʻradi:
`connect` ruxsatiga ega foydalanuvchilar tahrirlaydi, qolganlar faqat koʻradi.

## Asosiy tushunchalar

- **Ochiq kalit (public_key)** — har bir vidjetga avtomatik beriladigan, saytga joylashtiriladigan koddagi
  identifikator; JWT/login talab qilmaydi, shuning uchun ishonchsiz saytlarda ekspluatatsiyadan himoyalanish
  uchun **Ruxsat etilgan saytlar** roʻyxati muhim.
- **Qabul qiluvchi (Manzil)** — mijoz qoldirgan soʻrov birinchi navbatda qaysi ichki raqam/navbat/guruh/
  IVR'ga qoʻngʻiroq qilib ulanadi.
- **Ruxsat etilgan saytlar** — vidjet skripti faqat shu roʻyxatdagi domenlarda ishlaydi (masalan
  `https://sayt.uz`); boʻsh boʻlsa vidjet umuman ishlamaydi.
- **Ish vaqti guruhi** — [Ish vaqti](/docs/timegroups) shartiga bogʻlanadi; tanlanmasa vidjet doim ochiq
  hisoblanadi.
- **Ish vaqtidan tashqari** — "Qabul qilinmaydi" (soʻrov rad etiladi) yoki "Navbatga qoʻyiladi" (ish
  vaqti boshlanganda qoʻngʻiroq qilinadi).
- **Urinishlar/Qayta urinish oraligʻi** — operator javob bermasa, necha marta va qancha oraliqdan keyin
  qayta uriniladi.
- **CallerID prefiksi** — operator telefonida koʻrinadigan nom oldiga qoʻshiladigan belgi (masalan "Sayt:").
- **Koʻrinishi** — tugma rangi, joylashuvi (chap/oʻng) va uz/ru/en tillar uchun sarlavha/tugma/muvaffaqiyat matnlari.
- **Soʻrovlar jurnali** — har bir kelgan soʻrovning holati (navbatda, terilmoqda, ulandi, muvaffaqiyatsiz,
  rad etildi, bekor qilindi) va urinishlar tarixi.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nomi | Vidjet nomi (ichki, faqat panelda koʻrinadi) | Koʻpi bilan 128 belgi |
| Qabul qiluvchi (operator tomoni) | Qoʻngʻiroq birinchi qaysi manzilga boradi | Ichki raqam, navbat, guruh yoki IVR |
| Ruxsat etilgan saytlar | Vidjet ishlaydigan domenlar | Masalan `https://sayt.uz`; boʻsh — ishlamaydi |
| Ish vaqti guruhi | Qaysi jadvalga qarab ochiq/yopiq hisoblanadi | Tanlanmagan — doim ochiq |
| Ish vaqtidan tashqari | Rad etish yoki navbatga qoʻyish | Sukut — "Navbatga qoʻyiladi" |
| Urinishlar soni | Operator javob bermasa necha marta qoʻngʻiroq qilinadi | 1–5, sukut `2` |
| Qayta urinish oraligʻi (soniya) | Urinishlar orasidagi kutish | 60–1800, sukut `120` |
| CallerID prefiksi | Operator ekranida koʻrinadigan qoʻshimcha matn | Koʻpi bilan 16 belgi, masalan `Sayt:` |
| Xalqaro raqamlarga ruxsat | Mijoz xalqaro (+raqam) raqam kiritsa qabul qilinsinmi | Sukut — oʻchirilgan |
| Rang (HEX) | Tugma rangi | Masalan `#0f766e` |
| Joylashuvi | Tugma ekran chap/oʻng burchagida | Sukut — oʻngda |
| Sarlavha / Tugma / Muvaffaqiyat matni | uz/ru/en tillar uchun matnlar | — |

## Qanday qilinadi

### Yangi vidjet yaratish
1. **Yangi vidjet**ni bosing, nom kiriting.
2. **Qabul qiluvchi**ni (ichki raqam/navbat/guruh/IVR) tanlang.
3. **Ruxsat etilgan saytlar** roʻyxatiga kamida bitta domen (masalan `https://sayt.uz`) qoʻshing.
4. Kerak boʻlsa ish vaqti guruhi, urinishlar, CallerID prefiksi va koʻrinish sozlamalarini belgilang.
5. **Qoʻshish**ni bosing.

### Vidjetni saytga joylashtirish
1. Yaratilgan vidjet qatorida **Saytga joylashtirish kodi** bloqini oching.
2. **Kodni nusxalash**ni bosing va saytingizning `</body>` tegidan oldin joylashtiring.
3. Agar server manzili (`public_base_url`) sozlanmagan boʻlsa, tizim buni ogohlantiradi — admin bilan bogʻlanish kerak.

### Vidjetni tahrirlash
1. Qator ustida tahrirlash tugmasini bosing, kerakli maydonlarni oʻzgartiring, **Saqlash**.

### Kalitni yangilash (rotate)
1. Agar ochiq kalit (public_key) buzilgan/suiiste'mol qilingan deb hisoblasangiz, **kalitni yangilash**
   tugmasini bosing.
2. **Eslatma**: eski manzil ishdan chiqadi — saytdagi skript havolasini yangisiga almashtirish zarur boʻladi.

### Soʻrovlar jurnalini koʻrish
1. **Soʻrovlar jurnali** tabiga oʻting — har bir soʻrovning vaqti, telefon/ism, holati, urinishlar soni
   va (muvaffaqiyatsiz boʻlsa) xato matni koʻrinadi.

### Oʻchirish
1. Qator oxiridagi savat belgisini bosing, tasdiqlang — vidjet oʻchadi va saytdagi skript ishlamay qoladi.

> [!WARNING]
> **Ruxsat etilgan saytlar** roʻyxatini boʻsh qoldirmang — aks holda vidjet umuman ishlamaydi. Faqat
> haqiqatan sizning saytlaringiz domenini qoʻshing, aks holda begona saytlar ham skriptdan foydalanishi mumkin.

> [!TIP]
> **CallerID prefiksi**ni qoʻyib qoʻysangiz, operator kiruvchi qoʻngʻiroq saytdan kelganini darhol bilib oladi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Vidjet saytda umuman koʻrinmayapti | Sayt domeni **Ruxsat etilgan saytlar**da yoʻq yoki roʻyxat boʻsh | Toʻgʻri domenni (https bilan) qoʻshing |
| "Server manzili sozlanmagan" ogohlantirishi | `public_base_url` tizim darajasida sozlanmagan | Administrator bilan bogʻlanib umumiy manzilni sozlang |
| Mijoz raqam qoldirdi, lekin qoʻngʻiroq kelmadi | Ish vaqti sharti "Qabul qilinmaydi" holatida yoki qabul qiluvchi band | Ish vaqti sozlamasini va qabul qiluvchini tekshiring |
| Xalqaro raqam qabul qilinmadi | **Xalqaro raqamlarga ruxsat** oʻchirilgan | Kerak boʻlsa shu kalitni yoqing |
| Eski skript ishlamay qoldi | Kalit yangilangan (rotate), lekin saytdagi kod almashtirilmagan | Yangi "Saytga joylashtirish kodi"ni nusxalab saytga qoʻying |

## Bog'liq bo'limlar

- [Ish vaqti](/docs/timegroups)
- [Navbatlar](/docs/queues)
- [Qoʻngʻiroq guruhlari](/docs/ringgroups)
- [IVR](/docs/ivr)
- [Integratsiyalar](/docs/integrations)
