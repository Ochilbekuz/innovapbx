# O'zgarishlar tarixi

## 1.0.7 — 2026-11-03
- **Yangi: «Tizim holati» sahifasi** (Sozlamalar → Tizim holati, bosh paneldagi «Batafsil» havolasi ham shu yerga):
  - **Disk** — band/bo'sh joy va nima egallayotgani: qo'ng'iroq yozuvlari, zaxiralar, migratsiya fayllari,
    ovozli pochta, jurnallar (hajm va fayl soni);
  - **Tranklar** — har bir trank holati;
  - **Internet** — ulanish, DNS va kechikish (ms);
  - **SIP interfeysi** — Asterisk ishlayaptimi, transportlar (UDP/TCP/WSS, manzil:port), ro'yxatdan o'tgan qurilmalar soni.
- **Yangi: diskni tozalash.** «Diskni tozalash» oynasida tanlaysiz: N kundan eski yozuvlar, oxirgi N tadan tashqari
  zaxiralar, yuklangan FreePBX migratsiya fayllari. O'chirishdan oldin **qancha joy bo'shashi** ko'rsatiladi;
  ketayotgan zaxira/tiklash va faol migratsiyaga tegilmaydi; har bir tozalash auditga yoziladi. Faqat admin uchun.
- **Pleer: tezlik va istalgan joydan tinglash.** Qo'ng'iroqlar tarixidagi yozuv qatorida endi o'rin chizig'i —
  istalgan joyini bosib o'sha yerdan tinglaysiz (ijro boshlanmagan bo'lsa ham), vaqt «o'rin / davomiylik» ko'rinadi;
  **1× → 1.5× → 2×** tezlik tugmasi.
- Tuzatildi: ijrodan oldin tanlangan 2× tezlik birinchi «Tinglash»da 1× ga qaytib qolardi.

## 1.0.6 — 2026-11-03
- **Qo'ng'iroq yozuvlari — Qo'ng'iroqlar tarixida.** «Yozuv» ustuni endi jadvalning **oxirgi ustuni**:
  yozib olingan qo'ng'iroq qatorida ▶ **tinglash**, ⬇ **yuklab olish** (va huquqi bor admin uchun 🗑 o'chirish).
  Yozuvi yo'q qo'ng'iroqda ustun bo'sh turadi.
- Yuklab olingan fayl nomi endi tushunarli: `2026-11-03_01-12-35_<kimdan>_<kimga>.wav` (Toshkent vaqti);
  bitta qo'ng'iroqda bir nechta yozuv bo'lsa — `_1`, `_2`. Avval fayl nomi ichki ID edi. «Mening kabinetim»da ham shunday.
- Tuzatildi: Firefox'da yuklab olish ba'zan boshlanmay qolardi.
- Eslatma: qaysi qo'ng'iroq yozilishi **Ichki raqamlar → raqam → «Kiruvchi / Chiquvchi yozib olish»**
  (har doim / hech qachon / talab bo'yicha `*1`) sozlamasiga bog'liq.

## 1.0.5 — 2026-11-02
- **Yangi: rollar muharriri.** Sozlamalar → Foydalanuvchilar → **Rollar** bo'limida o'z rollaringizni yaratasiz
  (FreePBX'dagi User Management guruhlari kabi). Har bir rol uchun 6 ta bo'limning har biriga daraja beriladi:
  **Yo'q / Ko'rish / Tahrirlash**. Bo'limlar:
  - Monitoring (panel, ogohlantirishlar, jonli qo'ng'iroqlar);
  - Ichki raqamlar (qurilmalar, ovozli pochta);
  - Ulanish (trunklar, kiruvchi va chiquvchi marshrutlar);
  - Yo'naltirish (IVR, navbatlar, guruhlar, vaqt shartlari);
  - Ilovalar (audio, konferensiya, park, qora ro'yxat, kampaniyalar);
  - Hisobotlar (qo'ng'iroqlar, hisobotlar, yozuvlar).
- Foydalanuvchiga istalgan rolni berish mumkin. Ruxsat o'zgarsa, darhol kuchga kiradi, qayta kirish shart emas.
- «Ko'rish» darajasida sahifa ochiladi, lekin yaratish, tahrirlash va o'chirish tugmalari yashiriladi.
  Server ham bunday so'rovlarni rad etadi (403).
- Menyuda faqat ruxsat berilgan bo'limlar ko'rinadi.
- **Xavfsizlik:**
  - tizim bo'limi (foydalanuvchilar, xavfsizlik, zaxira, SIP, migratsiya, integratsiyalar) faqat admin uchun;
  - tizim rollari (admin, operator) o'zgartirilmaydi;
  - foydalanuvchisi bor rolni o'chirib bo'lmaydi.
- **Tuzatildi:** mavjud quti raqami bilan yangi umumiy ovozli pochta qutisi yaratilsa, «Bu quti raqami band» xatosi
  chiqadi (1.0.4 da umumiy «raqam band» xatosi chiqardi).

## 1.0.4 — 2026-11-02
- **Tuzatildi:** Boshqaruv panelidagi ogohlantirishlarda «Ko'rish» hech narsa qilmasdi — havolalar mavjud bo'lmagan
  sahifalarga (`/outbound-routes`, `/system`) yo'naltirardi. Endi to'g'ri sahifa ochiladi (Chiquvchi marshrutlar,
  Tizim holati, Reviziyalar).
- **Yangi:** panel HTTPS orqali ham ochiladi: `https://<server-IP>`. Sertifikat o'zi yaratiladi, 10 yil amal qiladi.
  Bu brauzer softfonining mikrofoni ishlashi uchun kerak. http orqali ochilsa, softfon HTTPS'ga o'tishni taklif qiladi.
  Oddiy http va telefon provizioningi (`/prov/`) avvalgidek ishlaydi. Brauzer birinchi kirishda sertifikat
  haqida ogohlantiradi — «Davom etish»ni bosing.
- **Xavfsizlik:** yangi o'rnatishda `/setup` bir martalik o'rnatish kodini so'raydi. Kod `install.sh` oxirida
  va server konsolida chiqadi. Endi tarmoqdagi istalgan odam birinchi bo'lib admin yarata olmaydi.
  Allaqachon sozlangan serverlarga bu ta'sir qilmaydi.
- **Tuzatildi:** ovozli pochta:
  - ichki raqam nomi o'zgarganda quti nomi ham yangilanadi;
  - umumiy quti raqami ichki raqam, navbat va boshqa raqamlar bilan to'qnashsa, tushunarli xato chiqadi;
  - bildirishnoma yuborishda xato bo'lsa, xabar yo'qolmaydi va qayta yuboriladi (migratsiya 0030).
- **Tasdiqlandi:** navbatda DND yoqilgan operator chaqirilmaydi. Park qilingan qo'ng'iroq 60 soniya javobsiz qolsa,
  park qilgan raqamga qaytadi. Ikkalasi jonli isbot bilan tekshirildi.
- **Ichki:** murakkab funksiyalar soddalashtirildi (`update_trunk`, FreePBX import mapperlari). Xatti-harakat o'zgarmadi.

## 1.0.3 — 2026-11-02
- **Tuzatildi:** «Yangi ichki raqam» oynasida «Qo'shimcha sozlamalar» ochilsa, oyna ekrandan oshib ketib, pastki maydonlar
  va «Yaratish» tugmasi ko'rinmasdi. Endi barcha modal oynalar ekran balandligiga sig'adi, ichi aylanadi,
  sarlavha va tugmalar doim ko'rinadi.

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
