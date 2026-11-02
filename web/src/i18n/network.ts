// "network" namespace — Tarmoq sahifasi (S38, M8): umumiy/interfeyslar/marshrutlar, qo'llash/tasdiqlash oqimi.

export const uz = {
  title: 'Tarmoq',
  loadFailed: 'Yuklab boʻlmadi.',
  retry: 'Qayta urinish',

  readonlyBanner: 'Tarmoq sozlamalari faqat koʻrish uchun: {{reason}}',
  readonlyReason: {
    netplan: 'bu serverda tarmoqni netplan boshqaradi. Tahrirlash Debian (ifupdown) oʻrnatmasida ishlaydi.',
    networkmanager: 'bu serverda tarmoqni NetworkManager boshqaradi. Tahrirlash Debian (ifupdown) oʻrnatmasida ishlaydi.',
  },
  helperUnavailableBanner: 'Tarmoq xizmati (netd) ishlamayapti — oʻzgarishlarni qoʻllab boʻlmaydi.',

  tabs: { general: 'Umumiy', interfaces: 'Interfeyslar', routes: 'Statik marshrutlar' },

  general: {
    hostnameLabel: 'Host nomi',
    dnsServersLabel: 'DNS serverlar',
    dnsServersHint: 'Vergul yoki qator bilan ajratilgan IP manzillar.',
    dnsSearchLabel: 'Qidiruv domenlari',
    dnsSearchHint: 'Masalan: innova.local',
    defaultGatewayLabel: 'Standart shlyuz',
    defaultGatewayValue: '{{address}} ({{iface}} orqali)',
    defaultGatewayNone: 'Belgilanmagan',
  },

  interfaces: {
    column: { name: 'Interfeys', status: 'Holat', mode: 'Rejim', address: 'Manzil', actions: '' },
    connected: 'Ulangan', disconnected: 'Ulanmagan',
    speed: '{{mbps}} Mbit/s',
    speedGbit: '{{gbit}} Gbit/s',
    mode: { dhcp: 'DHCP', static: 'Statik', manual: "Qo'lda", unconfigured: 'Sozlanmagan' },
    editButton: 'Sozlash',
    notEditable: 'Tahrirlanmaydi',
    modalTitle: '{{name}} interfeysini sozlash',
    modeLabel: 'Rejim',
    addressLabel: 'Manzil (CIDR)',
    addressPlaceholder: '192.168.10.20/24',
    gatewayLabel: 'Shlyuz',
    gatewayPlaceholder: '192.168.10.1',
    gatewayOptional: 'Ixtiyoriy',
    mtuLabel: 'MTU',
    currentAddresses: 'Hozirgi manzillar',
    noAddresses: 'Manzil yoʻq',
    save: 'Saqlash',
    cancel: 'Bekor qilish',
  },

  routes: {
    column: { destination: 'Manzil', gateway: 'Shlyuz', interface: 'Interfeys', metric: 'Metrik', actions: '' },
    empty: 'Statik marshrutlar yoʻq.',
    liveTitle: 'Joriy marshrutlar jadvali',
    addButton: 'Marshrut qoʻshish',
    editButton: 'Tahrirlash',
    deleteButton: 'Oʻchirish',
    modalTitleAdd: 'Marshrut qoʻshish',
    modalTitleEdit: 'Marshrutni tahrirlash',
    destinationLabel: 'Manzil (CIDR)',
    destinationPlaceholder: '10.20.0.0/16',
    gatewayLabel: 'Shlyuz',
    interfaceLabel: 'Interfeys',
    interfaceAny: 'Avtomatik',
    metricLabel: 'Metrik',
    metricOptional: 'Ixtiyoriy',
    save: 'Saqlash',
    cancel: 'Bekor qilish',
  },

  draftBar: {
    changes: '{{count}} ta oʻzgarish',
    discard: 'Bekor qilish',
    apply: 'Qoʻllash',
  },

  confirmModal: {
    title: 'Oʻzgarishlarni qoʻllash',
    diffTitle: 'Nima oʻzgaradi',
    warningsTitle: 'Ogohlantirishlar',
    timeoutLabel: 'Tasdiqlash uchun vaqt',
    timeoutHint: 'Shu vaqt ichida tasdiqlamasangiz — avtomatik eski holatga qaytadi.',
    cancel: 'Bekor qilish',
    confirm: 'Qoʻllash',
  },

  errorsBanner: 'Tekshiruvdan oʻtmadi — pastdagi maydonlarni tuzating.',

  pendingBanner: {
    title: 'Oʻzgarish kutilmoqda',
    countdown: 'Avtomatik qaytarilishga: {{time}}',
    confirmButton: 'Tasdiqlash',
    rollbackButton: 'Hozir qaytarish',
    expiredNotice: 'Muddat tugadi, holat qayta yuklanmoqda…',
  },

  lastResult: {
    confirmed: 'Tarmoq sozlamalari tasdiqlandi.',
    rolled_back: 'Oʻzgarish qaytarildi.',
    apply_failed: 'Qoʻllash muvaffaqiyatsiz tugadi.',
    dismiss: 'Yopish',
  },

  toast: {
    applied: 'Oʻzgarish qoʻllandi — tasdiqlashni unutmang.',
    confirmed: 'Tasdiqlandi.',
    rolledBack: 'Qaytarildi.',
  },

  validation: {
    cidrInvalid: 'CIDR koʻrinishida boʻlishi kerak (masalan 192.168.1.10/24).',
    ipInvalid: 'IP manzil notoʻgʻri.',
    required: 'Majburiy maydon.',
  },
};

