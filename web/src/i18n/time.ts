// "time" namespace — Sana va vaqt sahifasi (M12 B1, ../../replica/m12-contract.md §B1). Pending/confirm yo'q —
// to'g'ridan-to'g'ri qo'llanadi (tarmoq/firewall'dan farqli).

export const uz = {
  title: 'Sana va vaqt',
  loadFailed: 'Yuklab boʻlmadi.',
  retry: 'Qayta urinish',
  readonlyBanner: 'Sana/vaqt sozlamalari faqat koʻrish uchun: {{reason}}',

  serverTimeLabel: 'Server vaqti',
  ntpOff: 'NTP oʻchiq — vaqt internet bilan sinxronlanmaydi',
  syncServerLabel: 'Vaqt manbai',
  syncServerNone: 'javob yoʻq',
  syncNow: 'Hozir sinxronlash',
  syncedToast: 'Vaqt internet bilan sinxronlandi',
  syncedToastServer: 'Manba: {{server}}',
  syncFailedToast: 'Sinxronlab boʻlmadi',
  backendLabel: 'Sinxronlash xizmati',
  syncedYes: 'Sinxronlangan',
  syncedNo: 'Sinxronlanmagan',

  timezoneLabel: 'Vaqt zonasi',
  timezoneSearchPlaceholder: 'Shahar yoki UTC+05 boʻyicha qidirish',
  timezoneNoMatch: 'Mos zona topilmadi',
  timezoneHint: 'Server, PBX ish vaqti qoidalari va kampaniyalar shu zonada ishlaydi. Bu zonada hozir: {{time}}',
  pbxTimezoneApplied: 'PBX vaqt zonasi yangilandi',

  ntpEnabledLabel: 'NTP yoqilgan',
  ntpServersLabel: 'NTP serverlar',
  ntpEnabledDescription: 'Vaqt internetdagi NTP serverlardan avtomatik toʻgʻrilanadi.',
  ntpServersHint: 'Boʻsh qoldirilsa zonaga mos pool ishlatiladi ({{pool}} …). Vergul yoki qator bilan, koʻpi bilan {{max}} ta.',

  save: 'Saqlash',
  savedToast: "Sana/vaqt sozlamalari saqlandi.",
  errorsBanner: 'Tekshiruvdan oʻtmadi — pastdagi maydonlarni tuzating.',

  validation: {
    timezoneInvalid: "Vaqt zonasi IANA roʻyxatida topilmadi.",
    serverInvalid: 'Yaroqsiz NTP server.',
    tooMany: "Koʻpi bilan {{max}} ta NTP server boʻlishi mumkin.",
  },
};

export const ru = {
  title: 'Дата и время',
  loadFailed: 'Не удалось загрузить.',
  retry: 'Повторить',
  readonlyBanner: 'Настройки даты/времени только для просмотра: {{reason}}',

  serverTimeLabel: 'Время сервера',
  ntpOff: 'NTP выключен — время не синхронизируется с интернетом',
  syncServerLabel: 'Источник времени',
  syncServerNone: 'нет ответа',
  syncNow: 'Синхронизировать сейчас',
  syncedToast: 'Время синхронизировано с интернетом',
  syncedToastServer: 'Источник: {{server}}',
  syncFailedToast: 'Не удалось синхронизировать',
  backendLabel: 'Служба синхронизации',
  syncedYes: 'Синхронизировано',
  syncedNo: 'Не синхронизировано',

  timezoneLabel: 'Часовой пояс',
  timezoneSearchPlaceholder: 'Поиск по городу или UTC+05',
  timezoneNoMatch: 'Часовой пояс не найден',
  timezoneHint: 'Сервер, правила рабочего времени АТС и кампании работают в этом поясе. Сейчас в нём: {{time}}',
  pbxTimezoneApplied: 'Часовой пояс АТС обновлён',

  ntpEnabledLabel: 'NTP включён',
  ntpServersLabel: 'NTP-серверы',
  ntpEnabledDescription: 'Время автоматически корректируется по NTP-серверам в интернете.',
  ntpServersHint: 'Если пусто — используется пул для пояса ({{pool}} …). Через запятую или с новой строки, не более {{max}}.',

  save: 'Сохранить',
  savedToast: 'Настройки даты/времени сохранены.',
  errorsBanner: 'Проверка не пройдена — исправьте поля ниже.',

  validation: {
    timezoneInvalid: 'Часовой пояс не найден в списке IANA.',
    serverInvalid: 'Некорректный NTP-сервер.',
    tooMany: 'Не более {{max}} NTP-серверов.',
  },
};

export const en = {
  title: 'Date and time',
  loadFailed: 'Could not load.',
  retry: 'Retry',
  readonlyBanner: 'Date/time settings are read-only: {{reason}}',

  serverTimeLabel: 'Server time',
  ntpOff: 'NTP is off — time is not synced with the internet',
  syncServerLabel: 'Time source',
  syncServerNone: 'no reply',
  syncNow: 'Sync now',
  syncedToast: 'Time synced with the internet',
  syncedToastServer: 'Source: {{server}}',
  syncFailedToast: 'Could not sync',
  backendLabel: 'Sync service',
  syncedYes: 'Synced',
  syncedNo: 'Not synced',

  timezoneLabel: 'Timezone',
  timezoneSearchPlaceholder: 'Search by city or UTC+05',
  timezoneNoMatch: 'No matching timezone',
  timezoneHint: 'The server, PBX business-hours rules and campaigns run in this zone. Now there: {{time}}',
  pbxTimezoneApplied: 'PBX timezone updated',

  ntpEnabledLabel: 'NTP enabled',
  ntpServersLabel: 'NTP servers',
  ntpEnabledDescription: 'Time is corrected automatically from internet NTP servers.',
  ntpServersHint: 'Leave empty to use the pool for this zone ({{pool}} …). Comma or newline separated, up to {{max}}.',

  save: 'Save',
  savedToast: 'Date/time settings saved.',
  errorsBanner: 'Validation failed — fix the fields below.',

  validation: {
    timezoneInvalid: 'Timezone not found in the IANA list.',
    serverInvalid: 'Invalid NTP server.',
    tooMany: 'Up to {{max}} NTP servers allowed.',
  },
};
