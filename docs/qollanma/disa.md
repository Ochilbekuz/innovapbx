---
id: disa
title: DISA
group: apps
order: 100
path: /disa
summary: Tashqaridan qoʻngʻiroq qilib, PIN kiritgach, tizimning chiquvchi marshrutlaridan foydalanish (DISA).
---

# DISA

**DISA** (Direct Inward System Access) — xodim tashqarida boʻlganda oʻz telefon raqamidan ofis qoʻngʻiroq
qilib, PIN kiritib, xuddi ofisdagi telefondan qilayotgandek **tashqi raqamlarga chiquvchi qoʻngʻiroq**
qilish imkonini beradi. Masalan: safardagi xodim ofis raqamiga qoʻngʻiroq qilib, PIN kiritadi va shundan
keyin istalgan tashqi raqamni terib, ofis trunki orqali gaplashadi.

## Qayerda

Menyu: **Qoʻshimcha → DISA**. Kim koʻradi: `apps` ruxsatiga ega foydalanuvchilar tahrirlaydi, qolganlar
faqat koʻradi.

## Asosiy tushunchalar

- **DISA** — bitta sozlama toʻplami ([Kiruvchi marshrut](/docs/inbound)da yoki IVR'da manzil sifatida
  tanlanadi); tashqi qoʻngʻiroqchi shu manzilga ulanganda PIN soʻraladi.
- **PIN** — kirish uchun parol (4–8 raqam); saqlashda qaytarib olinmaydigan (HMAC) koʻrinishda saqlanadi —
  tahrirlashda koʻrinmaydi, faqat yangi PIN qoʻyish yoki olib tashlash mumkin.
- **PINsiz kirishga ruxsat** — yoqilsa, PIN kiritilmasa ham kirish mumkin; **faqat ishonchli trunklar**
  uchun tavsiya etiladi — PIN boʻsh qoldirilganda bu kalit albatta yoqilgan boʻlishi shart.
- **CID almashtirish** — DISA orqali qilingan chiquvchi qoʻngʻiroqlarda koʻrsatiladigan raqamni almashtiradi.
- **Urinishlar chegarasi** — notoʻgʻri PIN shuncha marta kiritilsa, qoʻngʻiroq avtomatik uziladi.
- DISA orqali faqat **chiquvchi marshrutlar** ochiladi — ichki xizmat kodlariga (feature code) yoʻl yoʻq.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nom | DISA sozlamasi nomi | Majburiy, koʻpi bilan 128 belgi |
| PIN | Kirish paroli | 4–8 raqam; boʻsh qoldirish faqat "PINsiz kirish" yoqilganda mumkin |
| PINsiz kirishga ruxsat | PIN soʻralmasdan kirish | Sukut — oʻchirilgan |
| CID almashtirish | Chiquvchi qoʻngʻiroqda koʻrsatiladigan raqam | Ixtiyoriy |
| Raqam kiritish kutish vaqti (soniya) | Har bir raqam orasidagi kutish | 1–60, sukut `5` |
| Javob kutish vaqti (soniya) | PIN/raqam kiritish uchun umumiy kutish | 1–60, sukut `10` |
| Maksimal urinishlar soni | Notoʻgʻri PIN qancha marta kiritilgandan keyin qoʻngʻiroq uziladi | 1–10, sukut `3` |
| Yoqilgan | DISA faol yoki vaqtincha toʻxtatilgan | Sukut — yoqilgan |

## Qanday qilinadi

### Yangi DISA yaratish
1. **Yangi DISA**ni bosing, nom kiriting.
2. PIN kiriting (4–8 raqam) yoki **PINsiz kirishga ruxsat**ni yoqib PINni boʻsh qoldiring.
3. Kerak boʻlsa CID almashtirish va vaqt/urinish sozlamalarini oʻzgartiring.
4. **Qoʻshish**ni bosing.

### DISAni kiruvchi marshrutga ulash
1. [Kiruvchi marshrutlar](/docs/inbound) yoki IVR ekranida manzil sifatida shu DISA'ni tanlang.
2. Endi shu DID/IVR tugmasiga tashqaridan qoʻngʻiroq qilganlar DISA orqali oʻtadi.

### PINni almashtirish/olib tashlash
1. DISA'ni tahrirlashga oching, **PIN** maydoniga yangi qiymat kiriting (eski PIN qayta koʻrsatilmaydi).
2. PINsiz foydalanish uchun **PINni olib tashlash**ni belgilang va **PINsiz kirishga ruxsat**ni yoqing.
3. **Saqlash**ni bosing.

### Vaqtincha oʻchirish
1. DISA'ni tahrirlashga oching, **Yoqilgan**ni oʻchiring, **Saqlash** — DISA ishlamay qoladi, lekin saqlanib qoladi.

### Oʻchirish
1. Qator oxiridagi savat belgisini bosing.
2. DISA boshqa joyda (marshrut, IVR) ishlatilayotgan boʻlsa, oʻchirish bloklanadi — avval shu bogʻlanishlarni olib tashlang; oʻchirilgandan keyin unga yoʻnaltirilgan qoʻngʻiroqlar javobsiz ohang eshittiradi.

> [!WARNING]
> **PINsiz kirishga ruxsat**ni faqat ishonchli, nazorat qilinadigan trunklarda yoqing — aks holda har
> kim ofis raqamiga qoʻngʻiroq qilib, bepul tashqi qoʻngʻiroqlar qilishi (toll fraud) mumkin.

> [!TIP]
> **Maksimal urinishlar soni**ni past (masalan 3) qilib qoʻying — PINni "qoʻpol kuch" bilan topishga urinishni qiyinlashtiradi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| "PIN boʻsh boʻlishi uchun allow_no_pin=true shart" xatosi | PIN boʻsh qoldirilgan, lekin "PINsiz kirish" yoqilmagan | PIN kiriting yoki "PINsiz kirishga ruxsat"ni yoqing |
| DISA chiquvchi qoʻngʻiroqqa ulanmayapti | Chiquvchi marshrutlar sozlanmagan yoki trunk band | [Chiquvchi marshrutlar](/docs/outbound)ni tekshiring |
| Notoʻgʻri PIN kiritilganda qoʻngʻiroq kutilganidan tez uzildi | **Maksimal urinishlar soni** kam qoʻyilgan | Sozlamada urinishlar sonini oshiring |
| DISAni oʻchirib boʻlmayapti | Marshrut/IVR'da ishlatilmoqda | Avval oʻsha bogʻlanishlarni olib tashlang |

## Bog'liq bo'limlar

- [Kiruvchi marshrutlar](/docs/inbound)
- [Chiquvchi marshrutlar](/docs/outbound)
- [IVR](/docs/ivr)
- [Xavfsizlik](/docs/security)