export const ru = {
  title: 'Сеть',
  loadFailed: 'Не удалось загрузить.',
  retry: 'Повторить',

  readonlyBanner: 'Сетевые настройки только для просмотра: {{reason}}',
  readonlyReason: {
    netplan: 'сетью этого сервера управляет netplan. Редактирование доступно в установке Debian (ifupdown).',
    networkmanager: 'сетью этого сервера управляет NetworkManager. Редактирование доступно в установке Debian (ifupdown).',
  },
  helperUnavailableBanner: 'Служба сети (netd) не работает — изменения невозможны.',

  tabs: { general: 'Общее', interfaces: 'Интерфейсы', routes: 'Статические маршруты' },

  general: {
    hostnameLabel: 'Имя хоста',
    dnsServersLabel: 'DNS-серверы',
    dnsServersHint: 'IP-адреса через запятую или с новой строки.',
    dnsSearchLabel: 'Домены поиска',
    dnsSearchHint: 'Например: innova.local',
    defaultGatewayLabel: 'Стандартный шлюз',
    defaultGatewayValue: '{{address}} (через {{iface}})',
    defaultGatewayNone: 'Не задан',
  },

  interfaces: {
    column: { name: 'Интерфейс', status: 'Статус', mode: 'Режим', address: 'Адрес', actions: '' },
    connected: 'Подключён', disconnected: 'Не подключён',
    speed: '{{mbps}} Мбит/с',
    speedGbit: '{{gbit}} Гбит/с',
    mode: { dhcp: 'DHCP', static: 'Статический', manual: 'Вручную', unconfigured: 'Не настроен' },
    editButton: 'Настроить',
    notEditable: 'Не редактируется',
    modalTitle: 'Настройка интерфейса {{name}}',
    modeLabel: 'Режим',
    addressLabel: 'Адрес (CIDR)',
    addressPlaceholder: '192.168.10.20/24',
    gatewayLabel: 'Шлюз',
    gatewayPlaceholder: '192.168.10.1',
    gatewayOptional: 'Необязательно',
    mtuLabel: 'MTU',
    currentAddresses: 'Текущие адреса',
    noAddresses: 'Нет адреса',
    save: 'Сохранить',
    cancel: 'Отмена',
  },

  routes: {
    column: { destination: 'Адрес', gateway: 'Шлюз', interface: 'Интерфейс', metric: 'Метрика', actions: '' },
    empty: 'Статических маршрутов нет.',
    liveTitle: 'Текущая таблица маршрутов',
    addButton: 'Добавить маршрут',
    editButton: 'Изменить',
    deleteButton: 'Удалить',
    modalTitleAdd: 'Добавить маршрут',
    modalTitleEdit: 'Изменить маршрут',
    destinationLabel: 'Адрес (CIDR)',
    destinationPlaceholder: '10.20.0.0/16',
    gatewayLabel: 'Шлюз',
    interfaceLabel: 'Интерфейс',
    interfaceAny: 'Автоматически',
    metricLabel: 'Метрика',
    metricOptional: 'Необязательно',
    save: 'Сохранить',
    cancel: 'Отмена',
  },

  draftBar: {
    changes: '{{count}} изменений',
    discard: 'Отменить',
    apply: 'Применить',
  },

  confirmModal: {
    title: 'Применить изменения',
    diffTitle: 'Что изменится',
    warningsTitle: 'Предупреждения',
    timeoutLabel: 'Время на подтверждение',
    timeoutHint: 'Если не подтвердите за это время — вернётся прежнее состояние.',
    cancel: 'Отмена',
    confirm: 'Применить',
  },

  errorsBanner: 'Проверка не пройдена — исправьте поля ниже.',

  pendingBanner: {
    title: 'Изменение ожидает подтверждения',
    countdown: 'Автоматический откат через: {{time}}',
    confirmButton: 'Подтвердить',
    rollbackButton: 'Откатить сейчас',
    expiredNotice: 'Время истекло, состояние перезагружается…',
  },

  lastResult: {
    confirmed: 'Сетевые настройки подтверждены.',
    rolled_back: 'Изменение откатано.',
    apply_failed: 'Не удалось применить изменения.',
    dismiss: 'Закрыть',
  },

  toast: {
    applied: 'Изменение применено — не забудьте подтвердить.',
    confirmed: 'Подтверждено.',
    rolledBack: 'Откатано.',
  },

  validation: {
    cidrInvalid: 'Нужен формат CIDR (например 192.168.1.10/24).',
    ipInvalid: 'Некорректный IP-адрес.',
    required: 'Обязательное поле.',
  },
};

