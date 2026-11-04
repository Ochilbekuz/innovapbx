---
id: trunks
title: Trunklar
group: connect
order: 10
path: /trunks
summary: SIP operatorlari bilan ulanish (trunk) — host/port, autentifikatsiya, kodeklar, sogʻlik holati, sinash.
---

# Trunklar

Trunk — sizning Innova PBXingiz bilan telefon operatori (yoki boshqa PBX) orasidagi SIP ulanish; shundan tashqi dunyoga qoʻngʻiroq chiqadi va tashqaridan kiradi. Bu boʻlimda trunklarni qoʻshish, sozlash, sogʻlik holatini kuzatish va sinab koʻrish mumkin.

## Qayerda

Menyu: **Ulanish → Trunklar**. Kim koʻradi: `connect:view` ruxsati. Qoʻshish/tahrirlash/oʻchirish — `connect:edit` ruxsati; boʻlmasa sahifada **"Sizda trunklarni boshqarish ruxsati yoʻq — faqat koʻrish va sinash mumkin"** eslatmasi chiqadi (sinash koʻrish huquqi bilan ham ishlaydi).

## Asosiy tushunchalar

- **Autentifikatsiya usuli**:
  - **IP boʻyicha (CIDR)** — operatordan keladigan paketlar koʻrsatilgan tarmoq(lar)dan kelganini tekshiradi, login/parol kerak emas.
  - **Registratsiya (login/parol)** — Innova PBX operatorga login/parol bilan registratsiya qiladi (klassik SIP registratsiya).
- **Sogʻlik holati** — **Ishlayapti**, **Aloqa yoʻq**, **Tekshirilmagan**, **Oʻchirilgan**; Registratsiya rejimida qoʻshimcha **Registratsiya qilingan** / **rad etildi** / **kutilmoqda** belgisi.
- **Sinash** — trunkka darhol tekshirish soʻrovi yuborib, aloqa bor/yoʻqligini va javob vaqtini koʻrsatadi.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| **Nom** | Trunkni tanish uchun nom | — (majburiy) |
| **Host** | Operator IP yoki domeni | `sip.operator.uz` (majburiy) |
| **Port** | SIP port | 1–65535 oraligʻida, sukut: 5060 |
| **Autentifikatsiya usuli** | **IP boʻyicha (CIDR)** yoki **Registratsiya (login/parol)** | — |
| **Qabul qilish (match CIDR)** | *(faqat IP rejimida)* Qaysi tarmoqlardan kelgan paket shu trunkka tegishli deb hisoblanadi | Har qatorda bitta CIDR, masalan `203.0.113.0/24` |
| **Login** / **Parol** | *(faqat Registratsiya rejimida)* Operator bergan hisob maʼlumotlari | Parolni oʻzgartirmasa boʻsh qoldirilsa joriysi qoladi |
| **From domain** | *(faqat Registratsiya rejimida)* Registratsiya qilinadigan domen/host | `sip.operator.uz` |
| **Chiquvchi Caller ID** | Bu trunk orqali chiqayotgan qoʻngʻiroqlarda koʻrsatiladigan raqam | ixtiyoriy, masalan `+998712000000` |
| **Kodeklar** | Qaysi ovoz kodeklari ishlatiladi | `ulaw`, `alaw`, `g722`, `opus` — kamida bittasi tanlanishi shart |
| **Maks. kanal** | Bir vaqtda shu trunk orqali nechta qoʻngʻiroq boʻlishi mumkin | boʻsh — cheklanmagan |
| **Yoqilgan** | Trunkni vaqtincha oʻchirib qoʻyish | sukut: yoqilgan |

## Qanday qilinadi

### Yangi trunk qoʻshish (IP boʻyicha)
1. **Yangi trunk** tugmasini bosing.
2. **Nom**, **Host**, **Port** kiriting, **Autentifikatsiya usuli**da **IP boʻyicha (CIDR)**ni tanlang.
3. **Qabul qilish (match CIDR)** maydoniga operator tarmog'ini kiriting.
4. Kerakli **Kodeklar**ni belgilang, ixtiyoriy **Chiquvchi Caller ID** va **Maks. kanal**ni kiriting.
5. **Qoʻshish** tugmasini bosing.

### Yangi trunk qoʻshish (Registratsiya orqali)
1. **Yangi trunk** tugmasini bosing, **Autentifikatsiya usuli**da **Registratsiya (login/parol)**ni tanlang.
2. **Login**, **Parol**, **From domain** maydonlarini toʻldiring.
3. Kodeklarni tanlang, **Qoʻshish**ni bosing.

### Trunkni sinash
1. Jadvalda kerakli trunk qatorida ulash (plug) ikonkasini bosing.
2. Ochilgan modalda **Muvaffaqiyatli**/**Muvaffaqiyatsiz** natija va javob vaqti (ms) koʻrinadi.

### Trunkni oʻchirish
1. Qatorda **Oʻchirish** ikonkasini bosing.
2. Ogohlantirishni oʻqing — bu trunk orqali chiqayotgan/kiruvchi aloqa darhol toʻxtaydi — va tasdiqlang.

## Maslahatlar va cheklovlar

> [!WARNING]
> Trunkni oʻchirish shu zahoti amal qiladi — agar trunk chiqish marshrutlarida ishlatilayotgan boʻlsa, bu yoʻnalishlar ishlamay qoladi. Oʻchirishdan oldin [Chiquvchi marshrutlar](/docs/outbound) boʻlimida qaysi marshrutlar shu trunkni ishlatayotganini tekshiring.

> [!TIP]
> Parolni oʻzgartirish shart boʻlmasa, **Parol** maydonini boʻsh qoldiring — joriy parol oʻzgarmasdan qoladi.

> [!TIP]
> Kamida bitta kodek tanlanishi shart; operator qoʻllab-quvvatlamaydigan kodekni belgilash chaqiruv sifatini yomonlashtirishi mumkin.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| "Host notoʻgʻri" | Host maydoni IP yoki domen shaklida emas | To'gri IP/domen kiriting |
| "«...» CIDR shaklida emas" | **Qabul qilish** maydonidagi qator CIDR formatida yozilmagan | `203.0.113.0/24` kabi formatda yozing |
| "Register rejimida parol kerak" | Registratsiya rejimida parol kiritilmagan (va trunkda hali parol saqlanmagan) | Parol maydonini toʻldiring |
| **Aloqa yoʻq** holati | Operator serveri javob bermayapti yoki tarmoq muammosi | Host/port toʻgʻriligini tekshiring, **Sinash** tugmasi bilan diagnostika qiling |
| **Registratsiya rad etildi** | Login/parol notoʻgʻri yoki operator tomonidan bloklangan | Login/parolni operator bilan tekshirib qayta kiriting |

## Bog'liq bo'limlar

- [Chiquvchi marshrutlar](/docs/outbound)
- [Kiruvchi marshrutlar](/docs/inbound)
