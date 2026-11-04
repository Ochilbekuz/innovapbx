---
id: audit
title: Audit jurnali
group: system
order: 20
path: /settings/audit
summary: Tizimdagi barcha yozish amallari va kirishlarning izi — kim, qachon, nimani oʻzgartirgan.
---

# Audit jurnali

Tizimda kim nima qilgani (kim yaratdi, oʻzgartirdi, oʻchirdi, kirdi/kira olmadi, qayta tikladi va h.k.)
toʻliq ro'yxati. Masalan, trunk sozlamasi kutilmaganda oʻzgargan boʻlsa — bu yerdan qaysi foydalanuvchi va
qachon oʻzgartirganini, eski va yangi qiymatini aniq koʻrish mumkin.

## Qayerda
Menyu: **Tizim → Audit jurnali**. Kim koʻradi: faqat `*` (toʻliq administrator) ruxsati bor foydalanuvchi.

## Asosiy tushunchalar

- **Amal turi**: Yaratildi, Oʻzgartirildi, Oʻchirildi, Kirildi, Kirish xato, Qaytarildi, Qayta ishga
  tushirildi, Vaqtincha oʻzgartirildi, Tinglash/kirish.
- **Obʼyekt** — nimaga amal qilingani (masalan `trunk`, `extension`, `user`).
- Agar amal boʻyicha aniq oʻzgarish tafsiloti mavjud boʻlsa, qatorda koʻz belgisi chiqadi — bosib eski/yangi
  qiymatlarni koʻrish mumkin. Parollar va boshqa maxfiy qiymatlar jurnalda `***` bilan yashiriladi.
- «Kim» ustunida tizim oʻzi bajargan amallar uchun **tizim** deb koʻrsatiladi (foydalanuvchisiz).

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Boshlanishi / Tugashi | Sana oraligʻi | Sukut: oxirgi 30 kun |
| Amal | Amal turi boʻyicha filtr | Sukut: Hammasi |
| Obʼyekt turi | Matn boʻyicha filtr (ixtiyoriy) | `trunk`, `extension` |
| Qidirish | Login yoki obʼyekt nomi boʻyicha erkin qidiruv (ixtiyoriy) | — |

## Qanday qilinadi

### Oʻzgarishlarni filtrlab topish
1. **Boshlanishi**/**Tugashi** sanasini belgilang.
2. Kerak boʻlsa **Amal** turini tanlang (masalan, faqat «Oʻchirildi»).
3. **Obʼyekt turi** maydoniga `trunk`, `extension` kabi matn kiritib, faqat shu turdagi yozuvlarni koʻring.
4. **Qidirish** maydoniga login yoki obʼyekt nomini kiritib, tezkor topish.

### Oʻzgarish tafsilotini koʻrish
1. Qator oxiridagi koʻz belgisini bosing (faqat tafsilot mavjud yozuvlarda koʻrinadi).
2. Ochilgan oynada har bir oʻzgargan maydon uchun **eski** (qizil) va **yangi** (yashil) qiymat koʻrsatiladi.

## Maslahatlar va cheklovlar

> [!TIP]
> Shubhali holat (masalan, kutilmagan konfiguratsiya oʻzgarishi) boʻlsa — avval **Amal: Oʻzgartirildi** va
> tegishli **Obʼyekt turi** bilan filtrlab, aybdor foydalanuvchi va vaqtni tezda aniqlash mumkin.

- Jurnal faqat koʻrish uchun — bu yerdan hech narsani oʻchirish yoki tahrirlash mumkin emas.
- Parol va shunga oʻxshash maxfiy maydonlar har doim `***` koʻrinishida — haqiqiy qiymat hech qachon
  koʻrsatilmaydi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| «Bu filtrga mos yozuv topilmadi» | Sana oraligʻi yoki filtr juda tor | Filtrlarni kengaytiring yoki boshqattan tekshiring |
| Koʻz belgisi koʻrinmaydi | Bu yozuv uchun oʻzgarish tafsiloti saqlanmagan (masalan, kirish amali) | Odatiy holat — barcha amal turlarida tafsilot boʻlmaydi |

## Bog'liq bo'limlar

- [Konfiguratsiya reviziyalari](/docs/revisions)
- [Foydalanuvchilar va rollar](/docs/rollar)
- [Xavfsizlik](/docs/security)
