---
id: network
title: Tarmoq
group: system
order: 80
path: /settings/network
summary: Host nomi, DNS, tarmoq interfeyslari va statik marshrutlar — xavfsiz qoʻllash va avtomatik qaytarish bilan.
---

# Tarmoq

Serverning tarmoq sozlamalari: host nomi, DNS serverlari, har bir tarmoq interfeysi (DHCP/statik/qoʻlda) va
statik marshrutlar. Oʻzgarish darhol kuchga kirgandan keyin tasdiqlanmasa, **avtomatik ravishda eski
holatga qaytadi** — bu serverga ulanishni butunlay yoʻqotib qoʻymaslik uchun himoya.

## Qayerda
Menyu: **Tizim → Tarmoq**, toʻrt tab: **Umumiy**, **Interfeyslar**, **Statik marshrutlar**, **Ping**. Kim koʻradi:
faqat `*` (toʻliq administrator) ruxsati bor foydalanuvchi.

## Asosiy tushunchalar

- **Faqat koʻrish rejimi** — agar serverda tarmoqni **netplan** yoki **NetworkManager** boshqarsa, bu
  sahifadan tahrirlash **ishlamaydi** (faqat Debian/ifupdown oʻrnatmasida tahrirlash mumkin) — sabab
  bannerida koʻrsatiladi.
- **Tarmoq xizmati (netd) ishlamasa** — oʻzgarishlarni umuman qoʻllab boʻlmaydi, xato bannerida
  koʻrsatiladi.
- **Loyiha (draft)** — ekrandagi oʻzgarishlar darhol serverga yuborilmaydi, avval **qoralama** sifatida
  saqlanadi; pastda nechta oʻzgarish borligi koʻrsatiladi.
- **Qoʻllash → Tasdiqlash oqimi**: **Qoʻllash**ni bosganda tizim avval tekshiradi (validatsiya), keyin
  **nima oʻzgarishini (diff)** koʻrsatadi, siz **vaqt chegarasi (timeout)**ni belgilaysiz va tasdiqlaysiz.
  Oʻzgarish darhol kuchga kiradi, lekin **kutilayotgan (pending)** holatda qoladi.
- **Avtomatik qaytarish** — agar belgilangan vaqt ichida **Tasdiqlash**ni bosmasangiz, oʻzgarish
  **avtomatik eski holatga qaytariladi** — bu, masalan, notoʻgʻri IP kiritib serverga ulanishni
  yoʻqotmaslik uchun. Istalgan vaqt **Hozir qaytarish** bilan ham qaytarish mumkin.
- **Interfeys rejimi**: DHCP, Statik (qoʻlda IP/CIDR va shlyuz), Qoʻlda, Sozlanmagan.
- **Statik marshrut** — manzil (CIDR), shlyuz, ixtiyoriy interfeys va metrik.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Host nomi | Serverning tarmoqdagi nomi | — |
| DNS serverlar | Vergul yoki qator bilan ajratilgan IP’lar | — |
| Qidiruv domenlari | DNS qidiruv domenlari | `innova.local` |
| **Interfeys** → Rejim | DHCP / Statik / Qoʻlda | — |
| Manzil (CIDR) | Statik rejimda IP/maska | `192.168.10.20/24` |
| Shlyuz | Ixtiyoriy | `192.168.10.1` |
| MTU | Interfeys MTU qiymati | — |
| **Marshrut** → Manzil (CIDR) | Qaysi tarmoqqa | `10.20.0.0/16` |
| Shlyuz / Interfeys / Metrik | Qanday yoʻnaltirilsin | Interfeys sukuti: Avtomatik |
| Tasdiqlash uchun vaqt | Qoʻllashdan keyin tasdiqlash muddati | — |

## Qanday qilinadi

### Umumiy sozlamalarni oʻzgartirish
1. **Umumiy** tabida host nomi, DNS serverlar va qidiruv domenlarini tahrirlang.
2. Pastdagi ogʻtirilgan panelda nechta oʻzgarish borligini koʻring.

### Interfeysni sozlash
1. **Interfeyslar** tabida kerakli interfeys qatorida **Sozlash**ni bosing (tahrirlanmaydigan interfeyslar
   uchun bu tugma koʻrinmaydi).
2. **Rejim**ni tanlang: DHCP, Statik yoki Qoʻlda.
3. Statik tanlansa — **Manzil (CIDR)** va ixtiyoriy **Shlyuz**, kerak boʻlsa **MTU**ni kiriting.
4. **Saqlash**ni bosing — bu qoralamaga qoʻshiladi, hali serverga yuborilmaydi.

### Statik marshrut qoʻshish/tahrirlash/oʻchirish
1. **Statik marshrutlar** tabida **Marshrut qoʻshish**ni bosing, yoki mavjud qatorda **Tahrirlash**/
   **Oʻchirish**ni tanlang.
