# Innova PBX ↔ 1C integratsiyasini o'rnatish (o'zbekcha)

Bu qo'llanma ikki tomonni ham qamrab oladi: **Innova PBX panelida** sozlash va
**1C konfiguratsiyasida** obyektlarni yaratish. Fayllar: `InnovaPBX_HTTPServis.bsl`,
`InnovaPBX_Ulanish.bsl`, `Metadata-tavsifi.md` (shu papkada).

> Eslatma: bu BSL kodi 1C platformasi o'rnatilmagan serverda tayyorlangan —
> faqat sintaksis jihatidan ko'rib chiqilgan. Birinchi marta test (nusxa)
> bazasida ishga tushiring, keyin productionga o'tkazing.

## 1-qadam — Innova PBX panelida API kalit yaratish

1. Panelga admin huquqi bilan kiring → **Integratsiyalar** bo'limi.
2. **REST API** kartasida **Sozlash** → **Kalit yaratish**.
3. Nomi: masalan `1C-Buxgalteriya`. Scope'lar — faqat kerak bo'lganini belgilang:
   - `calls:read` — qo'ng'iroqlar tarixi kerak bo'lsa.
   - `recordings:read` — yozuvlarni 1C orqali yuklab olish kerak bo'lsa.
   - `calls:originate` — 1C'dan chaqiruv boshlash (click-to-call) kerak bo'lsa.
   - `extensions:read` — ichki raqamlar ro'yxati kerak bo'lsa.
4. **Yaratish**'dan keyin kalit (`ipk_...`) **FAQAT BIR MARTA** ko'rsatiladi —
   nusxa oling va xavfsiz joyga (parol menejeriga) saqlang. Keyinroq uni qayta
   ko'rish MUMKIN EMAS, faqat bekor qilib yangisini yaratish mumkin.

## 2-qadam — Webhook yaratish (PBX → 1C hodisalari)

1. **Integratsiyalar** → **Webhook'lar** → **Yaratish**.
2. **URL**: 1C HTTP-servis manzili, masalan:
   `https://1c.misol.uz/innova-pbx/hs/innova/event`
   (manba — `Metadata-tavsifi.md` 1-bandi, publikatsiya 3-qadamda tushuntirilgan).
