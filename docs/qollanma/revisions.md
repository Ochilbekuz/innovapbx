---
id: revisions
title: Konfiguratsiya reviziyalari
group: system
order: 25
path: /settings/revisions
summary: Har bir sozlama saqlanganda yaratiladigan reviziya tarixi — farqni koʻrish va avvalgi holatga qaytarish.
---

# Konfiguratsiya reviziyalari

Tizimdagi deyarli har bir sozlama saqlanganda (trunk, marshrut, ichki raqam va h.k.) yangi **reviziya**
yaratiladi — bu xuddi "versiyalar tarixi" kabi. Agar biror oʻzgarish keyin muammo keltirib chiqarsa, shu
yerdan avvalgi holatga qaytarish mumkin.

## Qayerda
Sahifa sarlavhasidagi **reviziya belgisi** (joriy reviziya raqami) orqali ochiladi, yoki **Tizim →
Reviziyalar**. Kim koʻradi: faqat `*` (toʻliq administrator) ruxsati bor foydalanuvchi.

## Asosiy tushunchalar

- **Reviziya** — bir vaqtdagi barcha sozlamalar holatining suratga olingan nusxasi, `r<raqam>` koʻrinishida.
- **Holat**: Qoʻllandi (muvaffaqiyatli kuchga kirgan), Qaytarildi (keyinroq orqaga qaytarilgan), Qoʻllanmoqda
  (hozir amalga oshirilayotgan).
- **Farq (diff)** — tanlangan reviziyani **avvalgisi** yoki **joriy holat** bilan solishtirib, qaysi
  qatorlar qoʻshilgan (+) yoki olib tashlangan (−) koʻrsatadi.

## Qanday qilinadi

### Reviziyalar tarixini koʻrish
1. Sahifaning chap tomonidagi roʻyxatdan kerakli reviziyani tanlang — har birida sana, foydalanuvchi va
   qisqa izoh koʻrsatiladi.
2. Oʻng tomonda **Avvalgisi bilan solishtirish** yoki **Joriy holat bilan solishtirish**ni tanlab, farqni
   koʻring (qizil — olib tashlangan, yashil — qoʻshilgan qatorlar).

### Avvalgi holatga qaytarish
1. Kerakli reviziyani tanlang.
2. **Shu holatga qaytarish**ni bosing.
3. Ogohlantirish oynasida oʻqib, **Qaytarish**ni tasdiqlang.
4. Tizim joriy sozlamalarni tanlangan reviziya holatiga qaytaradi va buni **yangi reviziya** sifatida
   qoʻllaydi (eski reviziyalar oʻchirilmaydi).

## Maslahatlar va cheklovlar

> [!WARNING]
> Avvalgi holatga qaytarish joriy sozlamalarni **almashtiradi** — qaytarilgan paytdan keyin qilingan barcha
> oʻzgarishlar yoʻqoladi (lekin ular tarixda reviziya sifatida saqlanib qoladi, kerak boʻlsa yana oldinga
> qaytarish mumkin).

> [!TIP]
> Nimani qaytarayotganingizni aniq bilish uchun avval **farqni** koʻrib chiqing, keyin qaytarishni
> tasdiqlang.

- Har bir qaytarish [Audit jurnali](/docs/audit)da alohida yozuv sifatida qayd etiladi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| «Yuklab boʻlmadi» | Server bilan aloqa uzilgan | **Qayta urinish**ni bosing |
| «Farq topilmadi — bu birinchi reviziya boʻlishi mumkin» | Tanlangan reviziyadan oldin boshqa reviziya yoʻq | Odatiy holat, tashvishlanmang |
| Qaytarib boʻlmadi | Server xatosi yoki tarmoq muammosi | Xabar matnini oʻqing, qayta urinib koʻring; davom etsa administratorga murojaat qiling |

## Bog'liq bo'limlar

- [Audit jurnali](/docs/audit)
- [Boshqaruv paneli](/docs/dashboard)
