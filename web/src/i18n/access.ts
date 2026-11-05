// "access" namespace — Kirish (SSH va veb-panel) sahifasi (M12 B4) va ommaviy `/access-confirm` sahifasi.
// `firewall`dagi bilan bir xil qo'llash/tasdiqlash oqimi — tarjima kalitlari ham shunga mos.

export const uz = {
  title: 'Kirish (SSH va veb-panel)',
  loadFailed: 'Yuklab boʻlmadi.',
  retry: 'Qayta urinish',
  readonlyBanner: 'Kirish sozlamalari faqat koʻrish uchun: {{reason}}',

  ssh: {
    title: 'SSH',
    active: 'Ishlayapti',
    inactive: 'Ishlamayapti',
    currentPort: 'Joriy port',
    listening: 'Tinglanayotgan portlar: {{ports}}',
    passwordAuthOn: 'Parol bilan kirish: yoqilgan',
    passwordAuthOff: "Parol bilan kirish: oʻchirilgan",
    attentionWarning: "sshd ishlamayapti yoki eʼlon qilingan portda tinglamayapti — pastdagi buyruq ishlamasligi mumkin.",
    hostFirewallNote: "Diqqat: host firewall'ingiz (ufw/hosting) yangi portni ochishi kerak.",
    rootLoginNote: "Root bilan toʻgʻridan-toʻgʻri kirish xavfsizlik uchun yopiq — kirgach sudo -i buyrugʻini ishlating.",
    noLoginUser: "Bu serverda SSH orqali parol bilan kira oladigan foydalanuvchi yoʻq: root faqat SSH kalit bilan kira oladi (Debian / Proxmox LXC shablonining sukut sozlamasi). Proxmox konsolida (pct enter <ID>) quyidagini bajaring — keyin root va uning paroli bilan kira olasiz:",
    loginInstructions: 'Kirish yoʻriqnomasi',
    copy: 'Nusxalash',
    copied: 'Nusxalandi',
    portLabel: 'Yangi SSH port',
    apply: 'Qoʻllash',
    timeoutLabel: 'Tasdiqlash uchun vaqt (soniya)',
    pendingHint: 'Endi yangi port bilan ulanib koʻring: {{command}}. Ishlasa — Tasdiqlash tugmasini bosing.',
  },

  web: {
    title: 'Veb-panel',
    httpPort: 'HTTP port',
    httpsPort: 'HTTPS port',
    apply: 'Qoʻllash',
    confirmModal: {
      title: "Veb-panel manzili oʻzgaradi",
      warning: "Qoʻllagandan keyin panel yangi manzilga koʻchadi: {{url}}. Diqqat bilan davom eting.",
      timeoutLabel: 'Tasdiqlash uchun vaqt (soniya)',
      cancel: 'Bekor qilish',
      confirm: 'Qoʻllash',
    },
  },

  pendingBanner: {
    title: 'Oʻzgarish kutilmoqda',
    countdown: 'Avtomatik qaytarilishga: {{time}}',
    confirmButton: 'Tasdiqlash',
    rollbackButton: 'Hozir qaytarish',
    expiredNotice: 'Muddat tugadi, holat qayta yuklanmoqda…',
  },

  lastResult: {
    confirmed: 'Kirish sozlamalari tasdiqlandi.',
    rolled_back: 'Oʻzgarish qaytarildi.',
    dismiss: 'Yopish',
  },

  toast: { applied: 'Oʻzgarish qoʻllandi — tasdiqlashni unutmang.', confirmed: 'Tasdiqlandi.', rolledBack: 'Qaytarildi.' },

  confirmPage: {
    title: 'Veb-panel manzilini tasdiqlash',
    confirming: 'Tasdiqlanmoqda…',
    success: 'Tasdiqlandi, panel endi shu manzilda.',
    loginButton: 'Kirish',
    failed: "Tasdiqlab boʻlmadi — havola yaroqsiz yoki muddati tugagan. Eski manzil avtomatik tiklanishi mumkin.",
    missingId: "Tasdiqlash havolasi yaroqsiz.",
  },
};

