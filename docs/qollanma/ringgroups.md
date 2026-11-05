---
id: ringgroups
title: Qoʻngʻiroq guruhlari
group: routing
order: 40
path: /ringgroups
summary: Bir nechta ichki raqam/tashqi raqamga bir vaqtda yoki tartib bilan jiringlatish (masalan "Buxgalteriya").
---

# Qoʻngʻiroq guruhlari

**Qoʻngʻiroq guruhi** — bir qoʻngʻiroqni bir nechta raqamga yoʻnaltiradi: masalan "Buxgalteriya" guruhiga
qoʻngʻiroq kelganda, boʻlimdagi barcha xodimlarning telefoni bir vaqtda jiringlaydi. Navbatdan farqi — bu yerda
kutish/navbat mantig‘i yoʻq, faqat "qaysi birisi birinchi koʻtaradi" tamoyili ishlaydi.

## Qayerda

Menyu: **Marshrutlash → Qoʻngʻiroq guruhlari**. Kim koʻradi: `routing` ruxsatiga ega foydalanuvchilar
tahrirlaydi, qolganlar faqat koʻradi.

## Asosiy tushunchalar

- **Strategiya** — qoʻngʻiroq aʼzolarga qanday yetib boradi (jadvalga qarang).
- **Aʼzo** — ichki raqam **yoki** tashqi raqam (mobil telefon kabi) boʻlishi mumkin, ikkisini bitta aʼzoda
  birga berib boʻlmaydi.
- **Koʻrsatiladigan raqam old qoʻshimchasi** — operator telefonida kiruvchi raqam oldiga qoʻshiladigan matn
  (masalan "SOTUV: "), shu orqali operator qaysi guruhdan qoʻngʻiroq kelayotganini biladi.
- **Javob boʻlmasa** manzili — hech kim koʻtarmasa (yoki belgilangan davomiylik tugasa) qoʻngʻiroq qayerga
  boradi.

## Maydonlar

Tahrirlash oynasi FreePBX **Ring Groups** moduli andozasiga yaqinlashtirilib beshta boʻlimga boʻlingan:
**Umumiy**, **Aʼzolar**, **Jiringlash va eʼlonlar**, **Caller ID**, **Kengaytirilgan**.

### Umumiy

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nom | Guruh nomi | — |
| Raqam | Ixtiyoriy — toʻgʻridan-toʻgʻri terish uchun | 2–10 ta `0-9*#` belgi |
| Strategiya | Aʼzolarga jiringlash tartibi | Sukut — **Hammasi birdan** |
| Qoʻngʻiroq davomiyligi (soniya) | Javob kutish vaqti | 5–300, sukut 20 |

### Aʼzolar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Aʼzolar | Ichki raqamlar va/yoki tashqi raqamlar roʻyxati, tartib bilan | — |

### Jiringlash va eʼlonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Eʼlon (qoʻngʻiroqdan oldin) | Aʼzolarga ulanishdan oldin chaqiruvchiga chalinadigan ovoz | Ixtiyoriy, sukut — yoʻq |
| Jiringlash paytida | Oddiy jiringlash ohangi yoki kutish musiqasi (MOH) sinfi | Sukut — oddiy ohang |
| Kutish musiqasi sinfi | "Jiringlash paytida" = MOH boʻlsa, qaysi sinf chalinadi | Faqat MOH tanlanganda koʻrinadi |
| Alert-Info | IP-telefonga maxsus ring-tone tanlash koʻrsatmasi (SIP sarlavhasi) | Ixtiyoriy, masalan `Internal` |
| Band aʼzoni oʻtkazib yuborish | Telefonda gaplashayotgan aʼzoga jiringlamaydi | Sukut — oʻchirilgan |
| Qoʻngʻiroqni tasdiqlash | Aʼzo javob berganda qabul qilishni 1 tugmasi bilan tasdiqlashni soʻraydi | Sukut — oʻchirilgan |
| Tasdiqlash eʼloni | "Qoʻngʻiroqni tasdiqlash" yoqilganda aʼzoga tasdiqlashdan oldin chalinadigan ovoz | Faqat tasdiqlash yoqilganda koʻrinadi |

### Caller ID

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Koʻrsatiladigan raqam old qoʻshimchasi | Operator ekranida kiruvchi raqam oldiga qoʻshiladi | Ixtiyoriy, masalan `SOTUV: ` |

### Kengaytirilgan

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Suhbatni yozib olish | Shu guruh orqali oʻtgan qoʻngʻiroqlarni yozib olish siyosati | Sukut — **Oʻzgartirmaslik** (ichki raqam sozlamasiga qaraydi) |
| Hech kim javob bermasa | Vaqt tugaganda boradigan manzil | Majburiy |

### Strategiyalar

