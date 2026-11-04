---
id: ornatish
title: O'rnatish
group: start
order: 20
summary: Innova PBXni ISO orqali yoki mavjud serverga skript bilan o'rnatish, keyinchalik yangilash.
---

# O'rnatish

Innova PBX ikki xil usulda o'rnatiladi — tayyor **ISO** orqali to'liq avtomatik, yoki mavjud Linux serverga **skript** bilan; ikkisining natijasi bir xil: `/opt/innova` papkasi, `innova-pbx` systemd xizmati va avtomatik generatsiya qilingan maxfiy kalitlar.

## Asosiy tushunchalar

- **Talablar**: 64-bitli (x86-64) server, kamida 2 yadro, 4 GB RAM, 20 GB+ disk (ISO uchun 32 GB+).
- **Asterisk host tarmoq rejimida** ishlaydi — SIP/RTP uchun NAT yo'q, shu sababli trafik to'g'ridan-to'g'ri server IP'siga keladi.
- **ISO** — Debian 13 (trixie) asosida, internetga ulanmasdan ham o'rnatiladi, disk butunlay serverga ajratiladi.
- **Skript (`install.sh`)** — Debian 12/13, Ubuntu 22.04/24.04 ustiga qo'yiladi, internet talab qiladi (Docker obrazlarini quradi yoki yuklaydi), serverdagi boshqa xizmatlarga tegmaydi (faqat kerakli portlar bo'sh bo'lishi kerak).
- Har ikki usulda ham oxirida konsolda bir martalik **O'rnatish kodi** chiqadi — bu kod [Birinchi sozlash](/docs/birinchi-sozlash) bosqichida administrator hisobini yaratishda so'raladi.

## Qanday qilinadi

