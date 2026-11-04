---
id: missedcalls
title: Javobsiz qoʻngʻiroq xabari
group: apps
order: 90
path: /missed-calls
summary: Javobsiz qoldirilgan qoʻngʻiroqlar haqida Telegram/E-mail orqali avtomatik xabar beruvchi qoidalar.
---

# Javobsiz qoʻngʻiroq xabari

Ushbu boʻlim javobsiz qolgan qoʻngʻiroqlar haqida kerakli odamlarga **Telegram** yoki **E-mail** orqali
darhol xabar beradi. Masalan: barcha DID raqamlariga tushgan javobsiz qoʻngʻiroqlar haqida menejerning
Telegram chatiga xabar yuborilsin — deb qoida yaratish mumkin.

## Qayerda

Menyu: **Ilovalar → Javobsiz qoʻngʻiroq xabari**. Kim koʻradi: `apps` ruxsatiga ega foydalanuvchilar
tahrirlaydi, qolganlar faqat koʻradi.

## Asosiy tushunchalar

- **Qoida** — qaysi qoʻngʻiroqlar (qamrov) haqida, kimga (qabul qiluvchilar) xabar yuborilishini belgilaydi.
- **Qamrov** — qoidaning qaysi qoʻngʻiroqlarga tegishli ekani: **Hammasi**, muayyan **DID**, **Navbat**,
  **Guruh** yoki **Ichki raqam**.
- **Ichki qoʻngʻiroqlarni ham oʻz ichiga olsin** — yoqilmasa, faqat tashqaridan kelgan javobsiz
  qoʻngʻiroqlar haqida xabar beriladi; yoqilsa, ichki raqamlar orasidagi javobsiz qoʻngʻiroqlar ham hisobga olinadi.
- **Qabul qiluvchilar** — Telegram chat ID(lar) va/yoki E-mail manzil(lar); bir qoidada bir nechtasi boʻlishi mumkin.
- **Xabarlar jurnali** — har bir yuborilgan (yoki yuborilmagan) xabarning holati (navbatda/yuborildi/
  muvaffaqiyatsiz), urinishlar soni va xato matni koʻrinadigan tarix.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nomi | Qoida nomi | Majburiy, koʻpi bilan 128 belgi |
| Qamrov turi | Qaysi qoʻngʻiroqlarga tegishli | Hammasi / DID / Navbat / Guruh / Ichki raqam |
| Qiymat | Qamrov turi "Hammasi" dan farqli boʻlsa — aniq DID/navbat/guruh/ichki raqam | Masalan DID uchun `998712345678` |
| Ichki qoʻngʻiroqlarni ham oʻz ichiga olsin | Ichki-ichki javobsiz qoʻngʻiroqlar ham xabar qilinsinmi | Sukut — oʻchirilgan |
| Telegram chat ID | Xabar yuboriladigan Telegram chat(lar) | Masalan `-100123456789` |
| E-mail | Xabar yuboriladigan email manzil(lar) | Masalan `ism@korxona.uz` |
| Yoqilgan | Qoida faol yoki vaqtincha toʻxtatilgan | Sukut — yoqilgan |

## Qanday qilinadi

### Yangi qoida yaratish
1. **Yangi qoida**ni bosing, nom kiriting.
2. **Qamrov turi**ni tanlang; "Hammasi"dan farqli boʻlsa — tegishli qiymatni (DID/navbat/guruh/ichki raqam) kiriting.
3. Kerak boʻlsa **Ichki qoʻngʻiroqlarni ham oʻz ichiga olsin**ni yoqing.
4. Bitta yoki bir nechta **Telegram chat ID** va/yoki **E-mail** qoʻshing.
5. **Qoʻshish**ni bosing.

### Qoidani sinash
1. Qoida qatorida sinov belgisini (test tugmasi) bosing — barcha qabul qiluvchilarga sinov xabari yuboriladi.
2. Natija toast xabarida koʻrinadi: muvaffaqiyatli yoki xato matni bilan.

### Qoidani vaqtincha oʻchirish
1. Qoidani tahrirlashga oching, **Yoqilgan**ni oʻchiring, **Saqlash** — qoida ishlamaydi, lekin saqlanib qoladi.

### Xabarlar jurnalini koʻrish
1. **Xabarlar jurnali** tabiga oʻting — yuborilgan har bir xabarning vaqti, qoidasi, qoʻngʻiroq maʼlumoti,
   holati, urinishlar soni va (muvaffaqiyatsiz boʻlsa) xato matni koʻrinadi.

### Oʻchirish
1. Qator oxiridagi savat belgisini bosing, tasdiqlang.

> [!TIP]
> Avval **Sinash** tugmasi bilan Telegram/E-mail toʻgʻri sozlanganini tekshirib oling — ishlab turgan
> sozlamaga ishonib qolmang.

> [!WARNING]
> Bir qoʻngʻiroq bir nechta qoidaga toʻgʻri kelishi mumkin (masalan "Hammasi" va aniq bir "Navbat" qoidasi)
> — bunday holda **barcha mos qoidalar** boʻyicha alohida xabar yuboriladi, takrorlanishi mumkin.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Xabar kelmayapti | Qoida oʻchirilgan yoki qamrov mos kelmaydi | Qoidani **Yoqilgan** holatga oʻtkazing, qamrovni tekshiring |
| Telegramga xabar yetib bormayapti | Chat ID notoʻgʻri yoki bot guruhga qoʻshilmagan | Chat ID'ni tekshiring, botni guruhga qoʻshing, **Sinash** bilan tasdiqlang |
| E-mail kelmayapti | Manzil notoʻgʻri yoki SMTP sozlanmagan | [Integratsiyalar](/docs/integrations)da SMTP sozlamalarini tekshiring |
| Jurnalda "Muvaffaqiyatsiz" holati koʻp | Qabul qiluvchi manzil/chat yaroqsiz | Xato matnini oʻqib, qabul qiluvchini toʻgʻrilang |

## Bog'liq bo'limlar

- [Integratsiyalar](/docs/integrations)
- [Navbatlar](/docs/queues)
- [Qoʻngʻiroq guruhlari](/docs/ringgroups)
- [CDR (qoʻngʻiroqlar tarixi)](/docs/cdr)
