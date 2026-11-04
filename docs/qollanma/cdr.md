---
id: cdr
title: Qoʻngʻiroqlar tarixi
group: reports
order: 10
path: /cdr
summary: Barcha qoʻngʻiroqlarning tarixi — sana/yoʻnalish filtri, kengaytirilgan qidiruv, yozuvlarni tinglash, CSV eksport.
---

# Qoʻngʻiroqlar tarixi

Bu yerda IP-ATS orqali oʻtgan HAR BIR qoʻngʻiroq saqlanadi: kim qoʻshdi, kimga, qachon, necha soniya davom etdi,
qanday tugadi (javob berildi/javobsiz/band) va, agar yozib olish yoqilgan boʻlsa, ovoz yozuvi. Masalan, mijoz
«menga hech kim qayta telefon qilmadi» desa — shu yerdan uning raqamini qidirib, qachon va kimga qoʻngʻiroq
qilganini koʻrish mumkin.

## Qayerda
Menyu: **Hisobotlar → Qoʻngʻiroqlar tarixi**. Kim koʻradi: `reports:view`/`reports:edit` ruxsati bor foydalanuvchi —
**barcha** qoʻngʻiroqlarni; faqat `calls:read:own` ruxsati bor operator — **faqat oʻzining** ichki raqamiga
tegishli (kelgan yoki ketgan) qoʻngʻiroqlarni.

## Asosiy tushunchalar

- **Yoʻnalish**: Kiruvchi (tashqaridan), Chiquvchi (tashqariga), Ichki (ikki ichki raqam orasida).
- **Natija (disposition)**: Javob berildi, Javobsiz, Band, Muvaffaqiyatsiz.
- **DID** — kiruvchi qoʻngʻiroq kelgan tashqi raqam (trunkdagi raqam).
- **Hisob (accountcode)** — qoʻngʻiroqqa biriktirilgan PIN hisob belgisi (`/pinsets` bilan bogʻliq boʻlsa).
- **Sifat (QA)** — shu qoʻngʻiroqqa baho qoʻyilgan boʻlsa, foiz bilan koʻrsatiladi (batafsil — [Sifat baholash](/docs/quality)).

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Boshlanishi / Tugashi | Sana oraligʻi (sana + soat:daqiqa, Toshkent vaqti) | Sukut: oxirgi 7 kun, 00:00–23:59 |
| Yoʻnalish | Hammasi / Kiruvchi / Chiquvchi / Ichki | Sukut: Hammasi |
| **Kengaytirilgan qidiruv** → Kimdan (src) | Qoʻngʻiroq qiluvchi raqam — moslik rejimi bilan (tarkibida/boshlanishi/tugashi/aniq mos) + «Emas» (inkor) | Masalan: `99890` |
| Kimga (dst) | Qabul qiluvchi raqam — xuddi shu rejim/inkor bilan | Masalan: `99890` |
| DID | Kiruvchi tashqi raqam — xuddi shu rejim/inkor bilan | Masalan: `998712345678` |
| Qoʻngʻiroq qiluvchi nomi | Aniq matn boʻyicha qidirish | — |
| Ichki raqam (ext) | Aniq matn boʻyicha qidirish | — |
| Trunk | Trunk nomi boʻyicha qidirish | — |
| Hisob (accountcode) | Hisob kodi boʻyicha qidirish | — |
| Yozuv | Hammasi / Yozuvi bor / Yozuvi yoʻq | Sukut: Hammasi |
| Davomiyligi (soniya) | Dan/Gacha — butun, manfiy boʻlmagan son | — |
| Natija | Bir nechta belgi tanlash mumkin (Javob berildi, Javobsiz, Band, Muvaffaqiyatsiz) | Sukut: hammasi |

## Qanday qilinadi

