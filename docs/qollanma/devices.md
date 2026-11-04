---
id: devices
title: Telefon apparatlari
group: users
order: 20
path: /devices
summary: Fizik IP-telefonlarni avtomatik sozlash (provizioning) — qoʻshish, tugmalar, konfiguratsiyani koʻrish, jurnal.
---

# Telefon apparatlari

Bu boʻlim fizik IP-telefonlarni (Yealink, Grandstream, Fanvil va boshqalar) tarmoq orqali avtomatik sozlash uchun: apparat yoqilganda oʻzi konfiguratsiyasini yuklab oladi, qoʻlda sozlash shart boʻlmaydi.

## Qayerda

Menyu: **Foydalanuvchilar → Telefon apparatlari**. Kim koʻradi: `extensions:view` ruxsati. Toʻliq boshqarish (qoʻshish/tahrirlash/oʻchirish/tugmalar/qayta sozlash) — `extensions:edit` ruxsati; bu ruxsat boʻlmasa sahifa tepasida **"Faqat koʻrish — bu boʻlimni oʻzgartirish uchun maʼmur huquqi kerak"** banneri chiqadi.

## Asosiy tushunchalar

- **Provizioning** — apparat tarmoqdan (DHCP option 66 orqali avtomatik yoki qoʻlda kiritilgan manzildan) oʻz sozlamalar faylini yuklab olishi.
- **Topilgan qurilmalar** — roʻyxatda yoʻq MAC manzildan provizioning soʻrovi kelgan apparatlar; ichki raqamga biriktirish yoki eʼtiborsiz qoldirish mumkin.
- **Dastur tugmalari (BLF/Speed dial)** — apparat tugmalariga hamkasb holatini koʻrsatish (BLF), tezkor terish, liniya, parkovka yoki DND funksiyasini biriktirish; soni modelga bogʻliq.
- Ekranda uch tab bor: **Apparatlar**, **Sozlamalar**, **Jurnal**.

## Maydonlar

**Apparatlar** jadvali:

| Ustun | Nima koʻrsatadi |
|---|---|
| **Holat** | **Hech soʻramagan**, **Sozlandi**, **Roʻyxatda**, **Yangilanishi kerak** |
| **MAC** | Apparat MAC manzili |
| **Vendor / model** | Masalan Yealink T46S |
| **Ichki raqam** | Biriktirilgan raqam yoki **Biriktirilmagan** |
| **IP** | Oxirgi koʻrilgan IP |
| **Firmware** | Apparat firmware versiyasi |
| **Oxirgi koʻrinish** | Oxirgi soʻrov vaqti |

**Apparat qoʻshish/tahrirlash** formasi:

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| **MAC manzil** | 12 hex belgi (`:`/`-` bilan ham kiritiladi); qoʻshilgandan keyin oʻzgarmaydi | — |
| **Vendor** | Apparat ishlab chiqaruvchisi | Yealink / Grandstream / Fanvil |
| **Model** | Tanlangan vendorga mos modellar roʻyxati | — |
| **Ichki raqam** | Qaysi raqamga ulanadi | **Brauzer softfoni (WebRTC) yoqilgan raqamga apparat ulab boʻlmaydi** |
| **Yorliq** | Ixtiyoriy, jadval va konfiguratsiyada koʻrinadi | "Qabulxona" |
| **Yoqilgan** | Oʻchirilgan apparat konfiguratsiya olmaydi | sukut: yoqilgan |

## Qanday qilinadi

### Yangi apparat qoʻlda qoʻshish
1. **Apparatlar** tabida **Apparat qoʻshish** tugmasini bosing.
2. **MAC manzil**, **Vendor**, **Model** va **Ichki raqam**ni kiriting.
3. Ixtiyoriy **Yorliq** yozing, **Saqlash** tugmasini bosing.

