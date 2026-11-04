---
id: live
title: Jonli monitoring
group: overview
order: 20
path: /live
summary: Hozir davom etayotgan qoʻngʻiroqlar, navbatlar va ichki raqamlar holatini real vaqtda kuzatish, nazorat qilish.
---

# Jonli monitoring

Jonli monitoring — supervayzer yoki administrator uchun ekran: hozir kim bilan kim gaplashayotgani, navbatda necha kishi kutayotgani va qaysi ichki raqam band/boʻsh ekanini real vaqtda koʻrsatadi, kerak boʻlsa qoʻngʻiroqni tinglash/shivirlash/qoʻshilish imkonini beradi.

## Qayerda

Menyu: **Umumiy → Jonli monitoring**. Kim koʻradi: `monitor:view` ruxsati bor rol. Nazorat (tinglash/shivirlash/qoʻshilish) uchun amalga mos yozish huquqi (`monitor:edit`) kerak.

## Asosiy tushunchalar

- **Nazorat (spy) rejimlari** — faol qoʻngʻiroqqa boshqa odam sezmasdan qoʻshilish usullari:
  - **Tinglash** — faqat eshitadi, suhbatga taʼsir qilmaydi.
  - **Shivirlash** — faqat oʻz tomonidagi operatorga gapiradi, qoʻng'iroq qiluvchi eshitmaydi.
  - **Qoʻshilish** — suhbatga toʻliq uchinchi tomon sifatida qoʻshiladi, hamma eshitadi.
- Sahifa maʼlumotlari avtomatik yangilanadi; davomiylik hisoblagichlari soniya sayin jonli yuradi.
- Agar Asterisk bilan aloqa uzilsa, sahifa tepasida **"Asterisk bilan aloqa yoʻq"** ogohlantirishi chiqadi va maʼlumotlar vaqtincha yangilanishdan toʻxtaydi.

## Maydonlar

**Faol qoʻngʻiroqlar** jadvali:

| Ustun | Nima koʻrsatadi |
|---|---|
| Yoʻnalish belgisi | Kiruvchi / chiquvchi / ichki qoʻngʻiroq ikonkasi |
| **Kimdan** / **Kimga** | Qoʻngʻiroq tomonlari raqami |
| **Holat** | **Chaqirilmoqda**, **Suhbatda** yoki **Kutishda** |
| **Davomiyligi** | Qoʻngʻiroq boshlanganidan beri oʻtgan vaqt (jonli hisoblanadi) |
| Nazorat tugmalari | **Tinglash** / **Shivirlash** / **Qoʻshilish** |

**Navbatlar** kartalari (har bir navbat uchun alohida karta): **Navbatda** (kutayotganlar soni), **Eng uzun kutish**, **Operatorlar** (qancha operator faol/jamidan).

**Ichki raqamlar holati** panjarasi — har bir raqam uchun raqam, ism va holat belgisi: **Boʻsh**, **Chaqirilmoqda**, **Band**, **Band qilmaslik**.

## Qanday qilinadi

### Faol qoʻngʻiroqni nazorat qilish
1. **Faol qoʻngʻiroqlar** jadvalida kerakli qatorni toping.
2. Qator oʻng tomonidagi uch tugmadan birini bosing: **Tinglash**, **Shivirlash** yoki **Qoʻshilish**.
3. Muvaffaqiyatli boshlansa — **"Nazorat boshlandi"** bildirishnomasi chiqadi.

### Ichki raqam holatini tekshirish
1. Sahifa pastidagi **Ichki raqamlar holati** boʻlimiga qarang.
2. Har bir raqam kartasida joriy holat rangli belgi bilan koʻrsatiladi (masalan band boʻlsa qizil **Band** belgisi).

## Maslahatlar va cheklovlar

> [!WARNING]
> Nazorat qilish uchun sizning hisobingiz ichki raqamga bogʻlangan boʻlishi kerak — aks holda tugma bosilganda **"Sizning hisobingiz ichki raqamga bogʻlanmagan — nazorat qila olmaysiz"** xabari chiqadi.

> [!TIP]
> **Qoʻshilish** rejimidan ehtiyot boʻling — bu rejimda siz suhbatga toʻliq ishtirokchi sifatida qoʻshilasiz va barcha taraflar sizni eshitadi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| "Asterisk bilan aloqa yoʻq" ogohlantirishi | Asterisk xizmati bilan aloqa uzilgan | [Boshqaruv paneli](/docs/dashboard)dagi tizim sogʻligʻini tekshiring; davom etsa server administratoriga murojaat qiling |
| "Nazoratni boshlab boʻlmadi" | Qoʻngʻiroq allaqachon tugagan yoki hisobingiz ichki raqamga bogʻlanmagan | Jadvalni yangilang, hisobingizga ichki raqam biriktirilganini tekshiring |
| Ichki raqamlar roʻyxati boʻsh | Hali hech qanday ichki raqam yaratilmagan | [Ichki raqamlar](/docs/extensions) boʻlimida raqam qoʻshing |

## Bog'liq bo'limlar

- [Boshqaruv paneli](/docs/dashboard)
- [Ichki raqamlar](/docs/extensions)
