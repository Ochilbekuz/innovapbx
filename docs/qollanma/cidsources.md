---
id: cidsources
title: CID qidirish manbalari
group: connect
order: 50
path: /cidsources
summary: Kiruvchi qoʻngʻiroqda chaqiruvchi raqamining nomini tashqi manbadan (telefon kitobi, CRM, HTTP) topish.
---

# CID qidirish manbalari

CID qidirish manbasi — [kiruvchi marshrut](/docs/inbound)ga biriktirilib, qoʻngʻiroq kirganda chaqiruvchi raqamining ismini (masalan telefon kitobi, CRM yoki tashqi HTTP xizmatidan) topib, ekranda/apparatda koʻrsatadigan sozlama.

## Qayerda

Menyu: **Ulanish → CID qidirish manbalari**. Kim koʻradi: `connect:view` ruxsati. Qoʻshish/tahrirlash/oʻchirish — `connect:edit` ruxsati; boʻlmasa **"Sizda bu manbalarni boshqarish ruxsati yoʻq — faqat koʻrish mumkin"** eslatmasi chiqadi. Sinash tugmasi koʻrish huquqi bilan ham ishlaydi.

## Asosiy tushunchalar

- **Manba turi**:
  - **Telefon kitobi** — tizimdagi ichki telefon kitobi yozuvlaridan qidiradi.
  - **CRM** — ulangan CRM integratsiyasidan qidiradi.
  - **HTTP (JSON)** — koʻrsatilgan HTTP manzilga soʻrov yuborib, JSON javobdan ismni ajratib oladi.
- **HTTP manzil**dagi `{number}` belgisi chaqiruvchi raqam bilan avtomatik almashtiriladi (masalan `https://crm.local/lookup?q={number}`).
- **JSON yoʻl** — HTTP javobidan qaysi maydonni ism sifatida olish (masalan `data.name`).
- **Taymaut** va **Keshlash muddati** — soʻrov qancha kutilishi va natija qancha vaqt eslab qolinishi (keyingi shu raqamdan qoʻngʻiroqlarda qayta soʻrov yubormaslik uchun).
- **Sinash** — har qanday manba uchun qatorda mavjud, raqam kiritib natijani (topildi/topilmadi/xato, va javob vaqti) darhol koʻrish mumkin.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| **Nom** | Manbani tanish uchun nom | — (majburiy) |
| **Turi** | Telefon kitobi / CRM / HTTP (JSON) | sukut: Telefon kitobi |
| **HTTP manzil** | *(faqat HTTP turida)* Qidirish uchun chaqiriladigan URL | `https://crm.local/lookup?q={number}` (majburiy HTTP turida) |
| **JSON yoʻl** | *(faqat HTTP turida)* Javobdan ism olinadigan maydon yoʻli | `data.name` |
| **Taymaut (ms)** | Soʻrovga javob kutish muddati | sukut: 1500 |
| **Keshlash muddati (soniya)** | Natija qancha vaqt eslab qolinadi | sukut: 3600 |
| **Yoqilgan** | Manbani vaqtincha oʻchirib qoʻyish | sukut: yoqilgan |

## Qanday qilinadi

### Yangi manba qoʻshish (Telefon kitobi yoki CRM)
1. **Yangi manba** tugmasini bosing.
2. **Nom** kiriting, **Turi**da **Telefon kitobi** yoki **CRM**ni tanlang.
3. **Qoʻshish** tugmasini bosing.

### Yangi manba qoʻshish (HTTP)
1. **Yangi manba** tugmasini bosing, **Turi**da **HTTP (JSON)**ni tanlang.
2. **HTTP manzil**ga `{number}` oʻrnini bosib koʻrsatuvchi URL kiriting.
3. Kerak boʻlsa **JSON yoʻl**ni toʻldiring, **Taymaut** va **Keshlash muddati**ni sozlang.
4. **Qoʻshish** tugmasini bosing.

### Manbani sinash
1. Jadvalda kerakli manba qatorida sinov (flakon) ikonkasini bosing.
2. **Sinov raqami** kiriting, **Ishga tushirish**ni bosing.
3. Natija: **"Topildi: <ism> (<ms> ms)"**, **"Topilmadi (<ms> ms)"** yoki **"Xato: <xabar>"** koʻrinadi.

### Manbani kiruvchi marshrutga biriktirish
1. [Kiruvchi marshrutlar](/docs/inbound) boʻlimida kerakli marshrutni tahrirlang.
2. **CID qidirish manbasi** maydonida yaratilgan manbani tanlang, ixtiyoriy **CID nom prefiksi** kiriting, **Saqlash**ni bosing.

### Manbani oʻchirish
1. Qatorda **Oʻchirish** ikonkasini bosing.
2. Agar manba hali bir kiruvchi marshrutda ishlatilayotgan boʻlsa, tizim qaysi marshrutlar ekanini koʻrsatadi va oʻchirishga ruxsat bermaydi — avval marshrutdan olib tashlang.

## Maslahatlar va cheklovlar

> [!TIP]
> Yangi HTTP manba qoʻshgandan keyin darhol **Sinash** bilan haqiqiy raqam ustida tekshirib koʻring — URL/JSON yoʻl xato boʻlsa, bu kiruvchi qoʻngʻiroqlarda ismsiz koʻrsatilishiga olib keladi.

> [!TIP]
> **Keshlash muddati**ni oshirish tashqi xizmatga yuklamani kamaytiradi, lekin CRM/telefon kitobidagi oʻzgarishlar shu muddat davomida koʻrinmay qolishi mumkin.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| "Topilmadi" (sinovda) | Raqam manbada mavjud emas yoki JSON yoʻl notoʻgʻri | JSON yoʻlni va manbadagi maʼlumotni tekshiring |
| "Xato: ..." (sinovda) | HTTP manzilga ulanib boʻlmadi yoki javob formati notoʻgʻri | URL, tarmoq va JSON formatini tekshiring |
| Manbani oʻchirib boʻlmayapti | Manba hali bir kiruvchi marshrutda ishlatilmoqda | Koʻrsatilgan marshrut(lar)dan avval olib tashlang |
| Qoʻngʻiroqda ism koʻrinmayapti | Manba kiruvchi marshrutga biriktirilmagan yoki **Yoqilgan** emas | [Kiruvchi marshrutlar](/docs/inbound)da marshrutga manbani biriktiring va yoqilganini tekshiring |

## Bog'liq bo'limlar

- [Kiruvchi marshrutlar](/docs/inbound)
- [Trunklar](/docs/trunks)
