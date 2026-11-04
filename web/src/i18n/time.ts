// "time" namespace — Sana va vaqt sahifasi (M12 B1, ../../replica/m12-contract.md §B1). Pending/confirm yo'q —
// to'g'ridan-to'g'ri qo'llanadi (tarmoq/firewall'dan farqli).

export const uz = {
  title: 'Sana va vaqt',
  loadFailed: 'Yuklab boʻlmadi.',
  retry: 'Qayta urinish',
  readonlyBanner: 'Sana/vaqt sozlamalari faqat koʻrish uchun: {{reason}}',

  nowLabel: 'Hozirgi vaqt (UTC)',
  backendLabel: 'Sinxronlash xizmati',
  syncedYes: 'Sinxronlangan',
  syncedNo: 'Sinxronlanmagan',

  timezoneLabel: 'Vaqt zonasi',
  timezoneSearchPlaceholder: 'Qidirish… (masalan Tashkent)',

  ntpEnabledLabel: 'NTP yoqilgan',
  ntpServersLabel: 'NTP serverlar',
  ntpServersHint: 'Vergul yoki qator bilan ajratilgan IP yoki mezbon nomlar, koʻpi bilan {{max}} ta.',

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

  nowLabel: 'Текущее время (UTC)',
  backendLabel: 'Служба синхронизации',
  syncedYes: 'Синхронизировано',
  syncedNo: 'Не синхронизировано',

  timezoneLabel: 'Часовой пояс',
  timezoneSearchPlaceholder: 'Поиск… (например Tashkent)',

  ntpEnabledLabel: 'NTP включён',
  ntpServersLabel: 'NTP-серверы',
  ntpServersHint: 'IP или имена хостов через запятую/с новой строки, не более {{max}}.',

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

  nowLabel: 'Current time (UTC)',
  backendLabel: 'Sync service',
  syncedYes: 'Synced',
  syncedNo: 'Not synced',

  timezoneLabel: 'Timezone',
  timezoneSearchPlaceholder: 'Search… (e.g. Tashkent)',

  ntpEnabledLabel: 'NTP enabled',
  ntpServersLabel: 'NTP servers',
  ntpServersHint: 'Comma or newline separated IPs or hostnames, up to {{max}}.',

  save: 'Save',
  savedToast: 'Date/time settings saved.',
  errorsBanner: 'Validation failed — fix the fields below.',

  validation: {
    timezoneInvalid: 'Timezone not found in the IANA list.',
    serverInvalid: 'Invalid NTP server.',
    tooMany: 'Up to {{max}} NTP servers allowed.',
  },
};
