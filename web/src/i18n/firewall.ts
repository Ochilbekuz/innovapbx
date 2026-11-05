// "firewall" namespace — Firewall sahifasi (M12 B3, ../../replica/m12-contract.md §B3). `network`dagi bilan
// bir xil qoʻllash/tasdiqlash oqimi (draftBar/confirmModal/pendingBanner/lastResult — tarjima kalitlari ham
// shunga mos).

export const uz = {
  title: 'Firewall',
  tabs: { rules: 'Qoidalar', access: 'SSH va veb-panel' },
  loadFailed: 'Yuklab boʻlmadi.',
  retry: 'Qayta urinish',
  readonlyBanner: 'Firewall sozlamalari faqat koʻrish uchun: {{reason}}',

  services: {
    title: 'Xizmatlar',
    column: { name: 'Xizmat', mode: 'Rejim', allow: 'Ruxsat etilgan CIDR' },
    name: { ssh: 'SSH', web: 'Veb-panel', sip: 'SIP', rtp: 'RTP (ovoz)' },
    mode: { all: 'Hammaga ochiq', allowlist: 'Faqat roʻyxatdagilarga' },
    allowHint: 'Vergul yoki qator bilan ajratilgan IPv4 CIDR (masalan 192.168.1.0/24).',
    allowEmpty: 'Hech kim yoʻq — allowlist rejimida kamida bitta CIDR kerak.',
    portLabel: 'Port: {{port}}',
    webPortsLabel: 'HTTP: {{http}}, HTTPS: {{https}}',
  },

  accessLink: 'SSH va veb-panelga kirish sozlamalari',

  blocked: {
    title: 'Bloklangan manzillar',
    hint: 'Vergul yoki qator bilan ajratilgan IPv4 CIDR roʻyxati — shu manzillardan HAMMA port yopiladi.',
    empty: 'Bloklangan manzil yoʻq.',
  },

  timeoutLabel: 'Tasdiqlash uchun vaqt (soniya)',

  draftBar: { changes: '{{count}} ta oʻzgarish', discard: 'Bekor qilish', apply: 'Qoʻllash' },

  confirmModal: {
    title: 'Oʻzgarishlarni qoʻllash',
    diffTitle: 'Nima oʻzgaradi',
    timeoutHint: 'Shu vaqt ichida tasdiqlamasangiz — avtomatik eski holatga qaytadi.',
    cancel: 'Bekor qilish',
    confirm: 'Qoʻllash',
  },

  errorsBanner: 'Tekshiruvdan oʻtmadi — pastdagi maydonlarni tuzating.',
  selfLockoutError: "Diqqat: bu sozlama joriy administratorni oʻzini qulflab qoʻyishi mumkin edi — oldini olindi.",

  pendingBanner: {
    title: 'Oʻzgarish kutilmoqda',
    countdown: 'Avtomatik qaytarilishga: {{time}}',
    confirmButton: 'Tasdiqlash',
    rollbackButton: 'Hozir qaytarish',
    expiredNotice: 'Muddat tugadi, holat qayta yuklanmoqda…',
  },

  lastResult: {
    confirmed: 'Firewall sozlamalari tasdiqlandi.',
    rolled_back: 'Oʻzgarish qaytarildi.',
    apply_failed: 'Qoʻllash muvaffaqiyatsiz tugadi.',
    dismiss: 'Yopish',
  },

  toast: { applied: 'Oʻzgarish qoʻllandi — tasdiqlashni unutmang.', confirmed: 'Tasdiqlandi.', rolledBack: 'Qaytarildi.' },
};

