---
id: xususiyat-kodlari
title: Xususiyat kodlari (toʻliq roʻyxat)
group: appendix
order: 10
summary: Telefondan * bilan teriladigan barcha standart xususiyat kodlarining toʻliq roʻyxati.
---

# Xususiyat kodlari (toʻliq roʻyxat)

Innova PBX’da ichki raqamdan telefon tugmalari bilan terib ishlatiladigan barcha standart `*`-kodlarning
toʻliq roʻyxati — tezkor maʼlumotnoma sifatida. Kodlarning oʻzini oʻzgartirish [Xususiyat
kodlari](/docs/featurecodes) sahifasida amalga oshiriladi.

## Standart kodlar roʻyxati

| Xususiyat | Standart kod | Izoh |
|---|---|---|
| Oʻz ovozli pochtasi | `*97` | Ovozli pochtaga kirish |
| Boshqa ichki raqam ovozli pochtasi | `*98` | Boshqa ichki raqamning ovozli pochtasiga qoldirish |
| DND almashtirish | `*76` | «Bezovta qilmang» rejimini yoqish/oʻchirish |
| Doimiy yoʻnaltirish — yoqish | `*72` | Shartsiz qoʻngʻiroq yoʻnaltirish |
| Doimiy yoʻnaltirish — oʻchirish | `*73` | |
| Band boʻlsa yoʻnaltirish — yoqish | `*90` | |
| Band boʻlsa yoʻnaltirish — oʻchirish | `*91` | |
| Guruh pickup | `*8` | Jiringlayotgan guruhdagi qoʻngʻiroqni qabul qilish |
| Toʻgʻridan-toʻgʻri pickup | `**` + ichki raqam | Aniq ichki raqamdagi qoʻngʻiroqni qabul qilish |
| Park | `*70` | Qoʻngʻiroqni «parkovka»ga qoʻyish |
| Eho testi | `*43` | Ovoz sifatini tekshirish |
| Gapiradigan soat | `*60` | Ovozli vaqt xabari |
| Follow Me yoqish/oʻchirish | `*21` | «Meni kuzatib yur» xususiyatini almashtirish |
| Navbat login/logout | `*45` | Navbat operatorining kirish/chiqishi (odatda Navbatlar boʻlimidan boshqariladi) |
| Pauza almashtirish | `*46` | Navbat operatorining pauzasi (odatda Navbatlar boʻlimidan boshqariladi) |
| Intercom (ichki tezkor chaqiruv) | `*80` + ichki raqam | |
| Qoʻngʻiroq kutish — yoqish | `*56` | Call waiting |
| Qoʻngʻiroq kutish — oʻchirish | `*57` | |

## Format qoidasi

Har bir kod `*` bilan boshlanadi va undan keyin 1-6 ta belgi (raqam, `*` yoki `#`) keladi: `^\*[0-9*#]{1,6}$`.

## Toʻqnashuv (clash) qoidasi

Ikki xususiyatga bir xil kod **yoki** biri ikkinchisining **prefiksi** boʻlgan kod berib boʻlmaydi —
masalan `*7` va `*72` bir vaqtda mavjud boʻla olmaydi, chunki Asterisk teriladigan raqamni ikkisidan
qaysi biriga tegishli ekanini ishonchli ajrata olmaydi. Bunday holatda tizim saqlashni rad etadi va «Bu
kod boshqa funksiya bilan toʻqnashadi» deb xato beradi.

> [!NOTE]
> Kun/Tun rejimini almashtirish kodi (`*28<kod>`) — bu alohida mexanizm, [Xususiyat
> kodlari](/docs/featurecodes) jadvalida koʻrinmaydi, balki har bir vaqt jadvali (time condition) uchun
> [Kun/Tun](/docs/day_night) boʻlimida sozlanadi.

## Bog'liq bo'limlar

- [Xususiyat kodlari](/docs/featurecodes)
- [Kun/Tun](/docs/day_night)
- [SIP va tarmoq](/docs/sip)