2. Manzil (CIDR), shlyuz, ixtiyoriy interfeys va metrikni kiriting.
3. **Saqlash**ni bosing.

### Oʻzgarishlarni qoʻllash va tasdiqlash
1. Qoralamada oʻzgarish boʻlsa, pastki panelda **Qoʻllash**ni bosing.
2. Tizim tekshiradi; xato boʻlsa tegishli maydonlar qizil bilan belgilanadi.
3. Toʻgʻri boʻlsa, **nima oʻzgarishi (diff)** va ogohlantirishlar koʻrsatiladi — **Tasdiqlash uchun
   vaqt**ni belgilab (sukut qiymat bor), **Qoʻllash**ni tasdiqlang.
4. Oʻzgarish darhol kuchga kiradi va **kutilayotgan** holatga oʻtadi — yuqorida jonli hisoblagich
   koʻrinadi.
5. Yangi sozlama toʻgʻri ishlaganiga ishonch hosil qilib, **Tasdiqlash**ni bosing — shunda oʻzgarish
   doimiy boʻladi.
6. Agar muddat ichida tasdiqlamasangiz, tizim **avtomatik eski holatga qaytaradi**; darhol qaytarish
   uchun **Hozir qaytarish**ni bosish mumkin.

### Qoralamani bekor qilish
1. Hali qoʻllanmagan oʻzgarishlarni **Bekor qilish**ni bosib tashlab yuborishingiz mumkin — qoralama
   serverdagi joriy holatga qaytadi.

### Ulanishni tekshirish (Ping)
1. **Ping** tabini oching. Tez tanlash tugmalari: **Shlyuz** (standart shlyuz), har bir **SIP** trunk hosti,
   **Internet** (`1.1.1.1`, `8.8.8.8`) va **DNS nomi** (`google.com` — DNS ishlashini ham tekshiradi).
2. Yoki **Host** maydoniga IP manzil (IPv4/IPv6) yoki domen nomini yozing; **Paketlar soni** — 1 dan 10 gacha
   (standart 4).
3. **Ping**ni bosing. Natijada: javob bor/yoʻq belgisi, yoʻqotish foizi, yuborilgan/qaytgan paketlar,
   kechikish min/oʻrtacha/maks (ms) va buyruqning toʻliq chiqishi.
- Ping sozlamalarni oʻzgartirmaydi — tarmoq faqat koʻrish rejimida boʻlsa ham ishlaydi. Tarmoq xizmati
  (netd) ishlamasa, tab buni ogohlantiradi va tugma oʻchiq boʻladi.
- Domen nomi javob bermasa, IP esa javob bersa — muammo DNSda (Umumiy tabdagi DNS serverlarni tekshiring).

## Maslahatlar va cheklovlar

> [!WARNING]
> Agar yangi sozlama notoʻgʻri boʻlib, serverga ulanishni yoʻqotib qoʻysangiz — **tashvishlanmang**, siz
> tasdiqlamagan holda belgilangan muddat tugaganda tizim **oʻzi** avvalgi holatga qaytaradi.

> [!TIP]
> Uzoqroq test qilish kerak boʻlsa, **Tasdiqlash uchun vaqt**ni oshiring — lekin muddat tugaguncha
> tasdiqlamasangiz baribir avtomatik qaytariladi, shuning uchun ishonchli bo'lmaguncha tasdiqlashga
> shoshilmang.

- Netplan/NetworkManager boshqargan serverlarda bu sahifa **faqat koʻrish** uchun ishlaydi.
- Bir vaqtning oʻzida faqat bitta **kutilayotgan** oʻzgarish boʻlishi mumkin — u hal qilinmaguncha
  (tasdiqlangan/qaytarilgan) yangisini qoʻllab boʻlmaydi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| «Tarmoq sozlamalari faqat koʻrish uchun» | Netplan/NetworkManager boshqaradi | Faqat Debian (ifupdown) oʻrnatmasida tahrirlash mumkin |
| «Tarmoq xizmati (netd) ishlamayapti» | netd xizmati toʻxtagan | Serverda netd xizmatini tekshiring/qayta ishga tushiring |
| «Tekshiruvdan oʻtmadi» | CIDR/IP formati notoʻgʻri yoki majburiy maydon boʻsh | Qizil belgilangan maydonlarni tuzating |
| Oʻzgarish kutilayotgan holatda qolib ketdi | Tasdiqlanmagan/qaytarilmagan | **Tasdiqlash** yoki **Hozir qaytarish**ni bosing, yoki muddat tugashini kuting |
| Qoʻllashdan keyin serverga ulanib boʻlmaydi | Notoʻgʻri IP/shlyuz kiritilgan | Hech narsa qilmang — muddat tugaganda avtomatik qaytariladi |

## Bog'liq bo'limlar

- [Firewall](/docs/firewall)
- [SIP va tarmoq](/docs/sip)
- [Tizim holati](/docs/status)
- [Muammolar](/docs/muammolar)
