# O'zgarishlar tarixi

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
