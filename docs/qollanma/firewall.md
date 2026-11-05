---
id: firewall
title: Firewall
group: system
order: 140
path: /settings/firewall
summary: SSH/veb-panel/SIP/RTP xizmatlarini kim ishlatishi mumkinligini va bloklangan manzillarni boshqarish — xavfsiz qoʻllash-tasdiqlash oqimi bilan.
---

# Firewall

Serverning tashqi himoyasi — qaysi manzillardan **SSH**, **veb-panel**, **SIP** va **RTP (ovoz)**
xizmatlariga ulanish mumkinligini va qaysi manzillar **butunlay bloklanganini** shu yerdan boshqarasiz.
Oʻzgarish **Tarmoq** sahifasidagi kabi avval tekshiriladi, soʻng tasdiqlash kutiladi va muddat ichida
tasdiqlanmasa **avtomatik eski holatga qaytadi** — bu serverga kirishni butunlay yoʻqotib qoʻymaslik
uchun himoya.

## Qayerda
Menyu: **Tizim → Firewall**. Kim koʻradi: faqat `*` (toʻliq administrator) ruxsati bor foydalanuvchi.

## Asosiy tushunchalar

- **Xizmat** — toʻrttasi bor: **SSH**, **Veb-panel**, **SIP**, **RTP (ovoz)**. Har biri mustaqil rejimga
  ega.
- **Rejim**: **Hammaga ochiq** (hech qanday cheklov yoʻq) yoki **Faqat roʻyxatdagilarga** (allowlist) —
  faqat koʻrsatilgan IPv4 CIDR manzillaridan ulanish mumkin.
- **Ruxsat etilgan CIDR** — allowlist rejimida kiritiladigan manzillar roʻyxati (masalan
  `192.168.1.0/24`); boʻsh qoldirilsa hech kim ulanolmaydi (kamida bitta CIDR shart).
- **Bloklangan manzillar** — bu roʻyxatdagi manzillardan **BARCHA** port (xizmatlardan qatʼi nazar)
  yopiladi — eng qattiq cheklov.
- **Oʻz-oʻzini qulflashdan himoya** — tizim siz kirgan manzilni/sessiyani **oʻzi avtomatik bloklaydigan**
  sozlamani qabul qilmaydi — bunday holatda ogohlantirish chiqadi va oʻzgarish oldini olinadi.
- **Qoralama (draft)** — ekrandagi oʻzgarishlar darhol serverga yuborilmaydi, pastda nechta oʻzgarish
  borligi koʻrsatiladi.
- **Qoʻllash → Tasdiqlash oqimi** — **Tarmoq** sahifasi bilan bir xil: **Qoʻllash** tekshiradi, **nima
  oʻzgarishi (diff)**ni koʻrsatadi, siz **tasdiqlash uchun vaqt**ni belgilaysiz (sukut **120 soniya**) va
  tasdiqlaysiz. Oʻzgarish darhol kuchga kiradi, lekin **kutilayotgan** holatda qoladi.
- **Avtomatik qaytarish** — belgilangan muddat ichida **Tasdiqlash**ni bosmasangiz, oʻzgarish
  **avtomatik eski holatga qaytariladi**; istalgan vaqt **Hozir qaytarish** bilan ham qaytarish mumkin.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| **Xizmat** → Rejim | Hammaga ochiq / Faqat roʻyxatdagilarga | Sukut: xizmatga bogʻliq |
| Ruxsat etilgan CIDR | Allowlist rejimida ruxsat etilgan manzillar | `192.168.1.0/24` |
| Bloklangan manzillar | Barcha porti yopiladigan manzillar | — |
| Tasdiqlash uchun vaqt (soniya) | Qoʻllashdan keyin tasdiqlash muddati | 120 soniya |

## Qanday qilinadi

### Xizmat rejimini oʻzgartirish
1. **Xizmatlar** boʻlimida kerakli xizmat (SSH/Veb-panel/SIP/RTP) qatorida rejimni tanlang.
2. **Faqat roʻyxatdagilarga** tanlansa, **Ruxsat etilgan CIDR** maydoniga manzillarni (vergul yoki qator
   bilan ajratib) kiriting.