export const en = {
  title: 'Network',
  loadFailed: 'Could not load.',
  retry: 'Retry',

  readonlyBanner: 'Network settings are read-only: {{reason}}',
  readonlyReason: {
    netplan: 'this server\'s network is managed by netplan. Editing is available on the Debian (ifupdown) install.',
    networkmanager: 'this server\'s network is managed by NetworkManager. Editing is available on the Debian (ifupdown) install.',
  },
  helperUnavailableBanner: 'The network service (netd) is down — changes cannot be applied.',

  tabs: { general: 'General', interfaces: 'Interfaces', routes: 'Static routes' },

  general: {
    hostnameLabel: 'Hostname',
    dnsServersLabel: 'DNS servers',
    dnsServersHint: 'Comma or newline separated IP addresses.',
    dnsSearchLabel: 'Search domains',
    dnsSearchHint: 'e.g. innova.local',
    defaultGatewayLabel: 'Default gateway',
    defaultGatewayValue: '{{address}} (via {{iface}})',
    defaultGatewayNone: 'Not set',
  },

  interfaces: {
    column: { name: 'Interface', status: 'Status', mode: 'Mode', address: 'Address', actions: '' },
    connected: 'Connected', disconnected: 'Disconnected',
    speed: '{{mbps}} Mbit/s',
    speedGbit: '{{gbit}} Gbit/s',
    mode: { dhcp: 'DHCP', static: 'Static', manual: 'Manual', unconfigured: 'Unconfigured' },
    editButton: 'Configure',
    notEditable: 'Not editable',
    modalTitle: 'Configure {{name}}',
    modeLabel: 'Mode',
    addressLabel: 'Address (CIDR)',
    addressPlaceholder: '192.168.10.20/24',
    gatewayLabel: 'Gateway',
    gatewayPlaceholder: '192.168.10.1',
    gatewayOptional: 'Optional',
    mtuLabel: 'MTU',
    currentAddresses: 'Current addresses',
    noAddresses: 'No address',
    save: 'Save',
    cancel: 'Cancel',
  },

  routes: {
    column: { destination: 'Destination', gateway: 'Gateway', interface: 'Interface', metric: 'Metric', actions: '' },
    empty: 'No static routes.',
    liveTitle: 'Current routing table',
    addButton: 'Add route',
    editButton: 'Edit',
    deleteButton: 'Delete',
    modalTitleAdd: 'Add route',
    modalTitleEdit: 'Edit route',
    destinationLabel: 'Destination (CIDR)',
    destinationPlaceholder: '10.20.0.0/16',
    gatewayLabel: 'Gateway',
    interfaceLabel: 'Interface',
    interfaceAny: 'Automatic',
    metricLabel: 'Metric',
    metricOptional: 'Optional',
    save: 'Save',
    cancel: 'Cancel',
  },

  draftBar: {
    changes: '{{count}} changes',
    discard: 'Discard',
    apply: 'Apply',
  },

  confirmModal: {
    title: 'Apply changes',
    diffTitle: "What's changing",
    warningsTitle: 'Warnings',
    timeoutLabel: 'Confirmation window',
    timeoutHint: "If you don't confirm within this time, it will roll back automatically.",
    cancel: 'Cancel',
    confirm: 'Apply',
  },

  errorsBanner: 'Validation failed — fix the fields below.',

  pendingBanner: {
    title: 'Change pending confirmation',
    countdown: 'Auto-rollback in: {{time}}',
    confirmButton: 'Confirm',
    rollbackButton: 'Roll back now',
    expiredNotice: 'Time expired, reloading state…',
  },

  lastResult: {
    confirmed: 'Network settings confirmed.',
    rolled_back: 'Change rolled back.',
    apply_failed: 'Failed to apply the change.',
    dismiss: 'Dismiss',
  },

  toast: {
    applied: 'Change applied — remember to confirm it.',
    confirmed: 'Confirmed.',
    rolledBack: 'Rolled back.',
  },

  validation: {
    cidrInvalid: 'Must be CIDR format (e.g. 192.168.1.10/24).',
    ipInvalid: 'Invalid IP address.',
    required: 'This field is required.',
  },
};
