# O'zgarishlar tarixi

## 1.0.20 — 2026-11-05
- Yuqori paneldagi **Dialplan reviziyasi belgisi** endi faqat soatni emas, **sana, vaqt va vaqt zonasini** ko'rsatadi:
  «qo'llandi 05.11.26 19:48 UTC+5». Zona ustiga sichqoncha olib borilsa to'liq nomi chiqadi (`Asia/Tashkent`).
  Ilgari faqat «19:48» edi — qaysi kun va qaysi zona ekani noma'lum edi.

## 1.0.19 — 2026-11-04
- **Yangi yon menyu**: bir vaqtda faqat bitta bo'lim ochiq (akkordeon) — boshqasini ochsangiz oldingisi yig'iladi;
  boshqa bo'limdagi sahifaga o'tilsa o'sha bo'lim o'zi ochiladi.
- Menyuni **yig'ish/yoyish va qotirish**: qotirilgan (to'liq) yoki ixcham (faqat ikonalar) rejim; ixcham rejimda
  sichqoncha olib borilsa menyu sahifa ustida vaqtincha ochiladi. Tugma yoki **Ctrl+B** (⌘B); tanlov brauzerda saqlanadi.
- Asosiy bo'limlar **rang bilan ajratildi** (har bo'limga o'z rangi va ikonasi, ochiq bo'lim chizig'i, faol sahifa
  belgisi, ichidagi sahifalar soni); yopiq bo'limda turgan bo'lsangiz ham sarlavhada belgi qoladi.
- **Qo'llanma endi rus va ingliz tillarida ham** (54 bo'lim) — panel tilini almashtirsangiz qo'llanma ham, qidiruv ham
  o'sha tilga o'tadi. «Ilovalar» bo'limi nomi qo'llanmada menyu bilan bir xil qilindi.
- Pastki paneldagi Asterisk ish vaqti va holat yozuvlari endi tanlangan tilda (ilgari doim uzbekcha edi).
- Veb-server statik fayllarni gzip bilan siqib beradi — panel birinchi marta ~3 barobar tezroq yuklanadi.

## 1.0.18 — 2026-11-04
- **Tuzatish — «Sana va vaqt» sahifasi uzoq yuklanib, ochilmasdi**: server tizim buyrug'i (`timedatectl`) qotib qolsa
  netd uni timeout'da faqat «ustidan» to'xtatardi — `nsenter` ichidagi asl buyruq tirik qolib javobni 25–30 s ushlab
  turardi, API esa 10 s da uzilib xato berardi. Endi butun jarayon guruhi o'ldiriladi (timeout haqiqatan 3–10 s).
  Bu tarmoq, quvvat va firewall sahifalaridagi xuddi shu xavfni ham yopadi.
- Vaqt holatini o'qishda bitta yordamchi buyruq javob bermasa ham sahifa ochiladi (ma'lum bo'lmagan maydonlar bo'sh).
- netd buyruq timeout'ini endi aniq xato sifatida qaytaradi (`command_timeout`, 504) — ilgari ulanish jim uzilardi.
- «Sana va vaqt» yuklanmasa sahifa endi sababini ham ko'rsatadi (uz/ru/en).

## 1.0.17 — 2026-11-04
- **Muhim tuzatish — ish vaqti (vaqt shartlari) ishlamas edi**: hafta kunlari dialplan'da vergul bilan yozilardi
  (`mon,tue,...`) — Asterisk `GotoIfTime` buni hech qachon mos deb hisoblamaydi, natijada qo'ng'iroq doim «ish
  vaqtidan tashqari» yo'liga tushardi. Endi `mon&tue&...`. Bundan tashqari Asterisk konteyneri UTC'da ishlaydi —
  vaqt shartlari endi PBX vaqt zonasida (`GotoIfTime` 5-maydoni) tekshiriladi, 5 soatlik siljish yo'q.
- **Sana va vaqt** — qidiriladigan vaqt zonasi tanlagich (shahar yoki `+05` bo'yicha, har zona yonida UTC siljishi,
  O'zbekiston/qo'shnilar boshida); yuradigan server soati (server zonasida + UTC); «Vaqt manbai» (javob bergan NTP
  server); **Hozir sinxronlash** tugmasi (NTP javobini ~10 s kutadi, kelmasa aniq xato).
- NTP serverlar ro'yxati bo'sh bo'lsa — tanlangan zona mintaqasining `pool.ntp.org` serverlari (masalan
  `0–3.asia.pool.ntp.org`) ishlatiladi; o'z serverlaringiz bo'lsa ular zaxira bo'lib qoladi.
- Server vaqt zonasi o'zgarsa PBX zonasi ham shunga o'tadi (ish vaqti, kampaniya oynalari) — dialplan qayta quriladi.
- **Bildirishnomalar** endi o'zi yopiladi (muvaffaqiyat 4 s, ma'lumot 5 s, xato 8 s, «qo'llanmadi» 12 s) va bir xil
  xabar qayta-qayta to'planmaydi (bittasi qoladi; ekranda ko'pi bilan 4 ta).

