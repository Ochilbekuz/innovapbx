---
id: portal
title: Mening kabinetim
group: users
order: 30
path: /me
summary: Har bir xodim uchun shaxsiy sahifa — DND, yoʻnaltirish, navbat, statistika, ovozli pochta, 2FA, brauzer telefoni.
---

# Mening kabinetim

**Mening kabinetim** — har bir foydalanuvchining oʻz ichki raqami bilan ishlashi uchun shaxsiy sahifa: band qilmaslik va yoʻnaltirishni boshqarish, navbatga kirish/chiqish, bugungi statistikani koʻrish, soʻnggi qoʻngʻiroqlar va ovozli xabarlarni eshitish, hisobni ikki bosqichli tasdiqlash bilan himoyalash.

## Qayerda

Menyu: **Foydalanuvchilar → Mening kabinetim**. Kim koʻradi: tizimga kirgan har qanday foydalanuvchi, oʻziga tegishli maʼlumot boʻyicha (`me:*`). Agar hisobga ichki raqam biriktirilmagan boʻlsa, sahifada **"Ichki raqam bogʻlanmagan"** xabari chiqadi va qolgan boʻlimlar koʻrinmaydi — adminga murojaat qiling.

## Asosiy tushunchalar

- **Band qilmaslik (DND)** — yoqilganda sizga qoʻngʻiroqlar yetib bormaydi.
- **Qoʻngʻiroqlarni yoʻnaltirish** — barcha kiruvchi qoʻngʻiroqlarni boshqa ichki/tashqi raqamga doimiy yoʻnaltirish (shartsiz yoʻnaltirish).
- **Follow Me** — band/javobsiz holatda qoʻngʻiroqni ketma-ket boshqa raqamlarga sinab koʻrish qoidalari (batafsil — [Ichki raqamlar](/docs/extensions)).
- **Telefonga ulash (QR)** — mobil Linphone ilovasini QR kod orqali parolsiz sozlash; havola bir martalik va 60 soniyadan keyin yaroqsiz boʻladi.
- **Brauzer telefoni** — sahifa yuqori qismidagi (header) softfon chipi: WebRTC orqali toʻgʻridan-toʻgʻri brauzerdan qoʻngʻiroq qilish/qabul qilish. Faqat WebRTC yoqilgan ichki raqamga ega foydalanuvchilarda koʻrinadi.
- **2FA (ikki bosqichli tasdiqlash)** — ixtiyoriy, kirishda ilovadan 6 xonali kod talab qiladi.
- **Parolni oʻzgartirish** — joriy va yangi parol (kamida 10 belgi); saqlangach boshqa qurilmalardagi sessiyalar yopiladi.

> Profil, parol va 2FA boʻlimi **ichki raqami boʻlmagan** foydalanuvchida (masalan, admin) ham koʻrinadi. Tez kirish: yuqori oʻng burchakdagi ism belgisi → **Profil va xavfsizlik**.

## Maydonlar