### ISO orqali o'rnatish
1. ISO faylini yuklab olib USB flashga yozing (`dd` buyrug'i, Rufus yoki Etcher — "DD rejimi") yoki virtual mashinada CD sifatida ulang.
2. Serverni shu tashqi diskdan yuklang. Boot menyusidagi birinchi band — **"Innova PBX — avtomatik o'rnatish"** — 10 soniyada oʻzi boshlanadi (BIOS va UEFI ikkisida ham ishlaydi).
3. Faqat bir savol beriladi: `innova` foydalanuvchisi uchun parol (keyinchalik SSH va konsolga kirish uchun kerak bo'ladi). DHCP topilmasa, tarmoq sozlamalari (IP, maska, gateway, DNS) ham so'raladi.
4. O'rnatish tugagach server avtomatik qayta yuklanadi; birinchi yurish 2–5 daqiqa davom etadi (Docker obrazlari yuklanadi).
5. Konsolda chiqqan `http://<server-IP>/` manzilini boshqa kompyuterdan brauzerda oching — administrator yaratish sahifasi ([Birinchi sozlash](/docs/birinchi-sozlash)) ochiladi.

> [!WARNING]
> O'rnatish jarayonida **tanlangan diskdan tashqari birinchi topilgan disk butunlay tozalanadi** (LVM, bitta partitsiya qilib). Serverda saqlanishi kerak bo'lgan boshqa ma'lumotli disk bo'lsa, uni o'rnatishdan oldin uzib qo'ying.

### Skript bilan o'rnatish (mavjud serverga)
1. Serverga **root** huquqi bilan kiring, loyiha fayllarini (repozitoriyni) serverga joylang.
2. Quyidagi buyruqni ishga tushiring:
   ```
   sudo ./install.sh
   ```
3. Skript avval kerakli portlarni (80, 443, 5060, 5061, 5038, 8088, 5432, 8710) tekshiradi — ulardan biri band bo'lsa (masalan eski FreePBX/Asterisk, boshqa veb-server yoki Postgres), xato bilan to'xtaydi.
4. Docker o'rnatilmagan bo'lsa avtomatik o'rnatiladi (Debian 13 — rasmiy Debian repozitoriyasidan; Debian 12/Ubuntu — `download.docker.com`dan; compose 2.24+ allaqachon bor bo'lsa bu qadam o'tkazib yuboriladi).
5. Fayllar `/opt/innova`ga joylanadi, `innova-pbx` systemd xizmati yaratilib ishga tushiriladi.
6. Tayyor bo'lganda konsolda `TAYYOR: http://<server-IP>/` xabari va bir martalik **O'rnatish kodi** chiqadi.

### Qo'shimcha parametrlar (faqat skript usulida)
1. `--web-port 8080` — 80-port band bo'lsa boshqa portdan foydalanish uchun (faqat birinchi o'rnatishda qo'llanadi, keyin o'zgartirib bo'lmaydi).
2. `--images images.tar.zst` — tayyor Docker obrazlari fayli bilan o'rnatish (internetsiz yoki tezroq; ISO ichidagi `innova/images.tar.zst` yoki oldindan `docker save ... | zstd` bilan tayyorlangan fayl).
3. `--version V` — aniq versiyani o'rnatish (sukutda loyihadagi `VERSION` faylidagi versiya ishlatiladi).

### Keyinchalik yangilash
1. Serverga kirib quyidagini ishga tushiring:
   ```
   innova-update
   ```
   Bu GitHub'dan eng so'nggi versiyani oladi, bazani avval `/opt/innova/backups/` papkasiga zaxiraga oladi, `.env` fayli / baza / veb-port o'zgarishsiz qoladi.
2. Faqat yangi versiya bor-yo'qligini tekshirish: `innova-update --check`.
3. Tayyor obrazlar fayli bilan yangilash: `innova-update --images FAYL`.
4. Versiya "yangi emas" deb ko'rinsa ham qayta o'rnatish (buzilgan holatni tuzatish uchun): `innova-update --force`.

> [!NOTE]
> 1.0.1 versiyasidan oldin o'rnatilgan tizimlarda `innova-update` mavjud emas — bir marta qo'lda `git pull && ./install.sh` bajarilishi kerak, shundan keyin `innova-update` ishlay boshlaydi.

## Maslahatlar va cheklovlar

> [!WARNING]
> O'rnatishdan oldin 80, 5060, 5061, 5038, 8088, 5432, 8710-portlarni band qiluvchi boshqa xizmatlarni (eski FreePBX/Asterisk, veb-server, Postgres) to'xtating — aks holda skript shu yerda to'xtaydi.

> [!TIP]
> Serverga statik IP berish tavsiya etiladi — DHCP bilan IP o'zgarib qolsa, SIP qurilmalar ulanishni yo'qotishi mumkin.

> [!WARNING]
> Brauzerdagi softfon (WebRTC) mikrofonga kirish uchun **HTTPS** talab qiladi — oddiy `http://server-IP` orqali ishlamaydi. Stol telefonlari va mobil SIP ilovalari bunga qaramay muammosiz ishlaydi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| "portlar band" xatosi | Boshqa PBX/veb-server/Postgres shu portlarni egallagan | Mos xizmatni to'xtating yoki veb-port uchun `--web-port`dan foydalaning |
| `innova-pbx` xizmati ishga tushmadi | Docker konteyner xatosi | `journalctl -u innova-pbx -n 30` va `docker ps` orqali sababni tekshiring |
| Veb-panel uzoq vaqt ochilmaydi | Obrazlar yuklanishi uzoq davom etmoqda yoki xato yuz berdi | Yuqoridagi buyruqlar bilan loglarni tekshiring, keyin qaytadan urinib ko'ring |
| Brauzer softfoni ishlamayapti | Serverda HTTPS yo'q | Server uchun HTTPS (sertifikat) sozlang yoki stol telefon/SIP ilovasidan foydalaning |

## Bog'liq bo'limlar

- [Birinchi sozlash](/docs/birinchi-sozlash)
- [Tezkor boshlash](/docs/tez-boshlash)
- [Kirish](/docs/kirish)