export const ru = {
  title: 'Доступ (SSH и веб-панель)',
  loadFailed: 'Не удалось загрузить.',
  retry: 'Повторить',
  readonlyBanner: 'Настройки доступа только для просмотра: {{reason}}',

  ssh: {
    title: 'SSH',
    active: 'Работает',
    inactive: 'Не работает',
    currentPort: 'Текущий порт',
    listening: 'Прослушиваемые порты: {{ports}}',
    passwordAuthOn: 'Вход по паролю: включён',
    passwordAuthOff: 'Вход по паролю: выключен',
    attentionWarning: 'sshd не работает или не слушает указанный порт — команда ниже может не сработать.',
    hostFirewallNote: 'Внимание: ваш хостовый firewall (ufw/хостинг) должен открыть новый порт.',
    rootLoginNote: 'Прямой вход под root закрыт из соображений безопасности — после входа используйте sudo -i.',
    noLoginUser: 'На этом сервере нет пользователя, который может войти по SSH с паролем: root входит только по SSH-ключу (настройка по умолчанию Debian / шаблона Proxmox LXC). Выполните в консоли Proxmox (pct enter <ID>) — после этого можно войти как root с его паролем:',
    loginInstructions: 'Инструкция для входа',
    copy: 'Скопировать',
    copied: 'Скопировано',
    portLabel: 'Новый порт SSH',
    apply: 'Применить',
    timeoutLabel: 'Время на подтверждение (сек.)',
    pendingHint: 'Теперь попробуйте подключиться по новому порту: {{command}}. Получилось — нажмите Подтвердить.',
  },

  web: {
    title: 'Веб-панель',
    httpPort: 'HTTP порт',
    httpsPort: 'HTTPS порт',
    apply: 'Применить',
    confirmModal: {
      title: 'Адрес веб-панели изменится',
      warning: 'После применения панель переедет на новый адрес: {{url}}. Продолжайте внимательно.',
      timeoutLabel: 'Время на подтверждение (сек.)',
      cancel: 'Отмена',
      confirm: 'Применить',
    },
  },

  pendingBanner: {
    title: 'Изменение ожидает подтверждения',
    countdown: 'Автоматический откат через: {{time}}',
    confirmButton: 'Подтвердить',
    rollbackButton: 'Откатить сейчас',
    expiredNotice: 'Время истекло, состояние перезагружается…',
  },

  lastResult: {
    confirmed: 'Настройки доступа подтверждены.',
    rolled_back: 'Изменение откатано.',
    dismiss: 'Закрыть',
  },

  toast: { applied: 'Изменение применено — не забудьте подтвердить.', confirmed: 'Подтверждено.', rolledBack: 'Откатано.' },

  confirmPage: {
    title: 'Подтверждение адреса веб-панели',
    confirming: 'Подтверждается…',
    success: 'Подтверждено, панель теперь по этому адресу.',
    loginButton: 'Войти',
    failed: 'Не удалось подтвердить — ссылка недействительна или устарела. Старый адрес может восстановиться автоматически.',
    missingId: 'Ссылка для подтверждения недействительна.',
  },
};

export const en = {
  title: 'Access (SSH & web panel)',
  loadFailed: 'Could not load.',
  retry: 'Retry',
  readonlyBanner: 'Access settings are read-only: {{reason}}',

  ssh: {
    title: 'SSH',
    active: 'Running',
    inactive: 'Not running',
    currentPort: 'Current port',
    listening: 'Listening ports: {{ports}}',
    passwordAuthOn: 'Password auth: on',
    passwordAuthOff: 'Password auth: off',
    attentionWarning: "sshd isn't running or isn't listening on the announced port — the command below may not work.",
    hostFirewallNote: 'Note: your host firewall (ufw/hosting) must open the new port.',
    rootLoginNote: 'Direct root login is disabled for security — after logging in, use sudo -i.',
    noLoginUser: 'No user on this server can log in over SSH with a password: root may log in with an SSH key only (Debian / Proxmox LXC template default). Run this in the Proxmox console (pct enter <ID>) — then you can log in as root with its password:',
    loginInstructions: 'Login instructions',
    copy: 'Copy',
    copied: 'Copied',
    portLabel: 'New SSH port',
    apply: 'Apply',
    timeoutLabel: 'Confirmation window (seconds)',
    pendingHint: 'Now try connecting with the new port: {{command}}. If it works — press Confirm.',
  },

  web: {
    title: 'Web panel',
    httpPort: 'HTTP port',
    httpsPort: 'HTTPS port',
    apply: 'Apply',
    confirmModal: {
      title: 'The web panel address will change',
      warning: 'After applying, the panel will move to a new address: {{url}}. Continue carefully.',
      timeoutLabel: 'Confirmation window (seconds)',
      cancel: 'Cancel',
      confirm: 'Apply',
    },
  },

  pendingBanner: {
    title: 'Change pending confirmation',
    countdown: 'Auto-rollback in: {{time}}',
    confirmButton: 'Confirm',
    rollbackButton: 'Roll back now',
    expiredNotice: 'Time expired, reloading state…',
  },

  lastResult: {
    confirmed: 'Access settings confirmed.',
    rolled_back: 'Change rolled back.',
    dismiss: 'Dismiss',
  },

  toast: { applied: 'Change applied — remember to confirm it.', confirmed: 'Confirmed.', rolledBack: 'Rolled back.' },

  confirmPage: {
    title: 'Confirm web panel address',
    confirming: 'Confirming…',
    success: 'Confirmed, the panel is now at this address.',
    loginButton: 'Log in',
    failed: "Couldn't confirm — the link is invalid or expired. The old address may be restored automatically.",
    missingId: 'This confirmation link is invalid.',
  },
};