### Topilgan qurilmani biriktirish
1. Apparat tarmoqqa ulanib hali rasmiylashtirilmagan boʻlsa, u **"Topilgan qurilmalar"** boʻlimida koʻrinadi.
2. Kerakli qatorda **Raqamga biriktirish**ni bosing.
3. **Ichki raqam** va **Model**ni tanlang, ixtiyoriy **Yorliq** kiritib tasdiqlang.
4. Kerak boʻlmasa qatorni rad etish uchun **Eʼtiborsiz qoldirish** tugmasini bosing.

### Dastur tugmalarini sozlash
1. Jadvalda kerakli apparat qatorida **Tugmalar** ikonkasini bosing.
2. Har qator uchun turni tanlang (**BLF (hamkasb)**, **Tezkor terish**, **Liniya**, **Parkovka**, **DND**, **Boʻsh**), qiymat va yorliq kiriting.
3. Modelga ruxsat etilgan tugmalar sonidan oshmasdan **Tugma qoʻshish** orqali qator qoʻshing, **Saqlash**ni bosing.

### Konfiguratsiyani koʻrish va qayta sozlash
1. Qatorda **Config** ikonkasini bosib joriy sozlamalar faylini koʻring (parollar `***` bilan yashirilgan).
2. Apparat eski sozlama bilan ishlayotgan boʻlsa — **Qayta sozlash** tugmasini bosing, apparatga yangi konfiguratsiyani olish soʻrovi yuboriladi.

### Provizioning tokenini almashtirish
1. **Apparatlar** tabi tepasidagi **Provizioning manzili** kartasida **Tokenni almashtirish**ni bosing.
2. Ogohlantirishni oʻqib tasdiqlang — eski manzil darhol ishlamay qoladi, barcha apparatlarga yangi manzil qoʻlda kiritilishi yoki DHCP orqali avtomatik yangilanishi kerak boʻladi.

## Maslahatlar va cheklovlar

> [!TIP]
> DHCP serveringizda **option 66**ni provizioning URL manziliga sozlasangiz, yangi apparatlar hech qanday qoʻlda sozlashsiz avtomatik ishga tushadi.

> [!WARNING]
> **Brauzer softfoni (WebRTC)** yoqilgan ichki raqamga fizik apparat ulab boʻlmaydi — ikkisi bir raqamda birga ishlamaydi.

> [!WARNING]
> Provizioning tokenini almashtirgandan keyin DHCP orqali manzil olmagan barcha apparatlarda yangi URL qoʻlda kiritilishi kerak, aks holda ular yangi konfiguratsiyani ola olmaydi.

> [!NOTE]
> Bir ichki raqamga bir nechta apparat biriktirilgan boʻlsa, toʻgʻridan-toʻgʻri qoʻngʻiroqlarda hammasi bir vaqtda jiringlaydi. Navbat aʼzosi, API orqali qoʻngʻiroq chiqarish va paging guruhlarida faqat bitta apparat jiringlaydi — bu Asterisk `Page()` cheklovi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| "Nomaʼlum MAC" (jurnalda) | Roʻyxatda yoʻq apparat provizioning soʻrovi yubordi | "Topilgan qurilmalar" boʻlimida biriktiring |
| "Notoʻgʻri token" | Apparatda eski provizioning manzili qolgan | Apparatga yangi URL/DHCP manzilini qoʻlda kiriting |
| "Tarmoq rad etildi" | Apparat IP manzili **Sozlamalar** tabidagi ruxsat etilgan tarmoqlar roʻyxatiga kirmaydi | Sozlamalar tabida **Ruxsat etilgan tarmoqlar (CIDR)**ga apparat tarmogʻini qoʻshing |
| **Yangilanishi kerak** holati | Apparat konfiguratsiyasi oʻzgargan, lekin apparat hali yangisini olmagan | **Qayta sozlash** tugmasini bosing yoki apparatni qayta yuklang |
| "Limit oshdi" (jurnalda) | Bir apparatdan juda tez-tez soʻrov kelayapti | Biroz kutib qayta urinib koʻring; davom etsa tarmoq/apparat sozlamasini tekshiring |

## Bog'liq bo'limlar

- [Ichki raqamlar](/docs/extensions)
- [Mening kabinetim](/docs/portal)
