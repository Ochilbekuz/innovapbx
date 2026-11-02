# Recon xaritasi: FreePBX (+ OnlinePBX UX) — veb-panel

Sana: 2026-10-27. Ishchi nom: **pbx-klon** (brend keyin — `/replica-brand`).
Platforma: veb (desktop birinchi, planshet/mobil — moslashuvchan). Asos: Asterisk 20/22 LTS.

## Doira (scope) — tasdiqlangan
1. **Nima:** FreePBX 16/17 ning admin paneli funksiyalari (Asterisk ustidagi PBX boshqaruvi),
   OnlinePBX'ning zamonaviy UX'i va SaaS qismlari bilan birlashtirilgan **bitta mahsulot**.
2. **Qaysi bo'lak (asosiy halqa):** ichki raqamlar → trunk → kiruvchi/chiquvchi marshrut → IVR/guruh/navbat →
   ish vaqti → qo'ng'iroqlar tarixi va yozuvlar. Qolgani bosqichma-bosqich.
3. **Kim uchun:** O'zbekistondagi kompaniyalar (call-markaz, savdo, xizmat). Sotiladigan mahsulot:
   avval **on-prem** (mijoz serverida, FreePBX o'rnini bosadi), keyin **bulut, ko'p ijarachili** (OnlinePBX kabi).
4. **Klon usuli:** clean-room. FreePBX GPL/AGPL — uning PHP kodi, modul kodi, matnlari va logotipi OLINMAYDI;
   faqat funksiya va foydalanuvchi oqimi. Asterisk (GPLv2) — o'zgartirmasdan, alohida jarayon sifatida ishlatiladi.

## Manbalar

| manba | URL | nima beradi |
| --- | --- | --- |
| FreePBX rasmiy hujjatlar (wiki) | https://sangomakb.atlassian.net/wiki/spaces/FP/overview | har modul sozlamalari — eng to'liq funksiya ro'yxati |
| FreePBX modullar ro'yxati | https://github.com/FreePBX (ochiq repolar nomlari) | modul = funksiya; qaysilari asosiy (core, framework) |
| FreePBX tijorat modullari | https://www.sangoma.com/products/freepbx-commercial-modules/ | pullik qism (EPM, Call Center Pro, Sangoma Connect) — muhim deb sotiladi |
| Asterisk hujjatlari | https://docs.asterisk.org | PJSIP, dialplan, Queue, ARI/AMI — ijro qatlami |
| OnlinePBX recon | `/root/devteam/workspaces/793156577/onlinepbx-klon/replica/recon.md` (2026-10-24) | zamonaviy UX, SaaS, analitika, CRM, softfon |
| O'z tajribamiz | `knowledge/arxiv/telefoniya-pbx.md`, `callcenter/` (Dial Dashboard) | FreePBX'ning real og'riqlari: trunk sog'ligi, CDR sxema variantlari, navbat jurnali |
| Foydalanuvchining o'z FreePBX'lari | (ruxsat bilan, faqat o'qish) | haqiqiy holatlar, xato ekranlari — keyingi bosqichda skrinshot |

FreePBX'ning og'riqlari (bizning tajriba + forumlar) — klonning ustunligi shu yerda:
«Apply Config» qizil tugmasi (o'zgarish darhol ishlamaydi), eski Bootstrap 3 UI, rus/o'zbek tili yarim,
trunk «ishlayaptimi» degan savolga aniq javob yo'q, hisobotlar zaif (CDR Reports), call-markaz funksiyalari pullik,
modul yangilanishi serverni buzishi mumkin, ko'p ijarachilik yo'q.

## Asosiy halqa (core loop)

Admin **ichki raqam yaratadi → trunk ulaydi → kiruvchi qo'ng'iroqni IVR/navbatga yo'naltiradi → «Saqlash»
(darhol ishlaydi) → qo'ng'iroqni tarixda ko'radi va yozuvni tinglaydi**. Mijoz pul to'laydigan narsa:
«qo'ng'iroq to'g'ri odamga yetib boradi va hammasi qayd qilinadi».

FreePBX'da birinchi kiruvchi qo'ng'iroqqacha: ~45 bosish, 6 sahifa + Apply Config. **Maqsad: ≤ 15 bosish, sehrgar bilan.**

## Ekranlar

FreePBX menyusi (Admin / Applications / Connectivity / Reports / Settings) → bizda vazifaga ko'ra guruhlangan.
`S01–S20` — OnlinePBX recon bilan bir xil ma'noda qoldirildi; `S21+` — FreePBX'dan qo'shilganlar.

| ID | ekran | qanday kiriladi | maqsad | asosiy komponentlar | holatlar |
| --- | --- | --- | --- | --- | --- |
| S01 | O'rnatish sehrgari | birinchi ishga tushish | admin, til, vaqt zonasi, tarmoq (tashqi IP, NAT), birinchi trunk | qadamli forma | bo'sh, xato (NAT aniqlanmadi) |
| S02 | Kirish | `/login` | login + 2FA | forma, TOTP | xato, bloklangan, parol muddati |
| S03 | Bosh panel | kirgandan keyin | tizim sog'ligi (Asterisk, disk, trunk), jonli qo'ng'iroqlar, navbat holati, javobsizlar | KPI kartalar, jonli ro'yxat, ogohlantirishlar | yangi tizim, to'lgan, Asterisk ishlamayapti |
| S04 | Ichki raqamlar (Extensions) | Foydalanuvchilar → Ichki raqamlar | ro'yxat, ommaviy qo'shish/import CSV | jadval, filtr, ommaviy amal | bo'sh, to'lgan, raqam band |
| S05 | Ichki raqam kartasi | S04 → qator | SIP login/parol, CallerID, ovozli pochta, yo'naltirish (Follow Me), yozuv siyosati, kodeklar, NAT, ruxsat etilgan chiquvchi marshrutlar, qurilmalar holati | tablar, toggle, QR (softfon) | registratsiyalangan, oflayn, bir nechta qurilma |
| S06 | Trunklar | Ulanish → Trunklar | PJSIP trunk (registratsiya yoki IP bo'yicha), kodeklar, CallerID, maks. kanallar | jadval, forma, **sog'lik indikatori** | ulandi, registratsiya xato, IP-trunk (qualify), o'chirilgan |
| S07 | Kiruvchi marshrutlar (Inbound Routes / DID) | Ulanish → Kiruvchi | DID + CallerID bo'yicha → manzil | qoidalar ro'yxati, **manzil tanlagich** | mos marshrut yo'q (catch-all), to'qnashuv |
| S08 | Ish vaqti (Time Groups + Time Conditions + Calendar) | Marshrut → Ish vaqti | hafta jadvali, bayramlar, qo'lda «tungi rejim» (Call Flow Control) | hafta setkasi, sana tanlash, toggle | ish vaqti, tashqari, majburiy rejim |
| S09 | IVR | Ilovalar → IVR | salomlashuv, tugma → manzil, noto'g'ri/timeout, to'g'ridan-to'g'ri ichki raqam terish | tugma xaritasi, audio tanlash | bo'sh, halqa xavfi |
| S10 | Navbatlar (Queues) | Ilovalar → Navbatlar | strategiya, statik/dinamik agentlar, kutish musiqasi, pozitsiya e'loni, maks. kutish, SLA, failover | a'zolar ro'yxati, strategiya select | bo'sh navbat, hamma band |
| S21 | Qo'ng'iroq guruhlari (Ring Groups) | Ilovalar → Guruhlar | ringall / ketma-ket / xotira, tashqi raqam a'zo | a'zolar, strategiya | — |
| S22 | Chiquvchi marshrutlar | Ulanish → Chiquvchi | terish naqshlari (`998XXXXXXXXX`), trunk ketma-ketligi (failover), CallerID, PIN | naqsh muharriri, drag-drop tartib | naqsh xatosi, trunk yo'q |
| S11 | Audio kutubxona (System Recordings + Announcements + MoH) | Ilovalar → Audio | yuklash, brauzerda yozish, TTS (uz/ru/en), kutish musiqasi to'plamlari | yuklash, pleer, TTS forma | format xato, bo'sh |
| S23 | Ovozli pochta | S05 ichida + Ilovalar → Ovozli pochta | PIN, e-mail'ga yuborish, salomlashuv, xabarlar ro'yxati | pleer, ro'yxat | bo'sh, to'lgan |
| S24 | Xususiyat kodlari (Feature Codes) | Sozlamalar → Kodlar | `*97` pochta, `*2` o'tkazish, `*8` ushlab olish, DND, yo'naltirish | jadval, yoqish/o'chirish | to'qnashuv |
| S25 | Konferensiya xonalari | Ilovalar → Konferensiya | xona raqami, PIN, yozuv | forma, jonli ishtirokchilar | — |
| S26 | Park / Pickup / Paging / Intercom | Ilovalar → Qo'shimcha | parkovka joylari, guruh bo'yicha olish, e'lon | formalar | — |
| S27 | Qora ro'yxat / CallerID nomi | Ilovalar → Bloklash | raqam bloklash, anonimni bloklash, CID nom manbasi (kontaktlar/CRM) | jadval | — |
| S28 | Misc: Misc Destinations / Applications, DISA, Follow Me, Call Forward | ichki raqam / ilovalar | maxsus manzillar | formalar | — |
| S12 | Qo'ng'iroqlar tarixi (CDR) | Hisobotlar → Tarix | filtr, tinglash, yuklab olish, eksport | jadval, filtr, pleer | bo'sh, sahifalash |
| S13 | Analitika (Dial Dashboard qayta ishlatiladi) | Hisobotlar → Analitika | KPI, operator/navbat/bo'lim, SLA, javobsizlar | grafiklar, jadval | bo'sh |
| S29 | Jonli monitoring (Operator Panel / UCP o'rniga) | Monitoring → Jonli | hozirgi qo'ng'iroqlar, navbat, agent holati, tinglash/shivirlash/aralashish (ChanSpy) | jonli kartalar | — |
| S14 | Sifat baholash | Hisobotlar → Sifat | suhbatni mezon bo'yicha baholash | chek-list | — |
| S15 | Integratsiyalar | Integratsiya | CRM (amoCRM, Bitrix24, 1C), webhook, REST API kalitlari | kartalar | ulanmagan, xato |
| S16 | Softfon (WebRTC) | yuqori panel | brauzerdan qo'ng'iroq | tergich, kiruvchi oyna | band, ulanmoqda |
| S17 | Callback vidjet | Integratsiya → Vidjet | saytga «qayta qo'ng'iroq» | kod parchasi | — |
| S18 | Avtoinformator / avtoterish | Ilovalar → Kampaniyalar | ro'yxatga xabar / operatorga ulash (freepbx-autodialer asos) | CSV, natijalar | jarayonda |
| S30 | Foydalanuvchi portali (UCP o'rniga) | operator `/me` | o'z tarixi, ovozli pochta, yo'naltirish, DND, softfon | kartalar | — |
| S31 | Admin foydalanuvchilar va rollar | Sozlamalar → Adminlar | rol/ruxsat, audit jurnali | jadval | — |
| S32 | Tizim: tarmoq/SIP sozlamalari | Sozlamalar → SIP | tashqi IP, lokal tarmoqlar, portlar, TLS, RTP oralig'i, kodeklar | forma | NAT noto'g'ri |
| S33 | Xavfsizlik (Firewall + Fail2ban o'rniga) | Sozlamalar → Xavfsizlik | ishonchli tarmoqlar, bloklangan IP, SIP hujum hisobi, chiquvchi qo'ng'iroq limiti (toll fraud) | jadval, grafik | hujum ostida |
| S34 | Zaxira va tiklash | Sozlamalar → Zaxira | jadval, saqlash joyi (lokal/S3/SFTP), tiklash | jadval, progress | xato |
| S35 | Telefon apparatlari (EPM o'rniga) | Qurilmalar | Yealink/Grandstream/Fanvil avtoprovizioning, MAC → ichki raqam | jadval, shablonlar | topildi, provizionlandi |
| S36 | Tizim holati / yangilanish / loglar | Sozlamalar → Tizim | versiya, yangilanish, Asterisk CLI loglar (faqat o'qish), xizmatlar | log ko'ruvchi | — |
| S19 | Litsenziya / balans | Hisob | on-prem: litsenziya (lic.uzmik.uz bor); bulut: tarif, to'lov | kartalar | muddati tugagan |
| S20 | Mobil ilova | iOS/Android | — | — | doiradan tashqari (keyingi bosqich) |

Jami: **36 ekran** (S20 — keyinga).

## Oqimlar

```
F01 Yangi PBX'ni ishga tushirish (onboarding)
    S01 sehrgar (admin, NAT, tashqi IP) -> S06 trunk -> S04 3 ta ichki raqam (CSV yoki tez qo'shish)
    -> S07 kiruvchi «hammasi -> S21 guruh» -> S16 sinov qo'ng'irog'i
    FreePBX: ~45 bosish + Apply Config. Maqsad: <= 15.
    edge: NAT noto'g'ri (bir tomonlama ovoz), trunk IP bo'yicha (registratsiyasiz), port 5060 band/bloklangan

F02 Mijoz qo'ng'iroq qiladi -> ish vaqti -> IVR -> navbat
    DID -> S07 -> S08 (ish vaqti?) -> S09 IVR «1» -> S10 navbat -> agent javob beradi -> S12 tarix + yozuv
    edge: ish vaqti emas -> S23 ovozli pochta; navbat to'la/maks. kutish -> failover; hech kim yo'q; bayram

F03 Chiquvchi qo'ng'iroq
    ichki raqam terdi -> S22 naqsh mos -> trunk 1 (xato) -> trunk 2 (failover) -> CallerID almashtiriladi
    edge: ruxsat etilmagan yo'nalish (xalqaro), toll fraud limiti, trunk kanallari to'la

F04 Admin yangi xodim qo'shadi va telefonini ulaydi
    S04 -> «+» -> S05 (ism, raqam avtomatik) -> QR / provizioning (S35) -> registratsiya ko'rinadi
    edge: raqam band, parol zaif, qurilma NAT orqasida

F05 Rahbar kunni tahlil qiladi (OnlinePBX F05 bilan bir xil)
    S13 -> S12 filtr -> yozuvni tinglash -> S14 baholash

F06 Supervayzer jonli kuzatadi
    S29 -> navbatda 5 kishi kutmoqda -> agentni navbatga qo'shadi / qo'ng'iroqni tinglaydi (ChanSpy, shivirlash)

F07 Ish vaqtidan tashqari / bayram rejimi
    S08 -> bayram sanasi qo'shiladi YOKI «tungi rejim» toggle (yoki *28 kod) -> kiruvchi oqim darhol o'zgaradi

F08 Javobsizga qayta qo'ng'iroq (OnlinePBX F03)
    S03 javobsizlar -> bir bosishda S16 dan qo'ng'iroq

F09 Muammo: «qo'ng'iroqlar kelmayapti»
    S03 ogohlantirish «Trunk X: 10 daqiqadir qo'ng'iroq yo'q / qualify xato» -> S06 sog'lik tafsiloti
    (registratsiya, OPTIONS javobi, oxirgi muvaffaqiyatli qo'ng'iroq) -> SIP iz (faqat o'qish)
```

## Komponentlar

| komponent | variantlar | holatlar | qayerda |
| --- | --- | --- | --- |
| **Manzil tanlagich (Destination picker)** | ichki raqam, guruh, navbat, IVR, ish vaqti, ovozli pochta, e'lon, tashqi raqam, osish | bo'sh, o'chirilgan obyekt (singan havola) | S07, S08, S09, S10, S21, S28 — FreePBX'ning markaziy tushunchasi |
| **Qo'ng'iroq oqimi grafigi** | DID dan boshlab daraxt (faqat ko'rish, keyin tahrirlash) | to'g'ri, halqa, singan manzil | S07, S09 — FreePBX'da yo'q, bizning ustunlik |
| Jadval | sahifalash, filtr, saralash, ommaviy tanlash, CSV import/eksport | bo'sh, yuklanmoqda, xato | S04, S06, S12, S22 |
| Hafta setkasi + kalendar | ish vaqti, bayram | — | S08 |
| Audio pleer / yozuvchi | qator ichida, to'liq, brauzerda yozish | o'ynayapti, yuklanmoqda | S11, S12, S23 |
| Naqsh muharriri (dial pattern) | prefiks, naqsh, CallerID | noto'g'ri naqsh | S22 |
| Drag-drop tartib ro'yxati | trunk ketma-ketligi, a'zolar | — | S10, S21, S22 |
| Holat belgisi (status pill) | onlayn/oflayn/xato/o'chirilgan | jonli yangilanadi | S04, S06, S29 |
| Sog'lik indikatori | trunk, Asterisk, disk | yashil/sariq/qizil + sabab | S03, S06 |
| Softfon paneli | kichik, kengaytirilgan | kiruvchi, gaplashmoqda, ushlab turish | S16 |
| KPI karta / grafik | son, trend | bo'sh | S03, S13 |
| Forma / tablar / modal | yaratish, tahrir | validatsiya xatosi, saqlanmagan o'zgarish | hammasi |
| Toast | muvaffaqiyat, xato, «PBX'ga qo'llanmadi» | — | hammasi |
| Log ko'ruvchi | jonli, filtr | — | S36, F09 |

## Xulosa qilingan ma'lumotlar modeli

FreePBX'da ma'lumot MySQL `asterisk` bazasida (har modul o'z jadvali) + Asterisk `astdb`; konfiguratsiya fayllari
«Apply Config» da qayta generatsiya qilinadi. Biz: **bitta normallashgan sxema** (PostgreSQL), ijro — Asterisk.

```
Tenant        id, nom, vaqt_zonasi, til                         (on-prem: bitta qator) | ishonch: yuqori (OnlinePBX)
Extension     id, tenant_id, raqam, ism, email, callerid, sip_parol, maks_kontakt, kodeklar, nat,
              yozuv_siyosati (har doim|hech qachon|talab), ovozli_pochta(json), follow_me(json),
              dnd, chiquvchi_ruxsat (marshrut ro'yxati), dept_id
              dalil: FreePBX Extensions moduli maydonlari | ishonch: yuqori
Device        id, extension_id, tur (sip|webrtc|ip_telefon), mac, model, oxirgi_registratsiya | ishonch: yuqori (EPM)
Trunk         id, nom, tur (registratsiya|ip), host, port, login, parol, kodeklar, maks_kanal, callerid,
              qualify, holat | dalil: Trunks moduli (pjsip) | ishonch: yuqori
InboundRoute  id, did (bo'sh = hammasi), callerid_naqsh, manzil, cid_prefiks, yozuv | ishonch: yuqori
OutboundRoute id, nom, naqshlar[] (prefiks, naqsh, callerid), trunk_tartib[], callerid, pin, ruxsat | ishonch: yuqori
TimeGroup     id, nom, oraliqlar[] (hafta kuni, vaqt, sana) | ishonch: yuqori
TimeCondition id, time_group_id, mos_manzil, mos_emas_manzil, majburiy_rejim (auto|ochiq|yopiq), kod | ishonch: yuqori
Ivr           id, nom, salom_audio_id, tugmalar[] (tugma -> manzil), timeout, noto'g'ri_manzil, takror,
              to'g'ridan_ichki_terish | ishonch: yuqori
RingGroup     id, raqam, strategiya, a'zolar[], vaqt, javobsiz_manzil | ishonch: yuqori
Queue         id, raqam, nom, strategiya, statik_a'zolar[], dinamik_a'zolar[], moh_id, maks_kutish,
              pozitsiya_e'loni, sla_sek, wrapup, javobsiz_manzil | ishonch: yuqori
Announcement  id, audio_id, keyingi_manzil | ishonch: yuqori
AudioFile     id, nom, til, manba (yuklangan|yozilgan|tts), fayl | ishonch: yuqori
MohClass      id, nom, fayllar[], tasodifiy | ishonch: yuqori
Conference    id, raqam, pin, admin_pin, yozuv | ishonch: yuqori
FeatureCode   kod, amal, yoqiq | ishonch: yuqori
Blacklist     raqam, sabab | ishonch: yuqori
Destination   (polimorf havola) tur + id — har manzil maydoni shu turda; o'chirishda «kim ishlatyapti» tekshiruvi
              dalil: FreePBX'da singan manzil — mashhur muammo | ishonch: yuqori (dizayn qarori)
Call (CDR/CEL) Asterisk CDR + navbat jurnali (Dial Dashboard modeli qayta ishlatiladi) | ishonch: yuqori
Recording     call_id, fayl, saqlash_muddati | ishonch: yuqori
AdminUser, Role, AuditLog       (callcenter RBAC qayta ishlatiladi) | ishonch: yuqori
Backup        id, jadval, manzil, holat | ishonch: o'rta
Integration, Webhook, Campaign  (OnlinePBX recon'dan) | ishonch: o'rta
```

Munosabatlar: hamma «manzil» maydonlari → `Destination` (Extension | RingGroup | Queue | Ivr | TimeCondition |
Announcement | Voicemail | Conference | Tashqi raqam | Hangup). InboundRoute → Destination; Ivr.tugmalar → Destination;
OutboundRoute n-n Trunk (tartib bilan); Queue n-n Extension.

**Arxitektura uchun asosiy savol (replica-architect hal qiladi):** FreePBX kabi `.conf` fayl generatsiya + `reload`
YOKI Asterisk **Realtime (PJSIP sorcery → PostgreSQL)** + dialplan'ni **ARI Stasis** ilovasida boshqarish.
Ikkinchisi «Apply Config» siz darhol ishlashni va ko'p ijarachilikni osonlashtiradi, lekin murakkabroq.

## Bizda allaqachon bor qismlar (tezlashtiradi)

- **callcenter / Dial Dashboard 1.20.4** — CDR, navbat jurnali, hisobotlar, jonli monitoring, RBAC, bo'limlar,
  Telegram ogohlantirish, i18n uz/ru/en, litsenziya (lic.uzmik.uz), yangilanish tizimi → S12, S13, S29, S31, S19, S36.
- **freepbx-autodialer** → S18. **1C↔Asterisk CTI** tajribasi → S15.
- FreePBX/Asterisk real hayot saboqlari (arxiv): IP-trunk sog'ligi registratsiya bilan o'lchanmaydi, CDR sxema
  variantlari, MySQL/MariaDB matritsasi.
- OnlinePBX recon: S01–S20, F01–F06, ma'lumotlar modeli.

## Feature matritsa

`features.csv` ga qarang (OnlinePBX matritsasi bilan birlashtirilgan, `original` ustuni: `freepbx`, `onlinepbx`, `ikkalasi`).

## Doiradan tashqari (klonlanmaydi)

- FreePBX/Sangoma kodi, matnlari, logotipi, «FreePBX» nomi (savdo belgisi) — ishlatilmaydi; FreePBX modul
  bozori (Module Admin + uchinchi tomon modullar ekotizimi).
- Sangoma'ga bog'liq: SIPStation trunklari, Sangoma telefonlarining yopiq firmware'i, Sangoma Connect/Zulu,
  Sangoma Talk mobil ilovasi, tijorat litsenziyalash serveri.
- Faks (Fax Pro), DAHDI/analog kartalar, SS7 — talab past, apparatga bog'liq (could → skip).
- Operator litsenziyasi / o'z raqamlar bazasi — mijoz o'z trunkini ulaydi (OnlinePBX recon bilan bir xil).
- High Availability (FreePBX HA tijorat moduli) — L hajmidan tashqari, keyinroq.

## Hajm

Ekranlar 36 (asosiy halqa uchun 14: S01–S10, S12, S21, S22, S11), oqimlar 9, entitilar ~25.

Eng qiyin qismlar:
1. **Konfiguratsiya → Asterisk ijrosi:** dialplan generatsiyasi yoki ARI; har o'zgarish xavfsiz qo'llanishi,
   faol qo'ng'iroqlarni uzmasligi, xato bo'lsa orqaga qaytishi.
2. **SIP/RTP real dunyo:** NAT, IP-trunklar, kodeklar, WebRTC softfon (TLS/DTLS), toll fraud himoyasi.
3. **Manzil grafigi:** polimorf manzillar, halqa va singan havola tekshiruvi, vizual oqim.
4. (+) FreePBX'dan ko'chirish vositasi — mijozni olishning eng muhim sharti (mavjud `asterisk` MySQL bazasidan import).

O'lcham: asosiy halqa (must) — **L** (bir chorak, 2–3 kishi yoki agentlar bilan bosqichma-bosqich);
hammasi (FreePBX + OnlinePBX, bulut, ko'p ijarachilik) — **XL** → bosqichlarga bo'linadi:
- **1-bosqich (MVP, on-prem):** S01–S10, S21, S22, S11, S12 + manzil tanlagich + darhol qo'llash.
- **2-bosqich:** ovozli pochta, kodlar, konferensiya, park/pickup, analitika (Dial Dashboard birlashadi), jonli monitoring, UCP.
- **3-bosqich:** softfon WebRTC, CRM, provizioning, zaxira, xavfsizlik, FreePBX'dan import.
- **4-bosqich:** bulut/ko'p ijarachilik, billing, callback vidjet, mobil.

Mukammal nusxa va'da qilinmaydi — maqsad: FreePBX funksiyalari, sezilarli darajada oson va chiroyli.