| Strategiya | Qanday ishlaydi |
|---|---|
| Hammasi birdan (`ringall`) | Barcha aʼzolarga bir vaqtda jiringlaydi (sukut) |
| Hammasi birdan, birinchisi asosiy (`ringall-prim`) | `ringall` bilan bir xil, lekin faqat 1-aʼzo asosiy hisoblanadi |
| Navbat bilan (`hunt`) | Roʻyxat tartibida birin-ketin, har birida qoʻngʻiroq davomiyligi davomida |
| Navbat bilan, birinchisi asosiy (`hunt-prim`) | `hunt` bilan bir xil, lekin 1-aʼzo asosiy hisoblanadi |
| Yigʻilib boruvchi (`memoryhunt`) | Birinchi aʼzoga jiringlaydi, keyin 1+2ga, keyin 1+2+3ga... — oldingilar jiringlashda qoladi |
| Yigʻilib boruvchi, birinchisi asosiy (`memoryhunt-prim`) | `memoryhunt` bilan bir xil, lekin 1-aʼzo asosiy hisoblanadi |
| Birinchi boʻsh ichki raqam (`firstavailable`) | Faqat band boʻlmagan birinchi aʼzoga jiringlaydi |
| Birinchi band boʻlmagan ichki raqam (`firstnotonphone`) | `firstavailable`ga oʻxshash, telefon holatiga qarab tanlaydi |

> [!NOTE]
> FreePBX'da Ring Group strategiyasi sifatida koʻrinadigan **"random"** aslida faqat Navbatlar (Queue)
> moduliga tegishli — Ring Groups'da haqiqiy Asterisk opsiyasi emas, shuning uchun bu yerga ataylab
> qoʻshilmagan.

## Qanday qilinadi

### Yangi guruh yaratish
1. **Guruh qoʻshish**ni bosing, nom va strategiyani tanlang.
2. **+ Ichki raqam qoʻshish** orqali aʼzolarni qoʻshing; tashqi raqam qoʻshish uchun maxsus maydonga raqamni kiritib qoʻshing (`+998901234567` formatida, 3–15 belgi).
3. **Hech kim javob bermasa** manzilini tanlang (masalan ovozli pochta).
4. **Qoʻshish**ni bosing.

### Tashqi raqam qoʻshish
1. Aʼzolar roʻyxati pastidagi "tashqi" maydoniga raqamni kiriting va qoʻshing.
2. Notoʻgʻri formatdagi yoki allaqachon qoʻshilgan raqam xato koʻrsatadi.

### Aʼzo tartibini oʻzgartirish
1. `Navbat bilan` yoki `Yigʻilib boruvchi` strategiyasida tartib muhim — qatorni sudrab kerakli oʻringa qoʻying.

### Qoʻngʻiroq guruhini kiruvchi marshrutga ulash
1. [Kiruvchi marshrutlar](/docs/inbound) ekranida DID manzilini shu guruhga yoʻnaltiring.
2. Yoki IVR tugmasida/ish vaqti shartida manzil sifatida tanlang.

### Oʻchirish
1. Qator oxiridagi savat belgisini bosing.
2. Guruh boshqa joyda ishlatilayotgan boʻlsa, oʻchirish bloklanadi — avval shu bogʻlanishlarni olib tashlang.

> [!TIP]
> "Koʻrsatiladigan raqam old qoʻshimchasi"ni har bir guruhga alohida nom bilan belgilang — bir nechta guruhga kiradigan operator qaysi yoʻnalishdan qoʻngʻiroq kelayotganini ekranidan koʻra oladi.

> [!WARNING]
> Tashqi raqamga jiringlash davomiyligi umumiy operator tarifiga qoʻshimcha xarajat bo'lishi mumkin — "Qoʻngʻiroq davomiyligi"ni haddan tashqari uzun qilib qoʻymang.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Tashqi raqam qoʻshilmayapti | Format notoʻgʻri yoki allaqachon qoʻshilgan | Faqat raqamlar, 3–15 belgi, `+` ixtiyoriy bilan kiriting |
| `Yigʻilib boruvchi`da hamma birdan jiringlayapti | Qoʻngʻiroq davomiyligi juda qisqa, keyingi aʼzo tez qoʻshilib ketadi | Davomiylikni oshiring |
| Guruhni oʻchirib boʻlmayapti | Kiruvchi marshrut yoki boshqa manzilda ishlatilmoqda | Avval oʻsha bogʻlanishlarni olib tashlang |

## FreePBX'dan ataylab qoʻshilmagan maydonlar

- **Ignore CF (forward)/CW (call waiting)/Call pickup** — semantikasi aʼzo qurilmasi sozlamalari bilan
  chalkashadi, Innova'da mos funksiya yoʻq.
- **Too-late announce** — "Qoʻngʻiroqni tasdiqlash" vaqti tugaganda oʻqiladigan maxsus eʼlon — alohida
  foyda kam, tasdiqlash oqimi "Tasdiqlash eʼloni" bilan yetarli qamrab olingan.
- **Change external CID / Fixed external CID** — bu ustunlar haqiqiy FreePBX bazasida ham mavjud emas
  (eskirgan/ishlatilmaydigan), shuning uchun ixtiro qilinmadi.

## Bog'liq bo'limlar

- [Kiruvchi marshrutlar](/docs/inbound)
- [Ichki raqamlar](/docs/extensions)
- [Ish vaqti](/docs/timegroups)