## 1.0.16 — 2026-11-04
- **Qo'llanma** — panelda to'liq foydalanuvchi qo'llanmasi: menyuda **Qo'llanma** (`/docs`), har ekran uchun alohida
  bo'lim (vazifasi, maydonlar, qadamma-qadam sozlash, maslahatlar, muammolar va yechimlar), boshlash bo'limlari
  (o'rnatish, birinchi sozlash, tezkor boshlash, rollar) va ilovalar (xizmat kodlari, umumiy muammolar, lug'at).
  Qo'llanma bo'yicha qidiruv, «Shu sahifada» mundarijasi, oldingi/keyingi bo'lim.
- Har sahifa sarlavhasida **?** belgisi — shu ekranning qo'llanma bo'limini ochadi.
- Qo'llanma matni o'zbekcha; ru/en interfeysda bu haqda eslatma chiqadi. Manba — `docs/qollanma/*.md` (GitHub'da ham o'qiladi).
- Tuzatish: **Xususiyat kodlari** sahifasida `*45`, `*46`, `*80`, `*56`, `*57` nomi o'rniga xom kalit chiqardi;
  **Jonli** sahifada ro'yxatdan o'tmagan raqam holati endi «Oflayn» deb ko'rinadi.

## 1.0.15 — 2026-11-04
- **Bir raqamda bir nechta qurilma** — endi BARCHASI jiringlaydi (stol telefoni + softfon + mobil). Avval
  qo'ng'iroq faqat birinchi ro'yxatdan o'tgan qurilmaga borardi. Tuzatish to'g'ridan-to'g'ri qo'ng'iroq,
  qo'ng'iroq guruhlari (DND hisobga olinadi), Follow Me va intercom (`*80`)ga taalluqli. Hech qaysi
  qurilma ulanmagan bo'lsa — avvalgidek ovozli pochta/javobsiz yo'nalish.
  Cheklov: navbat (Queue) a'zolari, API originate va **paging guruhlari** hozircha a'zoning birinchi
  qurilmasiga boradi — Asterisk `Page()` ilovasi har manzilni oldindan "device state" bilan tekshiradi
  va qo'ng'iroq-kontakt birikmasini qabul qilmaydi (jonli isbot bilan aniqlangan, 2026-11-04).

## 1.0.14 — 2026-11-04
- **Kun/Tun rejimi** — yangi sahifa **Marshrutlash → Kun/Tun** (`/day-night`): kunduzgi va tungi manzil, telefondan
  `*28<kod>` bilan almashtirish (ixtiyoriy PIN), BLF chiroqcha (`Custom:DAYNIGHT<kod>`), paneldan bir bosishda almashtirish.
  Holat qo'ng'iroq paytida o'qiladi — almashtirish uchun «Qo'llash» shart emas. Kiruvchi marshrutda
  manzil sifatida tanlanadi. Dublikat kod/nom endi aniq xabar bilan rad etiladi.
- **DISA** — yangi sahifa **Ilovalar → DISA** (`/disa`): tashqi qo'ng'iroqchi PIN kiritib ofis trunklari orqali
  chiqadi; 3 marta xato PIN — aloqa uziladi; faqat chiquvchi marshrutlarga, ichki xizmat kodlariga yo'l yo'q.
  PIN'lar faqat HMAC ko'rinishida saqlanadi va hech qachon qaytarilmaydi.
- **Sozlamalar → Sana va vaqt** — vaqt zonasi va NTP serverlari.
- **Tizim holati → Qayta yuklash / O'chirish** — hostname'ni yozib tasdiqlash, faol qo'ng'iroqlar soni ko'rsatiladi.
- **Sozlamalar → Firewall** — SSH/veb/SIP/RTP uchun ruxsat etilgan tarmoqlar. O'zingizni qulflab qo'yishdan himoya:
  qoidalar sinab qo'llanadi va 120 soniya ichida tasdiqlanmasa avtomatik eski holatga qaytadi.
- Menyudagi **Yangilanish** bandida yangi versiya chiqqanda nuqta ko'rinadi.
- Qayta qo'ng'iroq (callback) CDR'ida accountcode to'g'ri yoziladi.
- Xavfsizlik:
  - paneldan yangilash agentida symlink orqali host fayllariga yozish yopildi. API konteyneri endi faqat so'rov
    papkasiga yoza oladi, holat va jurnal faqat o'qish uchun ulanadi;
  - login'da IP bo'yicha cheklov qo'yildi va mavjud/mavjud bo'lmagan foydalanuvchiga bir xil javob beriladi;
  - AMI va host firewall faqat Innova ichki tarmog'iga ochiladi;
  - `X-Forwarded-For` faqat veb konteynerdan qabul qilinadi;
  - SFTP zaxira manziliga ulanishda kalit oldindan tekshiriladi;
  - jonli voqealar WebSocket'i baza ulanishini band qilib turmaydi;
  - xizmat kodlari dialplan yaratilayotganda qayta tekshiriladi.

