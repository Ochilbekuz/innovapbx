---
id: quality
title: Sifat baholash
group: reports
order: 30
path: /quality
summary: Operatorlarning qoʻngʻiroqlariga baholash varaqasi asosida baho qoʻyish, xulosa va statistika.
---

# Sifat baholash

Operatorlar mijozlar bilan qanday gaplashayotganini nazorat qilish uchun — har bir qoʻngʻiroqni tayyor
**baholash varaqasi** (chek-list) boʻyicha baholash, so'ng ichki raqamlar kesimida oʻrtacha ballni koʻrish
mumkin. Masalan, «Salomlashish standartiga amal qildimi?» va «Muammoni hal qildimi?» kabi savollarga javob
berib, qoʻngʻiroqqa foiz baho qoʻyiladi.

## Qayerda
Menyu: **Hisobotlar → Sifat baholash**. Kim koʻradi: har kim koʻra oladi, lekin faqat `reports:edit` ruxsati
bor foydalanuvchi varaqa yaratish/tahrirlash, baholash qoʻyish/tahrirlash/oʻchirish imkoniga ega — ruxsati
yoʻq foydalanuvchiga «Sizda sifat nazoratini boshqarish ruxsati yoʻq — faqat koʻrish mumkin» ogohlantirishi
chiqadi.

## Asosiy tushunchalar

- **Varaqa (chek-list)** — bir yoki bir nechta mezondan iborat baholash shabloni. Har mezon **Ha/Yoʻq** yoki
  **Baho 1–5** turida boʻladi, oʻz **vazni** bor va **Majburiy** deb belgilansa — shu mezonda muvaffaqiyatsiz
  boʻlinsa, umumiy ball **0%** boʻladi.
- **Baholash (evaluation)** — bitta qoʻngʻiroqqa bitta varaqa boʻyicha toʻldirilgan javoblar + ball foizi
  (0–100%) + ixtiyoriy izoh.
- Ball rangi: **≥80%** — yashil, **50–79%** — sariq, **<50%** — qizil.
- Bir qoʻngʻiroqni bir nechta marta (hatto turli varaqalar bilan) baholash mumkin.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| **Varaqa** → Nomi | Varaqa nomi | — |
| Faol | Yangi baholashda tanlanadi | Sukut: Faol |
| Mezon matni | Baholash savoli | «Salomlashish standartiga amal qildi» |
| Turi | Ha/Yoʻq yoki Baho 1–5 | — |
| Vazn | Mezonning umumiy balldagi ulushi | — |
| Majburiy | Belgilansa — muvaffaqiyatsiz boʻlsa butun baho 0% | Sukut: oʻchirilgan |
| **Baholash** → Varaqa | Qaysi varaqa boʻyicha baholanadi | — |
| Izoh | Ixtiyoriy matn izoh | — |

## Qanday qilinadi

### Yangi baholash varaqasi yaratish
1. **Varaqalar** tabida **Yangi varaqa** tugmasini bosing.
2. Nomini kiriting, **Faol** holatini belgilang.
3. **Mezon qoʻshish** tugmasi bilan har bir savolni qoʻshing: matn, tur (Ha/Yoʻq yoki Baho 1–5), vazn, kerak
   boʻlsa **Majburiy** belgisini qoʻying.
4. **Qoʻshish**ni bosing.

### Qoʻngʻiroqni baholash
1. [Qoʻngʻiroqlar tarixi](/docs/cdr) sahifasida kerakli qatorda **Baholash** tugmasini bosing (yoki shu
   sahifadagi **Baholashlar** tabida mavjud baholashni **Tahrirlash** bilan oching).
2. Ochilgan panelda **Varaqa**ni tanlang.
3. Har bir mezonga javob bering (Ha/Yoʻq yoki 1–5 baho) — barcha mezonlarga javob berilmaguncha saqlash
   tugmasi faol boʻlmaydi.
4. Kerak boʻlsa **Izoh** yozing.
5. **Baholashni saqlash**ni bosing — ball foizi avtomatik hisoblanadi.

### Varaqa/baholashni tahrirlash yoki oʻchirish
1. Kerakli qatorda qalam (tahrirlash) yoki savat (oʻchirish) belgisini bosing.
2. Oʻchirishda tasdiqlash oynasida yana bir bor tasdiqlang — amal qaytarilmaydi.

### Xulosani koʻrish
1. **Xulosa** tabini oching.
2. Jami baholashlar soni va oʻrtacha ballni, pastda — **ichki raqamlar boʻyicha** taqsimotni koʻring.

## Maslahatlar va cheklovlar

> [!TIP]
> Majburiy mezonni faqat haqiqatan "qoida buzilsa butun baho bekor boʻlishi kerak" boʻlgan holatlar uchun
> ishlating (masalan, mijozga doʻq-poʻpisa qilish) — boʻlmasa oʻrtacha ballar sun'iy pastlashib qoladi.

> [!WARNING]
> Baholash yoki varaqani oʻchirish qaytarilmaydi.

- Varaqa faol boʻlmasa ham, u bilan avval qilingan baholashlar tarixda qoladi — faqat yangi baholash uchun
  tanlanmaydi.
- Bitta varaqada hech boʻlmasa bitta mezon boʻlishi va barcha mezon matnlari toʻldirilgan boʻlishi shart —
  aks holda varaqa saqlanmaydi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| «Varaqa yaratish» tugmasi yoʻq | `reports:edit` ruxsati yoʻq | Administratordan ruxsat soʻrang ([Foydalanuvchilar va rollar](/docs/rollar)) |
| Baholashni saqlab boʻlmaydi | Barcha mezonlarga javob berilmagan | Har bir mezonga Ha/Yoʻq yoki 1–5 bahosini tanlang |
| «Bu varaqada mezon yoʻq» | Varaqa boʻsh yaratilgan | Varaqani tahrirlab, kamida bitta mezon qoʻshing |
| Oʻrtacha ball kutilganidan ancha past | Majburiy mezon koʻp ishlatilgan | Majburiy belgini faqat zarur mezonlarda qoldiring |

## Bog'liq bo'limlar

- [Qoʻngʻiroqlar tarixi](/docs/cdr)
- [Analitika](/docs/analytics)
- [Foydalanuvchilar va rollar](/docs/rollar)
