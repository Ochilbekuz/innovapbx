---
id: paging
title: Paging / Intercom
group: apps
order: 70
path: /paging
summary: Bir vaqtda bir nechta ichki raqamga ovozli xabar eshittirish (paging guruhi) va to'g'ridan-to'g'ri intercom qo'ng'iroq.
---

# Paging / Intercom

**Paging guruhi** — bitta raqamni terish orqali bir vaqtning oʻzida bir nechta ichki raqamga (xonadonga)
ovozli xabar eshittirish imkonini beradi. Masalan: "Hammaga eʼlon" guruhini yaratib, barcha boʻlim
telefonlariga ulab qoʻysangiz, bir raqam terib butun ofisga "Tushlik tanaffusi boshlandi" deb eʼlon qilish
mumkin.

## Qayerda

Menyu: **Ilovalar → Paging / Intercom**. Kim koʻradi: `routing` ruxsatiga ega foydalanuvchilar
tahrirlaydi, qolganlar faqat koʻradi (**"Sizda paging guruhlarini boshqarish ruxsati yoʻq"**
ogohlantirishi bilan) — garchi ekran menyuda "Ilovalar" boʻlimida koʻrsatilsa ham.

## Asosiy tushunchalar

- **Raqam** — shu raqam terilganda barcha aʼzolarga bir vaqtda ulanadi (ovozli xabar eshittiriladi).
- **Ikki tomonlama** — yoqilsa, aʼzolar ham javob berib gapirishi mumkin; oʻchirilgan boʻlsa — faqat
  bir tomonlama eʼlon (aʼzolar eshitadi, lekin javob bera olmaydi).
- **Band boʻlsa oʻtkazib yuborish** — yoqilgan boʻlsa, band turgan aʼzoga xabar yuborilmaydi.
- **Signal ohangi** — xabar boshlanishidan oldin qisqa signal (beep) eshittiriladi.
- **Intercom** (`*80<ichki raqam>`) — paging guruhidan farqli, bitta aniq ichki raqamga toʻgʻridan-toʻgʻri,
  avtomatik javob bilan ulanadigan xizmat kodi (sukut `*80`, [Xususiyat kodlari](/docs/featurecodes)da
  oʻzgartirilishi mumkin).

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nom | Guruh nomi | Koʻpi bilan 128 belgi |
| Raqam | Guruhga ulanish uchun teriladigan raqam | 1–10 ta `0-9*#` belgi |
| Ikki tomonlama | Aʼzolar javob berib gapira oladimi | Sukut — oʻchirilgan (bir tomonlama) |
| Band boʻlsa oʻtkazib yuborish | Band aʼzoga xabar yuborilmaydi | Sukut — yoqilgan |
| Signal ohangi | Xabardan oldin qisqa signal | Sukut — yoqilgan |
| Aʼzolar | Xabar eshittiriladigan ichki raqamlar | Ichki raqamlar roʻyxatidan tanlanadi |

## Qanday qilinadi

### Yangi paging guruhi yaratish
1. **Yangi guruh**ni bosing, nom va raqam kiriting.
2. Kerakli aʼzolarni (ichki raqamlarni) belgilang.
3. Kerak boʻlsa **Ikki tomonlama**, **Band boʻlsa oʻtkazib yuborish**, **Signal ohangi** sozlamalarini
   oʻzgartiring.
4. **Qoʻshish**ni bosing.

### Guruhni tahrirlash
1. Qator ustida tahrirlash tugmasini bosing, kerakli maydonlarni oʻzgartiring, **Saqlash**.

### Guruhga qoʻngʻiroq qilish
1. Istalgan ichki telefondan guruh raqamini tering — barcha aʼzolarga bir vaqtda ulanadi.

### Intercom orqali bitta raqamga toʻgʻridan-toʻgʻri ulanish
1. `*80<ichki raqam>` tering (masalan `*80205`) — qarshi tomon qurilmasi avtomatik javob beradi (agar
   qurilma intercomni qoʻllab-quvvatlasa).

### Oʻchirish
1. Qator oxiridagi savat belgisini bosing, tasdiqlang — guruh butunlay oʻchiriladi.

> [!WARNING]
> Paging guruhida bir ichki raqamda bir nechta qurilma (masalan stol telefoni + softfon) roʻyxatdan oʻtgan
> boʻlsa, hozircha **faqat birinchi roʻyxatdan oʻtgan qurilma** jiringlaydi — chunki Asterisk `Page()`
> ilovasi har manzilni oldindan "device state" bilan tekshiradi va bir raqam-koʻp qurilma birikmasini
> qabul qilmaydi (1.0.15 da aniqlangan, hali tuzatilmagan cheklov). Bir nechta qurilmali xodimlarni paging
> guruhiga qoʻshsangiz, bu holatni eʼtiborga oling.

> [!TIP]
> Faqat eshitish uchun eʼlon (masalan sexdagi dinamiklar) — **Ikki tomonlama**ni oʻchirib qoʻying, aks
> holda barcha aʼzolar mikrofoni ochilib shovqin aralashishi mumkin.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Koʻp qurilmali xodimda faqat bitta telefon jiringlayapti | Paging guruhlari hozircha faqat birinchi qurilmaga boradi (bilinarli cheklov) | Xodimning asosiy ishlatiladigan qurilmasini birinchi qilib roʻyxatdan oʻtkazing |
| Band aʼzoga ham xabar ketayapti | **Band boʻlsa oʻtkazib yuborish** oʻchirilgan | Guruh sozlamasida ushbu kalitni yoqing |
| Intercom ishlamayapti | Qarshi tomon qurilmasi avtojavobni qoʻllab-quvvatlamaydi yoki kod oʻzgartirilgan | Qurilma sozlamasini va [Xususiyat kodlari](/docs/featurecodes)dagi joriy kodni tekshiring |
| Guruhni oʻchirib boʻlmayapti | Boshqa joyda (marshrut, IVR) ishlatilmoqda | Avval oʻsha bogʻlanishlarni olib tashlang |

## Bog'liq bo'limlar

- [Xususiyat kodlari](/docs/featurecodes)
- [Ichki raqamlar](/docs/extensions)
- [Qoʻngʻiroq guruhlari](/docs/ringgroups)
