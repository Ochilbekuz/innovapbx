# O'zgarishlar tarixi

## 1.0.11 — 2026-11-03
OnlinePBX'dagi, lekin bizda hali bo'lmagan funksiyalar (M10):
- **Qayta qo'ng'iroq vidjeti (Callback widget)** — saytga bitta `<script>` qatori bilan qo'yiladi; mijoz raqamini
  qoldiradi → PBX avval operatorga, u javob bergach mijozga qo'ng'iroq qiladi. Ruxsat etilgan domenlar (Origin),
  spam-tuzoq (honeypot), IP/raqam/vidjet bo'yicha tezlik cheklovi, qora ro'yxat va toll-fraud himoyasi; so'rovlar tarixi.
- **O'tkazib yuborilgan qo'ng'iroq xabarnomasi** — qoida bo'yicha (hammasi / DID / navbat / ring group / ichki raqam) Telegram yoki e-pochtaga
  darhol xabar; «sinov» tugmasi, yuborilgan xabarlar jurnali.
- **Matndan nutq (TTS, Yandex SpeechKit)** — matn yozib audio yaratish va oldindan eshitish; integratsiyalar
  sahifasida kalit sozlash va sinov. Kalit bazada maxfiy saqlanadi, API'da qaytarilmaydi.
- **Qo'ng'iroq sifatini baholash (QA)** — baholash varaqalari (ha/yo'q va 1–5 ball, vazn, «muhim» mezon),
  qo'ng'iroqni baholash, operatorlar bo'yicha o'rtacha ball; operator o'z baholarini «Men» sahifasida ko'radi.
- **Ikki bosqichli kirish (2FA, TOTP)** — Google Authenticator va shu kabilar; zaxira kodlar; siyosat
  (o'chiq / faqat adminlar / hamma), admin foydalanuvchining 2FA'sini tiklay oladi. Noto'g'ri kodlar ham hisobni
  bloklaydi (parolni bilgan hujumchi kodlarni cheksiz terib ko'ra olmaydi).
- **Real vaqt hodisalar oqimi (WebSocket)** — `/api/public/v1/events/ws`: qo'ng'iroq hodisalari jonli, uzilishdan
  keyin `since_seq` bilan qayta olish; `events:read` huquqli API kalit bilan.

## 1.0.10 — 2026-11-03
Qo'ng'iroqlar tarixi (`/cdr`) tuzatishlari:
- **Boshlanish/tugash vaqti endi soat:daqiqa bilan** (sukut 00:00 — 23:59). Oraliq Toshkent vaqtida hisoblanadi —
  avval kun chegarasi UTC bo'yicha olinardi (5 soat siljish), 00:00–05:00 orasida «bugun» kechagi kun bo'lib qolardi.
- **Kengaytirilgan qidiruv kataklari to'g'ri joylashdi**: rejim tanlovi butun qatorni egallab, qiymat katagini
  siqib qo'yardi; shablon qatori ikki aniq guruhga (tanlash/qo'llash/o'chirish · nom/saqlash) ajratildi.
- Holat belgilari (badge) va vaqt ustuni endi qatorga bo'linmaydi; «Qoʻngʻiroq qiluvchi nomi» xatosi tuzatildi.

## 1.0.9 — 2026-11-03
FreePBX'ning asosiy, lekin hali bo'lmagan modullari qo'shildi:
- **E'lonlar (Announcements)** — audio ijro etib keyingi manzilga o'tadi (o'tkazib yuborish/takrorlash tugmasi, javob bermasdan ijro).
- **Boshqa manzillar (Misc Destinations)** — istalgan raqamga yo'naltirish (chiquvchi qoidalar, toll/PIN amal qiladi) va
  **Misc Applications** — o'z xizmat kodingiz → istalgan manzil.
- **Park sozlamalari** — lot raqami, slotlar, kutish vaqti va vaqt tugaganda qayerga; hozir park qilingan qo'ng'iroqlar ro'yxati.
- **Paging / Intercom** — guruhga e'lon (bir/ikki tomonlama, band qurilmani o'tkazib yuborish, signal), `*80<raqam>` intercom (avtojavob).
- **Call Waiting** — har bir ichki raqam uchun yoqish/o'chirish, `*56`/`*57` xizmat kodlari.
- **PIN to'plamlari (PIN Sets)** — chiquvchi marshrutga bir nechta PIN (har biri yorlig'i bilan), urinishlar cheklovi; yorliq CDR'ga yoziladi.
- **Telefon kitobi** — kontaktlar va raqamlar, CSV import/eksport.
- **CallerID Lookup** — kiruvchi qo'ng'iroq ismini telefon kitobi / CRM / HTTP manbadan aniqlash (sinov tugmasi bilan).
- **Kiruvchi marshrut: CID ism prefiksi va Alert-Info** (alohida qo'ng'iroq ohangi).
- **Ichki raqamlarni CSV import/eksport (Bulk Handler)** — avval «quruq sinov», keyin bitta tranzaksiyada qo'llash; yangi parollar bir marta yuklab olinadi.
- **Qo'ng'iroqlar tarixi: kengaytirilgan qidiruv (FreePBX CDR Reports shabloni).** Raqam/qabul qiluvchi/DID bo'yicha
  «o'z ichiga oladi / bilan boshlanadi / bilan tugaydi / aniq» va «emas»; CallerID ismi, ichki raqam, trunk, accountcode
  (PIN yorlig'i), holat (bir nechta), davomiylik oralig'i, **faqat yozuvli / yozuvsiz**. Qidiruvni **shablon** sifatida
  nom bilan saqlab, bir bosishda qayta qo'llash; natijani **CSV** ga eksport (Toshkent vaqti, Excel uchun xavfsiz).
  Jadvalda endi qo'ng'iroq qiluvchi ismi va accountcode ustuni.

## 1.0.8 — 2026-11-03
- **Yangi: «Tarmoq» sahifasi** (Sozlamalar → Tarmoq), Issabel'ning Network bo'limi andozasida, lekin xavfsizroq:
  - **Umumiy** — host nomi, DNS serverlar va qidiruv domenlari, joriy standart shlyuz;
  - **Interfeyslar** — har bir fizik/bond/vlan interfeys uchun DHCP↔Statik, IP/prefiks, shlyuz, MTU;
  - **Statik marshrutlar** — qo'shish/tahrirlash/o'chirish, jonli marshrut jadvalini ko'rish.
  - **Xavfsizlik: tasdiqlanmasa — avtomatik qaytariladi.** Har bir qo'llash 60–600 soniyalik taymer bilan
    (sukut 180 s): shu vaqt ichida yangi sozlamadan «Tasdiqlash» bosilmasa, eski holat avtomatik tiklanadi —
    noto'g'ri IP/shlyuz yozib serverni tarmoqdan uzib qo'yish imkonsiz. Xizmat qayta ishga tushsa ham
    tasdiqlanmagan o'zgarish darhol qaytariladi.
  - Faqat **Debian (ifupdown)** o'rnatmada (ISO) to'liq tahrirlanadi; netplan/NetworkManager boshqargan
    serverda (masalan rivojlanish muhiti) sahifa **faqat ko'rish** rejimida — sabab banner tarzida ko'rsatiladi.
- **Yangi: asosiy menyu yig'iladigan.** Har bir guruh sarlavhasi endi tugma — bosib yig'ish/yoyish mumkin;
  holat eslab qolinadi, faol sahifa joylashgan guruh doim ochiq turadi.

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
