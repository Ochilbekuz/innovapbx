# Qo'llanma fayl formati (yozuvchilar uchun — veb-panelga KIRMAYDI, `_` bilan boshlangan fayllar o'tkazib yuboriladi)

Har bo'lim — `docs/qollanma/<id>.md` fayli. Veb-paneldagi «Qo'llanma» sahifasi shu fayllarni o'qiydi,
GitHub ham to'g'ridan-to'g'ri ko'rsatadi.

## 1. Sarlavha bloki (majburiy, fayl boshida)

```
---
id: extensions
title: Ichki raqamlar
group: users
order: 10
path: /extensions
summary: Xodimlar uchun ichki raqam (SIP akkaunt) yaratish, parol, ovozli pochta, Follow Me.
---
```

- `id` — fayl nomi bilan bir xil. Ekran hujjati bo'lsa — ekran id'si (`web/src/shell/screens.ts`dagi `id`),
  shunda sahifadagi «?» tugmasi aynan shu bo'limni ochadi.
- `group` — `start` | `overview` | `users` | `connect` | `routing` | `apps` | `reports` | `system` | `appendix`.
- `order` — guruh ichidagi tartib (10, 20, 30… — menyudagi tartib bilan bir xil).
- `path` — ekran manzili (ekran bo'lmasa — qatorni yozmang).
- `summary` — bitta qator, 140 belgidan oshmasin (qidiruv va mundarija uchun).

## 2. Qo'llab-quvvatlanadigan Markdown (boshqa narsa ishlatmang — panel ko'rsatmaydi)

- `## Sarlavha`, `### Kichik sarlavha` (`#` — faqat bitta, fayl boshida, `title` bilan bir xil).
- Oddiy paragraflar; `**qalin**`, `*kursiv*`, `` `kod` ``.
- Ro'yxatlar: `- band` yoki `1. qadam` (bir daraja; ichma-ich ro'yxat — 2 bo'shliq bilan, faqat bitta qo'shimcha daraja).
- Jadval: `| A | B |` + `|---|---|` qatori.
- Kod bloki: ```` ``` ```` (til nomi ixtiyoriy).
- Havolalar: `[matn](/docs/<id>)` — boshqa bo'limga; `[matn](/extensions)` — panel ekraniga; `https://...` — tashqi.
- Eslatma bloklari (GitHub uslubi):
  ```
  > [!TIP]
  > Maslahat matni.
  ```
  Turlari: `[!NOTE]` (eslatma), `[!TIP]` (maslahat), `[!WARNING]` (diqqat), `[!CAUTION]` (xavfli).
- Rasm, HTML teglar, izoh `<!-- -->`, ichma-ich jadval — YO'Q.

## 3. Ekran bo'limining tuzilishi (shablon)

```
# <title>

<1–2 gapda: bu nima va nima uchun kerak — oddiy tilda, sohadan uzoq odam ham tushunsin.>

## Qayerda
Menyu: **<Guruh> → <Ekran nomi>** · Kim ko'radi: <rol/ruxsat>.

## Asosiy tushunchalar            (kerak bo'lsa — atamalar, qanday ishlaydi)

## Maydonlar                      (forma maydonlari jadvali: Maydon | Nima qiladi | Misol / sukut)

## Qanday qilinadi
### <Vazifa 1: masalan "Yangi ichki raqam qo'shish">
1. ...
### <Vazifa 2>

## Maslahatlar va cheklovlar       ([!TIP]/[!WARNING] bloklari, real cheklovlar)

## Muammolar va yechimlar          (| Belgi | Sabab | Yechim |)

## Bog'liq bo'limlar               (- [..](/docs/..))
```

## 4. Uslub

- Til: o'zbek (lotin), samimiy va aniq. Tugma/maydon nomlari — panelda qanday yozilgan bo'lsa AYNAN shunday,
  qalin bilan: **Saqlash**. (Manba: `web/src/i18n/<ns>.ts` faylidagi `uz` bloki.)
- Faqat kodda haqiqatda bor narsani yozing. Taxmin qilmang; ishonchingiz komil bo'lmasa — yozmang.
- Raqamlar/sukut qiymatlar/cheklovlar — koddan (API sxemasi `api/app/...`, forma validatsiyasi) tekshiring.

## 5. Tarjimalar (ru/en)

- Har bo'limning tarjimasi — `docs/qollanma/ru/<id>.md` va `docs/qollanma/en/<id>.md` (fayl nomi asl bilan bir xil).
  Panel foydalanuvchi tanlagan tilda ko'rsatadi; tarjimasi yo'q bo'lim uzbekcha chiqadi.
- `id`, `group`, `order`, `path` — asl bilan AYNAN bir xil; `title`, `summary` va matn tarjima qilinadi.
  Sarlavhalar, kod bloklari, eslatma bloklari va havola manzillari soni/tartibi o'zgarmaydi.
- Tugma/menyu nomlari — `web/src/i18n/<ns>.ts` dagi `ru`/`en` bloklaridan AYNAN.
- Uz bo'limini o'zgartirsangiz — ru/en ni ham yangilang. Tekshiruv: `python3 docs/qollanma/_tarjima_tekshir.py ru`
  (va `en`); `web/src/docs/content.test.ts` ham uchala tilni tekshiradi.
