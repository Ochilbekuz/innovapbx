---
id: access
title: Kirish (SSH va veb-panel)
group: system
order: 150
path: /settings/access
summary: SSH va veb-panel portlarini xavfsiz oʻzgartirish — qoʻllash-tasdiqlash oqimi, login buyrugʻi va ommaviy tasdiqlash havolasi bilan.
---

# Kirish (SSH va veb-panel)

Serverga qanday ulanilayotganini — **SSH** portini va **veb-panel**ning HTTP/HTTPS portlarini — shu
yerdan koʻrasiz va xavfsiz oʻzgartirasiz. Portni almashtirish ham **Firewall** sahifasidagi kabi avval
qoʻllanadi, soʻng tasdiqlash kutiladi: tasdiqlamasangiz, muddat tugaganda **avtomatik eski portga
qaytadi** — bu serverga kirishni butunlay yoʻqotib qoʻymaslik uchun himoya.

## Qayerda
Menyu: **Tizim → Kirish**. Kim koʻradi: faqat `*` (toʻliq administrator) ruxsati bor foydalanuvchi.

## Asosiy tushunchalar

- **SSH holati** — sshd ishlab turgani, joriy port, tinglanayotgan portlar va parol bilan kirish
  yoqilgan/oʻchirilganligi shu yerda koʻrinadi.
- **Kirish yoʻriqnomasi** — joriy portga mos `ssh -p <port> innova@<host>` buyrugʻi — **Nusxalash**
  tugmasi bilan bitta bosishda koʻchiriladi.
- **Root bilan kirish** — xavfsizlik uchun yopiq; kirgandan keyin `sudo -i` ishlatiladi.
- **Host firewall** — agar server tashqi (hosting/ufw) firewall orqali himoyalangan boʻlsa, yangi portni
  oʻsha tomonda ham ochish kerakligi haqida eslatma chiqadi.
- **Qoʻllash → Tasdiqlash oqimi** — **Firewall** sahifasi bilan bir xil: **Qoʻllash** bosilgach oʻzgarish
  darhol kuchga kiradi, lekin **kutilayotgan** holatda qoladi va tasdiqlash uchun hisoblagich koʻrinadi.
- **Veb-panel porti oʻzgarganda** — qoʻllagandan soʻng brauzer avtomatik yangi manzildagi ommaviy
  tasdiqlash sahifasiga (`/access-confirm`) oʻtkaziladi — u yerda **Tasdiqlash**ni bosib, yangi manzilga
  kirasiz.

## Maydonlar

| Maydon | Nima qiladi | Misol / sukut |
|---|---|---|
| Yangi SSH port | SSH xizmati tinglaydigan port | 1–65535 oraligʻida, masalan `2222` |
| HTTP port | Veb-panelning shifrlanmagan porti | masalan `8080` |
| HTTPS port | Veb-panelning shifrlangan porti | masalan `8443` |
| Tasdiqlash uchun vaqt (soniya) | Qoʻllashdan keyin tasdiqlash muddati | sukut qiymat bor, oʻzgartirish mumkin |

## Qanday qilinadi

### SSH portini oʻzgartirish
1. **SSH** boʻlimida **Yangi SSH port** maydoniga kerakli portni kiriting (1–65535).
2. **Qoʻllash**ni bosing — oʻzgarish darhol kuchga kiradi va **kutilayotgan** holatga oʻtadi.
3. Yangi port bilan ulanishni sinab koʻring (koʻrsatilgan `ssh -p <port> ...` buyrugʻi bilan).
4. Ishlasa — **Tasdiqlash**ni bosing. Agar muddat ichida tasdiqlamasangiz, port **avtomatik eskisiga
   qaytadi**.

### Veb-panel portlarini oʻzgartirish
1. **Veb-panel** boʻlimida **HTTP port** va/yoki **HTTPS port** maydonlarini toʻldiring.
2. **Qoʻllash**ni bosing — yangi manzil koʻrsatilgan tasdiqlash oynasida **Qoʻllash**ni yana bosing.
3. Brauzer avtomatik yangi manzildagi tasdiqlash sahifasiga oʻtadi — u yerda **Tasdiqlash**ni bosib,
   kirish sahifasiga qaytasiz.
4. Agar muddat ichida tasdiqlamasangiz, portlar **avtomatik eskisiga qaytadi**.

## Maslahatlar va cheklovlar

> [!WARNING]
> Agar yangi port bilan ulanishni (ayniqsa SSH) yoʻqotib qoʻysangiz — **tashvishlanmang**: tasdiqlamagan
> holda belgilangan muddat tugaganda tizim **oʻzi** avvalgi portga qaytaradi.

> [!TIP]
> Veb-panel portini oʻzgartirishdan oldin yangi tasdiqlash havolasini ochadigan brauzer oynasi bloklanib
> qolmasligiga ishonch hosil qiling (popup-bloker boʻlmasin).

- Bir vaqtning oʻzida faqat bitta **kutilayotgan** oʻzgarish boʻlishi mumkin — u hal qilinmaguncha
  (tasdiqlangan yoki muddati tugab qaytarilgan) yangisini qoʻllab boʻlmaydi.
- Port boshqa xizmat tomonidan band boʻlsa, qoʻllashda tegishli maydon qizil bilan belgilanadi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| «Bu port boshqa xizmat uchun band» | Kiritilgan port serverda allaqachon band | Boshqa boʻsh port tanlang |
| sshd ishlamayapti ogohlantirishi | SSH xizmati toʻxtagan yoki eʼlon qilingan portda tinglamayapti | Serverdagi sshd holatini tekshiring |
| Oʻzgarish kutilayotgan holatda qolib ketdi | Tasdiqlanmagan | **Tasdiqlash**ni bosing yoki muddat tugashini kuting (avtomatik qaytadi) |
| Veb-panel manziliga ulanib boʻlmayapti | Yangi port host firewallda ochilmagan | Host firewallda (ufw/hosting) yangi portni oching |
| Tasdiqlash havolasi ishlamayapti | Havola muddati oʻtgan yoki notoʻgʻri | Eski manzil avtomatik tiklanganini tekshiring, qayta urinib koʻring |

## Bog'liq bo'limlar

- [Firewall](/docs/firewall)
- [Tarmoq](/docs/network)
- [Xavfsizlik](/docs/security)
