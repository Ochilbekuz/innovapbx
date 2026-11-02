# 1C konfiguratsiyasida yaratiladigan metadata obyektlari

Bu ro'yxat `InnovaPBX_HTTPServis.bsl` va `InnovaPBX_Ulanish.bsl` modullari ishlashi uchun
Konfiguratorda (yoki 1C:EDT'da) qo'lda yaratilishi kerak bo'lgan obyektlarni tasvirlaydi.
Kodning o'zi tayyor — lekin metadata (HTTP-servis, registrlar, konstantalar) hali
konfiguratsiyada yo'q bo'lsa, modul ishga tushmaydi.

> DIQQAT: bu yerda ko'rsatilgan tip/uzunlik qiymatlari — tavsiya etilgan boshlang'ich
> qiymatlar. Real konfiguratsiyangizdagi nom to'qnashuvlarini (allaqachon mavjud
> `PBX*` prefiksli obyektlar) tekshirib, kerak bo'lsa prefiksni o'zgartiring.

## 1. HTTP-servis — `InnovaPBX`

| Xossa | Qiymat |
|---|---|
| Nomi | `InnovaPBX` |
| Korneviy shablon (URL) | `innova` |
| Bosh modul (сессия sozlamalari uchun, ixtiyoriy) | — |

**Shablonlar:**

| Shablon nomi | URL shabloni | Metod | Modul | Protsedura/Funksiya |
|---|---|---|---|---|
| Hodisa | `/event` | POST | `InnovaPBX_HTTPServis` | `ОбработкаСобытия` |

To'liq URL (publikatsiyadan keyin, masalan Apache ostida `/innova-pbx/`): \
`https://<1c-server>/innova-pbx/hs/innova/event`

Shu URL — PBX panelida "Webhook yaratish" qadamida kiritiladigan manzil.

## 2. Umumiy modul — `InnovaPBX_Ulanish`

| Xossa | Qiymat |
|---|---|
| На сервере | Истина |
| Клиент (обычное приложение) | Ложь |
| Клиент (управляемое приложение) | Ложь |
| Внешнее соединение | Ложь |
| Вызов сервера | Истина |
| Привилегированный режим | Ложь (registrlarga yozish — oddiy huquqlar bilan) |

Eksport qilingan metodlar: `ВызватьИзPBX`, `ЗаписьРазговора`, `СписокЗвонков`.

## 3. Regisrt сведений — `PBXВходящиеДоставки`

