---
id: birinchi-sozlash
title: Birinchi sozlash
group: start
order: 30
path: /setup
summary: O'rnatishdan keyin birinchi ochilishda administrator hisobi va tarmoq sozlamalarini kiritish sahifasi.
---

# Birinchi sozlash

O'rnatish tugagach, veb-panelni birinchi marta ochganingizda avtomatik ikki qadamli sozlash sahifasi chiqadi: administrator hisobi yaratish va tarmoq sozlamalarini kiritish. Bu sahifa faqat **bir marta** — administrator yaratilgandan keyin bir umrga yopiladi, qayta ochib bo'lmaydi.

## Asosiy tushunchalar

- **O'rnatish kodi** — [O'rnatish](/docs/ornatish) jarayoni tugaganda konsolda/terminalda bir martagina chiqqan kod; faqat shu sahifada, faqat bir marta kerak bo'ladi.
- Sahifa ikki qadamdan iborat: **1. Administrator** va **2. Til va tarmoq**.
- Ikkinchi qadamdan keyin alohida "Apply Config" bosqichi yo'q — har bir o'zgarish darhol kuchga kiradi.

## Maydonlar

**1-qadam — Administrator**:

| Maydon | Nima qiladi | Talab |
|---|---|---|
| **Oʻrnatish kodi** | O'rnatishda konsolda chiqqan bir martalik kod | Majburiy, to'g'ri kod kiritilishi shart |
| **Login** | Administratorning tizimga kirish nomi | Kamida 3 belgi |
| **Toʻliq ism** | Administratorning ism-sharifi | Kamida 2 belgi |
| **Parol** | Administrator hisobining paroli | Kamida 8 belgi |
| **Panel tili** | Panel interfeysi tili: oʻzbek / rus / ingliz | Sukut: oʻzbek |

**2-qadam — Til va tarmoq**:

| Maydon | Nima qiladi | Talab |
|---|---|---|
| **Vaqt zonasi** | Asia/Tashkent yoki Asia/Samarkand (ikkisi ham UTC+5) | Majburiy |
| **Tashqi IP manzil** | Serverning tashqi (internetdan ko'rinadigan) IP'si — SIP trunklar uchun kerak bo'lishi mumkin | Ixtiyoriy, IPv4 formatida boʻlsin |
| **Lokal tarmoqlar (CIDR)** | Qaysi tarmoqlar "ichki" hisoblanishi (NAT uchun) — har qatorga bitta CIDR | Majburiy, kamida bitta to'g'ri qator; sukut: `10.0.0.0/8` |

## Qanday qilinadi

### Administrator hisobini yaratish
1. Birinchi ochilgan sahifada **Oʻrnatish kodi**ni konsoldan/terminaldan ko'chirib kiriting.
2. **Login**, **Toʻliq ism** va **Parol**ni kiriting.
3. Kerak boʻlsa **Panel tili**ni (oʻzbek/rus/ingliz) tanlang.
4. **Davom etish**ni bosing — kod yoki maydonlar notoʻgʻri boʻlsa xato koʻrsatiladi.

### Til va tarmoqni sozlash
1. **Vaqt zonasi**ni tanlang (Asia/Tashkent yoki Asia/Samarkand).
2. Agar serverning tashqi IP manzili ma'lum bo'lsa, **Tashqi IP manzil**ga kiriting — bo'sh qoldirish ham mumkin, keyin [Sozlamalar → SIP](/docs/trunks)dan kiritish mumkin bo'ladi.
3. **Lokal tarmoqlar (CIDR)** maydoniga ichki tarmoq(lar)ni har qatorga bitta CIDR koʻrinishida kiriting (masalan `10.0.0.0/8`) — sukut qiymat tayyor turadi, kerak bo'lsa o'zgartiring.
4. **Tugatish**ni bosing — administrator hisobi bilan avtomatik tizimga kirilib, [Boshqaruv paneli](/docs/dashboard)ga o'tiladi.

## Maslahatlar va cheklovlar

> [!WARNING]
> **Oʻrnatish kodi** faqat bir marta ishlatiladi — administrator yaratilgandan keyin bu sahifa butunlay yopiladi, kodni qayta ishlatib boʻlmaydi va yangi kod ham chiqarilmaydi.

> [!TIP]
> **Lokal tarmoqlar (CIDR)** to'g'ri kiritilishi muhim — bu ro'yxat ichki raqamlarning NAT orqasida (masalan ofisdagi lokal tarmoqda) to'g'ri ishlashi uchun ishlatiladi. Shubha bo'lsa sukut `10.0.0.0/8`ni qoldiring, keyin kerak bo'lsa aniqlashtiring.

> [!TIP]
> **Tashqi IP manzil**ni bo'sh qoldirsangiz ham bo'ladi — keyin istalgan vaqt Sozlamalar bo'limidan kiritish mumkin.

> [!NOTE]
> Ikkinchi qadamdan keyin alohida tasdiqlash (Apply Config) bosqichi yo'q — kiritilgan tarmoq sozlamalari darhol ishlay boshlaydi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| "O'rnatish kodi noto'g'ri" | Kod xato kiritilgan yoki boshqa server konsolidan olingan | Konsoldagi/terminaldagi kodni aynan shu serverdan qayta ko'chirib kiriting |
| Koʻp marta xato kod kiritilgandan keyin bloklanish | Xavfsizlik uchun urinishlar soni cheklangan | Bir oz kutib qayta urinib ko'ring |
| "Parol kamida 8 belgi boʻlsin" / "Login kamida 3 belgi boʻlsin" va h.k. | Maydon talabga mos emas | Koʻrsatilgan talabga mos qiymat kiriting |
| CIDR maydonida xato | Noto'g'ri formatdagi qator kiritilgan (masalan `10.0.0.0/8` koʻrinishida emas) | Har qatorni toʻgʻri CIDR formatida yozing |
| Sahifa qayta ochilmayapti | Administrator allaqachon yaratilgan — sozlash bir martalik | [Kirish](/docs/kirish) sahifasidan oddiy login orqali kiring |

## Bog'liq bo'limlar

- [O'rnatish](/docs/ornatish)
- [Tezkor boshlash](/docs/tez-boshlash)
- [Boshqaruv paneli](/docs/dashboard)
