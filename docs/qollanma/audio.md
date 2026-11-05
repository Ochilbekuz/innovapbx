---
id: audio
title: Audio kutubxona
group: apps
order: 10
path: /audio
summary: IVR salomlashuvi, navbat eslatmalari va kutish musiqasi uchun audio fayllar; yozib olish va matndan audio yaratish (TTS).
---

# Audio kutubxona

**Audio kutubxona** — tizimda ishlatiladigan barcha ovozli xabarlarning markazi: IVR salomlashuvi, eʼlon
matnlari, kutish musiqasi (MOH) fayllari. Bu yerga fayl yuklash, mikrofon bilan yozib olish yoki matndan
(TTS) avtomatik audio yaratish mumkin — keyin boshqa ekranlarda (IVR, Eʼlonlar, Navbatlar) shu fayllardan
tanlanadi.

## Qayerda

Menyu: **Ilovalar → Audio kutubxona**. Kim koʻradi: `apps` ruxsatiga ega foydalanuvchilar tahrirlaydi,
qolganlar faqat koʻradi.

## Asosiy tushunchalar

- **Fayl** — yuklangan har qanday audio avtomatik `WAV, 8kHz, mono` formatiga oʻgiriladi (Asterisk shunday
  talab qiladi) — asl format WAV/MP3/OGG/WEBM boʻlishi mumkin.
- **Kutish musiqasi sinfi (MOH)** — bir nechta fayldan yigʻilgan toʻplam, [Navbatlar](/docs/queues)da
  tanlanadi. Har doim roʻyxatda bitta sinf **«Asosiy»** boʻladi — navbat, park va boshqa joylarda aniq
  sinf tanlanmagan boʻlsa, shu sinf ishlatiladi. Asosiy sinfni oʻchirib boʻlmaydi, lekin istalgan sinfni
  **Asosiy qilish** tugmasi orqali asosiy qilib tayinlash mumkin (nomi "default" boʻlishi shart emas).
- **Aralashtirib chalish** — yoqilsa, sinf fayllari tasodifiy tartibda, oʻchirilgan boʻlsa — roʻyxat
  tartibida ketma-ket chalinadi.
- **Matndan audio (TTS)** — matn kiritilsa, tizim uni ovozga aylantirib kutubxonaga saqlaydi. Ishlashi uchun
  [Integratsiyalar](/docs/integrations) sahifasida nutq sintezi provayderi (Yandex) sozlangan boʻlishi kerak.

## Maydonlar

### Fayl yuklash

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Fayl | Yuklanadigan audio | WAV, MP3 yoki OGG, 20MB gacha |

### Mikrofon bilan yozish

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Yozuv nomi | Saqlanadigan fayl nomi | Ixtiyoriy, boʻsh — «Yozuv» |
| Davomiylik | Yozib olish davomiyligi | Koʻpi bilan 5 daqiqa |

### Kutish musiqasi sinfi

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Nom | Sinf identifikatori | Faqat kichik lotin harflari/raqam/`_`/`-`, 1–32 belgi |
| Fayllarni aralashtirib chalish | Tartib tasodifiy yoki ketma-ket | Sukut — oʻchirilgan (ketma-ket) |
| Fayllar | Sinfga kiritilgan audiolar | Audio kutubxonadagi mavjud fayllardan tanlanadi |

### Matndan audio yaratish

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Audio nomi | Saqlanadigan fayl nomi | Boʻsh — matndan avtomatik olinadi |
| Matn | Ovozga aylantiriladigan matn | Koʻpi bilan 2000 belgi |

## Qanday qilinadi

### Fayl yuklash
1. **Fayllar** tabida faylni belgilangan maydonga tashlang yoki **Fayl tanlash**ni bosing.
2. WAV/MP3/OGG formatdagi, 20MB gacha fayl avtomatik yuklanadi va WAV 8kHz monoga oʻgiriladi.

### Mikrofon bilan yozib olish
1. **Yoki mikrofon bilan yozib oling** bloqida **Yozishni boshlash**ni bosing (brauzer mikrofonga ruxsat soʻraydi).
2. **Toʻxtatish**ni bosing, nomini kiriting, **Saqlash**.

### Matndan audio yaratish (TTS)
1. Avval [Integratsiyalar](/docs/integrations) sahifasida nutq sintezi provayderini sozlang (faqat admin uchun koʻrinadi, sozlanmagan boʻlsa karta shu haqda ogohlantiradi).
2. **Matndan audio yaratish** kartasida **Boshlash**ni bosing, matnni kiriting (koʻpi bilan 2000 belgi).
3. **Tinglab koʻrish** orqali natijani eshitib koʻring, mamnun boʻlsangiz nom kiritib **Saqlash**.

### Kutish musiqasi sinfi yaratish
1. **Kutish musiqasi** tabida **Yangi sinf**ni bosing.
2. Nom bering (faqat kichik lotin harf/raqam/`_`/`-`), kerakli fayllarni biriktiring.
3. **Aralashtirib chalish**ni kerak bo'lsa yoqing, **Qoʻshish**.
4. Yangi sinfni [Navbatlar](/docs/queues)dagi "Kutish musiqasi" maydonida tanlang.

### Sinfni asosiy qilish
1. **Kutish musiqasi** tabida kerakli sinf qatorida yulduzcha belgili **Asosiy qilish** tugmasini bosing.
2. «Asosiy» belgisi shu sinfga koʻchadi, avvalgi asosiy sinf oddiy sinfga aylanadi (uni endi oʻchirish ham mumkin).
3. Aniq sinf tanlanmagan barcha joylar (navbat, park, kanal hold) darhol yangi asosiy sinfni eshita boshlaydi — qoʻshimcha sozlash kerak emas.

### Faylni oʻchirish
1. Qator oxiridagi savat belgisini bosing.
2. Fayl IVR/eʼlon/MOH sinfida ishlatilayotgan boʻlsa, oʻchirish bloklanadi — avval shu bogʻlanishlarni olib tashlang.

> [!TIP]
> Qisqa va aniq salomlashuv matnlari uchun TTS juda tez — studiyaga bormasdan "Diqqat, suhbat yozib olinadi" kabi xabarlarni bir necha soniyada tayyorlash mumkin.

> [!WARNING]
> Joriy asosiy kutish musiqasi sinfini oʻchirib boʻlmaydi — avval boshqa sinfni **Asosiy qilish** orqali tayinlang.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Fayl yuklanmayapti | Format qoʻllab-quvvatlanmaydi yoki 20MB dan katta | WAV/MP3/OGG/WEBM, 20MB gachasini yuklang |
| TTS tugmasi "sozlanmagan" deb koʻrsatadi | [Integratsiyalar](/docs/integrations)da nutq sintezi ulanmagan | Admin integratsiyani sozlashi kerak |
| Mikrofon ishlamayapti | Brauzer ruxsat bermagan yoki mikrofon topilmagan | Brauzer sozlamalarida mikrofonga ruxsat berib, qayta urining |
| Faylni oʻchirib boʻlmayapti | IVR/eʼlon/MOH sinfida ishlatilmoqda | Avval oʻsha bogʻlanishlarni olib tashlang |
| Asosiy sinfni oʻchirib boʻlmayapti | Joriy asosiy sinf, oʻchirish taqiqlangan | Boshqa sinfni **Asosiy qilish**, keyin eskisini oʻchiring |

## Bog'liq bo'limlar

- [IVR](/docs/ivr)
- [Navbatlar](/docs/queues)
- [Eʼlonlar](/docs/announcements)
- [Integratsiyalar](/docs/integrations)