Webhook idempotentligi uchun (`X-Innova-Delivery` bo'yicha).

| Turi | Nomi | Tip | Izoh |
|---|---|---|---|
| Измерение | `ИдентификаторДоставки` | Строка(36) | UUID, `X-Innova-Delivery` |
| Ресурс | `ДатаПолучения` | Дата (ДатаВремя) | Qabul qilingan vaqt (server local) |
| Ресурс | `ТипСобытия` | Строка(30) | `call.ringing` va h.k. |
| Ресурс | `КодОтвета` | Число(3,0) | Qaytarilgan HTTP kod |

Периодичность: **Непериодический**. Registrni tozalash uchun alohida fon vazifa
(masalan 90 kundan eski yozuvlarni o'chirish) tavsiya etiladi — bu namunaga kirmaydi.

## 4. Regisrt сведений — `PBXСобытияЗвонков`

Qo'ng'iroq hodisalarining o'zi (audit + keyingi tahlil uchun).

| Turi | Nomi | Tip | Izoh |
|---|---|---|---|
| Измерение | `ИдентификаторЗвонка` | Строка(50) | `call.id` (linkedid) |
| Измерение | `ТипСобытия` | Строка(20) | `call.ringing/answered/ended` |
| Ресурс | `Направление` | Строка(10) | `inbound/outbound/internal` |
| Ресурс | `От` | Строка(50) | `call.from` |
| Ресурс | `Кому` | Строка(50) | `call.to` |
| Ресурс | `ВнутреннийНомер` | Строка(20) | `call.extension` |
| Ресурс | `ОчередьИдентификатор` | Строка(36) | `call.queue.id`, bo'sh bo'lishi mumkin |
| Ресурс | `ОчередьНазвание` | Строка(100) | `call.queue.name` |
| Ресурс | `Статус` | Строка(20) | faqat `ended`: `answered/missed/busy/failed` |
| Ресурс | `ДлительностьС` | Число(10,0) | `duration_s` |
| Ресурс | `BillsecС` | Число(10,0) | `billsec` |
| Ресурс | `ОтветившийВнутренний` | Строка(20) | `answered_by` |
| Ресурс | `ТелоJSON` | Строка (неограниченная) | to'liq payload, audit uchun |

Периодичность: **По позиции регистратора** o'rniga oddiy — `Период` maydoni
avtomatik mavjud (har qanday регистр сведений'da bo'ladi); yozishda
`Запись.Период = ТекущаяДата()` qo'yiladi (kod shunday yozilgan).

## 5. Regisrt сведений — `PBXСекреты` (BSP bo'lmaganda zaxira variant)

Agar konfiguratsiyada BSP (Библиотека стандартных подсистем) va uning
`БезопасноеХранилищеДанных` umumiy moduli O'RNATILMAGAN bo'lsa, shu registrni
yarating — kod avtomatik fallback qiladi (`Попытка...Исключение`).

| Turi | Nomi | Tip | Izoh |
|---|---|---|---|
| Измерение | `Калит` (Ключ) | Строка(50) | `WebhookSecret`, `APIКлюч` |
| Ресурс | `Значение` | Строка (неограниченная) | sir qiymati |

Qo'shimcha eksport qilingan funksiya kerak bo'ladi: `РегистрыСведений.PBXСекреты.ПолучитьСекрет(Ключ)`
(registr manageriga Export funksiya sifatida yozing — standart 1C amaliyoti,
registr menejer modulida).

**Kirish huquqi** — roli faqat `Administrator` (yoki maxsus `PBXИнтеграция`) rolga
`Чтение`/`Запись` beriladi; boshqa rollarga umuman ko'rinmasin.

> Xavfsizlik eslatmasi: bu registr qiymatni shifrlamaydi, faqat huquqlar bilan
> cheklaydi. Productionda BSP'ning haqiqiy xavfsiz xotira mexanizmini ishlatish
> tavsiya etiladi.

## 6. Konstantalar

| Nomi | Tip | Sukut qiymat | Izoh |
|---|---|---|---|
| `PBXАдресСервераAPI` | Строка(200) | — | masalan `https://pbx.misol.uz` (sxema bilan, oxirida `/` siz) |
| `PBXТаймаутHTTPС` | Число(5,0) | `30` | REST so'rovlar uchun timeout (soniya) |
| `PBXДопустимоеОтклонениеВременнойМеткиС` | Число(5,0) | `300` | webhook imzosi uchun ±soniya oynasi |

## 7. Rollar

Yangi rol (yoki mavjud rolni kengaytirish) — HTTP-servis modulida foydalanilgan
registrlarga `Чтение`/`Добавление`/`Изменение` huquqi, konstantalarga `Чтение`.
HTTP-servis so'rovlari odatda alohida texnik foydalanuvchi nomidan (Basic-auth
yoki anonim, konfiguratsiya xavfsizlik sozlamalariga bog'liq) ishlaydi — shu
foydalanuvchiga minimal huquq (faqat kerakli registr/konstantalar) berilsin.

## Platforma talabi

1C:Enterprise **8.3.11 yoki yangiroq** kerak: HMAC hisobida `ПобитовоеИсключительноеИли`, `БуферДвоичныхДанных`, `СоединитьДвоичныеДанные`, `ПолучитьHexСтрокуИзДвоичныхДанных` ishlatilgan.
