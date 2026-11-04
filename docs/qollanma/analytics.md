---
id: analytics
title: Analitika
group: reports
order: 20
path: /analytics
summary: Qoʻngʻiroqlar statistikasi — KPI, kunlik/soatlik diagramma, navbat va operator boʻyicha jadval.
---

# Analitika

Call-markaz va umumiy qoʻngʻiroqlar oqimi boʻyicha umumiy koʻrinish: necha qoʻngʻiroq boʻldi, qanchasi javob
berildi, oʻrtacha kutish qancha, SLA darajasi qanday. Rahbar uchun — kunlik hisobot oʻrniga bir ekranda barcha
sonlar.

## Qayerda
Menyu: **Hisobotlar → Analitika**. Kim koʻradi: `reports:view` yoki `reports:edit` ruxsati bor foydalanuvchi.

## Asosiy tushunchalar

- **SLA darajasi** — belgilangan vaqt ichida javob berilgan qoʻngʻiroqlar foizi (navbat sozlamasidagi SLA
  chegarasiga asoslanadi, [Navbatlar](/docs/queues)).
- **Oʻtkazib yuborilgan** — javobsiz qolgan yoki navbatda vaqt tugab uzilgan qoʻngʻiroqlar.
- Diagrammalar va jadvallar tanlangan **davr** va **navbat filtri**ga mos holda yangilanadi.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Davr | Bugun / Kecha / Oxirgi 7 kun / Oxirgi 30 kun / Boshqa (sana oraligʻi) | Sukut: Oxirgi 7 kun |
| Boshlanishi / Tugashi | Faqat «Boshqa» tanlanganda koʻrinadi — sana oraligʻi | Eng koʻpi — 92 kun |
| Navbat | Faqat bitta navbat boʻyicha filtrlash | Sukut: Barcha navbatlar |

## Qanday qilinadi

### Davr va navbat boʻyicha koʻrish
1. **Davr** tanlang (tezkor variant yoki **Boshqa** bilan oʻz sana oraligʻingizni kiriting).
2. Kerak boʻlsa **Navbat** roʻyxatidan bitta navbatni tanlang — barcha KPI, diagramma va jadvallar shu
   navbatga mos qiymatlarga qisqaradi.
3. KPI kartalari (jami qoʻngʻiroqlar, javob berilgan, oʻtkazib yuborilgan, oʻrtacha kutish, oʻrtacha suhbat,
   SLA darajasi) avtomatik hisoblanadi.

### Diagrammalarni oʻqish
1. **Kunlar boʻyicha** diagramma — har kun uchun javob berilgan/oʻtkazib yuborilgan qoʻngʻiroqlar soni.
2. **Soatlar boʻyicha** diagramma — kun ichidagi soatlar boʻyicha kiruvchi/javob berilgan/oʻtkazib yuborilgan
   taqsimot — eng band soatlarni aniqlash uchun qulay.

### Navbat va operator jadvallarini tahlil qilish
1. **Navbatlar boʻyicha** jadvalda har bir navbat uchun qoʻngʻiroqlar, javob berilgan, oʻtkazib yuborilgan,
   oʻrtacha kutish va SLA koʻrsatkichlarini solishtiring.
2. **Operatorlar boʻyicha** jadvalda har bir operatorning javob bergan qoʻngʻiroqlari soni, jami suhbat vaqti
   va oʻrtacha suhbat davomiyligini koʻring.

## Maslahatlar va cheklovlar

> [!TIP]
> Agar bir nechta navbat ishlatilsa, avval **Barcha navbatlar** bilan umumiy koʻrinishni, keyin har bir
> navbatni alohida tekshiring — shunda muammoli navbatni tezroq topasiz.

- Sana oraligʻi eng koʻpi bilan **92 kun** boʻlishi kerak — undan uzunroq oraliq tanlansa, xato xabari chiqadi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| «Sana oraligʻi notoʻgʻri» xabari | Tugash sanasi boshlanishidan oldin yoki oraliq 92 kundan uzun | Sana oraligʻini qisqartiring yoki tartibini toʻgʻrilang |
| Diagramma/jadvalda «Bu davrda maʼlumot yoʻq» | Tanlangan davr/navbatda qoʻngʻiroq boʻlmagan | Davr yoki navbatni oʻzgartiring |
| KPI qiymatlari «—» koʻrinadi | Maʼlumot hali yuklanmoqda yoki mos yozuv topilmadi | Bir oz kuting; davom etsa sahifani yangilang |

## Bog'liq bo'limlar

- [Qoʻngʻiroqlar tarixi](/docs/cdr)
- [Navbatlar](/docs/queues)
- [Sifat baholash](/docs/quality)
- [Boshqaruv paneli](/docs/dashboard)
