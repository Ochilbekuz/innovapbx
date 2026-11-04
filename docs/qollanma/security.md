---
id: security
title: Xavfsizlik
group: system
order: 30
path: /settings/security
summary: SIP hujum himoyasi (fail2ban uslubida), IP bloklash, toll-fraud chegaralari, hodisalar va 2FA siyosati.
---

# Xavfsizlik

PBX serverga tashqaridan SIP orqali hujum qilishga (notoʻgʻri parol bilan qayta-qayta urinish, oʻgʻirlangan
hisob orqali xalqaro raqamlarga qoʻngʻiroq qilish — "toll fraud") qarshi himoya shu yerda sozlanadi. Soʻnggi
24 soat ichida qancha hujum urinishi boʻlgani, qaysi IP’lar bloklangani va hamma uchun 2FA talab qilinishi
kerak-yoʻqligi — barchasi bitta ekranda.

## Qayerda
Menyu: **Tizim → Xavfsizlik**. Kim koʻradi: har kim koʻra oladi, lekin faqat `*` (toʻliq administrator)
ruxsati bor foydalanuvchi sozlamalarni oʻzgartirishi, IP bloklashi/blokdan chiqarishi mumkin.

## Asosiy tushunchalar

- **SIP hujum himoyasi** — fail2ban uslubida ishlaydi: belgilangan **oyna** vaqtida (soniya) bir IP’dan
  belgilangan sondan koʻp **muvaffaqiyatsiz urinish** boʻlsa, shu IP avtomatik **bloklanadi**.
- **Ishonchli tarmoqlar** — bu CIDR'lardagi IP'lar hech qachon avtomatik bloklanmaydi (`127.0.0.0/8` doim
  ishonchli).
- **Lokal tarmoqni ishonchli deb hisoblash** — yoqilsa, ofis telefoni (192.168.x.x, 10.x.x.x, 172.16–31.x.x)
  notoʻgʻri login bilan necha marta urinsa ham bloklanmaydi, lekin urinishlar statistikada koʻrinib turadi.
- **Toll-fraud chegaralari** — bir ichki raqam soatiga/kuniga nechta chiquvchi (jumladan xalqaro)
  qoʻngʻiroq qilishi mumkinligini cheklaydi; limitdan oshsa ichki raqam avtomatik bloklanadi.
- **2FA siyosati** — ikki bosqichli tasdiqlash (TOTP ilovasi orqali) kimlar uchun majburiy: hech kim uchun
  emas, faqat adminlar, yoki hamma foydalanuvchi.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| **SIP hujum himoyasi** → Yoqilgan | Himoyani yoqadi/oʻchiradi | — |
| Maksimal muvaffaqiyatsiz urinish | Shu sondan oshsa bloklanadi | — |
| Oyna (soniya) | Urinishlar shu vaqt oynasida hisoblanadi | — |
| Bloklash muddati (soniya) | `0` — qoʻlda chiqarilmaguncha muddatsiz bloklaydi | — |
| Ishonchli tarmoqlar (CIDR) | Har qatorda bitta, hech qachon bloklanmaydi | `127.0.0.0/8` doim |
| Lokal tarmoqni avtomatik bloklamaslik | Yoqilsa — lokal IP’lar bloklanmaydi | — |
| **Toll-fraud** → Yoqilgan | Chegaralarni yoqadi/oʻchiradi | — |
| Bir vaqtda chiquvchi chaqiruvlar | `0` — chegaralanmagan | — |
| Ichki raqamga soatiga chiquvchi | Soatlik limit | — |
| Ichki raqamga kuniga xalqaro | Kunlik xalqaro qoʻngʻiroq limiti | — |
| **2FA** → Kim uchun majburiy | Majburiy emas / Faqat adminlar / Hamma foydalanuvchi | Sukut: Majburiy emas |

## Qanday qilinadi

### Soʻnggi hujum urinishlarini koʻrish
1. **Holat** tabida soʻnggi 24 soatlik muvaffaqiyatsiz/bloklangan urinishlar sonini va soatlik diagrammani
   koʻring.
