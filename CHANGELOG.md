# O'zgarishlar tarixi

## 1.0.2 — 2026-11-02
- **O'zgardi:** SIP login endi ichki raqamning o'zi (FreePBX'dagidek): telefonga `t1-100` emas, `100` yoziladi.
  Mavjud raqamlar yangilanishda avtomatik o'tadi (migratsiya 0027) — **telefonlarda login'ni `100` ga o'zgartiring**, parol o'sha.
  SIP ma'lumotlaridagi «Domen» endi server manzili (oldin `t1` chiqardi).
- **Tuzatildi:** «parol xato» — telefon noto'g'ri login bilan 5 marta urinsa, uning **lokal IP'si 1 soatga bloklanardi**
  va to'g'ri parol ham 403 olardi. Endi lokal tarmoq (192.168/10/172.16–31) avtomatik bloklanmaydi
  (Xavfsizlik → Sozlamalar → «Lokal tarmoqdagi qurilmalarni avtomatik bloklamaslik», sukut yoqiq).
- **Yangi:** ichki raqam yaratishda parolni o'zingiz yozasiz yoki tasodifiysini olasiz; parolni ko'rish, nusxalash va
  keyin istalgan vaqtda o'zgartirish (`PUT /extensions/{id}/secret`, zaif parol rad etiladi).
- **Yangi:** yaratish oynasida darhol sozlash: yoqiq/o'chiq, tashqi qo'ng'iroq ruxsati, chiquvchi CallerID, DND,
  yo'naltirish, pickup guruhi, yozib olish.
- **Yangi:** qo'ng'iroqni yozib olish **kiruvchi** va **chiquvchi** uchun alohida (Doim / Hech qachon / So'rov bo'yicha `*1`).
  Eski bitta sozlama ikkalasiga ko'chiriladi (migratsiya 0028); FreePBX importi ham ikkalasini olib keladi.

## 1.0.1 — 2026-11-02
- **Tuzatildi:** «Chiquvchi marshrutlar → Yangi marshrut» panel `http://<IP>/` (HTTPS'siz) ochilganda bo'sh oq sahifa berardi
  (`crypto.randomUUID` faqat HTTPS/localhost'da bor). Naqsh qatori qo'shish ham shu sababdan yiqilardi.
- **Tuzatildi:** yangi chiquvchi marshrut saqlanmasdi (422): bo'sh ixtiyoriy maydonlar `null` bo'lib ketardi va
  standart naqsh `_998XXXXXXXXX` `_` bilan yuborilardi. Endi naqsh normallashtiriladi (`_` olib tashlanadi, katta harf);
  backend `8!` kabi `!` bilan tugaydigan naqshni ham qabul qiladi.
- **Tuzatildi:** HTTPS'siz panelda «Nusxalash» tugmalari (SIP parol, API kalit, provizioning/QR havola, eksport buyrug'i) ishlamasdi.
- **Yangi:** sahifada kutilmagan xato bo'lsa — bo'sh sahifa o'rniga xato matni va «Qayta yuklash» tugmasi.
- **Yangi:** `innova-update` — bir buyruq bilan yangilash (baza zaxirasi, `--check`, `--force`, `--images`).
- Versiya endi repo ildizidagi `VERSION` faylida.
