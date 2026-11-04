---
id: day_night
title: Kun/Tun rejimi
group: routing
order: 70
path: /day-night
summary: Xizmat kodi (*28<kod>) yoki panel orqali bir bosishda kunduzgi/tungi manzilga almashtirish, BLF chiroqcha.
---

# Kun/Tun rejimi

**Kun/Tun rejimi** — [Ish vaqti shart](/docs/timegroups)iga oʻxshaydi, lekin jadval boʻyicha emas, qoʻlda
(telefon kodi yoki panel tugmasi bilan) almashtiriladigan oddiy "ochiq/yopiq" kalit. Masalan: kechqurun
qabulxona xodimi ketayotganda *28<kod>ni terib, barcha qoʻngʻiroqlarni tungi navbatchiga oʻtkazadi.

## Qayerda

Menyu: **Marshrutlash → Kun/Tun**. Kim koʻradi: `routing` ruxsatiga ega foydalanuvchilar tahrirlaydi,
qolganlar faqat koʻradi.

## Asosiy tushunchalar

- **Holat (mode)** — qoida doim ikki holatdan birida turadi: **Kunduzgi** yoki **Tungi**. Jadval bilan
  bogʻliq emas — faqat qoʻlda almashtiriladi.
- **Xizmat kodi** — har bir qoidaga bitta raqamli kod bogʻlanadi, telefondan `*28<kod>` terib holatni
  almashtirish mumkin (masalan qoida kodi `1` boʻlsa — `*281`).
- **PIN** — ixtiyoriy, 4–8 raqam. Belgilangan boʻlsa, holatni telefon orqali almashtirishdan oldin PIN
  soʻraladi.
- **BLF chiroqcha** — SIP telefonda `Custom:DAYNIGHT<kod>` kalit kodi bilan BLF tugma sozlansa, chiroqcha
  joriy holatni (kunduzgi/tungi) koʻrsatadi va bosilganda holatni almashtiradi.
- Panelda holatni almashtirish uchun PIN soʻralmaydi — PIN faqat telefon kodi orqali almashtirishda ishlaydi.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nom | Qoida nomi | Koʻpi bilan 128 belgi |
| Xizmat kodi | `*28`dan keyingi raqam | Bitta `0-9` raqam |
| Kunduzgi manzil | Holat «kunduzgi» boʻlganda qoʻngʻiroq shu yerga boradi | Majburiy |
| Tungi manzil | Holat «tungi» boʻlganda qoʻngʻiroq shu yerga boradi | Majburiy |
| PIN | Holatni almashtirishdan oldin soʻraladigan parol | Ixtiyoriy, 4–8 raqam |

## Qanday qilinadi

### Yangi qoida qoʻshish
1. **Qoida qoʻshish**ni bosing, nom va xizmat kodini (bitta raqam) kiriting.
2. **Kunduzgi manzil** va **Tungi manzil**ni tanlang.
3. Kerak boʻlsa PIN qoʻying.
4. **Qoʻshish**ni bosing — yangi qoida sukut boʻyicha **Kunduzgi** holatda boshlanadi.

### Holatni panel orqali almashtirish
1. Jadvalda qoida qatoridagi oy/quyosh belgisini bosing — holat darhol **Kunduzgi** ↔ **Tungi** almashadi.

### Holatni telefon orqali almashtirish
1. Telefonda `*28<kod>` terib yuboring (masalan `*281`).
2. PIN qoʻyilgan boʻlsa, soʻralganda PIN kiritiladi.

### BLF chiroqcha sozlash
1. SIP telefon/sip.js sozlamasida BLF tugmasiga `Custom:DAYNIGHT<kod>` kalit kodini kiriting — chiroqcha
   joriy holatni koʻrsatadi va bosilganda almashtiradi.

### PINni olib tashlash
1. Qoidani tahrirlashga oching, **PINni olib tashlash**ni belgilang, **Saqlash**.

### Oʻchirish
1. Qator oxiridagi savat belgisini bosing.
2. Qoida boshqa joyda ishlatilayotgan boʻlsa, oʻchirish bloklanadi — avval shu bogʻlanishlarni olib tashlang.
3. Oʻchirilgan qoidaga yoʻnaltirilgan qoʻngʻiroqlar endi javobsiz ohang eshittiradi.

> [!TIP]
> Kun/Tun rejimi — bitta tugma/kod bilan tezkor almashtirish uchun qulay; agar haftalik avtomatik jadval kerak boʻlsa, [Ish vaqti](/docs/timegroups) sharti koʻproq mos keladi.

> [!WARNING]
> Holat avtomatik qaytmaydi — "Tungi"ga oʻtkazilgan qoida ertalab yana qoʻlda (kod yoki panel orqali) "Kunduzgi"ga qaytarilmaguncha shunday qolaveradi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| `*28<kod>` ishlamayapti | Kod notoʻgʻri terilgan yoki PIN xato kiritilgan | Qoidadagi aniq kodni va PINni tekshiring |
| BLF chiroqcha yonmayapti | Telefonda `Custom:DAYNIGHT<kod>` toʻgʻri sozlanmagan | Kod qoidadagi xizmat kodiga mos ekanini tekshiring |
| Qoidani oʻchirib boʻlmayapti | Kiruvchi marshrut yoki boshqa manzilda ishlatilmoqda | Avval oʻsha bogʻlanishlarni olib tashlang |

## Bog'liq bo'limlar

- [Ish vaqti](/docs/timegroups)
- [Kiruvchi marshrutlar](/docs/inbound)
- [Xususiyat kodlari](/docs/featurecodes)