2. **Eng koʻp urinish qilgan IP’lar** roʻyxatida shubhali IP’ni topib, kerak boʻlsa **Bloklash** tugmasini
   bosing.

### IP’ni qoʻlda bloklash
1. **Bloklangan IP** tabida **IP’ni bloklash**ni bosing.
2. IP manzilini kiriting, ixtiyoriy izoh yozing.
3. **Muddat (soniya)** — `0` qiymati muddatsiz bloklaydi, aks holda shuncha soniyadan keyin avtomatik
   ochiladi.
4. **Bloklash**ni tasdiqlang.

### IP’ni blokdan chiqarish
1. **Bloklangan IP** roʻyxatida kerakli qatorda **Blokdan chiqarish**ni bosing.

### SIP himoyasi va toll-fraud chegaralarini sozlash
1. **Sozlamalar** tabini oching.
2. **SIP hujum himoyasi** blokida yoqilganligini, limitlarni va ishonchli tarmoqlarni belgilang.
3. **Toll-fraud chegaralari** blokida chiquvchi qoʻngʻiroqlar limitlarini kiriting.
4. **Saqlash**ni bosing.

### Toll-fraud sababli bloklangan ichki raqamni ochish
1. **Toll-fraud** tabida bloklangan ichki raqamni topib, **Blokdan chiqarish**ni bosing.

### 2FA siyosatini belgilash
1. **Sozlamalar** tabida **Ikki bosqichli tasdiqlash (2FA)** blokida **Kim uchun majburiy**ni tanlang.
2. **Saqlash**ni bosing — tanlangan guruh keyingi kirishda TOTP ilovasi orqali ulanishi shart boʻladi.

### Xavfsizlik hodisalarini koʻrish
1. **Hodisalar** tabida tur boʻyicha filtrlab (IP bloklandi, blokdan chiqarildi, toll-fraud va h.k.) tarixni
   koʻring.

## Maslahatlar va cheklovlar

> [!WARNING]
> Lokal tarmoqni ishonchli qilib qoʻysangiz, ofis ichidagi buzilgan/zararlangan qurilma ham cheklovsiz
> urinish qilishi mumkin — faqat ishonchli ofis tarmogʻida foydalaning.

> [!TIP]
> Agar oʻzingizning statik IP’ingizdan boshqaruv panelga ulanayotgan boʻlsangiz, uni **Ishonchli
> tarmoqlar**ga qoʻshib qoʻying — tasodifan oʻzingizni bloklab qolmaslik uchun.

- Bloklash muddati `0` bo'lsa, IP faqat qoʻlda ochilmaguncha bloklangan qoladi.
- 2FA siyosatini "Hamma foydalanuvchi"ga oʻrnatish — barcha foydalanuvchi keyingi kirishda TOTP ilovasini
  ulashi shart boʻladi (2FA qurilma yoʻqolgan holat uchun — [Muammolar](/docs/muammolar)).

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Oʻz IP’im bloklanib qoldi | SIP himoyasi notoʻgʻri login urinishlarini hujum deb hisobladi | Administrator **Bloklangan IP**dan blokdan chiqaradi; keyin IP’ni **Ishonchli tarmoqlar**ga qoʻshing |
| Ichki raqam qoʻngʻiroq qila olmaydi, «toll-fraud» sababi | Soatlik/kunlik limit oshib ketgan | **Toll-fraud** tabida blokdan chiqaring, kerak boʻlsa limitni **Sozlamalar**da oshiring |
| «IP manzil notoʻgʻri» | CIDR/IP formati xato kiritilgan | Toʻgʻri formatda kiriting, masalan `203.0.113.9` |
| 2FA qurilmasi yoʻqolgan | Foydalanuvchi TOTP ilovasiga kira olmaydi | [Muammolar](/docs/muammolar) boʻlimidagi "2FA qurilma yoʻqolsa" bandiga qarang |

## Bog'liq bo'limlar

- [Firewall](/docs/firewall)
- [Audit jurnali](/docs/audit)
- [Foydalanuvchilar va rollar](/docs/rollar)
- [Muammolar](/docs/muammolar)