### Oddiy qidiruv (sana + yoʻnalish)
1. **Boshlanishi**/**Tugashi** sanasi va soatini tanlang (sukut — oxirgi 7 kun).
2. Kerak boʻlsa **Yoʻnalish**ni tanlang.
3. Jadval avtomatik yangilanadi.

### Kengaytirilgan qidiruv
1. **Kengaytirilgan qidiruv** tugmasini bosing — panel ochiladi (FreePBX «CDR Reports» uslubida).
2. Kimdan/Kimga/DID uchun moslik rejimini (tarkibida, boshlanishi, tugashi, aniq mos) tanlang, kerak boʻlsa
   **Emas** (inkor) belgisini qoʻying — masalan, "DID tarkibida `998` **emas**" qoʻng'iroqlarni topish uchun.
3. Boshqa maydonlarni (nom, ext, trunk, hisob, davomiylik, natija, yozuv) toʻldiring.
4. **Qidirish** tugmasini bosing. Faol filtrlar soni tugma yonida belgi bilan koʻrsatiladi.
5. **Tozalash** — barcha kengaytirilgan filtrlarni bekor qiladi.

### Qidiruv shablonini saqlash va qayta ishlatish
1. Kengaytirilgan panelda kerakli filtrlarni toʻldiring.
2. **Joriy qidiruvni saqlash** maydoniga nom kiritib, **Saqlash**ni bosing (xuddi shu nomdagi eski shablon
   almashtiriladi).
3. Keyinchalik **Saqlangan shablon** roʻyxatidan tanlab, **Qoʻllash**ni bosing — forma toʻliq tiklanadi.
4. Kerak boʻlmasa, shablonni tanlab oʻchirish belgisi orqali oʻchirib tashlash mumkin.
5. Shablonlar faqat shu brauzerda saqlanadi (`localStorage`) — boshqa qurilma/brauzerda koʻrinmaydi.

### Yozuvni tinglash, yuklab olish, oʻchirish
1. Jadvalda **Yozuv** ustunida pleer tugmasini bosib, bevosita shu yerdan tinglang (ijro tezligini ham
   oʻzgartirish mumkin).
2. Yuklab olish belgisini bosib, `.wav` faylni saqlang — fayl nomi avtomatik `sana_vaqt_kimdan_kimga` shaklida
   shakllanadi.
3. Faqat `reports:edit` ruxsati bor foydalanuvchi — oʻchirish belgisini bosib, tasdiqlab, yozuvni butunlay
   oʻchirishi mumkin.

### Qoʻngʻiroqni baholash
1. Jadvalda **Sifat** ustunidagi **Baholash** tugmasini bosing — baholash paneli ochiladi.
2. Batafsil — [Sifat baholash](/docs/quality).

### Kiruvchi raqamni qora roʻyxatga qoʻshish
1. Faqat kiruvchi qoʻngʻiroq qatorida **Bloklash** tugmasi koʻrinadi.
2. Sabab (ixtiyoriy) kiritib, **Qoʻshish**ni bosing — raqam [Qora roʻyxat](/docs/blacklist)ga qoʻshiladi va
   keyingi qoʻngʻiroqlari avtomatik rad etiladi.

### CSV eksport qilish
1. Kerakli sana oraligʻi va filtrlarni qoʻllang.
2. **CSV eksport** tugmasini bosing — `calls.csv` fayli yuklab olinadi (joriy filtrlarga mos).

## Maslahatlar va cheklovlar

> [!TIP]
> Tezkor qidiruv uchun jadval ustidagi oddiy qidiruv maydoni ham ishlaydi (raqam/DID boʻyicha) — kengaytirilgan
> panelni ochmasdan.

> [!WARNING]
> Yozuvni oʻchirish qaytarilmaydi — fayl serverdan butunlay olib tashlanadi.

- CSV eksportda bir martada koʻpi bilan **10 000** qatorgacha chiqariladi — juda keng oraliqda qidirsangiz,
  filtr qoʻshib qisqartiring.
- Operator roli faqat oʻz ichki raqamiga tegishli qoʻngʻiroqlarni koʻradi — bloklash va yozuvni oʻchirish
  tugmalari unga koʻrinmaydi/faol emas.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| «Bu oraliqda qoʻngʻiroq topilmadi» | Sana oraligʻi yoki filtr juda tor | Sana oraligʻini kengaytiring yoki kengaytirilgan filtrlarni **Tozalash** bilan bekor qiling |
| Yozuv ustuni boʻsh | Qoʻngʻiroqda yozib olish yoqilmagan edi yoki fayl topilmadi | Yozib olish sozlamasini tekshiring (trunk/kengaytirilgan sozlamalar) |
| Yozuvni tinglashda xato chiqadi | Audio fayl buzilgan yoki server bilan aloqa uzilgan | Sahifani yangilang; davom etsa, administratorga murojaat qiling |
| Bloklash tugmasi koʻrinmaydi | Qoʻngʻiroq kiruvchi emas yoki ruxsat yoʻq | Faqat kiruvchi qoʻngʻiroqlarda va `apps:edit` ruxsati bilan ishlaydi |

## Bog'liq bo'limlar

- [Jonli monitoring](/docs/live)
- [Sifat baholash](/docs/quality)
- [Qora roʻyxat](/docs/blacklist)
- [Analitika](/docs/analytics)
