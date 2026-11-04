---
id: muammolar
title: Muammolar va yechimlar
group: appendix
order: 20
summary: Tez-tez uchraydigan umumiy muammolarning sabablari va yechimlari — boshqa boʻlimlardan havola qilinadi.
---

# Muammolar va yechimlar

Bu boʻlimda bir nechta sahifaga tegishli boʻlgan, tez-tez uchraydigan umumiy muammolar toʻplangan. Har bir
ekranning oʻz "Muammolar va yechimlar" jadvali bor — bu yerda faqat boshqa boʻlimlardan havola qilingan
va bir nechta joyga tegishli bandlar keltirilgan.

## 2FA qurilma yoʻqolsa

Foydalanuvchi ikki bosqichli tasdiqlash (2FA) uchun ishlatilgan telefon/ilovani yoʻqotib qoʻysa, u kodni
kirita olmay kirishga toʻsqinlik qiladi. Buni oʻzi mustaqil hal qila olmaydi — faqat **toʻliq
administrator (`*`)** yordam berishi mumkin:

1. Administrator **Tizim → Foydalanuvchilar** sahifasiga kiradi.
2. 2FA yoqilgan foydalanuvchi qatorida qalqon belgisini bosib, **2FA’ni tiklash**ni tasdiqlaydi.
3. Foydalanuvchi endi kod soʻramasdan kira oladi; keyingi kirishda tizim unga 2FA’ni **qaytadan
   ulashini** soʻraydi (yangi ilova/qurilma bilan).

Batafsil: [Foydalanuvchilar](/docs/users), [Xavfsizlik](/docs/security).

## Ovoz yoʻq yoki bir tomonlama eshitiladi

Qoʻngʻiroq ulanadi, lekin ovoz umuman eshitilmaydi yoki faqat bir tomon eshitadi — bu deyarli har doim
**RTP (ovoz) paketlari**ning tashqi tomonga toʻgʻri yetib bormasligi sababli boʻladi:

1. **SIP va tarmoq** sahifasida **Tashqi IP**ning toʻgʻri (serverning haqiqiy ommaviy IP) koʻrsatilganini
   tekshiring — ayniqsa server bulut/NAT ortida boʻlsa.
2. **Firewall** sahifasida **SIP** va **RTP** xizmatlarining rejimini tekshiring — allowlist rejimida
   boʻlsa, qoʻngʻiroq qilinadigan/qabul qilinadigan tomon manzillari roʻyxatda boʻlishi kerak.
3. RTP uchun ajratilgan port oraligʻi (**SIP va tarmoq** sahifasida koʻrsatilgan) serverning tashqi
   firewall’ida (provayder/router darajasida, bu paneldan tashqarida) ham ochiq boʻlishi kerak.
4. Sozlamani oʻzgartirgandan keyin **SIP va tarmoq** sahifasida **Qayta ishga tushirish** tugmasi bilan
   Asterisk xizmatini qayta yuklashni unutmang — aks holda yangi sozlama amal qilmaydi.

Batafsil: [SIP va tarmoq](/docs/sip), [Firewall](/docs/firewall), [Tarmoq](/docs/network).

## Serverga ulanish yoʻqoldi (Tarmoq/Firewall)

**Tarmoq** yoki **Firewall** sahifasida oʻzgarish qoʻllangandan keyin serverga (SSH, veb-panel) ulanib
boʻlmay qolsa:

- **Hech narsa qilmang** — bu ikki sahifada har bir oʻzgarish avval **kutilayotgan (pending)** holatda
  turadi va belgilangan muddat ichida tasdiqlanmasa, tizim **oʻzi avtomatik eski holatga qaytaradi**.
- Agar yana ulanish imkoni boʻlsa, **Hozir qaytarish** tugmasi bilan darhol qaytarish mumkin.

Batafsil: [Tarmoq](/docs/network), [Firewall](/docs/firewall).

## Zaxiradan tiklashda yoki koʻchirishda xatolik

Zaxiradan tiklash/koʻchirish jarayoni muvaffaqiyatsiz tugasa yoki toʻxtab qolsa — **Zaxira** sahifasidagi
jurnalni (agar koʻrsatilgan boʻlsa) tekshiring va amalni **tasdiqlash soʻzini qayta yozib** qaytadan
boshlang. Jarayon davomida serverni qoʻlda oʻchirmang/qayta yuklamang.

Batafsil: [Zaxira](/docs/backup), [Migratsiya](/docs/migration).

## Paneldan yangilashda xatolik

Yangilanish muvaffaqiyatsiz tugasa, xato sababi (masalan zaxira yoki oʻrnatish bosqichida) sahifada aniq
koʻrsatiladi; zaxira bosqichida toʻxtagan boʻlsa kod hali oʻzgarmagan, tizim avvalgidek ishlaydi. Oʻrnatish
bosqichidan keyin xato chiqsa — administratorga murojaat qilib, zaxiradan qoʻlda tiklash kerak boʻlishi
mumkin.

Batafsil: [Yangilanish](/docs/update).

## Ichki raqam/trunk ulanmayapti (SIP registratsiya)

- Ichki raqam uchun: login/parolni, ichki raqam holatini (faol/faolsizlantirilgan) va qurilma
  sozlamalarini (host/port/transport) tekshiring.
- Tashqi trunk uchun: **Aloqa yoʻq** holati koʻrinsa — host/port toʻgʻriligini tekshirib **Sinash**
  tugmasi bilan diagnostika qiling; **Registratsiya rad etildi** boʻlsa login/parolni operator bilan
  tasdiqlang.

Batafsil: [SIP va tarmoq](/docs/sip), [Tashqi liniyalar](/docs/trunks).

## Oʻzim bloklanib qoldim

SIP himoyasi notoʻgʻri urinishlarni hujum deb hisoblab IP’ni avtomatik bloklashi mumkin:

1. Administrator **Xavfsizlik** sahifasida **Bloklangan IP**lar roʻyxatidan sizning manzilingizni
   blokdan chiqaradi.
2. Keyin oʻz manzilingizni **Ishonchli tarmoqlar**ga qoʻshib, qayta bloklanishning oldini oladi.

Batafsil: [Xavfsizlik](/docs/security).

## Bog'liq bo'limlar

- [Foydalanuvchilar](/docs/users)
- [Xavfsizlik](/docs/security)
- [SIP va tarmoq](/docs/sip)
- [Firewall](/docs/firewall)
- [Tarmoq](/docs/network)
- [Zaxira](/docs/backup)
- [Yangilanish](/docs/update)
- [Lugʻat](/docs/lugat)