3. **Hodisalar**: kerakli turlarni belgilang (`call.ringing`, `call.answered`,
   `call.ended`; ichki qo'ng'iroqlar kerak bo'lsa `include_internal`ni yoqing).
4. **Yaratish**dan keyin **secret** (`whsec_...` kabi) **FAQAT BIR MARTA**
   ko'rsatiladi — nusxa olib saqlang. 1C tomonida shu qiymat kerak bo'ladi
   (3-qadam, 3-band).

## 3-qadam — 1C konfiguratsiyasida obyektlarni yaratish

Konfiguratorni oching va `Metadata-tavsifi.md` bo'yicha quyidagilarni yarating:

1. **HTTP-servis** `InnovaPBX` (shablon `innova`, metod `/event` → POST →
   modul `InnovaPBX_HTTPServis`, funksiya `ОбработкаСобытия`). Modul matnini
   `InnovaPBX_HTTPServis.bsl` dan nusxalang.
2. **Umumiy modul** `InnovaPBX_Ulanish` (На сервере = Истина). Modul matnini
   `InnovaPBX_Ulanish.bsl` dan nusxalang.
3. **Konstantalar**: `PBXАдресСервераAPI` (qiymat — PBX panel manzili,
   masalan `https://pbx.misol.uz`), `PBXТаймаутHTTPС` (sukut `30`),
   `PBXДопустимоеОтклонениеВременнойМеткиС` (sukut `300`).
4. **Regisrt сведений** `PBXВходящиеДоставки` va `PBXСобытияЗвонков`
   (tuzilma — `Metadata-tavsifi.md` 3–4-band).
5. Sirlarni saqlash:
   - BSP (Библиотека стандартных подсистем) o'rnatilgan bo'lsa —
     `БезопасноеХранилищеДанных.УстановитьЗначение("InnovaPBX_WebhookSecret", "whsec_...")`
     va `..."InnovaPBX_APIКлюч", "ipk_..."` ni bir martalik ishga tushirish
     (obrabotka yoki konsolda) orqali yozing.
   - BSP yo'q bo'lsa — `PBXСекреты` registrini yarating (5-band) va shu yerga
     ikkita yozuv kiriting: `Калит="WebhookSecret"`, `Значение="whsec_..."` va
     `Калит="APIКлюч"`, `Значение="ipk_..."`.
6. Konfiguratsiyani yangilang va bazaga qo'llang.

## 4-qadam — Publikatsiya (Apache/IIS)

1C HTTP-servislar web-server orqali ishlaydi (to'g'ridan-to'g'ri klient-server
rejimida ham mumkin, lekin PBX'dan tashqi so'rov kelishi uchun odatda veb
publikatsiya kerak):

1. Konfiguratorda **Администрирование → Публикация на веб-сервере**.
2. Nomi: masalan `innova-pbx`. Katalog — veb-server (Apache/IIS) kutayotgan joy.
3. **HTTP-сервисы** belgisini yoqing (webhook ishlashi uchun shu shart).
4. **Публиковать** — natijada `default.vrd` (yoki `.htaccess` + modul,
   platforma turi bo'yicha) fayllari yaratiladi.
5. HTTPS sertifikatini sozlang (PBX webhook'i `https://` talab qiladi —
   §3 shartnomasida URL tekshiruvi bo'lib, faqat http/https va LAN/tashqi
   manzillarga ruxsat beradi, lekin PBX tomonidan TLS tavsiya etiladi).
6. Tekshirish: brauzerda
   `https://1c.misol.uz/innova-pbx/hs/innova/event` ga **GET** so'rov yuborilsa
   405 (Method Not Allowed) qaytishi kerak (chunki faqat POST ro'yxatga
   olingan) — bu publikatsiya ishlayotganini bildiradi.

## 5-qadam — Test qilish

1. Innova PBX panelida **Webhook'lar** jadvalida yaratilgan webhook qatorida
   **Test** tugmasini bosing — bu `test.ping` hodisasini yuboradi.
2. **Yetkazishlar jurnali** (`Deliveries`) da status `2xx` bo'lishi kerak.
3. 1C tomonida: `РегистрСведений.PBXВходящиеДоставки` da yangi yozuv
   paydo bo'lishini tekshiring (Konfiguratorda yoki raqamli konsolda).
4. Agar `401 invalid_signature` qaytsa — secret 1C va PBX panelida bir xil
   ekanligini tekshiring (bo'sh joy/qo'shimcha belgi bo'lmasligi kerak).
5. Agar `401 stale_timestamp` qaytsa — 1C serveri va PBX serveri soati
   sinxron ekanligini (NTP) tekshiring (±300 soniya oynadan tashqari
   bo'lmasligi kerak).

## 6-qadam — Chaqiruv boshlash (ixtiyoriy, `calls:originate` scope kerak)

1C'dan sinov uchun qisqa obrabotka yozing (yoki konsolda ishga tushiring):

```bsl
Результат = InnovaPBX_Ulanish.ВызватьИзPBX("+998901234567", "101");
Если Результат.Успех Тогда
	Сообщение = "So'rov yuborildi: " + Результат.ИдентификаторЗапроса;
Иначе
	Сообщение = "Xato (" + Результат.КодОшибки + "): " + Результат.Сообщение;
КонецЕсли;
```

Natijada `101` ichki raqami jiringlashi, javob berilgandan keyin
`+998901234567` raqami terilishi kerak.

## Muammolarni bartaraf etish

| Belgisi | Sabab | Yechim |
|---|---|---|
| `401 invalid_api_key` | Kalit noto'g'ri/bekor qilingan | Panelda yangi kalit yarating, 1C sozlamasini yangilang |
| `403 insufficient_scope` | Kalitda kerakli scope yo'q | Kalitga scope qo'shish MUMKIN EMAS — yangi kalit yarating kerakli scope bilan |
| `422` originate'da | `to` raqami formati yoki ichki raqam band/mavjud emas | Raqam formatini (`normalize_number`) va ichki raqam holatini tekshiring |
| `429` | 120/daq limitdan oshdi | So'rovlarni kamaytiring yoki kechiktirib qayta urining |
| Webhook kelmayapti | Publikatsiyada HTTP-сервисы yoqilmagan yoki firewall | 4-qadamni qayta tekshiring, PBX serveridan 1C manziliga `curl -I` bilan tekshiring |

> **Platforma talabi:** 1C:Enterprise 8.3.11 yoki yangiroq.