### Manzil bloklash
1. **Bloklangan manzillar** maydoniga kerakli IPv4 CIDR’larni (vergul yoki qator bilan ajratib) kiriting.

### Oʻzgarishlarni qoʻllash va tasdiqlash
1. Qoralamada oʻzgarish boʻlsa, pastki panelda **Qoʻllash**ni bosing.
2. Tizim tekshiradi; xato boʻlsa tegishli maydonlar qizil bilan belgilanadi.
3. Toʻgʻri boʻlsa, **nima oʻzgarishi (diff)** koʻrsatiladi — **Tasdiqlash uchun vaqt**ni belgilab (sukut
   120 soniya), **Qoʻllash**ni tasdiqlang.
4. Oʻzgarish darhol kuchga kiradi va **kutilayotgan** holatga oʻtadi — yuqorida jonli hisoblagich
   koʻrinadi.
5. Yangi qoidalar bilan serverga ulanish (SSH/veb-panel) ishlab turganiga ishonch hosil qilib,
   **Tasdiqlash**ni bosing.
6. Agar muddat ichida tasdiqlamasangiz, tizim **avtomatik eski holatga qaytaradi**; darhol qaytarish
   uchun **Hozir qaytarish**ni bosish mumkin.

### Qoralamani bekor qilish
1. Hali qoʻllanmagan oʻzgarishlarni **Bekor qilish**ni bosib tashlab yuborishingiz mumkin.

## Maslahatlar va cheklovlar

> [!WARNING]
> Agar yangi qoidalar bilan serverga ulanishni (ayniqsa SSH/veb-panel) yoʻqotib qoʻysangiz —
> **tashvishlanmang**, siz tasdiqlamagan holda belgilangan muddat tugaganda tizim **oʻzi** avvalgi
> holatga qaytaradi.

> [!TIP]
> SSH va veb-panelni **faqat roʻyxatdagilarga** cheklashdan oldin, oʻzingiz ulanadigan manzil(lar)ni
> **albatta** roʻyxatga qoʻshing — aks holda sozlama qabul qilinmaydi (oʻz-oʻzini qulflashdan himoya).

- Bloklangan manzillar roʻyxati xizmat rejimidan ustun — u yerdagi manzil hech qaysi xizmatga ulanolmaydi.
- Bir vaqtning oʻzida faqat bitta **kutilayotgan** oʻzgarish boʻlishi mumkin — u hal qilinmaguncha
  (tasdiqlangan/qaytarilgan) yangisini qoʻllab boʻlmaydi.
- Allowlist rejimida boʻsh roʻyxat qoldirib boʻlmaydi — kamida bitta CIDR kerak.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| «Diqqat: bu sozlama joriy administratorni oʻzini qulflab qoʻyishi mumkin edi» | Sizning manzilingiz allowlist/bloklanganga tushib qolgan | Oʻz manzilingizni allowlistga qoʻshing yoki bloklangandan olib tashlang |
| «Hech kim yoʻq — allowlist rejimida kamida bitta CIDR kerak» | Allowlist rejimi tanlangan, lekin roʻyxat boʻsh | Kamida bitta CIDR kiriting |
| «Tekshiruvdan oʻtmadi» | CIDR formati notoʻgʻri yoki majburiy maydon boʻsh | Qizil belgilangan maydonlarni tuzating |
| Oʻzgarish kutilayotgan holatda qolib ketdi | Tasdiqlanmagan/qaytarilmagan | **Tasdiqlash** yoki **Hozir qaytarish**ni bosing, yoki muddat tugashini kuting |
| Qoʻllashdan keyin serverga (SSH/veb) ulanib boʻlmaydi | Notoʻgʻri CIDR kiritilgan | Hech narsa qilmang — muddat tugaganda avtomatik qaytariladi |
| «Firewall sozlamalari faqat koʻrish uchun» | `readonly_reason` bilan bloklangan | Koʻrsatilgan sababni bartaraf qilib qayta urinib koʻring |

## Bog'liq bo'limlar

- [Kirish (SSH va veb-panel)](/docs/access)
- [Tarmoq](/docs/network)
- [Xavfsizlik](/docs/security)
- [Tizim holati](/docs/status)
