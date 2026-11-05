// "status" namespace — Tizim holati sahifasi (S36): disk, tranklar, internet, SIP interfeysi + diskni tozalash.

export const uz = {
  title: 'Tizim holati',
  loadFailed: 'Yuklab boʻlmadi.',
  retry: 'Qayta urinish',

  disk: {
    title: 'Disk',
    usedOf: '{{used}} GB / {{total}} GB ishlatilgan',
    free: '{{free}} GB boʻsh',
    cleanButton: 'Diskni tozalash',
    category: {
      recordings: 'Qoʻngʻiroq yozuvlari', backups: 'Zaxiralar', migrations: 'Migratsiya fayllari',
      voicemail: 'Ovozli pochta', logs: 'Jurnallar',
    },
    categoryLine: '{{size}} — {{files}} fayl',
    notCleanable: 'Qoʻlda tozalanmaydi',
  },

  trunks: { title: 'Tranklar', empty: 'Tranklar sozlanmagan.' },

  internet: {
    title: 'Internet',
    connectionLabel: 'Ulanish', dnsLabel: 'DNS',
    up: 'Ulangan', down: 'Ulanmagan',
    dnsOk: 'DNS ishlayapti', dnsFail: 'DNS ishlamayapti',
    latency: 'Kechikish: {{ms}} ms',
    target: 'Manzil: {{target}}',
  },

  sip: {
    title: 'SIP interfeysi',
    asteriskUp: 'Asterisk ishlayapti', asteriskDown: 'Asterisk javob bermayapti',
    transportsTitle: 'Transportlar',
    column: { name: 'Nomi', protocol: 'Protokol', bind: 'Manzil' },
    endpointsOnline: 'Roʻyxatdan oʻtgan qurilmalar: {{online}} / {{total}}',
  },

  cleanup: {
    modalTitle: 'Diskni tozalash',
    recordingsLabel: 'Shuncha kundan eski yozuvlar oʻchirilsin',
    recordingsDays: 'kun',
    backupsLabel: 'Oxirgi shuncha zaxiradan tashqarisi oʻchirilsin',
    backupsKeepLast: 'ta',
    migrationsLabel: 'Yuklangan FreePBX migratsiya fayllari',
    previewLoading: 'Hisoblanmoqda…',
    previewResult: 'Boʻshaydi: {{size}} ({{files}} fayl)',
    previewEmpty: 'Hech narsa tanlanmagan.',
    confirm: 'Oʻchirish',
    cancel: 'Bekor qilish',
    doneToast: '{{size}} bosh joy ozod qilindi.',
    errorsTitle: 'Xatoliklar:',
  },

  power: {
    title: 'Qayta yuklash',
    activeCalls: 'Faol qoʻngʻiroqlar: {{count}}',
    rebootButton: 'Qayta yuklash',
    readonlyBanner: 'Boshqarib boʻlmaydi: {{reason}}',
    modalTitle: 'Tizimni qayta yuklash',
    modalWarning: 'Barcha faol qoʻngʻiroqlar uziladi va tizim bir necha daqiqaga ishlamay qoladi.',
    confirmHint: 'Tasdiqlash uchun «reboot» soʻzini yozing:',
    confirmPlaceholder: 'reboot',
    confirmMismatch: '«reboot» deb yozing.',
    cancel: 'Bekor qilish',
    confirm: 'Tasdiqlash',
    scheduledToast: '{{delay}} soniyadan keyin bajariladi.',
  },
};

