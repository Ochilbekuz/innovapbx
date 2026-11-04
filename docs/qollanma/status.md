---
id: status
title: Tizim holati
group: system
order: 70
path: /settings/status
summary: Disk boʻshligʻi, trunklar, internet/DNS, SIP interfeysi holati; diskni tozalash va qayta yuklash/oʻchirish.
---

# Tizim holati

Serverning hozirgi "sogʻligʻi"ni bir qarashda koʻrish uchun sahifa: disk qancha toʻlgan, trunklar ishlab
turganmi, internet/DNS bor-yoʻqligi, SIP transportlari va roʻyxatdan oʻtgan qurilmalar soni. Shu yerdan
diskni tozalash va serverni qayta yuklash/oʻchirish ham mumkin.

## Qayerda
Menyu: **Tizim → Tizim holati**. Kim koʻradi: faqat `*` (toʻliq administrator) ruxsati bor foydalanuvchi.

## Asosiy tushunchalar

- **Disk** — umumiy ishlatilgan/boʻsh hajm va kategoriya boʻyicha taqsimot (qoʻngʻiroq yozuvlari,
  zaxiralar, migratsiya fayllari, ovozli pochta, jurnallar); ayrim kategoriyalar **qoʻlda tozalanmaydi**
  deb belgilanadi.
- **Tranklar** — har bir trunkning holati (ishlayapti/muammo) va sababi, agar bor boʻlsa.
- **Internet** — tashqi ulanish bor-yoʻqligi, DNS ishlayapti-yoʻqligi, kechikish (ms) va tekshirilayotgan
  manzil.
- **SIP interfeysi** — Asterisk xizmati ishlab turganmi, qaysi transportlar (UDP/TLS) qaysi manzilga
  bogʻlangani, nechta qurilma roʻyxatdan oʻtgan.
- **Diskni tozalash** — eski qoʻngʻiroq yozuvlarini, ortiqcha zaxira nusxalarini va yuklangan FreePBX
  migratsiya fayllarini oʻchirib joy boʻshatish; oʻchirishdan oldin qancha joy boʻshayotgani **oldindan
  koʻrsatiladi (preview)**.
- **Qayta yuklash / oʻchirish** — serverni masofadan qayta yuklash yoki oʻchirish; agar sabab bilan
  bloklangan boʻlsa (`readonly_reason`), tugmalar ishlamaydi.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Shuncha kundan eski yozuvlar oʻchirilsin | Qoʻngʻiroq yozuvlarini tozalash chegarasi | 180 kun |
| Oxirgi shuncha zaxiradan tashqarisi oʻchirilsin | Lokal zaxira nusxalarini tozalash chegarasi | 3 ta |
| Yuklangan FreePBX migratsiya fayllari | Belgilansa — barcha yuklangan toʻplamlar oʻchiriladi | Sukut: oʻchirilgan |
| Hostname (tasdiqlash) | Qayta yuklash/oʻchirishni tasdiqlash uchun aniq yozish kerak | — |

## Qanday qilinadi

### Holatni koʻrish
1. Sahifa ochilganda disk, tranklar, internet va SIP kartalari avtomatik yuklanadi.
2. Muammo boʻlsa (masalan trunk aloqasi uzilgan) — mos karta **qizil/ogohlantirish** rangda koʻrsatiladi.

### Diskni tozalash
1. **Diskni tozalash** tugmasini bosing (disk toʻlib ketganda tugma qizil rangda chiqadi).
2. Kerakli bandlarni belgilang: eski qoʻngʻiroq yozuvlari (necha kundan eski), ortiqcha zaxira nusxalari
   (nechta soʻnggisi saqlansin), yuklangan migratsiya fayllari.
3. Har oʻzgarishdan keyin tizim avtomatik qancha joy boʻshayotganini (hajm va fayl soni) koʻrsatadi.
4. **Oʻchirish**ni bosib tasdiqlang — bu amal **qaytarilmaydi**.

### Serverni qayta yuklash yoki oʻchirish
1. **Qayta yuklash** yoki **Oʻchirish** tugmasini bosing.
2. Ochilgan oynada serverning **hostname**’ini aniq yozib tasdiqlang (xato bosilib ketmasligi uchun).
3. Tasdiqlagandan keyin amal darhol emas, biroz kechikish bilan (soniyalarda) bajariladi — shu haqida
   xabar chiqadi.

## Maslahatlar va cheklovlar

> [!WARNING]
> Qayta yuklash/oʻchirish barcha **faol qoʻngʻiroqlarni** uzadi. **Oʻchirish**dan keyin serverni qoʻlda
> (fizik yoki boshqaruv panelidan) yoqish kerak boʻladi.

> [!TIP]
> Diskni tozalashdan oldin **preview**da koʻrsatilgan hajmni tekshirib chiqing — ayniqsa zaxira nusxalari
> sonini kamaytirishdan oldin, kerakli nusxalar yetarlicha saqlanib qolayotganiga ishonch hosil qiling.

- Agar qayta yuklash/oʻchirish tugmalari **oʻchirilgan** boʻlsa, sahifada sababi (`readonly_reason`)
  koʻrsatiladi — masalan, boshqa tizim amali (zaxira/koʻchirish) ketayotgan boʻlishi mumkin.
- Ba'zi disk kategoriyalari (masalan jurnallar) **qoʻlda tozalanmaydi** deb belgilangan — ular shu sahifa
  orqali oʻchirilmaydi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| «Yuklab boʻlmadi» | Server bilan aloqa yoʻq | **Qayta urinish**ni bosing |
| Disk toʻlib ketgan (qizil) | Qoʻngʻiroq yozuvlari/zaxiralar koʻp joy band qilgan | **Diskni tozalash** bilan eski fayllarni oʻchiring |
| Trunk qizil/muammo | Provayder bilan ulanish yoʻq | Sabab matnini oʻqing, [SIP va tarmoq](/docs/sip) sozlamalarini tekshiring |
| Internet «Ulanmagan»/DNS ishlamayapti | Server tarmoq muammosi yoki DNS xizmati ishlamayapti | Server tarmoq sozlamalarini tekshiring |
| «Hostname mos emas» | Tasdiqlash maydoniga notoʻgʻri matn yozilgan | Hostname’ni aniq, katta-kichik harfigacha mos yozing |
| Qayta yuklash/oʻchirish tugmasi oʻchirilgan | `readonly_reason` bilan bloklangan | Koʻrsatilgan sababni bartaraf qilib qayta urinib koʻring |

## Bog'liq bo'limlar

- [Zaxira](/docs/backup)
- [SIP va tarmoq](/docs/sip)
- [Tarmoq](/docs/network)
- [Muammolar](/docs/muammolar)
