---
id: kirish
title: Kirish
group: start
order: 10
summary: Innova PBX nima, nimalardan iborat va bu qo'llanma qanday tuzilgan — umumiy tanishtiruv.
---

# Kirish

Innova PBX — Asterisk 22 ustida qurilgan, o'z veb-paneli bo'lgan IP-ATS (telefon stansiyasi): xodimlarning ichki raqamlarini, tashqi aloqa (trunk) liniyalarini, kiruvchi/chiquvchi qo'ngʻiroq yoʻnalishlarini, navbatlarni, konferensiya va boshqa aloqa vositalarini bitta brauzer oynasidan boshqarish imkonini beradi. Bu qo'llanma panelning har bir boʻlimini qadamma-qadam tushuntiradi.

## Asosiy tushunchalar

- **Texnik asos** — Asterisk 22 (qoʻngʻiroqlarni ulovchi "yurak"), FastAPI + PostgreSQL 16 (sozlamalar va maʼlumotlarni boshqaruvchi server), React (veb-panelning oʻzi). Hammasi Docker Compose orqali bitta serverda ishlaydi.
- **Veb-panel** — brauzer orqali ochiladigan boshqaruv markazi; chap menyu orqali boʻlimlar orasida yuriladi, har sahifa sarlavhasidagi **?** belgisi aynan shu boʻlim qoʻllanmasini ochadi.
- **Rollar** — har foydalanuvchiga rol biriktiriladi, rol esa qaysi boʻlimlarni koʻrish/oʻzgartirish mumkinligini belgilaydi (batafsil: [Rollar va ruxsatlar](/docs/rollar)).
- **Boʻlim guruhlari** — panel menyusi mantiqan guruhlangan: **Monitoring** (boshqaruv paneli, jonli holat), **Foydalanuvchilar** (ichki raqamlar, apparatlar, shaxsiy kabinet), **Ulanish** (trunklar, kiruvchi/chiquvchi marshrutlar, PIN toʻplamlari, CID manbalari), **Yoʻnaltirish** (vaqt guruhlari, IVR, navbatlar va h.k.), **Ilovalar** (audio, konferensiya, parkovka va h.k.), **Hisobotlar** (qoʻngʻiroqlar tarixi va tahlil), **Tizim** (sozlamalar, xavfsizlik, zaxira nusxalash — faqat administratorga).

## Qanday qilinadi

### Qo'llanmadan foydalanish
1. Chap menyudagi **Qoʻllanma** boʻlimini oching yoki istalgan sahifada sarlavha yonidagi **?** belgisini bosing — aynan shu sahifaga tegishli boʻlim ochiladi.
2. Har bir boʻlim bir xil tartibda tuzilgan: nima uchun kerak, maydonlar jadvali, qadamma-qadam koʻrsatmalar, maslahat/ogohlantirishlar va koʻp uchraydigan muammolar jadvali.

### Birinchi marta ishlatishni boshlash
1. Agar tizim hali oʻrnatilmagan boʻlsa — [O'rnatish](/docs/ornatish) boʻlimidan boshlang.
2. Oʻrnatilgandan keyin birinchi ochilishda chiqadigan sozlash sahifasini [Birinchi sozlash](/docs/birinchi-sozlash) boʻlimi orqali oʻtang.
3. Keyin [Tezkor boshlash](/docs/tez-boshlash) boʻlimidagi qadamlar bilan birinchi ichki raqam va qoʻngʻiroq yoʻnalishini sozlang.

## Maslahatlar va cheklovlar

> [!TIP]
> Qoʻllanmaning **start** guruhi (shu boʻlim, oʻrnatish, birinchi sozlash, tezkor boshlash, rollar) — yangi boshlaganlar uchun tartib boʻyicha oʻqilishi moʻljallangan.

> [!NOTE]
> Panel versiyasi (hozircha 1.0.15) sozlamalar boʻlimida koʻrinadi; yangilash haqida [O'rnatish](/docs/ornatish) boʻlimida yozilgan.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Menyuda kutilgan boʻlim koʻrinmayapti | Foydalanuvchi roliga shu boʻlim uchun ruxsat berilmagan | [Rollar va ruxsatlar](/docs/rollar) boʻlimini koʻring, administratordan soʻrang |
| Qaysidan boshlashni bilmayman | Tizim yangi oʻrnatilgan | [O'rnatish](/docs/ornatish) → [Birinchi sozlash](/docs/birinchi-sozlash) → [Tezkor boshlash](/docs/tez-boshlash) tartibida oʻtiling |

## Bog'liq bo'limlar

- [O'rnatish](/docs/ornatish)
- [Birinchi sozlash](/docs/birinchi-sozlash)
- [Tezkor boshlash](/docs/tez-boshlash)
- [Rollar va ruxsatlar](/docs/rollar)