export const ru = {
  title: 'Состояние системы',
  loadFailed: 'Не удалось загрузить.',
  retry: 'Повторить',

  disk: {
    title: 'Диск',
    usedOf: 'Использовано {{used}} ГБ из {{total}} ГБ',
    free: 'Свободно {{free}} ГБ',
    cleanButton: 'Очистить диск',
    category: {
      recordings: 'Записи звонков', backups: 'Резервные копии', migrations: 'Файлы миграции',
      voicemail: 'Голосовая почта', logs: 'Журналы',
    },
    categoryLine: '{{size}} — {{files}} файлов',
    notCleanable: 'Не очищается вручную',
  },

  trunks: { title: 'Транки', empty: 'Транки не настроены.' },

  internet: {
    title: 'Интернет',
    connectionLabel: 'Соединение', dnsLabel: 'DNS',
    up: 'Подключено', down: 'Нет соединения',
    dnsOk: 'DNS работает', dnsFail: 'DNS не работает',
    latency: 'Задержка: {{ms}} мс',
    target: 'Адрес: {{target}}',
  },

  sip: {
    title: 'SIP-интерфейс',
    asteriskUp: 'Asterisk работает', asteriskDown: 'Asterisk не отвечает',
    transportsTitle: 'Транспорты',
    column: { name: 'Имя', protocol: 'Протокол', bind: 'Адрес' },
    endpointsOnline: 'Зарегистрированные устройства: {{online}} / {{total}}',
  },

  cleanup: {
    modalTitle: 'Очистка диска',
    recordingsLabel: 'Удалить записи старше',
    recordingsDays: 'дней',
    backupsLabel: 'Оставить только последние',
    backupsKeepLast: 'копий',
    migrationsLabel: 'Загруженные файлы миграции FreePBX',
    previewLoading: 'Вычисляется…',
    previewResult: 'Освободится: {{size}} ({{files}} файлов)',
    previewEmpty: 'Ничего не выбрано.',
    confirm: 'Удалить',
    cancel: 'Отмена',
    doneToast: 'Освобождено {{size}}.',
    errorsTitle: 'Ошибки:',
  },

  power: {
    title: 'Перезагрузка',
    activeCalls: 'Активных звонков: {{count}}',
    rebootButton: 'Перезагрузить',
    readonlyBanner: 'Невозможно управлять: {{reason}}',
    modalTitle: 'Перезагрузить систему',
    modalWarning: 'Все активные звонки будут прерваны, система будет недоступна несколько минут.',
    confirmHint: 'Для подтверждения введите слово «reboot»:',
    confirmPlaceholder: 'reboot',
    confirmMismatch: 'Введите «reboot».',
    cancel: 'Отмена',
    confirm: 'Подтвердить',
    scheduledToast: 'Будет выполнено через {{delay}} сек.',
  },
};

export const en = {
  title: 'System status',
  loadFailed: 'Could not load.',
  retry: 'Retry',

  disk: {
    title: 'Disk',
    usedOf: '{{used}} GB of {{total}} GB used',
    free: '{{free}} GB free',
    cleanButton: 'Clean disk',
    category: {
      recordings: 'Call recordings', backups: 'Backups', migrations: 'Migration files',
      voicemail: 'Voicemail', logs: 'Logs',
    },
    categoryLine: '{{size}} — {{files}} files',
    notCleanable: 'Not cleaned manually',
  },

  trunks: { title: 'Trunks', empty: 'No trunks configured.' },

  internet: {
    title: 'Internet',
    connectionLabel: 'Connection', dnsLabel: 'DNS',
    up: 'Connected', down: 'Disconnected',
    dnsOk: 'DNS working', dnsFail: 'DNS not working',
    latency: 'Latency: {{ms}} ms',
    target: 'Target: {{target}}',
  },

  sip: {
    title: 'SIP interface',
    asteriskUp: 'Asterisk is running', asteriskDown: 'Asterisk is not responding',
    transportsTitle: 'Transports',
    column: { name: 'Name', protocol: 'Protocol', bind: 'Address' },
    endpointsOnline: 'Registered devices: {{online}} / {{total}}',
  },

  cleanup: {
    modalTitle: 'Clean disk',
    recordingsLabel: 'Delete recordings older than',
    recordingsDays: 'days',
    backupsLabel: 'Keep only the last',
    backupsKeepLast: 'backups',
    migrationsLabel: 'Uploaded FreePBX migration files',
    previewLoading: 'Calculating…',
    previewResult: 'Will free: {{size}} ({{files}} files)',
    previewEmpty: 'Nothing selected.',
    confirm: 'Delete',
    cancel: 'Cancel',
    doneToast: 'Freed {{size}}.',
    errorsTitle: 'Errors:',
  },

  power: {
    title: 'Reboot',
    activeCalls: 'Active calls: {{count}}',
    rebootButton: 'Reboot',
    readonlyBanner: 'Cannot be controlled: {{reason}}',
    modalTitle: 'Reboot the system',
    modalWarning: 'All active calls will be dropped and the system will be unavailable for a few minutes.',
    confirmHint: 'To confirm, type the word “reboot”:',
    confirmPlaceholder: 'reboot',
    confirmMismatch: 'Type “reboot”.',
    cancel: 'Cancel',
    confirm: 'Confirm',
    scheduledToast: 'Will run in {{delay}} seconds.',
  },
};
