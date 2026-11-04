---
id: tez-boshlash
title: Tezkor boshlash
group: start
order: 40
summary: Birinchi sozlashdan keyin ichki raqam yaratish, trunk ulash va qoʻngʻiroq yoʻnaltirishni sozlashgacha qisqa yoʻl.
---

# Tezkor boshlash

[Birinchi sozlash](/docs/birinchi-sozlash)ni oʻtgandan soʻng, Innova PBX orqali birinchi qoʻngʻiroqni amalga oshirish uchun quyidagi tartibda davom eting: ichki raqam yaratish, telefonni ulash, operator trunkini qoʻshish va qoʻngʻiroq yoʻnalishlarini sozlash.

## Qanday qilinadi

### 1. Birinchi ichki raqamni yaratish
1. **Foydalanuvchilar → Ichki raqamlar** boʻlimiga oʻting.
2. **Yangi ichki raqam** tugmasini bosing, **Raqam** va **Nom** kiriting (raqamni boʻsh qoldirsangiz avtomatik tanlanadi).
3. **Yaratish**ni bosib chiqqan SIP login/parol/domen/portni koʻchirib oling — bu maʼlumot keyin qayta koʻrsatilmaydi.

Batafsil: [Ichki raqamlar](/docs/extensions).

### 2. Telefonni ulash
- **Stol telefoni bor boʻlsa**: **Telefon apparatlari** boʻlimida apparatni qoʻshib, 1-qadamda yaratilgan ichki raqamga biriktiring (yoki provisioning URL/DHCP orqali avtomatik aniqlanishini kutib, **Telefon apparatlari** roʻyxatida tasdiqlang). Batafsil: [Telefon apparatlari](/docs/devices).
- **Apparat yoʻq boʻlsa**: [Ichki raqamlar](/docs/extensions) jadvalida shu raqam qatorida QR ikonkasini bosib, chiqqan QR kodni mobil Linphone ilovasi bilan 15 daqiqa ichida skanerlang — yoki **Mening kabinetim** ([Mening kabinetim](/docs/portal)) orqali brauzer softfonidan foydalaning (HTTPS talab qiladi).

### 3. Operator trunkini qoʻshish
1. **Ulanish → Trunklar** boʻlimiga oʻting, **Yangi trunk** tugmasini bosing.
2. Operatordan olingan **Host**/**Port** va autentifikatsiya maʼlumotlarini (IP boʻyicha yoki Registratsiya) kiriting, kodeklarni belgilang.
3. **Qoʻshish**dan keyin **Sinash** tugmasi bilan aloqani tekshiring.

Batafsil: [Trunklar](/docs/trunks).

### 4. Chiquvchi qoʻngʻiroqni sozlash
1. **Ulanish → Chiquvchi marshrutlar** boʻlimida **Yangi marshrut** yarating.
2. **Naqsh** qoidasiga terish formatini (masalan `998XXXXXXXXX`) kiriting, **Trunk zanjiri**da 3-qadamda qoʻshilgan trunkni tanlang.
3. Sahifadagi **Sinovchi** bilan ichki raqam va sinaladigan raqamni kiritib, marshrut toʻgʻri ishlayotganini tekshiring.

Batafsil: [Chiquvchi marshrutlar](/docs/outbound).

### 5. Kiruvchi qoʻngʻiroqni sozlash
1. **Ulanish → Kiruvchi marshrutlar** boʻlimida **Yangi marshrut** yarating.
2. Operator bergan **DID** raqamini kiriting (yoki **Har qanday DID**ni yoqilgan holda qoldiring).
3. **Manzil** maydonida tashqaridan kelgan qoʻngʻiroq qayerga (masalan 1-qadamdagi ichki raqamga) borishini tanlang, **Qoʻshish**ni bosing.

Batafsil: [Kiruvchi marshrutlar](/docs/inbound).

### 6. Natijani tekshirish
1. **Boshqaruv paneli** ([Boshqaruv paneli](/docs/dashboard)) yoki **Jonli monitoring** ([Jonli monitoring](/docs/live)) sahifasini oching.
2. Sinov qoʻngʻirogʻini amalga oshirib, uning jonli holatini va keyin boshqaruv panelidagi kunlik statistikada koʻrinishini tekshiring.

## Maslahatlar va cheklovlar

> [!TIP]
> Trunk va marshrutlarni sozlashdan oldin kamida bitta ichki raqam tayyor boʻlsin — shunda **Sinovchi** va **Manzil** maydonlarida uni darhol tanlab sinab koʻrish mumkin.

> [!WARNING]
> Ichki raqam uchun **Brauzer softfoni (WebRTC)**ni yoqsangiz, shu raqamga fizik apparat yoki QR orqali ulash imkoni yoʻqoladi — oldindan qaysi usulni tanlashni hal qiling.

> [!TIP]
> Yangi sozlangan trunk/marshrutlarni haqiqiy qoʻngʻiroq qilishdan oldin har doim **Sinash**/**Sinovchi** vositalari bilan tekshirib koʻring — xato sabablar shu yerda qadamma-qadam koʻrsatiladi.

## Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| Telefon registratsiya boʻlmayapti | SIP login/parol/domen notoʻgʻri kiritilgan yoki apparat tarmoqdan serverga yetib bormayapti | [Ichki raqamlar](/docs/extensions)dagi maʼlumotlarni qayta tekshiring, tarmoq/firewall sozlamalarini koʻring |
| Chiquvchi qoʻngʻiroq oʻtmayapti | Naqsh mos kelmadi, trunk ishlamayapti yoki ruxsat yoʻq | [Chiquvchi marshrutlar](/docs/outbound)dagi **Sinovchi** bilan sababni aniqlang |
| Kiruvchi qoʻngʻiroq kelmayapti | DID notoʻgʻri kiritilgan yoki trunk registratsiyasi ishlamayapti | [Trunklar](/docs/trunks)da sogʻlik holatini, [Kiruvchi marshrutlar](/docs/inbound)da DIDni tekshiring |
| Boshqaruv panelida hech narsa koʻrinmaydi | Hali birorta qoʻngʻiroq amalga oshirilmagan | Sinov qoʻngʻirogʻini amalga oshirib qaytadan tekshiring |

## Bog'liq bo'limlar

- [Birinchi sozlash](/docs/birinchi-sozlash)
- [Ichki raqamlar](/docs/extensions)
- [Trunklar](/docs/trunks)
- [Chiquvchi marshrutlar](/docs/outbound)
- [Kiruvchi marshrutlar](/docs/inbound)
- [Boshqaruv paneli](/docs/dashboard)