export const ru = {
  title: 'Firewall',
  tabs: { rules: 'Правила', access: 'SSH и веб-панель' },
  loadFailed: 'Не удалось загрузить.',
  retry: 'Повторить',
  readonlyBanner: 'Настройки firewall только для просмотра: {{reason}}',

  services: {
    title: 'Службы',
    column: { name: 'Служба', mode: 'Режим', allow: 'Разрешённые CIDR' },
    name: { ssh: 'SSH', web: 'Веб-панель', sip: 'SIP', rtp: 'RTP (голос)' },
    mode: { all: 'Открыто для всех', allowlist: 'Только из списка' },
    allowHint: 'IPv4 CIDR через запятую или с новой строки (например 192.168.1.0/24).',
    allowEmpty: 'Пусто — в режиме allowlist нужен хотя бы один CIDR.',
    portLabel: 'Порт: {{port}}',
    webPortsLabel: 'HTTP: {{http}}, HTTPS: {{https}}',
  },

  accessLink: 'Настройки доступа по SSH и веб-панели',

  blocked: {
    title: 'Блокированные адреса',
    hint: 'Список IPv4 CIDR через запятую/с новой строки — для них закрываются ВСЕ порты.',
    empty: 'Блокированных адресов нет.',
  },

  timeoutLabel: 'Время на подтверждение (сек.)',

  draftBar: { changes: '{{count}} изменений', discard: 'Отменить', apply: 'Применить' },

  confirmModal: {
    title: 'Применить изменения',
    diffTitle: 'Что изменится',
    timeoutHint: 'Если не подтвердите за это время — вернётся прежнее состояние.',
    cancel: 'Отмена',
    confirm: 'Применить',
  },

  errorsBanner: 'Проверка не пройдена — исправьте поля ниже.',
  selfLockoutError: 'Внимание: эта настройка могла заблокировать текущего администратора — это предотвращено.',

  pendingBanner: {
    title: 'Изменение ожидает подтверждения',
    countdown: 'Автоматический откат через: {{time}}',
    confirmButton: 'Подтвердить',
    rollbackButton: 'Откатить сейчас',
    expiredNotice: 'Время истекло, состояние перезагружается…',
  },

  lastResult: {
    confirmed: 'Настройки firewall подтверждены.',
    rolled_back: 'Изменение откатано.',
    apply_failed: 'Не удалось применить изменения.',
    dismiss: 'Закрыть',
  },

  toast: { applied: 'Изменение применено — не забудьте подтвердить.', confirmed: 'Подтверждено.', rolledBack: 'Откатано.' },
};

export const en = {
  title: 'Firewall',
  tabs: { rules: 'Rules', access: 'SSH & web panel' },
  loadFailed: 'Could not load.',
  retry: 'Retry',
  readonlyBanner: 'Firewall settings are read-only: {{reason}}',

  services: {
    title: 'Services',
    column: { name: 'Service', mode: 'Mode', allow: 'Allowed CIDRs' },
    name: { ssh: 'SSH', web: 'Web panel', sip: 'SIP', rtp: 'RTP (voice)' },
    mode: { all: 'Open to all', allowlist: 'Allowlist only' },
    allowHint: 'Comma or newline separated IPv4 CIDRs (e.g. 192.168.1.0/24).',
    allowEmpty: 'Empty — allowlist mode needs at least one CIDR.',
    portLabel: 'Port: {{port}}',
    webPortsLabel: 'HTTP: {{http}}, HTTPS: {{https}}',
  },

  accessLink: 'SSH and web panel access settings',

  blocked: {
    title: 'Blocked addresses',
    hint: 'Comma or newline separated IPv4 CIDR list — ALL ports are closed for these.',
    empty: 'No blocked addresses.',
  },

  timeoutLabel: 'Confirmation window (seconds)',

  draftBar: { changes: '{{count}} changes', discard: 'Discard', apply: 'Apply' },

  confirmModal: {
    title: 'Apply changes',
    diffTitle: "What's changing",
    timeoutHint: "If you don't confirm within this time, it will roll back automatically.",
    cancel: 'Cancel',
    confirm: 'Apply',
  },

  errorsBanner: 'Validation failed — fix the fields below.',
  selfLockoutError: 'Warning: this setting could have locked out the current administrator — it was prevented.',

  pendingBanner: {
    title: 'Change pending confirmation',
    countdown: 'Auto-rollback in: {{time}}',
    confirmButton: 'Confirm',
    rollbackButton: 'Roll back now',
    expiredNotice: 'Time expired, reloading state…',
  },

  lastResult: {
    confirmed: 'Firewall settings confirmed.',
    rolled_back: 'Change rolled back.',
    apply_failed: 'Failed to apply the change.',
    dismiss: 'Dismiss',
  },

  toast: { applied: 'Change applied — remember to confirm it.', confirmed: 'Confirmed.', rolledBack: 'Rolled back.' },
};