## 1.0.13 — 2026-11-04
- **Paneldan yangilash** — yangi sahifa **Sozlamalar → Yangilanish** (`/settings/update`, faqat administrator):
  joriy va yangi versiya, o'zgarishlar ro'yxati, «Tekshirish» va «Yangilash» tugmalari. Yangilash tasdiq oynasida
  versiya raqamini yozib tasdiqlanadi; jarayon bosqichlari (zaxira → kod → o'rnatish → qayta ishga tushish) va jurnal
  jonli ko'rinadi. API konteyneri qayta ishga tushsa ham jarayon uzilmaydi — ishni hostdagi agent bajaradi.
- Har yangilashdan oldin bazaning avtomatik zaxirasi (`backups/pre-update-*.sql.gz`); xato bo'lsa sahifada sabab
  (masalan, hostda qo'lda o'zgartirilgan fayllar) va zaxira fayl nomi ko'rsatiladi. Yangilanishlar tarixi saqlanadi.
- Yangi versiya har 12 soatda avtomatik tekshiriladi (`innova-update-check.timer`).
- Mustahkamlik: bir vaqtda faqat bitta yangilash/tekshiruv; parallel so'rov 409 bilan rad etiladi; to'xtab qolgan
  jarayon (masalan, reboot) «uzilgan» deb belgilanadi; ketma-ket xatolar agentni o'chirib qo'ymaydi.
- Menyu: «Javobsiz qo'ng'iroqlar» bandi uchala tilda to'g'ri nomlanadi (ilgari xom `nav.missedcalls` chiqardi).
- Eslatma: ISO'dan o'rnatilgan tizimlarda git manbasi yo'q — sahifa «manba topilmadi» deb ko'rsatadi (paneldan yangilash
  git orqali o'rnatilgan serverlar uchun).

## 1.0.12 — 2026-11-03
To'liq xavfsizlik auditi va tuzatishlar:
- **KRITIK — tarmoq sozlamalari orqali root buyruq bajarish yopildi.** IPv6 scope-id (`fe80::1%eth0\n...`) ichiga
  yangi qator yashirib `/etc/network/interfaces`ga ixtiyoriy `up <buyruq>` yozish mumkin edi. Endi manzil/shlyuz/marshrut
  faqat kanonik IPv4, hostname/DNS-qidiruv RFC1123, va har bir konfiguratsiya fayli yozishdan oldin `\r`/`\n`/NUL uchun
  qayta tekshiriladi (ikki qavat himoya).
- **Dialplan injeksiyasi yopildi** — kiruvchi/chiquvchi marshrut DID/CID/naqsh, CSV import va FreePBX migratsiyasi
  qiymatlari tekshiriladi; kompilyator ham xavfli belgili qiymatni rad etadi. Asterisk'da `func_shell`/`app_system`
  modullari o'chirildi (injeksiya bo'lsa ham OS buyrug'i ishlamaydi).
- **Zaxiradan tiklashda yo'l chetlab o'tish (path traversal) yopildi** — arxiv qismlari faqat ruxsat etilgan nomlar
  ro'yxatidan, staging papkasidan tashqariga yozilmaydi; scrypt parametrlari cheklangan (DoS'ga qarshi).
- **2FA kuchaytirildi** — yoqilgan 2FA'ni qayta sozlab bo'lmaydi; o'chirish/zaxira kodlarda noto'g'ri kod hisobni
  bloklaydi; yoqish/o'chirishda boshqa sessiyalar chiqarib yuboriladi.
- **Vidjet toll-fraud himoyasi** — xalqaro/qora ro'yxat tekshiruvi terish bilan bir xil normallashtirilgan raqamda;
  domenlar cheklangan bo'lsa, Origin'siz so'rov rad etiladi.
- **SSH** (zaxira SFTP, FreePBX migratsiyasi) — host kaliti autentifikatsiyadan OLDIN tekshiriladi (MITM'ga parol chiqmaydi).
- **SSRF** — Telegram bazaviy manzili tekshiriladi, masofaviy javob matni qaytarilmaydi.
- Ichki API tokeni barcha endpointlarda doimiy vaqtli solishtiriladi; zaif `SECRET_KEY`/`INTERNAL_API_TOKEN`
  (standart qiymat yoki 32 belgidan qisqa) bilan API ishga tushmaydi.
- Bog'liqliklar: `python-jose` → `PyJWT 2.15.1`, `fastapi 0.135.4`, `starlette 1.10.0`, `python-multipart 0.0.33`
  (ma'lum zaifliklar yo'q — pip-audit toza).

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