| Boʻlim | Nima koʻrsatadi/qiladi |
|---|---|
| **Band qilmaslik (DND)** | Yoqish/oʻchirish toggle + **Qoʻngʻiroqlarni yoʻnaltirish** maydoni (ichki yoki tashqi raqam) |
| **Bugungi statistika** | **Qoʻngʻiroqlar**, **Oʻtkazib yuborilgan**, **Suhbat vaqti** |
| Follow Me | Qisqartirilgan koʻrinishda — ketma-ket qoidalar roʻyxati |
| **Telefonga ulash** | QR modalini ochish tugmasi |
| **Mening navbatlarim** | Har bir navbat: holat (**Kirgan**/**Chiqgan**/**Pauzada**), **Kirish**/**Chiqish**/**Pauza**/**Davom etish** tugmalari |
| **Soʻnggi qoʻngʻiroqlar** | Oxirgi 24 soat: vaqt, yoʻnalish, raqam, natija belgisi, davomiylik, yozib olingan ovoz |
| **Mening baholarim** | Sifat nazorati baholagan varaqalar: sana, varaqa nomi, ball foizi, izoh |
| **Ikki bosqichli tasdiqlash (2FA)** | Yoqish/oʻchirish, zaxira kodlarni qayta yaratish |
| **Parolni oʻzgartirish** | **Joriy parol**, **Yangi parol** (kamida 10 belgi), **Parolni saqlash** |
| **Ovozli xabarlar** | Kimdan, sana, davomiylik, tinglash/oʻchirish, oʻqilmagan belgisi |

## Qanday qilinadi

### Band qilmaslik va yoʻnaltirishni yoqish
1. **Band qilmaslik (DND)** kartasida toggle’ni yoqing (kerak boʻlsa).
2. **Qoʻngʻiroqlarni yoʻnaltirish** maydoniga ichki yoki tashqi raqam kiriting (boʻsh qoldirilsa yoʻnaltirish oʻchiriladi).
3. **Saqlash** tugmasini bosing.

### Mobil telefonni QR orqali ulash
1. **Telefonga ulash** tugmasini bosing.
2. Mobil telefonga Linphone ilovasini oʻrnating, **Sozlamalar → Assistent → "QR skanerlash"** boʻlimini oching.
3. Kamerani ochilgan QR kodga qarating — raqam oʻzi qoʻshiladi. QR muddati tugasa, **Yangi QR** tugmasini bosing.

### Navbatga kirish, chiqish, pauza qilish
1. **Mening navbatlarim** kartasida kerakli navbat qatorini toping.
2. Kirish uchun **Kirish** tugmasini bosing; chiqish uchun **Chiqish**ni bosing.
3. Vaqtincha tanaffus uchun **Pauza** tugmasini bosing, ixtiyoriy sababni kiritib tasdiqlang; qaytganda **Davom etish**ni bosing.

### Brauzerdan qoʻngʻiroq qilish (brauzer telefoni)
1. Sahifa yuqorisidagi softfon chipini bosib panelni oching.
2. Raqamni terib yoki klaviatura orqali kiritib **Qoʻngʻiroq** tugmasini bosing.
3. Suhbat davomida mikrofonni oʻchirish, kutishga qoʻyish, boshqa raqamga oʻtkazish yoki yakunlash tugmalaridan foydalaning.

### 2FA yoqish
1. **Ikki bosqichli tasdiqlash (2FA)** kartasida **Yoqish** tugmasini bosing.
2. Ochilgan QR kodni autentifikator ilovasi (masalan Google Authenticator) bilan skanerlang va kodni kiritib tasdiqlang.
3. Koʻrsatilgan zaxira kodlarni xavfsiz joyga saqlang, **Tayyor**ni bosing.

### Parolni oʻzgartirish
1. **Parolni oʻzgartirish** kartasida joriy parolni va yangi parolni kiriting.
2. **Parolni saqlash**ni bosing — «Parol oʻzgartirildi» xabari chiqadi; boshqa qurilmalarda qayta kirish kerak boʻladi.

### Ovozli xabarni tinglash yoki oʻchirish
1. **Ovozli xabarlar** roʻyxatida kerakli xabarni toping.
2. Pleyer orqali tinglang; oʻqilmagan xabarni belgilash uchun tasdiqlash ikonkasini bosing.
3. Kerak boʻlmasa **Oʻchirish** ikonkasini bosing.

## Maslahatlar va cheklovlar

> [!WARNING]
> **Telefonga ulash** QR havolasi bir martalik — telefon uni olgandan keyin 60 soniyada yaroqsiz boʻladi, parol QR ichida saqlanmaydi.

> [!WARNING]
> Brauzer telefoni mikrofonga kirish uchun **HTTPS** (yoki `localhost`) talab qiladi — oddiy HTTP orqali ochilgan sahifada mikrofon ishlamaydi va ogohlantirish chiqadi.

> [!TIP]
> Navbat aʼzoligi **statik** boʻlsa, **Kirish**/**Chiqish** tugmalari koʻrinmaydi — "Statik aʼzolik — kirish/chiqish uchun adminga murojaat qiling" deb yoziladi.

> [!NOTE]
> Bir ichki raqamga bir nechta fizik apparat biriktirilgan boʻlsa, toʻgʻridan-toʻgʻri qoʻngʻiroqlarda barchasi bir vaqtda jiringlaydi; navbat aʼzosi yoki API orqali chiqarilgan qoʻngʻiroqda faqat bitta qurilma jiringlaydi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| "Ichki raqam bogʻlanmagan" | Hisobingizga hali ichki raqam biriktirilmagan | Administratorga murojaat qiling — [Ichki raqamlar](/docs/extensions) boʻlimida biriktirilishi kerak |
| "HTTPS kerak" ogohlantirishi | Panel HTTP orqali ochilgan | Panelni `https://` manzili orqali oching |
| "Mikrofonga ruxsat yoʻq" | Brauzer mikrofonga ruxsat bermagan | Brauzer sozlamalaridan mikrofonga ruxsat bering, sahifani yangilang |
| "Maʼlumot eskirgan" (DND saqlashda) | Maʼlumot boshqa joydan oʻzgartirilgan | Koʻrsatilgan tugmani bosib qaytadan saqlang |
| QR kodining muddati tugadi | 60 soniyadan koʻp vaqt oʻtdi | **Yangi QR** tugmasini bosib qayta skanerlang |

## Bog'liq bo'limlar

- [Ichki raqamlar](/docs/extensions)
- [Telefon apparatlari](/docs/devices)
