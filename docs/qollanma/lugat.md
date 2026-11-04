---
id: lugat
title: Lugʻat
group: appendix
order: 30
summary: Qoʻllanmada va panelda ishlatiladigan atama va qisqartmalarning izohi.
---

# Lugʻat

Qoʻllanma boʻylab uchraydigan atama va qisqartmalarning qisqa izohi — alifbo tartibida.

| Atama | Izoh |
|---|---|
| **2FA** | Ikki bosqichli tasdiqlash — login/parolga qoʻshimcha, TOTP ilovasi (Google Authenticator va sh.k.) orqali bir martalik kod talab qilish. |
| **API kalit** | Tashqi dasturlar `/api/public/v1/*` ochiq APIsiga kirishi uchun beriladigan, ruxsatlar (scope) bilan cheklangan kalit. |
| **Audit jurnali** | Tizimda kim nima qilgani (yaratdi/oʻzgartirdi/oʻchirdi/kirdi) haqidagi toʻliq yozuv. |
| **BLF** (Busy Lamp Field) | Telefon tugmasidagi chiroqcha — boshqa ichki raqam/manzilning band/boʻsh holatini koʻrsatadi. |
| **CDR** (Call Detail Record) | Har bir qoʻngʻiroq haqidagi yozuv: kim, kimga, qachon, qancha davom etdi, qanday tugadi. |
| **CID** (Caller ID) | Qoʻngʻiroq qilayotgan tomonning koʻrinadigan raqami/ismi. |
| **CIDR** | Tarmoq manzili yozish formati, masalan `192.168.1.0/24` — bitta IP yoki butun tarmoqni bildiradi. |
| **Diff** | Tarmoq/Firewall kabi sahifalarda oʻzgarish qoʻllashdan oldin koʻrsatiladigan "nima oʻzgaradi" roʻyxati. |
| **DISA** | Tashqaridan ofis raqamiga qoʻngʻiroq qilib, PIN kiritib, ofis trunki orqali tashqi raqamga chiquvchi qoʻngʻiroq qilish imkoni. |
| **DND** (Do Not Disturb) | "Bezovta qilmang" rejimi — yoqilganda ichki raqamga qoʻngʻiroqlar bormaydi. |
| **Draft (qoralama)** | Tarmoq/Firewall sahifalarida ekrandagi oʻzgarish darhol serverga yuborilmay, avval saqlanadigan vaqtinchalik holat. |
| **Follow Me** | Ichki raqamga kelgan qoʻngʻiroqni ketma-ket boshqa raqamlarga ham (masalan mobil telefon) sinab koʻrish. |
| **IVR** | Ovozli menyu — qoʻngʻiroq qiluvchiga tugma bosib boʻlim tanlash imkonini beradi. |
| **Konferensiya** | PIN bilan kiriladigan, bir nechta ishtirokchi bir vaqtda gaplasha oladigan qoʻngʻiroq xonasi. |
| **Navbat (queue)** | Qoʻngʻiroqlarni bir nechta operator orasida taqsimlaydigan, hammasi band boʻlsa kutish musiqasi bilan kutadigan mexanizm. |
| **NAT** | Lokal tarmoqdagi qurilmaning tashqi internetda boshqa (ommaviy) IP bilan koʻrinishi — SIP/RTP sozlamalarida alohida eʼtibor talab qiladi. |
| **Paging / Intercom** | Bitta raqam terib bir nechta ichki raqamga bir vaqtda ovozli xabar eshittirish. |
| **Park (parkovka)** | Qoʻngʻiroqni vaqtincha "joy"ga qoʻyib, boshqa telefondan davom ettirish. |
| **Pickup** | Jiringlayotgan boshqa ichki raqam/guruhdagi qoʻngʻiroqni oʻz telefonidan kod bilan qabul qilish. |
| **PIN toʻplami** | Chiquvchi marshrutga biriktiriladigan, qoʻngʻiroqdan oldin kod soʻraydigan PINlar roʻyxati. |
| **Qora roʻyxat (blacklist)** | Kiruvchi qoʻngʻiroqni chaqiruvchi raqamiga qarab avtomatik rad etish roʻyxati. |
| **Qoʻngʻiroq guruhi (ring group)** | Qoʻngʻiroq kelganda bir nechta ichki raqamni bir vaqtda jiringlatuvchi (navbatsiz) yoʻnaltirish. |
| **Reviziya** | Sozlama saqlangan sayin yaratiladigan "versiyalar tarixi" yozuvi — avvalgi holatga qaytarish imkonini beradi. |
| **RTP** (Real-time Transport Protocol) | Qoʻngʻiroq paytidagi ovoz paketlarini uzatish protokoli (SIP signalizatsiyasidan alohida). |
| **SIP** (Session Initiation Protocol) | Telefon qoʻngʻiroqlarini boshlash/boshqarish uchun ishlatiladigan asosiy protokol. |
| **SLA** | Xizmat darajasi koʻrsatkichi, masalan "belgilangan soniya ichida javob berilgan qoʻngʻiroqlar foizi". |
| **Toll-fraud** | Ichki raqam hisobidan ruxsatsiz koʻp sonli/qimmat tashqi qoʻngʻiroq qilinishi (hujum/suiste'mol) xavfi; soatlik/kunlik limit bilan oldini olinadi. |
| **TOTP** | Vaqtga bogʻliq bir martalik kod — 2FA ilovalari shu asosda kod yaratadi. |
| **Trunk** | PBX bilan telefon operatori (yoki boshqa PBX) orasidagi SIP ulanish — tashqi qoʻngʻiroqlar shu orqali oʻtadi. |
| **Vebhuk (webhook)** | Tizimda hodisa (masalan qoʻngʻiroq tugadi) yuz berganda, tashqi serveringizga avtomatik yuboriladigan HTTP xabar. |
| **Xususiyat kodi** | Telefondan `*`-kod terib ishlatiladigan amal (ovozli pochta, DND, Follow Me va h.k.). |

## Bog'liq bo'limlar

- [Xususiyat kodlari (toʻliq roʻyxat)](/docs/xususiyat-kodlari)
- [Muammolar va yechimlar](/docs/muammolar)
