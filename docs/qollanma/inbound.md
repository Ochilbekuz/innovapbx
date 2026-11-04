---
id: inbound
title: Kiruvchi marshrutlar
group: connect
order: 20
path: /inbound
summary: Tashqaridan kelayotgan qoʻngʻiroqlarni DID/CallerID boʻyicha kerakli manzilga (ichki raqam, navbat, IVR...) yoʻnaltirish.
---

# Kiruvchi marshrutlar

Kiruvchi marshrutlar — tashqaridan (operator trunki orqali) kelgan qoʻngʻiroqni qaysi DID raqamiga va qaysi chaqiruvchi raqamdan kelishiga qarab qayerga (ichki raqam, qoʻngʻiroq guruhi, navbat, IVR, ish vaqti jadvali va h.k.) yoʻnaltirishni belgilaydi.

## Qayerda

Menyu: **Ulanish → Kiruvchi marshrutlar**. Kim koʻradi: `connect:view` ruxsati. Qoʻshish/tahrirlash/oʻchirish — `connect:edit` ruxsati; boʻlmasa **"Sizda marshrutlarni boshqarish ruxsati yoʻq — faqat koʻrish mumkin"** eslatmasi chiqadi.

## Asosiy tushunchalar

- **DID** — operator sizga ajratgan tashqi telefon raqami; **Har qanday DID** yoqilsa, qaysi raqamga kelgan boʻlsa ham shu marshrutga tushadi.
- **CallerID (CID)** — qoʻngʻiroq qiluvchining raqami boʻyicha filtr; **Har qanday chaqiruvchi raqam** yoqilsa, kim qoʻngʻiroq qilsa ham moslashadi.
- **CID qidirish manbasi** — chaqiruvchi raqam nomini tashqi manbadan (telefon kitobi/CRM/HTTP) topib koʻrsatish; qoʻshimcha **CID nom prefiksi** chaqiruvchi nomi oldiga yoziladi.
- **Alert-Info** — maxsus qoʻngʻiroq ohangi yoki apparat LEDi uchun ixtiyoriy SIP sarlavhasi.
- **Qoʻngʻiroq yoʻlini koʻrish** — marshrut qayerga borib taqalishini (navbat → IVR → ichki raqam kabi zanjirni) server hisoblagan haqiqiy daraxt sifatida koʻrsatadi; tugunga bosib tegishli sahifaga oʻtish mumkin.
- **Oʻchirilgan (#id)** belgisi — marshrut manzili (masalan oʻchirilgan IVR) endi mavjud emasligini bildiradi.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| **Nom** | Marshrutni tanish uchun nom | — (majburiy) |
| **Har qanday DID** / **DID** | Qaysi tashqi raqamga mos kelishi | DID: 3–15 raqam, masalan `712000001` |
| **Har qanday chaqiruvchi raqam** / **CallerID (CID)** | Qaysi chaqiruvchi raqamga mos kelishi | masalan `+998901234567` |
| **Manzil** | Qoʻngʻiroq qayerga yoʻnaltiriladi | Ichki raqam, qoʻngʻiroq guruhi, navbat, IVR yoki ish vaqti jadvali |
| **Yoqilgan** | Marshrutni vaqtincha oʻchirib qoʻyish | sukut: yoqilgan |
| **CID qidirish manbasi** | Chaqiruvchi nomini topish uchun manba | sukut: Tanlanmagan |
| **CID nom prefiksi** | Topilgan nom oldiga qoʻshiladigan matn | masalan `Qabul: ` |
| **Alert-Info** | Maxsus ohang/LED uchun SIP sarlavhasi | masalan `Bellcore-dr2` |

## Qanday qilinadi

### Yangi kiruvchi marshrut qoʻshish
1. **Yangi marshrut** tugmasini bosing.
2. **Nom** kiriting; **Har qanday DID**ni oʻchirib aniq DID raqamini kiriting (yoki yoqilgan holda qoldiring).
3. Kerak boʻlsa **Har qanday chaqiruvchi raqam**ni oʻchirib aniq CID kiriting.
4. **Manzil** maydonida qoʻngʻiroq boradigan joyni tanlang.
5. **Qoʻshish** tugmasini bosing.

### CID qidirish va Alert-Info qoʻshish
1. Marshrutni tahrirlang.
2. **CID qidirish manbasi**ni tanlang, ixtiyoriy **CID nom prefiksi** kiriting.
3. Maxsus ohang kerak boʻlsa **Alert-Info** maydoniga qiymat kiriting, **Saqlash**ni bosing.

### Qoʻngʻiroq yoʻlini koʻrish
1. Jadvalda kerakli marshrut qatorida yoʻl (route) ikonkasini bosing.
2. Ochilgan panelda qoʻngʻiroqning haqiqiy yoʻlini (masalan IVR → navbat → ichki raqam) daraxt koʻrinishida koʻring.

## Maslahatlar va cheklovlar

> [!WARNING]
> Manzil (IVR, navbat va h.k.) oʻchirilgan boʻlsa, marshrut jadvalida **"Oʻchirilgan (#id)"** belgisi chiqadi — bu marshrutni qayta sozlamaguningizcha qoʻngʻiroqlar javobsiz qolishi mumkin.

> [!TIP]
> Bir xil DIDga bir nechta marshrut kerak boʻlsa, **CallerID (CID)** filtridan foydalanib turli chaqiruvchilarni turli manzillarga yoʻnaltirishingiz mumkin.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| "DID 3–15 ta raqamdan iborat boʻlsin" | DID maydoniga notoʻgʻri format kiritildi | Faqat raqam kiriting (+ belgisiz) |
| "CallerID notoʻgʻri formatda" | CID maydoni formatga mos emas | `+` bilan yoki bevosita raqam kiriting (3–15 raqam) |
| "Alert-Info notoʻgʻri formatda" | Ruxsat etilmagan belgilar kiritildi | Faqat lotin harf/raqam va `=<>:;/._@-` belgilaridan foydalaning |
| "Oʻchirilgan (#id)" | Marshrut manzili (IVR/navbat va h.k.) oʻchirilgan | Marshrutni tahrirlab yangi manzil tanlang |
| Qoʻngʻiroqlar kelmayapti | DID/CID hech qaysi marshrutga mos kelmayapti yoki marshrut oʻchirilgan | **Yoqilgan**ligini va DID/CIDni tekshiring, "Qoʻngʻiroq yoʻli"ni koʻring |

## Bog'liq bo'limlar

- [Trunklar](/docs/trunks)
- [CID qidirish manbalari](/docs/cidsources)
- [Chiquvchi marshrutlar](/docs/outbound)
